"""
High-Performance In-Memory RAM Cache System for Musicat.

Eliminates disk I/O bottlenecks during mass acoustic analysis (50,000+ tracks):
1. AnalysisMemoryCache:
   - High-speed in-memory SQLite buffer (:memory: / shared RAM).
   - Batches raw acoustic analysis results, keys, and waveform vectors in RAM.
   - Periodic or threshold-based asynchronous flushes to disk (musicat.db)
     to prevent physical SSD/USB drive wear.
2. WaveformMemoryCache:
   - Configurable LRU (Least Recently Used) cache for spectral waveform peak data.
   - Limits RAM consumption to user-defined threshold (e.g. 512MB / 1GB / 2GB).
   - Instant (<0.1ms) zero-I/O waveform retrieval during DJ track preview.
"""

from __future__ import annotations

import collections
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.core.db import Database


class AnalysisMemoryCache:
    """Thread-safe in-memory SQLite buffer for high-throughput acoustic analysis."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_memory_schema()

        # Auto-flush timer attributes
        self._auto_flush_timer: Optional[threading.Timer] = None
        self._auto_flush_active = False
        self._auto_flush_interval = 30.0
        self._auto_flush_threshold = 100
        self._target_disk_db: Optional[Database] = None
        self._flush_callback: Optional[Callable[[int], None]] = None
        self._last_flush_time = time.time()

    def _init_memory_schema(self) -> None:
        """Initializes fast RAM tables and indices."""
        with self._lock:
            self._conn.executescript("""
                PRAGMA synchronous = OFF;
                PRAGMA journal_mode = OFF;
                PRAGMA temp_store = MEMORY;

                CREATE TABLE IF NOT EXISTS memory_analysis_buffer (
                    filepath TEXT PRIMARY KEY,
                    bpm REAL,
                    bpm_rounded INTEGER,
                    musical_key TEXT,
                    camelot_key TEXT,
                    initial_key TEXT,
                    peak_db REAL,
                    rms_db REAL,
                    replay_gain_db REAL,
                    duration REAL,
                    waveform_json TEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_synced INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_mem_synced ON memory_analysis_buffer (is_synced);
            """)

    def store_result(self, result: Dict[str, Any]) -> None:
        """Stores a single analysis result into the RAM buffer.

        Args:
            result: Result dictionary from acoustic worker.
        """
        if not result or not result.get("filepath"):
            return

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO memory_analysis_buffer (
                    filepath, bpm, bpm_rounded, musical_key, camelot_key,
                    initial_key, peak_db, rms_db, replay_gain_db, duration,
                    waveform_json, is_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(filepath) DO UPDATE SET
                    bpm = excluded.bpm,
                    bpm_rounded = excluded.bpm_rounded,
                    musical_key = excluded.musical_key,
                    camelot_key = excluded.camelot_key,
                    initial_key = excluded.initial_key,
                    peak_db = excluded.peak_db,
                    rms_db = excluded.rms_db,
                    replay_gain_db = excluded.replay_gain_db,
                    duration = excluded.duration,
                    waveform_json = excluded.waveform_json,
                    is_synced = 0,
                    analyzed_at = CURRENT_TIMESTAMP
            """, (
                result.get("filepath"),
                result.get("bpm"),
                result.get("bpm_rounded"),
                result.get("musical_key"),
                result.get("camelot_key"),
                result.get("initial_key") or result.get("camelot_key"),
                result.get("peak_db"),
                result.get("rms_db"),
                result.get("replay_gain_db"),
                result.get("duration"),
                result.get("waveform_json"),
            ))
            self._conn.commit()

        self._check_auto_flush_threshold()

    def store_batch(self, results: List[Dict[str, Any]]) -> None:
        """Stores a batch of analysis results in a single RAM transaction.

        Args:
            results: List of result dictionaries from worker batch.
        """
        if not results:
            return

        with self._lock:
            cur = self._conn.cursor()
            records = [
                (
                    r.get("filepath"),
                    r.get("bpm"),
                    r.get("bpm_rounded"),
                    r.get("musical_key"),
                    r.get("camelot_key"),
                    r.get("initial_key") or r.get("camelot_key"),
                    r.get("peak_db"),
                    r.get("rms_db"),
                    r.get("replay_gain_db"),
                    r.get("duration"),
                    r.get("waveform_json"),
                )
                for r in results
                if r.get("filepath")
            ]

            cur.executemany("""
                INSERT INTO memory_analysis_buffer (
                    filepath, bpm, bpm_rounded, musical_key, camelot_key,
                    initial_key, peak_db, rms_db, replay_gain_db, duration,
                    waveform_json, is_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(filepath) DO UPDATE SET
                    bpm = excluded.bpm,
                    bpm_rounded = excluded.bpm_rounded,
                    musical_key = excluded.musical_key,
                    camelot_key = excluded.camelot_key,
                    initial_key = excluded.initial_key,
                    peak_db = excluded.peak_db,
                    rms_db = excluded.rms_db,
                    replay_gain_db = excluded.replay_gain_db,
                    duration = excluded.duration,
                    waveform_json = excluded.waveform_json,
                    is_synced = 0,
                    analyzed_at = CURRENT_TIMESTAMP
            """, records)
            self._conn.commit()

        self._check_auto_flush_threshold()

    def get_result(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Retrieves an analysis record from RAM buffer by filepath."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM memory_analysis_buffer WHERE filepath = ?", (filepath,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_pending_count(self) -> int:
        """Returns the number of records waiting to be flushed to disk."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memory_analysis_buffer WHERE is_synced = 0")
            return cur.fetchone()[0]

    def get_total_count(self) -> int:
        """Returns total records stored in the RAM buffer."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memory_analysis_buffer")
            return cur.fetchone()[0]

    def get_all_results(self) -> List[Dict[str, Any]]:
        """Retrieves all results currently in the RAM buffer."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM memory_analysis_buffer")
            return [dict(r) for r in cur.fetchall()]

    def flush_to_disk(
        self,
        disk_db: Database,
        write_physical_tags: bool = False,
    ) -> int:
        """Flushes all uncommitted RAM records to the persistent SQLite database on disk.

        Performs a single batch transaction to maximize disk I/O efficiency and avoid
        excessive write cycles on USB drives / external SSDs.

        Args:
            disk_db: The destination persistent database instance.
            write_physical_tags: If True, also updates physical ID3/Vorbis/MP4 tags on disk.

        Returns:
            Number of tracks flushed and committed to disk.
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM memory_analysis_buffer WHERE is_synced = 0")
            pending_rows = [dict(r) for r in cur.fetchall()]

            if not pending_rows:
                return 0

            # 1. Prepare batch updates for disk SQLite
            sql = """
                UPDATE tracks SET
                    bpm = :bpm,
                    musical_key = :musical_key,
                    camelot_key = :camelot_key,
                    initial_key = :initial_key,
                    waveform_peaks = :waveform_json,
                    duration = CASE WHEN duration IS NULL OR duration <= 0 THEN :duration ELSE duration END,
                    analyzed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE filepath = :filepath
            """

            with disk_db.get_connection() as disk_conn:
                disk_cur = disk_conn.cursor()
                disk_cur.executemany(sql, pending_rows)

            # 2. Optionally write physical audio tags if requested
            if write_physical_tags:
                try:
                    from src.tags.editor import AudioTagEditor

                    for row in pending_rows:
                        fp = row["filepath"]
                        tag_updates: Dict[str, Any] = {}
                        if row.get("bpm"):
                            tag_updates["bpm"] = row["bpm"]
                        if row.get("musical_key"):
                            tag_updates["musical_key"] = row["musical_key"]
                        if row.get("camelot_key"):
                            tag_updates["camelot_key"] = row["camelot_key"]
                        if tag_updates:
                            try:
                                AudioTagEditor.write_metadata(fp, tag_updates)
                            except Exception:
                                pass
                except ImportError:
                    pass

            # 3. Mark flushed rows as synced in memory
            filepaths = [(r["filepath"],) for r in pending_rows]
            cur.executemany(
                "UPDATE memory_analysis_buffer SET is_synced = 1 WHERE filepath = ?",
                filepaths,
            )
            self._conn.commit()
            self._last_flush_time = time.time()

            flushed_count = len(pending_rows)

        if self._flush_callback:
            try:
                self._flush_callback(flushed_count)
            except Exception:
                pass

        return flushed_count

    def start_auto_flush(
        self,
        disk_db: Database,
        interval_sec: float = 30.0,
        batch_threshold: int = 100,
        on_flush_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Starts periodic background flush timer.

        Args:
            disk_db: Target disk database instance.
            interval_sec: Flush interval in seconds (default: 30.0s).
            batch_threshold: Flush immediately when pending count exceeds this (default: 100).
            on_flush_callback: Optional callback invoked with the number of flushed tracks.
        """
        with self._lock:
            self._target_disk_db = disk_db
            self._auto_flush_interval = max(5.0, interval_sec)
            self._auto_flush_threshold = max(10, batch_threshold)
            self._flush_callback = on_flush_callback
            self._auto_flush_active = True
            self._schedule_next_flush()

    def _schedule_next_flush(self) -> None:
        """Schedules the next execution of the flush timer."""
        if not self._auto_flush_active:
            return
        if self._auto_flush_timer:
            self._auto_flush_timer.cancel()

        self._auto_flush_timer = threading.Timer(
            self._auto_flush_interval,
            self._on_auto_flush_timer_tick,
        )
        self._auto_flush_timer.daemon = True
        self._auto_flush_timer.start()

    def _on_auto_flush_timer_tick(self) -> None:
        """Triggered periodically by timer."""
        if not self._auto_flush_active or not self._target_disk_db:
            return

        try:
            self.flush_to_disk(self._target_disk_db)
        except Exception:
            pass
        finally:
            with self._lock:
                if self._auto_flush_active:
                    self._schedule_next_flush()

    def _check_auto_flush_threshold(self) -> None:
        """Checks if pending count exceeded the threshold for an immediate flush."""
        if not self._auto_flush_active or not self._target_disk_db:
            return

        if self.get_pending_count() >= self._auto_flush_threshold:
            try:
                self.flush_to_disk(self._target_disk_db)
            except Exception:
                pass

    def stop_auto_flush(self, final_flush: bool = True) -> int:
        """Stops the auto-flush timer and optionally executes a final flush.

        Args:
            final_flush: If True, flushes all remaining records immediately.

        Returns:
            Number of tracks flushed in the final flush.
        """
        with self._lock:
            self._auto_flush_active = False
            if self._auto_flush_timer:
                self._auto_flush_timer.cancel()
                self._auto_flush_timer = None

        if final_flush and self._target_disk_db:
            return self.flush_to_disk(self._target_disk_db)
        return 0

    def clear(self) -> None:
        """Wipes all records from the RAM buffer."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM memory_analysis_buffer")
            self._conn.commit()

    def close(self) -> None:
        """Closes memory database connection."""
        self.stop_auto_flush(final_flush=False)
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


class WaveformMemoryCache:
    """Configurable LRU (Least Recently Used) RAM cache for waveform peak data."""

    _instance: Optional["WaveformMemoryCache"] = None
    _instance_lock = threading.Lock()

    def __init__(self, max_memory_mb: int = 512) -> None:
        self._lock = threading.RLock()
        self._max_memory_mb = max(64, max_memory_mb)
        self._max_bytes = self._max_memory_mb * 1024 * 1024
        self._cache: collections.OrderedDict[str, List[float]] = collections.OrderedDict()
        self._current_bytes = 0
        self._hits = 0
        self._misses = 0

    @classmethod
    def get_instance(cls, default_mb: int = 512) -> "WaveformMemoryCache":
        """Singleton accessor for global application-wide waveform cache."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(max_memory_mb=default_mb)
            return cls._instance

    def _estimate_item_bytes(self, key: str, peaks: List[float]) -> int:
        """Calculates rough memory footprint of a waveform entry."""
        # Key string + list header + 8 bytes per float + dict entry overhead
        return len(key.encode("utf-8", errors="ignore")) + len(peaks) * 8 + 128

    def get_waveform(self, filepath: str) -> Optional[List[float]]:
        """Retrieves cached waveform peaks, moving entry to front of LRU.

        Args:
            filepath: Audio file path key.

        Returns:
            List of normalized peak floats, or None if not cached.
        """
        with self._lock:
            if filepath in self._cache:
                self._hits += 1
                self._cache.move_to_end(filepath)
                return self._cache[filepath]
            self._misses += 1
            return None

    def put_waveform(self, filepath: str, peaks: List[float]) -> None:
        """Stores waveform peaks into LRU cache, evicting oldest if limit is reached.

        Args:
            filepath: Audio file path key.
            peaks: List of normalized peak floats [0.0 - 1.0].
        """
        if not filepath or not peaks:
            return

        item_bytes = self._estimate_item_bytes(filepath, peaks)

        with self._lock:
            # If already present, subtract old size first
            if filepath in self._cache:
                old_bytes = self._estimate_item_bytes(filepath, self._cache[filepath])
                self._current_bytes -= old_bytes
                del self._cache[filepath]

            # Evict oldest entries until within memory limit
            while self._cache and (self._current_bytes + item_bytes > self._max_bytes):
                evicted_key, evicted_peaks = self._cache.popitem(last=False)
                self._current_bytes -= self._estimate_item_bytes(evicted_key, evicted_peaks)

            self._cache[filepath] = peaks
            self._current_bytes += item_bytes

    def has_waveform(self, filepath: str) -> bool:
        """Checks if waveform exists in RAM cache without altering LRU order."""
        with self._lock:
            return filepath in self._cache

    def remove(self, filepath: str) -> None:
        """Removes a specific filepath from the cache."""
        with self._lock:
            if filepath in self._cache:
                peaks = self._cache.pop(filepath)
                self._current_bytes -= self._estimate_item_bytes(filepath, peaks)

    def set_max_memory_mb(self, max_mb: int) -> None:
        """Updates max memory limit and evicts excess items if necessary."""
        with self._lock:
            self._max_memory_mb = max(64, max_mb)
            self._max_bytes = self._max_memory_mb * 1024 * 1024
            while self._cache and self._current_bytes > self._max_bytes:
                evicted_key, evicted_peaks = self._cache.popitem(last=False)
                self._current_bytes -= self._estimate_item_bytes(evicted_key, evicted_peaks)

    def clear(self) -> None:
        """Clears all cached waveforms and resets metrics."""
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Returns diagnostic statistics of the waveform cache."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100.0) if total_requests > 0 else 0.0
            return {
                "item_count": len(self._cache),
                "memory_bytes": self._current_bytes,
                "memory_mb": round(self._current_bytes / (1024 * 1024), 2),
                "max_memory_mb": self._max_memory_mb,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 1),
            }
