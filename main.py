"""
Musicat - Desktop Music Catalog, DJ Tag Editor & Smart Organizer.
Target repository: https://github.com/IlRed89/Musicat
"""

import sys
import os
import traceback
import argparse
from pathlib import Path

# Ensure 'src' is in python search path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.core.logger import MusicatLogger
from src.core.path_resolver import PathResolver


def setup_exception_logging():
    """Installs global uncaught exception handlers that write full stack traces to logs."""
    logger = MusicatLogger.get_logger()
    data_dir = PathResolver.get_data_dir()
    app_dir = PathResolver.get_app_dir()
    is_portable = PathResolver.is_portable_mode()

    def global_exception_handler(exctype, value, tb):
        if issubclass(exctype, KeyboardInterrupt):
            sys.__excepthook__(exctype, value, tb)
            return

        formatted = "".join(traceback.format_exception(exctype, value, tb))
        logger.critical("Uncaught Exception: %s", formatted)
        MusicatLogger.flush()

        # Always write crash.log for immediate inspection
        crash_targets = [data_dir / "crash.log"]
        if is_portable:
            crash_targets.append(app_dir / "crash.log")
            crash_targets.append(app_dir / "logs" / "crash.log")

        for target in crash_targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(formatted, encoding="utf-8")
            except Exception:
                pass

        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = global_exception_handler


def main():
    # 1. Initialize logging system immediately
    setup_exception_logging()
    logger = MusicatLogger.get_logger()

    is_portable = PathResolver.is_portable_mode()
    data_dir = PathResolver.get_data_dir()
    app_dir = PathResolver.get_app_dir()

    logger.info("==================================================")
    logger.info("Musicat v1.2.0 starting...")
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
    parser.add_argument("--version", action="version", version="Musicat 1.2.0")

    args, unknown = parser.parse_known_args()

    if args.scan:
        from src.core.db import Database
        from src.core.scanner import LibraryScanner

        logger.info(f"[*] Scanning directory in CLI mode: {args.scan}")
        db = Database()
        scanner = LibraryScanner(db)

        def print_progress(cur, total, path):
            if cur % 100 == 0 or cur == total:
                print(f"[{cur}/{total}] {Path(path).name}")

        result = scanner.scan_directory(args.scan, progress_callback=print_progress)
        logger.info(f"[✓] Scan Completed: {result['total_found']} found, {result['inserted']} inserted/updated, {result['errors']} errors.")
        return 0

    # Launch GUI
    try:
        from src.gui.app import run_app
        return run_app()
    except Exception:
        err = traceback.format_exc()
        logger.critical(f"FATAL APPLICATION ERROR IN MAIN GUI LOOP:\n{err}")
        MusicatLogger.flush()
        crash_targets = [data_dir / "crash.log"]
        if is_portable:
            crash_targets.append(app_dir / "crash.log")
            crash_targets.append(app_dir / "logs" / "crash.log")
        for target in crash_targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(err, encoding="utf-8")
            except Exception:
                pass
        raise


if __name__ == "__main__":
    sys.exit(main())
