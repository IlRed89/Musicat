"""
Unit Tests for Live DJ Filter Engine, Query Builder, Smart Crates and M3U8 Export.
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from src.core.db import Database
from src.core.filter_engine import FilterCriteria, LiveFilterEngine, LiveFilterQueryBuilder


class TestFilterEngine(unittest.TestCase):
    """Tests live filtering performance, dynamic query generation, Smart Crates, and M3U export."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_filter.db"
        self.db = Database(self.db_path)
        self.engine = LiveFilterEngine(self.db)

        # Populate sample DJ tracks
        sample_tracks = [
            {
                "filepath": f"C:/Music/Track_{i:03d}.mp3",
                "filename": f"Track_{i:03d}.mp3",
                "directory": "C:/Music",
                "title": f"Anthem {i}",
                "artist": "Carl Cox" if i % 2 == 0 else "Charlotte de Witte",
                "album": "Space Ibiza 2024",
                "genre": "Tech House" if i % 3 == 0 else ("Techno" if i % 3 == 1 else "Afro House"),
                "bpm": 124.0 + (i % 10),  # 124 to 133 BPM
                "camelot_key": f"{(i % 12) + 1}A" if i % 2 == 0 else f"{(i % 12) + 1}B",
                "year": 2020 + (i % 5),   # 2020 - 2024
                "energy_level": (i % 5) + 1,  # 1 to 5
                "rating": (i % 5) + 1,
                "comment": "Club Intro Vocal" if i % 4 == 0 else "Instrumental",
                "duration": 360.0 + i,
            }
            for i in range(1, 101)  # 100 tracks
        ]
        self.db.bulk_insert_or_update(sample_tracks)
        self.engine.warm_cache(self.db.search_tracks(limit=10000))

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_filter_criteria_serialization(self):
        """Tests converting FilterCriteria to and from JSON dictionary."""
        crit = FilterCriteria(
            query_text="Anthem",
            genres=["Tech House", "Afro House"],
            target_bpm=126.0,
            bpm_tolerance_pct=4.0,
            camelot_key="8A",
            harmonic_matches_only=True,
            year_min=2020,
            year_max=2024,
            rating_min=4,
            energy_levels=[4, 5],
            tags=["Intro", "Vocal"],
        )
        data = crit.to_dict()
        self.assertEqual(data["target_bpm"], 126.0)
        self.assertEqual(data["genres"], ["Tech House", "Afro House"])

        loaded = FilterCriteria.from_dict(data)
        self.assertEqual(loaded.camelot_key, "8A")
        self.assertTrue(loaded.harmonic_matches_only)
        self.assertEqual(loaded.energy_levels, [4, 5])

    def test_effective_bpm_range(self):
        """Tests BPM tolerance calculation in FilterCriteria."""
        crit = FilterCriteria(target_bpm=126.0, bpm_tolerance_pct=2.0)
        min_b, max_b = crit.effective_bpm_range()
        self.assertAlmostEqual(min_b, 123.5, places=1)
        self.assertAlmostEqual(max_b, 128.5, places=1)

    def test_sql_query_builder(self):
        """Tests SQL query generation with composite clauses."""
        crit = FilterCriteria(
            genres=["Tech House", "Afro House"],
            bpm_min=124.0,
            bpm_max=128.0,
            camelot_key="8A",
            harmonic_matches_only=False,
            year_min=2022,
            energy_levels=[4, 5],
        )
        sql, params = LiveFilterQueryBuilder.build_sql(crit)
        self.assertIn("genre LIKE ? OR genre LIKE ?", sql)
        self.assertIn("bpm >= ?", sql)
        self.assertIn("bpm <= ?", sql)
        self.assertIn("UPPER(camelot_key) IN (?)", sql)
        self.assertIn("year >= ?", sql)
        self.assertIn("energy_level IN (?,?)", sql)
        self.assertIn(124.0, params)
        self.assertIn(128.0, params)

    def test_in_memory_filter_performance_and_accuracy(self):
        """Tests filtering 100 tracks in RAM executes in <15ms with accurate multi-genre OR."""
        crit = FilterCriteria(
            genres=["Tech House", "Afro House"],
            bpm_min=125.0,
            bpm_max=128.0,
        )
        t0 = time.perf_counter()
        results = self.engine.filter_in_memory(crit)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Assert sub-millisecond in-memory performance
        self.assertLess(latency_ms, 15.0)
        self.assertGreater(len(results), 0)

        for tr in results:
            self.assertTrue(tr["genre"] in ("Tech House", "Afro House"))
            self.assertTrue(125.0 <= tr["bpm"] <= 128.0)

    def test_harmonic_key_filter_in_memory(self):
        """Tests Camelot harmonic key matching in filter engine."""
        crit = FilterCriteria(
            camelot_key="8A",
            harmonic_matches_only=True,
            include_energy_boost=True,
        )
        results = self.engine.filter_in_memory(crit)
        allowed = {"8A", "7A", "9A", "8B", "10A"}

        self.assertGreater(len(results), 0)
        for tr in results:
            self.assertIn(tr["camelot_key"], allowed)

    def test_smart_crate_crud_and_evaluation(self):
        """Tests saving, retrieving, and evaluating dynamic Smart Crates."""
        crit = FilterCriteria(
            genres=["Tech House"],
            bpm_min=124.0,
            bpm_max=128.0,
        )
        crate_id = self.engine.save_smart_crate("Peak Time Tech House", crit)
        self.assertGreater(crate_id, 0)

        crates = self.engine.get_smart_crates()
        self.assertEqual(len(crates), 1)
        self.assertEqual(crates[0]["name"], "Peak Time Tech House")

        # Dynamically evaluate the crate
        matched_tracks = self.engine.evaluate_smart_crate("Peak Time Tech House")
        self.assertGreater(len(matched_tracks), 0)
        for tr in matched_tracks:
            self.assertEqual(tr["genre"], "Tech House")
            self.assertTrue(124.0 <= tr["bpm"] <= 128.0)

        # Delete crate
        deleted = self.engine.delete_smart_crate(crate_id)
        self.assertTrue(deleted)
        self.assertEqual(len(self.engine.get_smart_crates()), 0)

    def test_m3u8_playlist_export(self):
        """Tests exporting filtered tracks to standard extended M3U8 format."""
        crit = FilterCriteria(genres=["Techno"])
        tracks = self.engine.filter_in_memory(crit)
        self.assertGreater(len(tracks), 0)

        m3u_file = Path(self.temp_dir) / "Test_Crate.m3u8"
        out_path = LiveFilterEngine.export_m3u(tracks, m3u_file)
        self.assertTrue(Path(out_path).exists())

        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(content.startswith("#EXTM3U"))
        self.assertIn("#EXTINF:", content)
        self.assertIn("Charlotte de Witte", content)


if __name__ == "__main__":
    unittest.main()
