"""
Unit tests for Musicat Smart Recommendations, Spotify Trends Home, and Library File Navigation.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.db import Database
from src.core.filter_engine import FilterCriteria, LiveFilterEngine, LiveFilterQueryBuilder
from src.core.path_resolver import PathResolver
from src.core.spotify_trends import SpotifyTrendsManager, TrendingTrack
from src.scrapers.similarity_engine import (
    LocalAffinityCalculator,
    SimilarityEngine,
    SimilarityScraper,
    SimilarTrackRecommendation,
)


class TestLocalAffinityCalculator(unittest.TestCase):
    """Tests harmonic, BPM, and acoustic similarity affinity calculations."""

    def setUp(self):
        self.ref_track = {
            "title": "Losing It",
            "artist": "FISHER",
            "genre": "Tech House",
            "bpm": 125.0,
            "camelot_key": "8A",
            "energy_level": 5,
        }

    def test_identical_track_high_affinity(self):
        score, breakdown, notes = LocalAffinityCalculator.calculate_affinity(
            self.ref_track, self.ref_track
        )
        self.assertGreaterEqual(score, 95.0)
        self.assertEqual(breakdown["harmonic"], 35.0)
        self.assertEqual(breakdown["bpm"], 30.0)
        self.assertEqual(breakdown["genre"], 20.0)

    def test_compatible_camelot_keys(self):
        # 8B is relative major of 8A -> high score
        target_relative = {
            "title": "Piece of Your Heart",
            "artist": "Meduza",
            "genre": "Tech House",
            "bpm": 124.0,
            "camelot_key": "8B",
            "energy_level": 4,
        }
        score, breakdown, notes = LocalAffinityCalculator.calculate_affinity(
            self.ref_track, target_relative
        )
        self.assertGreaterEqual(breakdown["harmonic"], 30.0)
        self.assertGreater(score, 80.0)

    def test_clashing_camelot_key(self):
        # 2A is very distant from 8A on Camelot Wheel
        target_clash = {
            "title": "Random Song",
            "artist": "Unknown",
            "genre": "Classical",
            "bpm": 80.0,
            "camelot_key": "2A",
            "energy_level": 1,
        }
        score, breakdown, notes = LocalAffinityCalculator.calculate_affinity(
            self.ref_track, target_clash
        )
        self.assertLess(score, 40.0)
        self.assertLess(breakdown["harmonic"], 10.0)

    def test_bpm_half_double_tempo_relationship(self):
        # 125 BPM vs 62.5 BPM (half time)
        half_tempo_track = {
            "title": "Half Beat",
            "artist": "Producer",
            "genre": "Tech House",
            "bpm": 62.5,
            "camelot_key": "8A",
            "energy_level": 4,
        }
        score, breakdown, notes = LocalAffinityCalculator.calculate_affinity(
            self.ref_track, half_tempo_track
        )
        # Should detect half-time relationship and award good BPM score
        self.assertGreaterEqual(breakdown["bpm"], 20.0)
        self.assertTrue(any("Half/Double" in n for n in notes))


class TestSimilarityEngine(unittest.TestCase):
    """Tests recommendation and local library matching orchestration."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(self.temp_db_path)

        # Seed test tracks
        self.db.insert_or_update_track({
            "filepath": "/music/fisher_losing_it.mp3",
            "title": "Losing It",
            "artist": "FISHER",
            "genre": "Tech House",
            "bpm": 125.0,
            "camelot_key": "8A",
            "energy_level": 5,
        })
        self.db.insert_or_update_track({
            "filepath": "/music/chris_lake_turn_off_lights.mp3",
            "title": "Turn Off The Lights",
            "artist": "Chris Lake",
            "genre": "Tech House",
            "bpm": 125.0,
            "camelot_key": "8A",
            "energy_level": 5,
        })
        self.db.insert_or_update_track({
            "filepath": "/music/charlotte_age_of_love.mp3",
            "title": "The Age Of Love",
            "artist": "Charlotte de Witte",
            "genre": "Techno",
            "bpm": 132.0,
            "camelot_key": "9A",
            "energy_level": 5,
        })

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.temp_db_path)
        except OSError:
            pass

    def test_find_all_similar_matches_local_library(self):
        ref = {
            "filepath": "/music/fisher_losing_it.mp3",
            "title": "Losing It",
            "artist": "FISHER",
            "genre": "Tech House",
            "bpm": 125.0,
            "camelot_key": "8A",
            "energy_level": 5,
        }
        res = SimilarityEngine.find_all_similar(
            reference_track=ref,
            db=self.db,
            min_affinity_score=50.0,
            local_limit=10,
            online_limit=5,
        )
        self.assertIsNotNone(res)
        self.assertGreater(len(res.local_similar_tracks), 0)
        top_match = res.local_similar_tracks[0]
        self.assertEqual(top_match.title, "Turn Off The Lights")
        self.assertGreaterEqual(top_match.similarity_pct, 85.0)

    def test_similarity_scraper_fallback(self):
        recs = SimilarityScraper._get_curated_fallbacks("FISHER", "Tech House")
        self.assertGreater(len(recs), 0)
        self.assertTrue(all(isinstance(r, SimilarTrackRecommendation) for r in recs))
        self.assertTrue(any("Chris Lake" in r.artist for r in recs))


