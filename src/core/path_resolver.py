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
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


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
            exec_path = Path(sys.executable).resolve()
            # If inside macOS app bundle (e.g. Musicat.app/Contents/MacOS/Musicat)
            posix_path = exec_path.as_posix()
            if "Contents/MacOS" in posix_path:
                # App directory is the folder enclosing Musicat.app (or Musicat.app itself)
                app_bundle = exec_path.parent.parent.parent
                return app_bundle.parent.resolve()
            return exec_path.parent.resolve()
        return Path(__file__).resolve().parent.parent.parent

    @classmethod
    def get_resource_path(cls, relative_path: str) -> Path:
        """Locates bundled or local resources across dev and PyInstaller."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            cand = Path(sys._MEIPASS) / relative_path
            if cand.exists():
                return cand
        app_res = cls.get_app_dir() / relative_path
        if app_res.exists():
            return app_res
        root_res = Path(__file__).resolve().parent.parent.parent / relative_path
        return root_res

    @classmethod
    def get_icon_path(cls) -> Optional[Path]:
        """Returns the application icon path (PNG, ICO or ICNS) prioritizing OS-native formats."""
        if sys.platform == "win32":
            names = ["assets/icon.ico", "assets/icon.png", "assets/icon.icns"]
        elif sys.platform == "darwin":
            names = ["assets/icon.icns", "assets/icon.png", "assets/icon.ico"]
        else:
            names = ["assets/icon.png", "assets/icon.ico", "assets/icon.icns"]

        for name in names:
            p = cls.get_resource_path(name)
            if p.exists():
                return p
        return None

    @classmethod
    def is_portable(cls) -> bool:
        """Alias for is_portable_mode."""
        return cls.is_portable_mode()

    @classmethod
    def is_portable_mode(cls) -> bool:
        """Checks whether Musicat is running in standalone portable mode.

        Portable mode is active if a 'portable.lock' file exists in the application root,
        or if a local 'musicat_data' directory is already present alongside the executable or bundle.

        Returns:
            bool: True if portable mode is enabled, False for standard OS installation.
        """
        app_dir = cls.get_app_dir()
        lock_file = app_dir / "portable.lock"
        local_data = app_dir / "musicat_data"

        if lock_file.exists() or local_data.exists():
            return True

        # On macOS, check also inside the .app bundle Resources if applicable
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            exec_parent = Path(sys.executable).parent.resolve()
            if (exec_parent / "portable.lock").exists() or (exec_parent / "musicat_data").exists():
                return True

        return False

    @classmethod
    def get_data_dir(cls) -> Path:
        """Resolves the active data directory for SQLite database, logs, and cache.

        If in portable mode (portable.lock exists), data is strictly isolated
        in './musicat_data' next to the app. In standard mode:
        - Windows: '%APPDATA%/Musicat'
        - macOS: '~/Library/Application Support/Musicat'
        - Linux: '~/.config/musicat'

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
                # If USB or app dir is read-only, fallback to standard OS directory
                pass

        # Standard installation mode based on active OS
        if sys.platform == "darwin":
            standard_dir = Path.home() / "Library" / "Application Support" / "Musicat"
        elif sys.platform == "win32":
            appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            standard_dir = Path(appdata) / "Musicat"
        else:
            standard_dir = Path.home() / ".config" / "musicat"

        standard_dir.mkdir(parents=True, exist_ok=True)
        return standard_dir

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Resolves the logs directory based on application operating mode:
        - Portable mode (portable.lock): adjacent './logs' directory.
        - Standard mode: '%APPDATA%/Musicat/logs' (Windows) or '~/Library/Application Support/Musicat/logs' (macOS).

        Returns:
            Path: Guaranteed existing Path directory for log files.
        """
        if cls.is_portable_mode():
            log_dir = cls.get_app_dir() / "logs"
        else:
            log_dir = cls.get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

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
    def to_portable_path(cls, abs_path: Union[str, Path]) -> Tuple[str, Optional[str]]:
        """Converts an absolute path to a portable volume-independent representation.

        Args:
            abs_path (str | Path): Full absolute system path.

        Returns:
            Tuple[str, Optional[str]]: Tuple containing:
                - portable_path: e.g. '[VOL:3C4D1A2B]/Music/Track.mp3' or '[APP]/Music/Track.mp3'
                - volume_serial: 8-character hex volume serial number, or None.
        """
        abs_str = str(abs_path)
        # Check /Volumes/<VolumeName>/ mount point (macOS POSIX path)
        clean_input = abs_str.replace("\\", "/")
        if clean_input.startswith("/Volumes/"):
            parts = clean_input.split("/", 3)
            if len(parts) >= 3 and parts[2]:
                vol_name = parts[2]
                rest = parts[3] if len(parts) > 3 else ""
                return f"[VOL:{vol_name}]/{rest.lstrip('/')}", vol_name

        normalized = os.path.abspath(abs_str)
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

        Supports Windows volume serials [VOL:XXXXXXXX], macOS mount points [VOL:VolumeName],
        and relative application paths [APP]/...

        Args:
            portable_path (str): Path stored with [VOL:...] or [APP] token.

        Returns:
            str: Resolved absolute path on the current system.
        """
        if not portable_path:
            return ""

        if portable_path.startswith("[APP]/"):
            rel = portable_path[6:].replace("/", os.sep)
            return str((cls.get_app_dir() / rel).resolve())

        vol_match = re.match(r"^\[VOL:([^\]]+)\]/(.*)$", portable_path)
        if vol_match:
            vol_id, rest = vol_match.group(1), vol_match.group(2)
            clean_rest_native = rest.replace("/", os.sep)

            # 1. If on macOS, check /Volumes/<vol_id>/
            if sys.platform == "darwin":
                mac_direct = Path(f"/Volumes/{vol_id}") / clean_rest_native
                if mac_direct.exists():
                    return str(mac_direct.resolve())

                # If vol_id was a Windows hex serial or volume renamed, check all /Volumes/
                volumes_dir = Path("/Volumes")
                if volumes_dir.exists():
                    for v in volumes_dir.iterdir():
                        cand = v / clean_rest_native
                        if cand.exists():
                            return str(cand.resolve())

            # 2. If on Windows, check Volume Serial Number cache
            serial_upper = vol_id.upper()
            if serial_upper not in cls._volume_cache:
                cls.refresh_volume_map()

            if serial_upper in cls._volume_cache:
                drive_root = cls._volume_cache[serial_upper]
                return os.path.normpath(os.path.join(drive_root, clean_rest_native))

            # 3. Fallback: check relative to current app directory or drive
            app_dir = cls.get_app_dir()
            app_cand = (app_dir / clean_rest_native).resolve()
            if app_cand.exists():
                return str(app_cand)

            app_drive = os.path.splitdrive(str(app_dir))[0]
            if app_drive:
                candidate = os.path.normpath(os.path.join(f"{app_drive}\\", clean_rest_native))
                if os.path.exists(candidate):
                    return candidate

        return os.path.normpath(portable_path)

    @classmethod
    def show_in_file_manager(cls, file_path: Union[str, Path]) -> bool:
        """Opens native file manager (Explorer / Finder / xdg-open) selecting the specified file.

        Args:
            file_path: Absolute or relative path to file or directory.

        Returns:
            bool: True if process launched successfully, False otherwise.
        """
        try:
            p = Path(file_path).resolve()
            if not p.exists():
                return False

            norm_p = os.path.normpath(str(p))

            if sys.platform == "win32":
                # Windows Explorer: /select,<path> highlights the file
                subprocess.Popen(["explorer", f"/select,{norm_p}"])
                return True
            elif sys.platform == "darwin":
                # macOS Finder: open -R <path> reveals the file
                subprocess.Popen(["open", "-R", norm_p])
                return True
            else:
                # Linux: open containing folder
                target_dir = norm_p if p.is_dir() else str(p.parent)
                subprocess.Popen(["xdg-open", target_dir])
                return True
        except Exception:
            return False
