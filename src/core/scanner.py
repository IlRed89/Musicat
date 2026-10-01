"""
High-Speed Directory Scanner and Library Indexer for Musicat.
Processes deep folder trees, reads metadata tags, translates portable paths,
and batches database insertions.
"""

import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from .db import Database
from .path_resolver import PathResolver
from ..tags.editor import AudioTagEditor, SUPPORTED_EXTENSIONS


class LibraryScanner:
    """Recursively scans directories and synchronizes records into SQLite."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signals the scanner to stop immediately."""
        self._is_cancelled = True

    def scan_directory(
        self,
        folder_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        batch_size: int = 250,
    ) -> Dict[str, int]:
        """
        Recursively indexes all supported audio files within folder_path.
        progress_callback signature: (current_count, total_estimated, current_filepath)
        Returns: {'scanned': N, 'inserted': M, 'errors': E}
        """
        self._is_cancelled = False
        target = Path(folder_path).resolve()
        if not target.exists() or not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {folder_path}")

        # Step 1: Rapid file discovery
        audio_files: List[str] = []
        for root, _, files in os.walk(str(target)):
            if self._is_cancelled:
                break
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    audio_files.append(os.path.join(root, f))

        total_files = len(audio_files)
        scanned_count = 0
        inserted_count = 0
        error_count = 0

        batch: List[Dict] = []

        for idx, file_path in enumerate(audio_files):
            if self._is_cancelled:
                break

            if progress_callback:
                progress_callback(idx + 1, total_files, file_path)

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

            except Exception:
                error_count += 1

        # Commit remaining batch
        if batch and not self._is_cancelled:
            inserted_count += self.db.bulk_insert_or_update(batch)
            batch.clear()

        return {
            "total_found": total_files,
            "scanned": scanned_count,
            "inserted": inserted_count,
            "errors": error_count,
            "cancelled": int(self._is_cancelled),
        }