class TestSpotifyTrendsManager(unittest.TestCase):
    """Tests Spotify charts fetching, category parsing, and library cross-checking."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(self.temp_db_path)

        # Insert a track that matches the fallback trends
        self.db.insert_or_update_track({
            "filepath": "/music/fred_again_lights.mp3",
            "title": "Turn On The Lights again..",
            "artist": "Fred again.. & Swedish House Mafia",
            "genre": "Electronic",
            "bpm": 132.0,
        })

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.temp_db_path)
        except OSError:
            pass

    def test_categories_available(self):
        cats = SpotifyTrendsManager.get_supported_categories()
        self.assertTrue(any("Dance / Electro" in c for c in cats))
        self.assertTrue(any("Tech House" in c for c in cats))
        self.assertTrue(any("Techno" in c for c in cats))
        self.assertTrue(any("Global Top 50" in c for c in cats))

    def test_fetch_curated_fallback_and_cross_check(self):
        mgr = SpotifyTrendsManager()
        tracks = mgr.fetch_trends("Dance / Electro", limit=10)
        self.assertGreater(len(tracks), 0)
        self.assertTrue(all(isinstance(t, TrendingTrack) for t in tracks))

        # Cross-check with DB: Fred again should be in library
        mgr.cross_check_with_library(tracks, self.db)
        found_in_lib = [t for t in tracks if t.in_library]
        self.assertGreater(len(found_in_lib), 0)
        self.assertTrue(any("Fred again" in t.artist for t in found_in_lib))


class TestPathResolverShowInFileManager(unittest.TestCase):
    """Tests cross-platform open in folder / file manager."""

    @patch("subprocess.Popen")
    def test_show_in_file_manager_existing_file(self, mock_popen):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"dummy")
            temp_path = tf.name

        try:
            res = PathResolver.show_in_file_manager(temp_path)
            self.assertTrue(res)
            mock_popen.assert_called_once()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    def test_show_in_file_manager_nonexistent_returns_false(self):
        res = PathResolver.show_in_file_manager("/path/that/does/not/exist/musicat.mp3")
        self.assertFalse(res)


class TestFilterCriteriaAndNavigation(unittest.TestCase):
    """Tests folder_path and cover_filter in FilterCriteria and LiveFilterEngine."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(self.temp_db_path)

        self.db.insert_or_update_track({
            "filepath": "/drives/usb1/house/track1.mp3",
            "title": "USB1 House",
            "artist": "Artist A",
            "genre": "House",
            "bpm": 124.0,
            "has_cover": 1,
        })
        self.db.insert_or_update_track({
            "filepath": "/drives/usb1/techno/track2.mp3",
            "title": "USB1 Techno",
            "artist": "Artist B",
            "genre": "Techno",
            "bpm": 130.0,
            "has_cover": 0,
        })
        self.db.insert_or_update_track({
            "filepath": "/drives/external_hdd/ambient.mp3",
            "title": "HDD Ambient",
            "artist": "Artist C",
            "genre": "Ambient",
            "bpm": 90.0,
            "has_cover": 1,
        })

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.temp_db_path)
        except OSError:
            pass

    def test_filter_criteria_is_empty(self):
        crit = FilterCriteria()
        self.assertTrue(crit.is_empty())

        crit_folder = FilterCriteria(folder_path="/drives/usb1")
        self.assertFalse(crit_folder.is_empty())

        crit_cover = FilterCriteria(cover_filter="with_cover")
        self.assertFalse(crit_cover.is_empty())

    def test_filter_by_folder_in_memory_and_sql(self):
        engine = LiveFilterEngine(self.db)
        all_tracks = self.db.search_tracks(limit=100)
        engine.warm_cache(all_tracks)

        # Filter by folder '/drives/usb1'
        crit = FilterCriteria(folder_path="/drives/usb1")
        res_mem = engine.query(crit, prefer_ram=True)
        self.assertEqual(len(res_mem), 2)

        res_sql = engine.query(crit, prefer_ram=False)
        self.assertEqual(len(res_sql), 2)

    def test_filter_by_cover(self):
        engine = LiveFilterEngine(self.db)
        all_tracks = self.db.search_tracks(limit=100)
        engine.warm_cache(all_tracks)

        crit_with = FilterCriteria(cover_filter="with_cover")
        res_with = engine.query(crit_with, prefer_ram=True)
        self.assertEqual(len(res_with), 2)

        crit_without = FilterCriteria(cover_filter="without_cover")
        res_without = engine.query(crit_without, prefer_ram=True)
        self.assertEqual(len(res_without), 1)
        self.assertEqual(res_without[0]["title"], "USB1 Techno")

    def test_get_distinct_directories(self):
        dirs = self.db.get_distinct_directories()
        self.assertIn(str(Path("/drives/usb1/house")), dirs)
        self.assertIn(str(Path("/drives/usb1/techno")), dirs)
        self.assertIn(str(Path("/drives/external_hdd")), dirs)


if __name__ == "__main__":
    unittest.main()
