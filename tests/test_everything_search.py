"""
Unit tests for Voidtools Everything Search Engine and FTS Fallback.
"""

import tempfile
import unittest
from pathlib import Path
from src.core.db import Database
from src.core.everything_search import EverythingSearchEngine


class TestEverythingSearch(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_fts.db"
        self.db = Database(self.db_path)

        # Seed database with sample tracks for FTS fallback
        tracks = [
            {
                "filepath": "C:/Music/deadmau5_strobe.mp3",
                "filename": "deadmau5_strobe.mp3",
                "directory": "C:/Music",
                "title": "Strobe",
                "artist": "Deadmau5",
                "album": "For Lack of a Better Name",
                "genre": "Progressive House",
                "bpm": 128.0,
                "camelot_key": "8B",
            },
            {
                "filepath": "C:/Music/carl_cox_phuture.mp3",
                "filename": "carl_cox_phuture.mp3",
                "directory": "C:/Music",
                "title": "Phuture 2000",
                "artist": "Carl Cox",
                "album": "Phuture",
                "genre": "Techno",
                "bpm": 134.0,
                "camelot_key": "11A",
            },
        ]
        self.db.bulk_insert_or_update(tracks)

    def tearDown(self):
        self.db.close()
        del self.db
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_fts_fallback_query(self):
        # Query matching 'Deadmau5'
        results, engine = EverythingSearchEngine.unified_search("Deadmau5", self.db)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["title"], "Strobe")
        self.assertIn("FTS", engine)

    def test_fts_multi_token_search(self):
        # Query matching 'Carl Techno'
        results, engine = EverythingSearchEngine.unified_search("Carl Techno", self.db)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["artist"], "Carl Cox")

    def test_fts_empty_query(self):
        results, engine = EverythingSearchEngine.unified_search("", self.db)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
