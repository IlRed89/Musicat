"""
Voidtools Everything SDK Integration for Musicat.

Provides instant MFT (Master File Table) queries over NTFS drives with tens of thousands of tracks.
Falls back transparently to local SQLite FTS (Full-Text Search) if Everything is absent or stopped.
"""

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .logger import MusicatLogger

# Everything IPC Request Flags
EVERYTHING_REQUEST_FILE_NAME = 0x00000001
EVERYTHING_REQUEST_PATH = 0x00000002
EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004
EVERYTHING_REQUEST_EXTENSION = 0x00000008
EVERYTHING_REQUEST_SIZE = 0x00000010
EVERYTHING_REQUEST_DATE_CREATED = 0x00000020
EVERYTHING_REQUEST_DATE_MODIFIED = 0x00000040

AUDIO_EXT_FILTER = "ext:mp3;flac;wav;aiff;aif;m4a;aac;ogg;opus;alac"


@dataclass
class SearchResultItem:
    """Represents a matched file from either Everything MFT or SQLite FTS."""

    filepath: str
    filename: str
    filesize: int
    modified_time: float
    source: str  # 'everything_mft' or 'sqlite_fts'


class EverythingSearchEngine:
    """Interfaces with Voidtools Everything SDK via ctypes with automatic FTS fallback."""

    _dll: Optional[Any] = None
    _dll_loaded: bool = False
    _dll_searched: bool = False

    @classmethod
    def _load_everything_dll(cls) -> Optional[Any]:
        """Locates and loads Everything64.dll or Everything32.dll dynamically.

        Returns:
            Optional[Any]: Loaded DLL handle if found, else None.
        """
        if cls._dll_searched:
            return cls._dll

        cls._dll_searched = True

        if sys.platform != "win32":
            return None

        # Determine architecture
        is_64bit = sys.maxsize > 2**32
        dll_name = "Everything64.dll" if is_64bit else "Everything32.dll"

        # Search candidates
        app_dir = Path(__file__).resolve().parent.parent.parent
        candidates = [
            app_dir / dll_name,
            app_dir / "bin" / dll_name,
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Everything" / dll_name,
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Everything" / dll_name,
            dll_name,  # Check Windows PATH
        ]

        for cand in candidates:
            try:
                cand_str = str(cand)
                dll = ctypes.WinDLL(cand_str)

                # =========================================================================
                # Voidtools Everything IPC & Ctypes Struct/Function Prototypes:
                #
                # The Everything desktop daemon maintains an in-memory index of NTFS MFT
                # (Master File Table) volumes and monitors the NTFS USN change journal.
                # Client applications interact with it via Everything64.dll, which sends
                # Win32 WM_COPYDATA messages and memory-mapped file requests to the hidden
                # window class 'EVERYTHING_IPC_SEARCH_CLIENT'.
                # =========================================================================

                # Everything_SetSearchW(LPCWSTR lpSearchString): Sets UTF-16 search query
                dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
                dll.Everything_SetSearchW.restype = None

                # Everything_SetRequestFlags(DWORD dwRequestFlags): Specifies MFT fields to populate
                dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint32]
                dll.Everything_SetRequestFlags.restype = None

                # Everything_SetMax(DWORD dwMax): Sets maximum return limit (pagination)
                dll.Everything_SetMax.argtypes = [ctypes.c_uint32]
                dll.Everything_SetMax.restype = None

                # Everything_SetOffset(DWORD dwOffset): Sets query offset (pagination)
                dll.Everything_SetOffset.argtypes = [ctypes.c_uint32]
                dll.Everything_SetOffset.restype = None

                # Everything_QueryW(BOOL bWait): Dispatches IPC query; bWait=True blocks until complete
                dll.Everything_QueryW.argtypes = [ctypes.c_bool]
                dll.Everything_QueryW.restype = ctypes.c_bool

                # Everything_GetNumResults(): Returns total count of matching records in IPC buffer
                dll.Everything_GetNumResults.argtypes = []
                dll.Everything_GetNumResults.restype = ctypes.c_uint32

                # Everything_GetResultFullPathNameW(DWORD index, LPWSTR buf, DWORD bufSize):
                # Copies the UTF-16 absolute path from the MFT record into caller-allocated buffer
                dll.Everything_GetResultFullPathNameW.argtypes = [
                    ctypes.c_uint32,
                    ctypes.c_wchar_p,
                    ctypes.c_uint32,
                ]
                dll.Everything_GetResultFullPathNameW.restype = ctypes.c_uint32

                # Everything_GetResultSize(DWORD index, LARGE_INTEGER *lpFileSize):
                # Returns 64-bit file byte length directly from NTFS MFT record
                dll.Everything_GetResultSize.argtypes = [
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint64),
                ]
                dll.Everything_GetResultSize.restype = ctypes.c_bool

                # Everything_IsDBLoaded(): Returns TRUE if the daemon MFT index is loaded and ready
                dll.Everything_IsDBLoaded.argtypes = []
                dll.Everything_IsDBLoaded.restype = ctypes.c_bool

                cls._dll = dll
                cls._dll_loaded = True
                MusicatLogger.get_logger().info(f"[EVERYTHING] Successfully loaded SDK from: {cand_str}")
                return cls._dll
            except Exception:
                continue

        return None

    @classmethod
    def is_everything_available(cls) -> bool:
        """Checks if Everything DLL is loaded and the Everything background service is responding.

        Returns:
            bool: True if live MFT queries can be executed via IPC, False otherwise.
        """
        dll = cls._load_everything_dll()
        if not dll:
            return False
        try:
            return bool(dll.Everything_IsDBLoaded())
        except Exception:
            return False

    @classmethod
    def is_available(cls) -> bool:
        """Alias for is_everything_available for unified engine compatibility."""
        return cls.is_everything_available()

    @classmethod
    def search_mft(
        cls,
        query: str,
        audio_only: bool = True,
        max_results: int = 1000,
        offset: int = 0,
    ) -> List[SearchResultItem]:
        """Queries Windows NTFS MFT directly through Voidtools Everything IPC.

        Args:
            query (str): Search term or regex.
            audio_only (bool): If True, restricts search to supported audio extensions.
            max_results (int): Maximum records to retrieve.
            offset (int): Pagination offset.

        Returns:
            List[SearchResultItem]: List of matching file records.

        Raises:
            RuntimeError: If Everything is not available or query fails.
        """
        dll = cls._load_everything_dll()
        if not dll or not dll.Everything_IsDBLoaded():
            raise RuntimeError("Everything service is not running or DLL is missing.")

        full_query = query.strip()
        if audio_only:
            full_query = f"{full_query} {AUDIO_EXT_FILTER}".strip()

        flags = (
            EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME
            | EVERYTHING_REQUEST_SIZE
            | EVERYTHING_REQUEST_DATE_MODIFIED
        )

        dll.Everything_SetSearchW(full_query)
        dll.Everything_SetRequestFlags(flags)
        dll.Everything_SetMax(max_results)
        dll.Everything_SetOffset(offset)

        start_time = time.perf_counter()
        success = dll.Everything_QueryW(True)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if not success:
            raise RuntimeError("Everything query execution failed.")

        num_results = dll.Everything_GetNumResults()
        results: List[SearchResultItem] = []

        buf = ctypes.create_unicode_buffer(2048)
        size_val = ctypes.c_uint64()

        for i in range(num_results):
            dll.Everything_GetResultFullPathNameW(i, buf, 2048)
            filepath = buf.value
            dll.Everything_GetResultSize(i, ctypes.byref(size_val))

            results.append(
                SearchResultItem(
                    filepath=filepath,
                    filename=os.path.basename(filepath),
                    filesize=size_val.value,
                    modified_time=0.0,
                    source="everything_mft",
                )
            )

        MusicatLogger.get_logger().debug(
            f"[EVERYTHING:MFT] '{full_query}' -> {len(results)} results in {elapsed_ms:.1f}ms"
        )
        return results

    @classmethod
    def unified_search(
        cls,
        query: str,
        db_instance: Any,
        audio_only: bool = True,
        max_results: int = 1000,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Performs MFT search if available, otherwise executes transparent SQLite FTS query.

        Args:
            query (str): Text query.
            db_instance (Database): Musicat Database instance for fallback FTS.
            audio_only (bool): If True, restricts to music filetypes.
            max_results (int): Max returned items.

        Returns:
            Tuple[List[Dict[str, Any]], str]: Tuple containing:
                - List of track or file result dictionaries.
                - Search engine used: 'Everything (MFT)' or 'SQLite (FTS Index)'.
        """
        if cls.is_everything_available():
            try:
                items = cls.search_mft(query=query, audio_only=audio_only, max_results=max_results)
                # Convert to dict representation
                dict_results = [
                    {
                        "filepath": item.filepath,
                        "filename": item.filename,
                        "filesize": item.filesize,
                        "title": Path(item.filename).stem,
                        "artist": "",
                        "source": "everything_mft",
                    }
                    for item in items
                ]
                return dict_results, "Everything (MFT)"
            except Exception as e:
                MusicatLogger.get_logger().warning(f"[EVERYTHING] Query error, falling back to SQLite FTS: {e}")

        # Fallback to local SQLite FTS / indexed search
        start_time = time.perf_counter()
        if hasattr(db_instance, "search_fts"):
            db_results = db_instance.search_fts(query=query, limit=max_results)
        else:
            db_results = db_instance.search_tracks(query=query, limit=max_results)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        MusicatLogger.get_logger().debug(
            f"[SQLITE:FTS] '{query}' -> {len(db_results)} results in {elapsed_ms:.1f}ms"
        )
        return db_results, "SQLite (FTS Index)"
