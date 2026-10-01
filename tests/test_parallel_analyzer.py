"""
Unit tests for Musicat Parallel Acoustic Analyzer & Worker Engine.
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from src.audio.parallel_analyzer import ParallelAnalyzer
from src.audio.worker import (
    analyze_single_track,
    analyze_track_batch_worker,
    extract_high_energy_chroma,
    load_partial_audio_window,
)
from src.core.memory_cache import AnalysisMemoryCache, WaveformMemoryCache


class TestParallelAnalyzer(unittest.TestCase):
    """Test suite for hardware-aware worker functions and ParallelAnalyzer."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.audio_files = []

        # Create 6 short synthetic audio files with 128 BPM beat pulses (C Major / A Minor)
        sr = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        # 128 BPM pulses (interval ~0.46875s)
        beat_interval = 60.0 / 128.0
        beat_frames = [int(i * beat_interval * sr) for i in range(int(duration / beat_interval))]

        for idx in range(6):
            sig = np.zeros_like(t)
            # Add synthetic kick transients
            for bf in beat_frames:
                if bf < len(sig) - 500:
                    sig[bf : bf + 500] += np.sin(2 * np.pi * 60 * np.linspace(0, 0.05, 500))

            # Add A4 (440Hz) tone for Am tonality
            sig += 0.2 * np.sin(2 * np.pi * 440.0 * t)

            fp = Path(cls.temp_dir) / f"synth_track_{idx}.wav"
            sf.write(str(fp), sig, sr)
            cls.audio_files.append(str(fp))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_worker_analyze_single_track(self):
        fp = self.audio_files[0]
        res = analyze_single_track(fp)

        self.assertTrue(res["success"])
        self.assertEqual(res["filepath"], fp)
        self.assertGreater(res["bpm"], 0.0)
        self.assertIn(res["camelot_key"], ["8A", "8B", "1A", "2A", "3A", "4A", "5A", "6A", "7A", "9A", "10A", "11A", "12A", "1B", "2B", "3B", "4B", "5B", "6B", "7B", "9B", "10B", "11B", "12B", ""])
        self.assertGreater(len(res["waveform_peaks"]), 0)
        self.assertGreater(res["compute_time_ms"], 0.0)

    def test_worker_nonexistent_file(self):
        res = analyze_single_track("C:/nonexistent_audio_path_9999.wav")
        self.assertFalse(res["success"])
        self.assertEqual(res["bpm"], 0.0)
        self.assertIsNotNone(res["error"])

    def test_worker_batch_function(self):
        batch = self.audio_files[:3]
        results = analyze_track_batch_worker(batch)

        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(r["success"])
            self.assertGreater(len(r["waveform_peaks"]), 0)

    def test_streaming_partial_window_and_chroma(self):
        fp = self.audio_files[0]
        signal, sr, total_dur = load_partial_audio_window(fp, target_sr=22050, window_duration_sec=2.0)

        self.assertEqual(sr, 22050)
        self.assertAlmostEqual(total_dur, 3.0, delta=0.5)
        self.assertGreater(len(signal), 0)

        musical_key, camelot = extract_high_energy_chroma(signal, sr, top_segments=2, segment_duration_sec=1.0)
        self.assertIsInstance(musical_key, str)
        self.assertIsInstance(camelot, str)

    def test_parallel_analyzer_hardware_detection(self):
        analyzer = ParallelAnalyzer()
        cpu_count = os.cpu_count() or 4
        expected_default = max(1, cpu_count - 1)
        self.assertEqual(analyzer.num_workers, expected_default)
        self.assertLessEqual(analyzer.num_workers, cpu_count)

    def test_parallel_analyzer_full_pipeline(self):
        mem_cache = AnalysisMemoryCache()
        wf_cache = WaveformMemoryCache(max_memory_mb=128)

        progress_calls = []
        batch_calls = []

        analyzer = ParallelAnalyzer(
            num_workers=2,
            batch_size=2,
            memory_cache=mem_cache,
            waveform_cache=wf_cache,
        )

        summary = analyzer.analyze_tracks(
            self.audio_files,
            on_progress=lambda info: progress_calls.append(info),
            on_batch_complete=lambda b: batch_calls.append(b),
        )

        self.assertEqual(summary["total"], 6)
        self.assertEqual(summary["processed"], 6)
        self.assertEqual(summary["success"], 6)
        self.assertEqual(summary["failed"], 0)
        self.assertGreater(len(progress_calls), 0)
        self.assertGreater(len(batch_calls), 0)

        # Check telemetry metrics in final progress call
        last_progress = progress_calls[-1]
        self.assertEqual(last_progress["processed"], 6)
        self.assertEqual(last_progress["percent"], 100.0)
        self.assertGreaterEqual(last_progress["throughput"], 0.0)

        # Verify RAM cache stores
        self.assertEqual(mem_cache.get_total_count(), 6)
        for fp in self.audio_files:
            self.assertTrue(wf_cache.has_waveform(fp))

        mem_cache.close()

    def test_parallel_analyzer_pause_and_cancel(self):
        analyzer = ParallelAnalyzer(num_workers=2, batch_size=1)
        self.assertFalse(analyzer.is_paused)
        self.assertFalse(analyzer.is_cancelled)

        analyzer.pause()
        self.assertTrue(analyzer.is_paused)

        analyzer.resume()
        self.assertFalse(analyzer.is_paused)

        analyzer.cancel()
        self.assertTrue(analyzer.is_cancelled)


if __name__ == "__main__":
    unittest.main()
