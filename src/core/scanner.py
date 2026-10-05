"""
High-Speed Directory Scanner and Library Indexer for Musicat.

Processes deep directory trees, reads technical and metadata tags, translates portable paths,
detects permission errors, and batches SQLite database insertions.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

from .db import Database
from .logger import MusicatLogger
from .path_resolver import PathResolver
from ..tags.editor import AudioTagEditor, SUPPORTED_EXTENSIONS


class LibraryScanner:
    """Recursively scans directories and synchronizes records into SQLite with deep logging.

    Example:
        >>> scanner = LibraryScanner(db)
        >>> result = scanner.scan_directory("C:/Music", progress_callback=lambda c, t, p: print(f"{c}/{t}"))
        >>> print(f"Scanned {result['total_found']} audio files.")
    """

    def __init__(self, db: Optional[Database] = None) -> None:
        """Initializes the scanner with an active or default Database connection.

        Args:
            db (Optional[Database]): Database instance. If None, default Database is initialized.
        """
        self.db = db or Database()
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signals the scanner to abort traversal and indexing immediately."""
        self._is_cancelled = True
        MusicatLogger.warning("SCAN", "Library indexing scan cancelled by user.")

    def scan_file(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Scans a single audio file and synchronizes its record into SQLite immediately.

        Args:
            file_path: Path to the target audio file.

        Returns:
            Dictionary containing the indexed track record if successful, None otherwise.
        """
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            MusicatLogger.warning("SCAN", f"File does not exist or is not a file: {file_path}")
            return None

        ext = p.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            MusicatLogger.warning("SCAN", f"Unsupported extension: {ext}")
            return None

        try:
            meta = AudioTagEditor.read_metadata(p)
            portable_path, vol_id = PathResolver.to_portable_path(str(p))

            rec = meta.to_dict()
            rec["portable_path"] = portable_path
            rec["volume_id"] = vol_id
            rec["directory"] = str(p.parent)
            rec["has_cover"] = 1 if meta.has_cover else 0

            self.db.bulk_insert_or_update([rec])
            MusicatLogger.info("SCAN", f"Single track indexed into SQLite: '{p.name}'")
            return rec
        except Exception as exc:
            MusicatLogger.error("SCAN", f"Failed scanning single file '{p}': {exc}")
            return None

    def scan_directory(
        self,
        folder_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        batch_size: int = 250,
    ) -> Dict[str, int]:
        """Recursively indexes all supported audio files within folder_path.

        Args:
            folder_path (Union[str, Path]): Target root directory to crawl.
            progress_callback (Optional[Callable[[int, int, str], None]]): Callback reporting
                (current_file_index, total_files_estimated, current_filepath).
            batch_size (int): Number of parsed track records to batch per SQLite transaction.

        Returns:
            Dict[str, int]: Summary dictionary with keys:
                - 'total_found': Total audio files found.
                - 'scanned': Successfully read files.
                - 'inserted': Inserted or updated rows in database.
                - 'errors': Count of unreadable/corrupt files.
                - 'cancelled': 1 if cancelled early, 0 otherwise.

        Raises:
            NotADirectoryError: If folder_path does not exist or is not a valid directory.

        Example:
            >>> stats = scanner.scan_directory("/Volumes/DJ_Drive/Music", batch_size=100)
            >>> print(f"Inserted: {stats['inserted']}")
        """
        self._is_cancelled = False
        t_start = time.perf_counter()

        target = Path(folder_path).resolve()
        if not target.exists() or not target.is_dir():
            MusicatLogger.error("SCAN", f"Directory does not exist or is inaccessible: '{folder_path}'")
            raise NotADirectoryError(f"Directory not found: {folder_path}")

        MusicatLogger.info("SCAN", f"Starting recursive directory scan on '{target}' (batch_size: {batch_size})...")

        # Step 1: Rapid file discovery with permission failure handling
        audio_files: List[str] = []
        skipped_paths: List[str] = []

        def _on_walk_error(err: OSError) -> None:
            MusicatLogger.warning("SCAN:PERM", f"Access denied or unreadable directory: {err.filename} ({err.strerror})")
            skipped_paths.append(f"{err.filename}: {err.strerror}")

        for root, _, files in os.walk(str(target), onerror=_on_walk_error):
            if self._is_cancelled:
                break
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_p = os.path.join(root, f)
                    audio_files.append(full_p)

        total_files = len(audio_files)
        MusicatLogger.debug("SCAN", f"Discovery complete for '{target}': found {total_files} audio files.")

        scanned_count = 0
        inserted_count = 0
        error_count = 0
        batch: List[Dict] = []

        # Step 2: Extract metadata and batch insert
        for idx, file_path in enumerate(audio_files):
            if self._is_cancelled:
                break

            if progress_callback:
                try:
                    progress_callback(idx + 1, total_files, file_path)
                except Exception:
                    pass

            try:
                meta = AudioTagEditor.read_metadata(file_path)
                portable_path, vol_id = PathResolver.to_portable_path(file_path)

                rec = meta.to_dict()
                rec["portable_path"] = portable_path
                rec["volume_id"] = vol_id
                rec["directory"] = str(Path(file_path).parent)
                rec["has_cover"] = 1 if meta.has_cover else 0

                batch.append(rec)
                scanned_count += 1

                if len(batch) >= batch_size:
                    inserted_count += self.db.bulk_insert_or_update(batch)
                    batch.clear()

            except Exception as e:
                error_count += 1
                skipped_paths.append(f"{file_path} (Corrupt/Read Error: {e})")
                MusicatLogger.warning("SCAN:ERR", f"Skipped unreadable track: '{file_path}': {e}")

        # Commit remaining batch
        if batch and not self._is_cancelled:
            try:
                inserted_count += self.db.bulk_insert_or_update(batch)
            except Exception as e:
                MusicatLogger.error("SCAN:DB", f"Failed committing final batch of {len(batch)} tracks: {e}")
            batch.clear()

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        MusicatLogger.log_scan(
            str(target),
            total_files,
            inserted_count,
            errors=error_count,
            elapsed_ms=elapsed_ms,
            skipped_files=skipped_paths,
        )

        return {
            "total_found": total_files,
            "scanned": scanned_count,
            "inserted": inserted_count,
            "errors": error_count,
            "cancelled": int(self._is_cancelled),
        }
