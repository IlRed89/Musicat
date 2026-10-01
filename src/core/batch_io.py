"""
Multithreaded Batch I/O Pipeline for Metadata Tag Writing.

Writes physical ID3/Vorbis/MP4 tags to disk asynchronously without locking
the GUI event loop or audio playback.
"""

from __future__ import annotations

import concurrent.futures
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.tags.editor import AudioTagEditor


@dataclass
class TagWriteTask:
    """Represents a metadata write task for a specific file."""

    filepath: str
    tags: Dict[str, Any]


@dataclass
class TagWriteResult:
    """Represents the outcome of writing tags to a file."""

    filepath: str
    success: bool
    error_message: Optional[str] = None


class BatchTagWriter:
    """Asynchronous batch I/O pipeline for tag modifications."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def write_sync(self, tasks: List[TagWriteTask]) -> List[TagWriteResult]:
        """Synchronously processes a list of tag write tasks and returns results."""
        results: List[TagWriteResult] = []
        for task in tasks:
            p = Path(task.filepath)
            if not p.exists():
                results.append(
                    TagWriteResult(
                        filepath=task.filepath,
                        success=False,
                        error_message=f"File not found: {task.filepath}",
                    )
                )
                continue
            try:
                AudioTagEditor.write_metadata(task.filepath, task.tags)
                results.append(TagWriteResult(filepath=task.filepath, success=True))
            except Exception as e:
                results.append(
                    TagWriteResult(filepath=task.filepath, success=False, error_message=str(e))
                )
        return results

    def write_batch_async(
        self,
        updates: List[Tuple[str, Dict[str, Any]]],
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_finished: Optional[Callable[[int, int], None]] = None,
    ) -> concurrent.futures.Future:
        """Schedules asynchronous batch tag writing on background worker threads.

        Args:
            updates: List of (filepath, metadata_dict) pairs.
            on_progress: Callback(completed_count, total_count).
            on_finished: Callback(success_count, error_count).

        Returns:
            Future object tracking completion.
        """
        def _task():
            total = len(updates)
            success = 0
            errors = 0

            for idx, (filepath, tag_dict) in enumerate(updates):
                try:
                    AudioTagEditor.write_metadata(filepath, tag_dict)
                    success += 1
                except Exception:
                    errors += 1

                if on_progress:
                    try:
                        on_progress(idx + 1, total)
                    except Exception:
                        pass

            if on_finished:
                try:
                    on_finished(success, errors)
                except Exception:
                    pass

            return {"success": success, "errors": errors, "total": total}

        return self._executor.submit(_task)

    def shutdown(self) -> None:
        """Shuts down background thread pool."""
        self._executor.shutdown(wait=False)
