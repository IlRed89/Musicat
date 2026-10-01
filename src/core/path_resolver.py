"""
Path Resolver & Portability Engine for Musicat.

Ensures file references survive drive letter changes when operating
from external USB drives and removable storage across different Windows machines.
Detects dual-mode execution (Standard in %APPDATA% vs Portable with portable.lock).
"""

import os
import sys
import ctypes
import re
from pathlib import Path
from typing import Dict, Optional, Tuple


class PathResolver:
    """Translates absolute paths to portable volume-independent identifiers and vice versa.

    Format:
        [VOL:XXXXXXXX]/path/to/track.mp3
        [APP]/path/to/track.mp3
    """

    _volume_cache: Dict[str, str] = {}  # serial_number -> current_drive_root (e.g. "E:\\")
    _drive_serial_cache: Dict[str, str] = {}  # "E:" -> serial_number

    @classmethod
    def get_app_dir(cls) -> Path:
        """Returns the directory where the application is installed or running.

        Returns:
            Path: Absolute path to the directory containing the executable or main script.
        """
        if getattr(sys, "frozen", False):
            # PyInstaller creates a temporary folder and stores path in _MEIPASS,
            # but executable lives in sys.executable directory.
            return Path(sys.executable).parent.resolve()
        return Path(__file__).resolve().parent.parent.parent

    @classmethod
    def is_portable_mode(cls) -> bool:
        """Checks whether Musicat is running in standalone portable mode.

        Portable mode is active if a 'portable.lock' file exists in the application root,
        or if a local 'musicat_data' directory is already present alongside the executable.

        Returns:
            bool: True if portable mode is enabled, False for standard OS installation.
        """
        app_dir = cls.get_app_dir()
        lock_file = app_dir / "portable.lock"
        local_data = app_dir / "musicat_data"
        return lock_file.exists() or local_data.exists()

    @classmethod
    def get_data_dir(cls) -> Path:
        """Resolves the active data directory for SQLite database, logs, and cache.

        If in portable mode (portable.lock exists), data is strictly isolated
        in './musicat_data' next to the app. In standard mode, '%APPDATA%/Musicat'
        is used.

        Returns:
            Path: Path to the active data folder.
        """
        app_dir = cls.get_app_dir()

        if cls.is_portable_mode():
            portable_data_dir = app_dir / "musicat_data"
            try:
                portable_data_dir.mkdir(parents=True, exist_ok=True)
                test_file = portable_data_dir / ".write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink(missing_ok=True)
                return portable_data_dir
            except Exception:
                # If USB is read-only, fallback to APPDATA
                pass

        # Standard installation mode
        appdata = os.getenv("APPDATA") or str(Path.home())
        standard_dir = Path(appdata) / "Musicat"
        standard_dir.mkdir(parents=True, exist_ok=True)
        return standard_dir

    @classmethod
    def get_volume_serial(cls, drive_or_path: str) -> Optional[str]:
        """Retrieves the 32-bit hex Volume Serial Number for a given path or drive letter on Windows.

        Args:
            drive_or_path (str): Filepath or drive letter (e.g. 'E:' or 'E:\\Music').

        Returns:
            Optional[str]: Hexadecimal Volume Serial Number (e.g. '3C4D1A2B') or None.
        """
        drive = os.path.splitdrive(os.path.abspath(drive_or_path))[0]
        if not drive:
            return None
        drive_letter = drive.upper()

        if drive_letter in cls._drive_serial_cache:
            return cls._drive_serial_cache[drive_letter]

        if sys.platform != "win32":
            return None

        try:
            root_path = f"{drive_letter}\\"
            volume_name_buf = ctypes.create_unicode_buffer(1024)
            fs_name_buf = ctypes.create_unicode_buffer(1024)
            serial_number = ctypes.c_ulong()
            max_component_len = ctypes.c_ulong()
            fs_flags = ctypes.c_ulong()

            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root_path),
                volume_name_buf,
                ctypes.sizeof(volume_name_buf),
                ctypes.byref(serial_number),
                ctypes.byref(max_component_len),
                ctypes.byref(fs_flags),
                fs_name_buf,
                ctypes.sizeof(fs_name_buf),
            )
            if res:
                serial_hex = f"{serial_number.value:08X}"
                cls._drive_serial_cache[drive_letter] = serial_hex
                cls._volume_cache[serial_hex] = root_path
                return serial_hex
        except Exception:
            pass

        return None

    @classmethod
    def refresh_volume_map(cls) -> None:
        """Refreshes the internal mapping of all connected drives and their volume serials."""
        cls._volume_cache.clear()
        cls._drive_serial_cache.clear()

        if sys.platform != "win32":
            return

        try:
            import string
            for letter in string.ascii_uppercase:
                drive_root = f"{letter}:\\"
                if os.path.exists(drive_root):
                    serial = cls.get_volume_serial(f"{letter}:")
                    if serial:
                        cls._volume_cache[serial] = drive_root
        except Exception:
            pass

    @classmethod
    def to_portable_path(cls, abs_path: str) -> Tuple[str, Optional[str]]:
        """Converts an absolute path to a portable volume-independent representation.

        Args:
            abs_path (str): Full absolute system path.

        Returns:
            Tuple[str, Optional[str]]: Tuple containing:
                - portable_path: e.g. '[VOL:3C4D1A2B]/Music/Track.mp3' or '[APP]/Music/Track.mp3'
                - volume_serial: 8-character hex volume serial number, or None.
        """
        normalized = os.path.abspath(abs_path)
        app_dir = str(cls.get_app_dir())

        # If inside app directory, use relative [APP] token
        try:
            rel_to_app = os.path.relpath(normalized, app_dir)
            if not rel_to_app.startswith(".."):
                return f"[APP]/{rel_to_app.replace(os.sep, '/')}", None
        except Exception:
            pass

        drive, rest = os.path.splitdrive(normalized)
        serial = cls.get_volume_serial(drive)
        if serial:
            clean_rest = rest.lstrip("\\/").replace("\\", "/")
            return f"[VOL:{serial}]/{clean_rest}", serial

        # Fallback to standard normalized path
        return normalized.replace("\\", "/"), None

    @classmethod
    def to_absolute_path(cls, portable_path: str) -> str:
        """Resolves a portable path to the current machine's absolute path.

        Args:
            portable_path (str): Path stored with [VOL:XXXXXXXX] or [APP] token.

        Returns:
            str: Resolved absolute path on the current system.
        """
        if not portable_path:
            return ""

        if portable_path.startswith("[APP]/"):
            rel = portable_path[6:].replace("/", os.sep)
            return str((cls.get_app_dir() / rel).resolve())

        vol_match = re.match(r"^\[VOL:([A-Fa-f0-9]+)\]/(.*)$", portable_path)
        if vol_match:
            serial, rest = vol_match.group(1).upper(), vol_match.group(2)
            if serial not in cls._volume_cache:
                cls.refresh_volume_map()

            if serial in cls._volume_cache:
                drive_root = cls._volume_cache[serial]
                return os.path.normpath(os.path.join(drive_root, rest.replace("/", os.sep)))

            # If volume not found by serial, check if rest exists relative to app root or current drive
            app_drive = os.path.splitdrive(str(cls.get_app_dir()))[0]
            candidate = os.path.normpath(os.path.join(f"{app_drive}\\", rest.replace("/", os.sep)))
            if os.path.exists(candidate):
                return candidate

        return os.path.normpath(portable_path)
