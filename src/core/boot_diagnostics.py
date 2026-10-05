"""
macOS & Cross-Platform Launch Diagnostics & Early Bootstrap Tracing Suite for Musicat.

Features:
- Zero-dependency early logger using exclusively the Python Standard Library.
- Immediate line-by-line flushing (flush + fsync) to prevent log loss during hard crashes.
- Dual-target file logging on macOS:
    1. ~/Library/Application Support/Musicat/logs/musicat_boot.log (or portable folder)
    2. ~/Desktop/musicat_debug.log (or portable/app directory)
- Native C/C++ Segfault and fatal signal trap via `faulthandler.enable()`.
- Global unhandled exception hook via `sys.excepthook`.
- Deep telemetry: macOS exact build, Rosetta 2 emulation detection, CPU architecture,
  Python binary/environment, frozen status, and critical environment variables.
- Pre-flight diagnostic probe for libVLC (dlopen testing with exact error interception).
- macOS sandbox and filesystem permissions verifier (/Volumes, ~/Music, Desktop, AppSupport).
- Qt Cocoa Display Engine inspector (QApplication platform, Cocoa plugin, screen DPI).
"""

from __future__ import annotations

import ctypes
from datetime import datetime
import faulthandler
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple


class EarlyBootLogger:
    """Zero-dependency early bootstrap logger active before any heavy GUI or audio imports.
    Guarantees physical disk flushing and native C/C++ crash interception."""

    _instance: Optional["EarlyBootLogger"] = None
    _primary_file: Optional[Path] = None
    _secondary_file: Optional[Path] = None
    _file_handles: List[Tuple[Path, Any]] = []
    _faulthandler_enabled: bool = False
    _initialized: bool = False

    def __init__(self) -> None:
        self.targets: List[Path] = []
        self._handles: List[Tuple[Path, Any]] = []

    @classmethod
    def get_instance(cls) -> "EarlyBootLogger":
        if cls._instance is None:
            cls._instance = cls()
        if not cls._instance._initialized:
            cls._instance._do_initialize()
        return cls._instance

    @classmethod
    def initialize(cls) -> "EarlyBootLogger":
        """Resolves target paths, creates directories, opens handles, and enables traps."""
        return cls.get_instance()

    def _do_initialize(self) -> None:
        """Internal initialization logic."""
        if self._initialized:
            return
        self.targets = self._resolve_target_paths()
        self._open_handles()
        self._setup_faulthandler()
        self._setup_excepthook()
        self._initialized = True

    def _resolve_target_paths(self) -> List[Path]:
        """Calculates primary and secondary log file targets based on OS and portable mode."""
        targets: List[Path] = []

        # Determine app directory and portability
        if getattr(sys, "frozen", False):
            exec_path = Path(sys.executable).resolve()
            posix = exec_path.as_posix()
            if "Contents/MacOS" in posix:
                app_dir = exec_path.parent.parent.parent.parent.resolve()
            else:
                app_dir = exec_path.parent.resolve()
        else:
            app_dir = Path(__file__).resolve().parent.parent.parent

        is_portable = (app_dir / "portable.lock").exists() or (app_dir / "musicat_data").exists()

        if sys.platform == "darwin":
            # macOS: Primary in Application Support, Secondary on Desktop
            if is_portable:
                primary = app_dir / "musicat_data" / "logs" / "musicat_boot.log"
                secondary = app_dir / "logs" / "musicat_debug.log"
            else:
                primary = Path.home() / "Library" / "Application Support" / "Musicat" / "logs" / "musicat_boot.log"
                desktop = Path.home() / "Desktop"
                secondary = desktop / "musicat_debug.log" if desktop.exists() else (app_dir / "logs" / "musicat_debug.log")
            targets.extend([primary, secondary])
        elif sys.platform == "win32":
            if is_portable:
                primary = app_dir / "musicat_data" / "logs" / "musicat_boot.log"
                secondary = app_dir / "logs" / "musicat_boot.log"
            else:
                appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
                primary = Path(appdata) / "Musicat" / "logs" / "musicat_boot.log"
                secondary = app_dir / "logs" / "musicat_boot.log"
            targets.append(primary)
            if primary.resolve() != secondary.resolve():
                targets.append(secondary)
        else:
            if is_portable:
                primary = app_dir / "musicat_data" / "logs" / "musicat_boot.log"
            else:
                primary = Path.home() / ".config" / "musicat" / "logs" / "musicat_boot.log"
            targets.append(primary)

        return targets

    def _open_handles(self) -> None:
        """Opens append file handles for all target paths with immediate buffering."""
        self._handles.clear()
        for target in self.targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = open(target, "a", encoding="utf-8", buffering=1)
                self._handles.append((target, handle))
                if self._primary_file is None:
                    self._primary_file = target
            except Exception as e:
                # If target location is restricted (e.g. sandboxed Desktop), write to stderr
                if sys.stderr and hasattr(sys.stderr, "write"):
                    sys.stderr.write(f"[BOOT:WARN] Could not open log target '{target}': {e}\n")

    def _setup_faulthandler(self) -> None:
        """Hooks Python's faulthandler to the primary boot log file descriptor."""
        if not self._handles:
            return
        try:
            primary_handle = self._handles[0][1]
            faulthandler.enable(file=primary_handle, all_threads=True)
            self._faulthandler_enabled = True
        except Exception as e:
            if sys.stderr and hasattr(sys.stderr, "write"):
                sys.stderr.write(f"[BOOT:WARN] Failed to enable faulthandler: {e}\n")

    def _setup_excepthook(self) -> None:
        """Installs early unhandled exception hook."""
        original_hook = sys.excepthook

        def early_exception_handler(exctype, value, tb):
            if issubclass(exctype, KeyboardInterrupt):
                original_hook(exctype, value, tb)
                return

            formatted = "".join(traceback.format_exception(exctype, value, tb))
            self.log(f"CRITICAL UNHANDLED BOOTSTRAP EXCEPTION:\n{formatted}", level="CRITICAL")

            # Write crash.log next to all active boot log files
            for target_path, _ in self._handles:
                try:
                    crash_file = target_path.parent / "crash.log"
                    with open(crash_file, "a", encoding="utf-8") as cf:
                        cf.write(f"[{datetime.now().isoformat()}] FATAL CRASH:\n{formatted}\n")
                        cf.flush()
                        os.fsync(cf.fileno())
                except Exception:
                    pass

            original_hook(exctype, value, tb)

        sys.excepthook = early_exception_handler

    def log(self, message: str, level: str = "BOOT") -> None:
        """Writes a timestamped line to stdout/stderr and all open log files, flushing immediately."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{now_str}] [{level:<7}] {message}\n"

        # Console stream
        stream = sys.stderr if level in ("ERROR", "CRITICAL", "WARNING") else sys.stdout
        if stream and hasattr(stream, "write"):
            try:
                stream.write(line)
                stream.flush()
            except Exception:
                pass

        # All disk log files
        for target_path, handle in self._handles:
            try:
                handle.write(line)
                handle.flush()
                # fsync ensures physical write to drive even in case of kernel panic/sudden abort
                os.fsync(handle.fileno())
            except Exception:
                pass

    def flush(self) -> None:
        """Flushes all open file handles."""
        for _, handle in self._handles:
            try:
                handle.flush()
                os.fsync(handle.fileno())
            except Exception:
                pass

    @property
    def active_log_paths(self) -> List[str]:
        return [str(p) for p, _ in self._handles]


# Global convenience shorthand
def boot_log(message: str, level: str = "BOOT") -> None:
    EarlyBootLogger.get_instance().log(message, level=level)


# =====================================================================
# SYSTEM & HARDWARE TELEMETRY INSPECTION
# =====================================================================

def check_rosetta_emulation() -> Dict[str, Any]:
    """Detects whether the process is executing under Rosetta 2 emulation on macOS."""
    info = {
        "is_macos": (sys.platform == "darwin"),
        "machine": platform.machine(),
        "is_rosetta": False,
        "description": "Native Execution",
    }
    if sys.platform != "darwin":
        return info

    try:
        res = subprocess.run(
            ["sysctl", "-in", "sysctl.proc_translated"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0 and res.stdout.strip() == "1":
            info["is_rosetta"] = True
            info["description"] = "Apple Silicon (Rosetta 2 x86_64 Emulation)"
        elif platform.machine() == "arm64":
            info["description"] = "Apple Silicon (Native ARM64)"
        elif platform.machine() == "x86_64":
            info["description"] = "Intel Mac (Native x86_64)"
    except Exception as e:
        info["error"] = str(e)

    return info


def get_macos_version_info() -> Dict[str, Any]:
    """Retrieves exact macOS release, product version, and build."""
    data = {
        "is_macos": (sys.platform == "darwin"),
        "platform_str": platform.platform(),
        "mac_ver": ("", ("", "", ""), ""),
        "product_version": "",
        "build_version": "",
    }
    if sys.platform != "darwin":
        return data

    try:
        rel, vtuple, cputype = platform.mac_ver()
        data["mac_ver"] = (rel, vtuple, cputype)
        data["product_version"] = rel
    except Exception:
        pass

    try:
        sw_vers = subprocess.run(["sw_vers"], capture_output=True, text=True, timeout=1)
        if sw_vers.returncode == 0:
            for line in sw_vers.stdout.splitlines():
                if "ProductVersion:" in line:
                    data["product_version"] = line.split(":", 1)[1].strip()
                elif "BuildVersion:" in line:
                    data["build_version"] = line.split(":", 1)[1].strip()
    except Exception:
        pass

    return data


def get_critical_env_vars() -> Dict[str, Optional[str]]:
    """Captures runtime environment variables critical for dynamic linking and Qt/VLC."""
    keys = [
        "PATH",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "DYLD_FRAMEWORK_PATH",
        "PYTHONPATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "QT_QPA_PLATFORM",
        "QT_PLUGIN_PATH",
        "QT_DEBUG_PLUGINS",
        "QT_MAC_WANTS_LAYER",
        "PYTHON_VLC_LIB_PATH",
        "PYTHON_VLC_MODULE_PATH",
        "VLC_PLUGIN_PATH",
    ]
    return {k: os.environ.get(k) for k in keys}


def check_macos_permissions() -> List[Dict[str, Any]]:
    """Checks macOS sandbox and filesystem permissions for essential directories."""
    results: List[Dict[str, Any]] = []
    if sys.platform != "darwin":
        return results

    # 1. Removable volumes (/Volumes)
    vol_info: Dict[str, Any] = {"name": "Removable Volumes (/Volumes)", "path": "/Volumes"}
    try:
        vols = os.listdir("/Volumes")
        vol_info["status"] = "OK"
        vol_info["details"] = f"Accessible ({len(vols)} entries: {', '.join(vols[:5])})"
    except Exception as e:
        vol_info["status"] = "RESTRICTED"
        vol_info["details"] = str(e)
    results.append(vol_info)

    # 2. User Music folder (~/Music)
    music_dir = Path.home() / "Music"
    music_info: Dict[str, Any] = {"name": "User Music (~/Music)", "path": str(music_dir)}
    try:
        if music_dir.exists():
            r = os.access(str(music_dir), os.R_OK)
            w = os.access(str(music_dir), os.W_OK)
            music_info["status"] = "OK" if r else "READ_RESTRICTED"
            music_info["details"] = f"Read={r}, Write={w}"
        else:
            music_info["status"] = "NOT_FOUND"
            music_info["details"] = "Directory does not exist"
    except Exception as e:
        music_info["status"] = "RESTRICTED"
        music_info["details"] = str(e)
    results.append(music_info)

    # 3. Application Support directory
    app_supp = Path.home() / "Library" / "Application Support" / "Musicat"
    supp_info: Dict[str, Any] = {"name": "Application Support", "path": str(app_supp)}
    try:
        app_supp.mkdir(parents=True, exist_ok=True)
        probe_file = app_supp / ".probe_perm"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        supp_info["status"] = "OK"
        supp_info["details"] = "Full Read/Write confirmed"
    except Exception as e:
        supp_info["status"] = "RESTRICTED"
        supp_info["details"] = str(e)
    results.append(supp_info)

    # 4. User Desktop directory (~/Desktop)
    desktop_dir = Path.home() / "Desktop"
    desk_info: Dict[str, Any] = {"name": "Desktop (~/Desktop)", "path": str(desktop_dir)}
    try:
        if desktop_dir.exists():
            w = os.access(str(desktop_dir), os.W_OK)
            desk_info["status"] = "OK" if w else "WRITE_RESTRICTED"
            desk_info["details"] = f"Write={w}"
        else:
            desk_info["status"] = "NOT_FOUND"
            desk_info["details"] = "Directory does not exist"
    except Exception as e:
        desk_info["status"] = "RESTRICTED"
        desk_info["details"] = str(e)
    results.append(desk_info)

    return results


# =====================================================================
# LIBVLC DIAGNOSTIC PROBING & DLOPEN VERIFICATION
# =====================================================================

def probe_vlc_libraries() -> Dict[str, Any]:
    """Discovers and dlopen-probes libVLC dynamic library candidates on macOS and other platforms.
    Captures exact OSError and architecture mismatches."""
    report: Dict[str, Any] = {
        "verified_path": None,
        "plugins_path": None,
        "candidates_checked": [],
        "errors": [],
    }

    # Determine candidate directories
    candidates: List[Path] = []
    if getattr(sys, "frozen", False):
        exec_path = Path(sys.executable).resolve()
        posix = exec_path.as_posix()
        if "Contents/MacOS" in posix:
            app_dir = exec_path.parent.parent.parent.parent.resolve()
            bundle_macos = exec_path.parent
            bundle_frameworks = exec_path.parent.parent / "Frameworks"
            candidates.extend([
                bundle_frameworks / "libvlc.dylib",
                bundle_macos / "lib" / "libvlc.dylib",
                bundle_macos / "libvlc.dylib",
            ])
        else:
            app_dir = exec_path.parent.resolve()
    else:
        app_dir = Path(__file__).resolve().parent.parent.parent

    if sys.platform == "darwin":
        candidates.extend([
            app_dir / "Contents" / "Frameworks" / "libvlc.dylib",
            app_dir / "Contents" / "MacOS" / "lib" / "libvlc.dylib",
            app_dir / "libvlc.dylib",
            Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib"),
            Path.home() / "Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib",
            Path("/opt/homebrew/lib/libvlc.dylib"),
            Path("/usr/local/lib/libvlc.dylib"),
            Path("/opt/local/lib/libvlc.dylib"),
        ])
    elif sys.platform == "win32":
        prog_files = Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        prog_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))
        candidates.extend([
            app_dir / "vlc" / "libvlc.dll",
            app_dir / "libvlc.dll",
            prog_files / "VideoLAN" / "VLC" / "libvlc.dll",
            prog_files_x86 / "VideoLAN" / "VLC" / "libvlc.dll",
        ])
    else:
        candidates.extend([
            Path("/usr/lib/libvlc.so"),
            Path("/usr/lib/x86_64-linux-gnu/libvlc.so"),
            Path("/usr/lib/aarch64-linux-gnu/libvlc.so"),
            Path("/usr/local/lib/libvlc.so"),
        ])

    for cand in candidates:
        cand_entry = {"path": str(cand), "exists": cand.exists(), "dlopen_ok": False, "error": None}
        if not cand.exists():
            report["candidates_checked"].append(cand_entry)
            continue

        # File exists: attempt dynamic load probe via ctypes
        try:
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(cand.parent))
                except Exception:
                    pass
            probe_handle = ctypes.CDLL(str(cand))
            cand_entry["dlopen_ok"] = True
            report["candidates_checked"].append(cand_entry)

            if report["verified_path"] is None:
                report["verified_path"] = str(cand)
                os.environ["PYTHON_VLC_LIB_PATH"] = str(cand)

                # Locate plugins
                possible_plugins = [
                    cand.parent / "vlc" / "plugins",
                    cand.parent / "plugins",
                    cand.parent.parent / "plugins",
                ]
                if sys.platform == "darwin":
                    possible_plugins.append(Path("/Applications/VLC.app/Contents/MacOS/plugins"))
                for p in possible_plugins:
                    if p.exists():
                        report["plugins_path"] = str(p)
                        os.environ["VLC_PLUGIN_PATH"] = str(p)
                        break
        except Exception as e:
            err_msg = str(e)
            cand_entry["error"] = err_msg
            report["errors"].append(f"{cand}: {err_msg}")
            report["candidates_checked"].append(cand_entry)

    return report


# =====================================================================
# FULL BOOTSTRAP REPORT DISPATCHER
# =====================================================================

def log_full_boot_report(logger: Optional[EarlyBootLogger] = None) -> None:
    """Emits comprehensive hardware, OS, permissions, and environment telemetry."""
    if logger is None:
        logger = EarlyBootLogger.get_instance()

    logger.log("================================================================================")
    logger.log("          MUSICAT EARLY BOOTSTRAP & HARDWARE DIAGNOSTICS SUITE")
    logger.log("================================================================================")

    # 1. Active Log Target Files
    logger.log(f"Active Log Targets ({len(logger.active_log_paths)}):")
    for p in logger.active_log_paths:
        logger.log(f"  --> {p}")
    logger.log(f"Native faulthandler Segfault Trap: {'ENABLED (All Threads)' if logger._faulthandler_enabled else 'DISABLED'}")

    # 2. Host & Hardware
    mac_info = get_macos_version_info()
    rosetta_info = check_rosetta_emulation()
    logger.log(f"Host OS: {platform.platform()} | System: {sys.platform}")
    if mac_info["is_macos"]:
        logger.log(f"macOS Version: {mac_info['product_version']} (Build {mac_info['build_version'] or 'N/A'})")
        logger.log(f"CPU Architecture: {rosetta_info['description']}")
    else:
        logger.log(f"CPU Architecture: {platform.machine()} | Cores: {os.cpu_count()}")

    # 3. Python Runtime & Process Execution
    logger.log(f"Python: {sys.version.splitlines()[0]}")
    logger.log(f"Executable: {sys.executable}")
    logger.log(f"Frozen Bundle (sys.frozen): {getattr(sys, 'frozen', False)}")
    if hasattr(sys, "_MEIPASS"):
        logger.log(f"PyInstaller Temporary Directory (_MEIPASS): {getattr(sys, '_MEIPASS', '')}")
    logger.log(f"Process PID: {os.getpid()} | Parent PID: {os.getppid()} | CWD: {os.getcwd()}")
    logger.log(f"Command Line Arguments (sys.argv): {sys.argv}")

    # 4. Critical Environment Variables
    logger.log("Critical Environment Variables:")
    env_vars = get_critical_env_vars()
    for k, v in env_vars.items():
        if v is not None:
            logger.log(f"  {k} = {v}")

    # 5. macOS Permissions Check
    if sys.platform == "darwin":
        logger.log("macOS Filesystem & Sandbox Permissions:")
        perms = check_macos_permissions()
        for perm in perms:
            logger.log(f"  [{perm['status']:<15}] {perm['name']}: {perm['details']}")

    # 6. libVLC Candidate Probing
    logger.log("Probing libVLC Dynamic Library Candidates:")
    vlc_report = probe_vlc_libraries()
    for cand in vlc_report["candidates_checked"]:
        if cand["dlopen_ok"]:
            status_tag = "VALID (dlopen OK)"
        elif cand["exists"]:
            status_tag = f"FAILED: {cand['error']}"
        else:
            status_tag = "NOT_FOUND"
        logger.log(f"  - {cand['path']} -> {status_tag}")

    if vlc_report["verified_path"]:
        logger.log(f"[✓] libVLC dynamic library verified: {vlc_report['verified_path']}")
        if vlc_report["plugins_path"]:
            logger.log(f"[✓] VLC plugins directory verified: {vlc_report['plugins_path']}")
    else:
        logger.log("[!] No verified libVLC dynamic library found. Fallback audio engine will be used.", level="WARNING")

    logger.log("================================================================================")
    logger.log("          EARLY BOOTSTRAP INITIALIZED SUCCESSFULLY - LAUNCHING APP")
    logger.log("================================================================================")
    logger.flush()


def get_qt_display_diagnostics(app: Any) -> Dict[str, Any]:
    """Captures Qt Display Engine and Cocoa integration telemetry from active QApplication."""
    info: Dict[str, Any] = {
        "platform_name": "unknown",
        "screens_count": 0,
        "screens": [],
    }
    try:
        info["platform_name"] = app.platformName()
        screens = app.screens()
        info["screens_count"] = len(screens)
        for idx, scr in enumerate(screens):
            geom = scr.geometry()
            info["screens"].append({
                "index": idx,
                "name": scr.name(),
                "resolution": f"{geom.width()}x{geom.height()}",
                "device_pixel_ratio": scr.devicePixelRatio(),
                "dpi": f"{scr.logicalDotsPerInch():.1f}",
            })
    except Exception as e:
        info["error"] = str(e)
    return info
