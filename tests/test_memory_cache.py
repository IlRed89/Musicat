"""
Unit tests for Musicat In-Memory RAM Cache System (AnalysisMemoryCache & WaveformMemoryCache).
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from src.core.db import Database
from src.core.memory_cache import AnalysisMemoryCache, WaveformMemoryCache


class TestMemoryCache(unittest.TestCase):
    """Test suite for in-memory SQLite buffer and waveform LRU cache."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_musicat.db"
        self.disk_db = Database(self.db_path)
        self.mem_cache = AnalysisMemoryCache()
        self.wf_cache = WaveformMemoryCache(max_memory_mb=64)

    def tearDown(self):
        self.mem_cache.close()
        self.disk_db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analysis_memory_cache_store_and_retrieve(self):
        result = {
            "filepath": "C:/Music/test1.mp3",
            "bpm": 128.0,
            "bpm_rounded": 128,
            "musical_key": "Am",
            "camelot_key": "8A",
            "initial_key": "8A",
            "peak_db": -0.5,
            "rms_db": -12.4,
            "replay_gain_db": -1.6,
            "duration": 240.5,
            "waveform_json": "[0.1, 0.5, 0.9]",
        }
        self.mem_cache.store_result(result)
        self.assertEqual(self.mem_cache.get_pending_count(), 1)
        self.assertEqual(self.mem_cache.get_total_count(), 1)

        cached = self.mem_cache.get_result("C:/Music/test1.mp3")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["bpm"], 128.0)
        self.assertEqual(cached["camelot_key"], "8A")
        self.assertEqual(cached["is_synced"], 0)

    def test_analysis_memory_cache_batch_store(self):
        batch = [
            {
                "filepath": f"C:/Music/track_{i}.mp3",
                "bpm": 120.0 + i,
                "bpm_rounded": 120 + i,
                "musical_key": "Cm",
                "camelot_key": "5A",
                "initial_key": "5A",
                "peak_db": -1.0,
                "rms_db": -14.0,
                "replay_gain_db": 0.0,
                "duration": 180.0,
                "waveform_json": "[]",
            }
            for i in range(10)
        ]
        self.mem_cache.store_batch(batch)
        self.assertEqual(self.mem_cache.get_pending_count(), 10)
        self.assertEqual(self.mem_cache.get_total_count(), 10)

        all_res = self.mem_cache.get_all_results()
        self.assertEqual(len(all_res), 10)

    def test_flush_to_disk_database(self):
        # 1. Insert seed tracks into disk DB
        tracks_to_insert = [
            {
                "filepath": f"C:/Music/disk_{i}.mp3",
                "filename": f"disk_{i}.mp3",
                "directory": "C:/Music",
                "title": f"Song {i}",
                "artist": "DJ Test",
            }
            for i in range(5)
        ]
        self.disk_db.bulk_insert_or_update(tracks_to_insert)

        # 2. Store analysis in RAM buffer
        ram_results = [
            {
                "filepath": f"C:/Music/disk_{i}.mp3",
                "bpm": 126.0,
                "bpm_rounded": 126,
                "musical_key": "Gm",
                "camelot_key": "6A",
                "initial_key": "6A",
                "peak_db": -0.8,
                "rms_db": -13.5,
                "replay_gain_db": -0.5,
                "duration": 300.0,
                "waveform_json": "[0.2, 0.4, 0.6]",
            }
            for i in range(5)
        ]
        self.mem_cache.store_batch(ram_results)
        self.assertEqual(self.mem_cache.get_pending_count(), 5)

        # 3. Flush to disk
        flushed_count = self.mem_cache.flush_to_disk(self.disk_db)
        self.assertEqual(flushed_count, 5)
        self.assertEqual(self.mem_cache.get_pending_count(), 0)

        # 4. Verify disk records are updated
        for i in range(5):
            track = self.disk_db.get_track(f"C:/Music/disk_{i}.mp3")
            self.assertIsNotNone(track)
            self.assertEqual(track["bpm"], 126.0)
            self.assertEqual(track["camelot_key"], "6A")
            self.assertIsNotNone(track["analyzed_at"])

    def test_waveform_lru_cache_basic(self):
        self.wf_cache.put_waveform("C:/track1.mp3", [0.1, 0.5, 0.8])
        self.assertTrue(self.wf_cache.has_waveform("C:/track1.mp3"))

        peaks = self.wf_cache.get_waveform("C:/track1.mp3")
        self.assertEqual(peaks, [0.1, 0.5, 0.8])

        # Miss
        self.assertIsNone(self.wf_cache.get_waveform("C:/nonexistent.mp3"))

        stats = self.wf_cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["item_count"], 1)

    def test_waveform_lru_eviction(self):
        # Create a tiny cache of 64 KB for testing eviction
        tiny_cache = WaveformMemoryCache(max_memory_mb=64)
        tiny_cache._max_bytes = 2048  # Force limit to 2 KB

        for i in range(20):
            tiny_cache.put_waveform(f"C:/track_{i}.mp3", [float(j) for j in range(100)])

        stats = tiny_cache.get_stats()
        # Should have evicted older items and kept only ~1-2 items fitting in 2KB
        self.assertLess(stats["memory_bytes"], 2048)
        self.assertLess(stats["item_count"], 20)
        # Most recent track should be retained
        self.assertTrue(tiny_cache.has_waveform("C:/track_19.mp3"))
        # Earliest track should have been evicted
        self.assertFalse(tiny_cache.has_waveform("C:/track_0.mp3"))


if __name__ == "__main__":
    unittest.main()
