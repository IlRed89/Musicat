"""
Musicat - Desktop Music Catalog, DJ Tag Editor & Smart Organizer.
Target repository: https://github.com/IlRed89/Musicat

Pre-Bootstrap Early Diagnostics & Launch Tracing Engine.
"""

# ==============================================================================
# 1. IMMEDIATE PRE-BOOTSTRAP EARLY LOGGING & HARDWARE TRACING
# Executed before ANY heavy GUI, audio, or metadata parsing libraries are loaded.
# Uses ONLY the Python standard library with immediate line-by-line disk flush.
# ==============================================================================
import argparse
from datetime import datetime
import faulthandler
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback

# Ensure root directory is at the beginning of sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Initialize EarlyBootLogger and full diagnostics before importing PySide6/libVLC/Mutagen
from src.core.boot_diagnostics import (
    EarlyBootLogger,
    boot_log,
    log_full_boot_report,
)

# Active immediately: enables faulthandler segfault trap & dual-file logging on macOS
boot_logger = EarlyBootLogger.initialize()
log_full_boot_report(boot_logger)

# ==============================================================================
# 2. INTERNAL SUBSYSTEM IMPORTS
# ==============================================================================
from src import __version__
from src.core.logger import MusicatLogger
from src.core.path_resolver import PathResolver


def setup_exception_logging() -> None:
    """Installs global uncaught exception handlers that write full stack traces to all loggers."""
    logger = MusicatLogger.get_logger()
    data_dir = PathResolver.get_data_dir()
    app_dir = PathResolver.get_app_dir()
    is_portable = PathResolver.is_portable_mode()

    def global_exception_handler(exctype, value, tb):
        if issubclass(exctype, KeyboardInterrupt):
            sys.__excepthook__(exctype, value, tb)
            return

        formatted = "".join(traceback.format_exception(exctype, value, tb))
        boot_log(f"CRITICAL UNCAUGHT EXCEPTION:\n{formatted}", level="CRITICAL")
        logger.critical("Uncaught Exception:\n%s", formatted)
        MusicatLogger.flush()
        boot_logger.flush()

        # Always write crash.log for immediate user/support inspection
        crash_targets = [data_dir / "crash.log"]
        if is_portable:
            crash_targets.append(app_dir / "crash.log")
            crash_targets.append(app_dir / "logs" / "crash.log")

        if sys.platform == "darwin":
            desktop_crash = Path.home() / "Desktop" / "musicat_crash.log"
            crash_targets.append(desktop_crash)

        for target in crash_targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "a", encoding="utf-8") as cf:
                    cf.write(f"[{datetime.now().isoformat()}] FATAL CRASH:\n{formatted}\n")
                    cf.flush()
            except Exception:
                pass

        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = global_exception_handler


def main() -> int:
    # 0. Windows Taskbar AppUserModelID registration
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "ilred89.musicat.djcataloger.app.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            boot_log("[OS:WIN] Registered Windows AppUserModelID successfully.", level="OS")
        except Exception as e:
            boot_log(f"[OS:WIN] AppUserModelID registration skipped: {e}", level="WARNING")

    # 1. Initialize logging system
    setup_exception_logging()
    logger = MusicatLogger.get_logger()

    is_portable = PathResolver.is_portable_mode()
    data_dir = PathResolver.get_data_dir()
    app_dir = PathResolver.get_app_dir()

    logger.info("==================================================")
    logger.info(f"Musicat v{__version__} starting...")
    logger.info(f"Python: {sys.version.split()[0]} | Platform: {sys.platform} | Frozen: {getattr(sys, 'frozen', False)}")
    logger.info(f"Execution Mode: {'PORTABLE' if is_portable else 'STANDARD'}")
    logger.info(f"Application Directory: {app_dir}")
    logger.info(f"Data Directory: {data_dir}")
    logger.info(f"Active Log File: {data_dir / 'logs' / 'musicat.log'}")
    if is_portable:
        logger.info(f"Portable Root Log File: {app_dir / 'logs' / 'musicat.log'}")
    logger.info("==================================================")

    parser = argparse.ArgumentParser(description="Musicat - DJ Catalog & Smart Organizer")
    parser.add_argument("--scan", type=str, help="Scan a directory in headless mode")
    parser.add_argument("--version", action="version", version=f"Musicat {__version__}")

    args, unknown = parser.parse_known_args()

    if args.scan:
        from src.core.db import Database
        from src.core.scanner import LibraryScanner

        boot_log(f"Starting CLI scanner mode for target: '{args.scan}'", level="CLI")
        logger.info(f"[*] Scanning directory in CLI mode: {args.scan}")
        db = Database()
        scanner = LibraryScanner(db)

        def print_progress(cur, total, path):
            if cur % 100 == 0 or cur == total:
                print(f"[{cur}/{total}] {Path(path).name}")

        result = scanner.scan_directory(args.scan, progress_callback=print_progress)
        logger.info(f"[✓] Scan Completed: {result['total_found']} found, {result['inserted']} inserted/updated, {result['errors']} errors.")
        boot_log(f"Scan finished successfully: {result['total_found']} found.", level="CLI")
        return 0

    # Launch GUI
    try:
        boot_log("Importing and launching GUI application loop (src.gui.app)...", level="GUI")
        from src.gui.app import run_app
        return run_app()
    except Exception:
        err = traceback.format_exc()
        boot_log(f"FATAL APPLICATION ERROR IN MAIN GUI LOOP:\n{err}", level="CRITICAL")
        logger.critical(f"FATAL APPLICATION ERROR IN MAIN GUI LOOP:\n{err}")
        MusicatLogger.flush()
        boot_logger.flush()
        crash_targets = [data_dir / "crash.log"]
        if is_portable:
            crash_targets.append(app_dir / "crash.log")
            crash_targets.append(app_dir / "logs" / "crash.log")
        if sys.platform == "darwin":
            crash_targets.append(Path.home() / "Desktop" / "musicat_crash.log")
        for target in crash_targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "a", encoding="utf-8") as cf:
                    cf.write(f"[{datetime.now().isoformat()}] GUI FATAL CRASH:\n{err}\n")
            except Exception:
                pass
        raise


if __name__ == "__main__":
    sys.exit(main())
