"""
Parallel Acoustic Analysis Engine for Musicat.

Features:
- Hardware-aware dynamic multiprocessing pool (ProcessPoolExecutor) that
  saturates multi-core CPUs while keeping 1 core available for OS, VLC, and Qt GUI.
- Chunking & Batch Scheduling (20-50 tracks per batch) to minimize IPC serialization.
- Non-blocking execution with thread-safe Pause, Resume, and Cancel primitives.
- Real-time telemetry: sliding-window throughput (tracks/sec), percentage, ETA.
- Direct integration with AnalysisMemoryCache (RAM buffer) and WaveformMemoryCache (LRU).
"""

from __future__ import annotations

import collections
import concurrent.futures
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from src.audio.worker import analyze_track_batch_worker
from src.core.memory_cache import AnalysisMemoryCache, WaveformMemoryCache


class ParallelAnalyzer:
    """Hardware-aware parallel audio analyzer utilizing dynamic process pools."""

    def __init__(
        self,
        num_workers: Optional[int] = None,
        batch_size: int = 25,
        memory_cache: Optional[AnalysisMemoryCache] = None,
        waveform_cache: Optional[WaveformMemoryCache] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initializes ParallelAnalyzer.

        Args:
            num_workers: Number of worker processes. Defaults to max(1, os.cpu_count() - 1).
            batch_size: Number of tracks dispatched per worker task (default: 25).
            memory_cache: Optional AnalysisMemoryCache instance for RAM buffering.
            waveform_cache: Optional WaveformMemoryCache instance for LRU caching.
            options: Audio processing options passed down to worker.
        """
        logical_cores = os.cpu_count() or 4
        self.max_system_cores = logical_cores

        if num_workers is None or num_workers <= 0:
            self.num_workers = max(1, logical_cores - 1)
        else:
            self.num_workers = min(logical_cores, num_workers)

        self.batch_size = max(1, batch_size)
        self.memory_cache = memory_cache
        self.waveform_cache = waveform_cache or WaveformMemoryCache.get_instance()
        self.options = options or {}

        # Concurrency & Control Flags
        self._lock = threading.RLock()
        self._is_running = False
        self._is_paused = False
        self._is_cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Unpaused initially

        # Telemetry
        self._start_time = 0.0
        self._processed_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_count = 0
        self._throughput_history: collections.deque[tuple[float, int]] = collections.deque(maxlen=20)
        self._last_processed_file: str = ""

    @property
    def is_running(self) -> bool:
        """Returns True if analysis is actively running."""
        with self._lock:
            return self._is_running

    @property
    def is_paused(self) -> bool:
        """Returns True if analysis is currently paused."""
        with self._lock:
            return self._is_paused

    @property
    def is_cancelled(self) -> bool:
        """Returns True if analysis was cancelled."""
        with self._lock:
            return self._is_cancelled

    def pause(self) -> None:
        """Pauses the dispatching and processing of pending batches."""
        with self._lock:
            if not self._is_paused:
                self._is_paused = True
                self._pause_event.clear()

    def resume(self) -> None:
        """Resumes analysis execution."""
        with self._lock:
            if self._is_paused:
                self._is_paused = False
                self._pause_event.set()

    def cancel(self) -> None:
        """Cancels analysis and stops scheduling remaining batches."""
        with self._lock:
            self._is_cancelled = True
            self._is_paused = False
            self._pause_event.set()  # Unblock any waiting loops

    def _calculate_throughput(self) -> float:
        """Computes rolling tracks per second using sliding-window history."""
        now = time.time()
        # Keep entries within the last 5 seconds
        while self._throughput_history and (now - self._throughput_history[0][0]) > 6.0:
            self._throughput_history.popleft()

        if len(self._throughput_history) < 2:
            elapsed = max(0.1, now - self._start_time)
            return round(self._processed_count / elapsed, 1)

        t_start, count_start = self._throughput_history[0]
        t_end, count_end = self._throughput_history[-1]
        dt = max(0.001, t_end - t_start)
        dn = max(0, count_end - count_start)
        return round(dn / dt, 1)

    def analyze_tracks(
        self,
        filepaths: List[Union[str, Path]],
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_batch_complete: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Runs parallel acoustic analysis over a list of audio filepaths.

        Blocks the calling thread until completion or cancellation, while dispatching
        batches across the configured ProcessPoolExecutor.

        Args:
            filepaths: List of target filepaths to analyze.
            on_progress: Callback invoked with real-time metrics dictionary.
            on_batch_complete: Callback invoked when a batch finishes.
            on_finished: Callback invoked upon completion.

        Returns:
            Summary dictionary with total, processed, success, and elapsed metrics.
        """
        paths_str = [str(p) for p in filepaths if p]
        self._total_count = len(paths_str)

        with self._lock:
            self._is_running = True
            self._is_paused = False
            self._is_cancelled = False
            self._pause_event.set()
            self._processed_count = 0
            self._success_count = 0
            self._failure_count = 0
            self._start_time = time.time()
            self._throughput_history.clear()
            self._throughput_history.append((self._start_time, 0))

        if not paths_str:
            summary = self._build_summary()
            if on_finished:
                on_finished(summary)
            with self._lock:
                self._is_running = False
            return summary

        # 1. Chunk filepaths into batches
        batches = [
            paths_str[i : i + self.batch_size]
            for i in range(0, len(paths_str), self.batch_size)
        ]

        # 2. Execute with ProcessPoolExecutor
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                # Submit all batches
                future_to_batch = {
                    executor.submit(analyze_track_batch_worker, b, self.options): b
                    for b in batches
                }

                for future in concurrent.futures.as_completed(future_to_batch):
                    # Check cancellation
                    if self._is_cancelled:
                        # Cancel remaining futures
                        for f in future_to_batch:
                            f.cancel()
                        break

                    # Check pause
                    self._pause_event.wait()

                    try:
                        batch_results = future.result()
                    except Exception as exc:
                        # Handle worker failure gracefully
                        original_batch = future_to_batch[future]
                        batch_results = [
                            {
                                "filepath": fp,
                                "bpm": 0.0,
                                "bpm_rounded": 0,
                                "musical_key": "",
                                "camelot_key": "",
                                "initial_key": "",
                                "peak_db": -99.0,
                                "rms_db": -99.0,
                                "replay_gain_db": 0.0,
                                "duration": 0.0,
                                "waveform_peaks": [],
                                "waveform_json": "[]",
                                "success": False,
                                "error": str(exc),
                                "compute_time_ms": 0.0,
                            }
                            for fp in original_batch
                        ]

                    # Process batch results
                    self._handle_batch_results(
                        batch_results,
                        on_progress=on_progress,
                        on_batch_complete=on_batch_complete,
                    )

        finally:
            with self._lock:
                self._is_running = False

        summary = self._build_summary()
        if on_finished:
            on_finished(summary)
        return summary

    def _handle_batch_results(
        self,
        batch_results: List[Dict[str, Any]],
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_batch_complete: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> None:
        """Processes completed batch results, updating caches and emitting metrics."""
        now = time.time()
        for res in batch_results:
            self._processed_count += 1
            if res.get("success"):
                self._success_count += 1
            else:
                self._failure_count += 1

            self._last_processed_file = Path(res.get("filepath", "")).name

            # Store waveform in RAM LRU cache
            peaks = res.get("waveform_peaks")
            if peaks and self.waveform_cache:
                self.waveform_cache.put_waveform(res["filepath"], peaks)

        # Store batch in SQLite RAM buffer
        if self.memory_cache:
            self.memory_cache.store_batch(batch_results)

        # Update throughput tracking
        self._throughput_history.append((now, self._processed_count))
        throughput = self._calculate_throughput()

        # Telemetry metrics
        elapsed = max(0.1, now - self._start_time)
        percent = (self._processed_count / self._total_count * 100.0) if self._total_count > 0 else 100.0
        remaining_tracks = max(0, self._total_count - self._processed_count)
        eta_seconds = (remaining_tracks / throughput) if throughput > 0 else 0.0

        progress_info = {
            "processed": self._processed_count,
            "total": self._total_count,
            "success": self._success_count,
            "failed": self._failure_count,
            "percent": round(percent, 1),
            "throughput": throughput,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta_seconds, 1),
            "current_track": self._last_processed_file,
            "active_workers": self.num_workers,
            "pending_ram_count": self.memory_cache.get_pending_count() if self.memory_cache else 0,
            "is_paused": self._is_paused,
            "is_cancelled": self._is_cancelled,
        }

        if on_progress:
            try:
                on_progress(progress_info)
            except Exception:
                pass

        if on_batch_complete:
            try:
                on_batch_complete(batch_results)
            except Exception:
                pass

    def _build_summary(self) -> Dict[str, Any]:
        """Constructs final summary dictionary."""
        now = time.time()
        elapsed = max(0.001, now - self._start_time) if self._start_time > 0 else 0.0
        avg_throughput = round(self._processed_count / elapsed, 1) if elapsed > 0 else 0.0

        return {
            "total": self._total_count,
            "processed": self._processed_count,
            "success": self._success_count,
            "failed": self._failure_count,
            "elapsed_seconds": round(elapsed, 2),
            "average_throughput": avg_throughput,
            "active_workers": self.num_workers,
            "cancelled": self._is_cancelled,
            "waveform_cache_stats": self.waveform_cache.get_stats() if self.waveform_cache else {},
        }
