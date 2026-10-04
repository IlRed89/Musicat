"""
Integrated File Manager for Musicat.

Handles cut, copy, paste, and drag-and-drop operations on audio files directly
within the interface and synchronizes physical file paths in SQLite in real time
without invalidating acoustic analysis (BPM, Key, Waveform).
"""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.core.db import Database
from src.core.path_resolver import PathResolver


class ClipboardMode:
    """Clipboard action mode."""

    NONE = "none"
    CUT = "cut"
    COPY = "copy"


class CollisionStrategy:
    """Collision strategies for duplicate files."""

    ASK = "ask"
    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


@dataclass
class FileOperationResult:
    """Result of a paste/transfer operation."""

    moved: int = 0
    copied: int = 0
    skipped: int = 0
    processed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class MusicFileManager:
    """Physical file management and SQLite path reconciliation."""

    _instance: Optional["MusicFileManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, db: Optional[Database] = None) -> None:
        self._lock = threading.RLock()
        self.db = db
        self._clipboard_files: List[str] = []
        self._is_cut_mode: bool = False

    @classmethod
    def get_instance(cls, db: Optional[Database] = None) -> "MusicFileManager":
        """Singleton accessor."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(db)
            elif db and cls._instance.db is None:
                cls._instance.db = db
            return cls._instance

    @property
    def clipboard_mode(self) -> str:
        """Returns the current clipboard mode ('cut', 'copy', or 'none')."""
        with self._lock:
            if not self._clipboard_files:
                return ClipboardMode.NONE
            return ClipboardMode.CUT if self._is_cut_mode else ClipboardMode.COPY

    @property
    def clipboard_files(self) -> List[str]:
        """Returns filepaths currently in clipboard."""
        return self.get_clipboard_files()

    def cut_files(self, filepaths: List[Union[str, Path]]) -> None:
        """Stores filepaths in internal clipboard marked for move (Cut)."""
        with self._lock:
            self._clipboard_files = [str(Path(p).resolve()) for p in filepaths if p]
            self._is_cut_mode = True
            self._sync_system_clipboard()

    def copy_files(self, filepaths: List[Union[str, Path]]) -> None:
        """Stores filepaths in internal clipboard marked for duplicate (Copy)."""
        with self._lock:
            self._clipboard_files = [str(Path(p).resolve()) for p in filepaths if p]
            self._is_cut_mode = False
            self._sync_system_clipboard()

    def has_clipboard(self) -> bool:
        """Checks if files are currently in clipboard."""
        with self._lock:
            return bool(self._clipboard_files)

    def is_cut_mode(self) -> bool:
        """Returns True if current clipboard operation is Cut."""
        with self._lock:
            return self._is_cut_mode

    def get_clipboard_files(self) -> List[str]:
        """Returns list of filepaths currently in clipboard."""
        with self._lock:
            return list(self._clipboard_files)

    def clear_clipboard(self) -> None:
        """Wipes the internal clipboard."""
        with self._lock:
            self._clipboard_files = []
            self._is_cut_mode = False

    def _sync_system_clipboard(self) -> None:
        """Syncs internal clipboard to system clipboard via Qt MIME if available."""
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QClipboard
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                from PySide6.QtCore import QMimeData

                mime = QMimeData()
                urls = [QUrl.fromLocalFile(fp) for fp in self._clipboard_files]
                mime.setUrls(urls)
                clipboard.setMimeData(mime)
        except Exception:
            pass

    def get_system_clipboard_files(self) -> List[str]:
        """Extracts audio filepaths from internal or system clipboard."""
        with self._lock:
            if self._clipboard_files:
                return list(self._clipboard_files)
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                mime = clipboard.mimeData()
                if mime and mime.hasUrls():
                    files = [
                        url.toLocalFile()
                        for url in mime.urls()
                        if url.isLocalFile() and url.toLocalFile()
                    ]
                    if files:
                        return files
        except Exception:
            pass
        return self.get_clipboard_files()

    def _resolve_rename_collision(self, target_dir: Path, filename: str) -> Path:
        """Generates a non-conflicting incremented filename, e.g. Track (1).mp3."""
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        new_path = target_dir / f"{stem} ({counter}){suffix}"
        while new_path.exists():
            counter += 1
            new_path = target_dir / f"{stem} ({counter}){suffix}"
        return new_path

    def paste_files(
        self,
        target_dir: Union[str, Path],
        db: Optional[Database] = None,
        default_strategy: str = CollisionStrategy.ASK,
        collision_strategy: Optional[str] = None,
        collision_callback: Optional[Callable[[str, str], str]] = None,
    ) -> FileOperationResult:
        """Pastes clipboard files into the target folder and updates the SQLite database.

        Args:
            target_dir: Target directory destination.
            db: Database instance to update (defaults to self.db or new instance).
            default_strategy: Fallback strategy if callback is not provided.
            collision_strategy: Optional alias for strategy.
            collision_callback: Callback(src_file, dst_file) returning 'overwrite', 'rename', or 'skip'.

        Returns:
            FileOperationResult with moved, copied, skipped, and processed file lists.
        """
        active_db = db or self.db
        if active_db is None:
            active_db = Database()

        dest_dir = Path(target_dir).resolve()
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)

        files_to_process = self.get_system_clipboard_files()
        if not files_to_process:
            return FileOperationResult(errors=["Clipboard is empty"])

        is_cut = self.is_cut_mode()
        moved_count = 0
        copied_count = 0
        skipped_count = 0
        processed_files: List[str] = []
        skipped_files: List[str] = []
        errors: List[str] = []
        effective_strategy = collision_strategy or default_strategy

        for src_str in files_to_process:
            src = Path(src_str).resolve()
            if not src.exists():
                errors.append(f"File not found: {src_str}")
                continue

            # Don't move to same folder
            if src.parent == dest_dir:
                continue

            dst = dest_dir / src.name

            collision_note = ""
            # Collision handling
            if dst.exists():
                strategy = effective_strategy
                if strategy == CollisionStrategy.ASK and collision_callback:
                    strategy = collision_callback(str(src), str(dst))

                if strategy == CollisionStrategy.SKIP:
                    skipped_count += 1
                    skipped_files.append(str(src))
                    from .logger import MusicatLogger
                    MusicatLogger.log_file_op("SKIP", str(src), str(dst), collision_resolved="SKIP", success=True)
                    continue
                elif strategy == CollisionStrategy.RENAME:
                    dst = self._resolve_rename_collision(dest_dir, src.name)
                    collision_note = f"RENAME -> {dst.name}"
                elif strategy == CollisionStrategy.OVERWRITE:
                    collision_note = "OVERWRITE"
                else:
                    skipped_count += 1
                    skipped_files.append(str(src))
                    from .logger import MusicatLogger
                    MusicatLogger.log_file_op("SKIP", str(src), str(dst), collision_resolved="DEFAULT_SKIP", success=True)
                    continue

            try:
                from .logger import MusicatLogger
                if is_cut:
                    # Physical Move
                    shutil.move(str(src), str(dst))
                    # Immediate DB synchronization
                    self._update_db_after_move(active_db, str(src), str(dst))
                    moved_count += 1
                    processed_files.append(str(dst))
                    MusicatLogger.log_file_op("MOVE", str(src), str(dst), collision_resolved=collision_note, success=True)
                else:
                    # Physical Copy
                    shutil.copy2(str(src), str(dst))
                    # Immediate DB duplication
                    self._duplicate_db_after_copy(active_db, str(src), str(dst))
                    copied_count += 1
                    processed_files.append(str(dst))
                    MusicatLogger.log_file_op("COPY", str(src), str(dst), collision_resolved=collision_note, success=True)

            except Exception as exc:
                errors.append(f"Error transferring {src.name}: {exc}")
                from .logger import MusicatLogger
                MusicatLogger.log_file_op("TRANSFER_FAIL", str(src), str(dst), collision_resolved=collision_note, success=False, details=str(exc))

        # If it was a cut operation, clear internal clipboard
        if is_cut:
            self.clear_clipboard()

        return FileOperationResult(
            moved=moved_count,
            copied=copied_count,
            skipped=skipped_count,
            processed_files=processed_files,
            skipped_files=skipped_files,
            errors=errors,
        )

    def _update_db_after_move(self, db: Database, old_path: str, new_path: str) -> bool:
        """Updates track record with new location in SQLite without re-analysis."""
        p_new = Path(new_path).resolve()
        norm_new_path = str(p_new)
        portable_path, _ = PathResolver.to_portable_path(p_new)

        sql = """
            UPDATE tracks SET
                filepath = ?,
                directory = ?,
                filename = ?,
                portable_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE filepath = ? OR filepath = ?
        """
        resolved_old = str(Path(old_path).resolve())
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        sql,
                        (norm_new_path, str(p_new.parent), p_new.name, portable_path, old_path, resolved_old),
                    )
                    return cur.rowcount > 0
                finally:
                    cur.close()
        except Exception:
            return False

    def _duplicate_db_after_copy(self, db: Database, old_path: str, new_path: str) -> bool:
        """Clones existing track row in SQLite for the newly copied file."""
        resolved_old = str(Path(old_path).resolve())
        track = db.get_track(old_path) or db.get_track(resolved_old)
        if not track:
            with db.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT * FROM tracks WHERE filepath LIKE ? LIMIT 1", (f"%{Path(old_path).name}",))
                    row = cur.fetchone()
                    if row:
                        track = dict(row)
                finally:
                    cur.close()

        if not track:
            return False

        p_new = Path(new_path).resolve()
        norm_new_path = str(p_new)
        track_copy = dict(track)
        track_copy.pop("id", None)
        track_copy["filepath"] = norm_new_path
        track_copy["directory"] = str(p_new.parent)
        track_copy["filename"] = p_new.name
        portable_path, _ = PathResolver.to_portable_path(p_new)
        track_copy["portable_path"] = portable_path

        try:
            db.insert_or_update_track(track_copy)
            return True
        except Exception:
            return False
