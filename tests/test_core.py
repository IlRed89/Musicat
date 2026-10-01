"""
Unit tests for Musicat Core Database and Path Resolver.
"""

import os
import tempfile
import unittest
from pathlib import Path
from src.core.db import Database
from src.core.path_resolver import PathResolver


class TestCoreEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_musicat.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        import gc
        self.db.close()
        del self.db
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_database_insert_and_query(self):
        track_data = {
            "filepath": "C:/DJ_Tracks/House/Track01.mp3",
            "filename": "Track01.mp3",
            "directory": "C:/DJ_Tracks/House",
            "title": "Deep Inside",
            "artist": "Hardrive",
            "bpm": 124.0,
            "camelot_key": "8A",
            "musical_key": "Am",
            "genre": "House",
            "year": 1993,
            "duration": 390.0,
        }

        self.db.insert_or_update_track(track_data)
        record = self.db.get_track(track_data["filepath"])
        self.assertIsNotNone(record)
        self.assertEqual(record["title"], "Deep Inside")
        self.assertEqual(record["artist"], "Hardrive")
        self.assertEqual(record["bpm"], 124.0)

    def test_database_bulk_upsert_and_filters(self):
        tracks = [
            {
                "filepath": f"C:/Tracks/track_{i}.mp3",
                "filename": f"track_{i}.mp3",
                "directory": "C:/Tracks",
                "title": f"Song {i}",
                "artist": "DJ Test",
                "bpm": 120.0 + (i % 10),
                "genre": "Techno" if i % 2 == 0 else "House",
                "camelot_key": f"{((i % 12) + 1)}A",
            }
            for i in range(50)
        ]

        inserted = self.db.bulk_insert_or_update(tracks)
        self.assertEqual(inserted, 50)
        self.assertEqual(self.db.count_tracks(), 50)

        # Multi-attribute filter test
        res = self.db.search_tracks(genre="Techno", bpm_min=124.0, bpm_max=128.0)
        self.assertTrue(len(res) > 0)
        for r in res:
            self.assertEqual(r["genre"], "Techno")
            self.assertTrue(124.0 <= r["bpm"] <= 128.0)

    def test_path_resolver_tokens(self):
        fake_path = "D:/DJ_Music/Tech/track.mp3"
        port_path, vol_id = PathResolver.to_portable_path(fake_path)
        self.assertTrue(isinstance(port_path, str))


if __name__ == "__main__":
    unittest.main()
