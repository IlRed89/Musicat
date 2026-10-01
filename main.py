"""
Musicat - Desktop Music Catalog, DJ Tag Editor & Smart Organizer.
Target repository: https://github.com/IlRed89/Musicat
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure 'src' is in python search path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def main():
    parser = argparse.ArgumentParser(description="Musicat - DJ Catalog & Smart Organizer")
    parser.add_argument("--scan", type=str, help="Scan a directory in headless mode")
    parser.add_argument("--version", action="version", version="Musicat 1.0.0")

    args, unknown = parser.parse_known_args()

    if args.scan:
        from src.core.db import Database
        from src.core.scanner import LibraryScanner

        print(f"[*] Scanning directory: {args.scan}")
        db = Database()
        scanner = LibraryScanner(db)

        def print_progress(cur, total, path):
            if cur % 100 == 0 or cur == total:
                print(f"[{cur}/{total}] {Path(path).name}")

        result = scanner.scan_directory(args.scan, progress_callback=print_progress)
        print(f"[✓] Completed: {result['total_found']} found, {result['inserted']} inserted/updated, {result['errors']} errors.")
        return 0

    # Launch GUI
    from src.gui.app import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
