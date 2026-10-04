"""
Unit tests for MusicFileManager in Musicat.
Verifies physical file cut, copy, paste, collision strategies and SQLite path synchronization.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.core.db import Database
from src.core.file_manager import MusicFileManager, ClipboardMode, CollisionStrategy


class TestMusicFileManager(unittest.TestCase):
    """Tests for physical file operations with database synchronization."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.source_dir = (self.base_path / "source").resolve()
        self.dest_dir = (self.base_path / "dest").resolve()
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.base_path / "test.db"
        self.db = Database(str(self.db_path))
        self.file_manager = MusicFileManager(self.db)

        # Create dummy track files
        self.file1 = (self.source_dir / "track1.mp3").resolve()
        self.file2 = (self.source_dir / "track2.mp3").resolve()
        self.file1.write_text("audio content 1")
        self.file2.write_text("audio content 2")

        # Insert dummy tracks into DB
        self.db.insert_track({
            "filepath": str(self.file1),
            "directory": str(self.source_dir),
            "filename": "track1.mp3",
            "title": "Track 1",
            "artist": "Artist 1",
            "bpm": 128.0,
            "camelot_key": "8A",
        })
        self.db.insert_track({
            "filepath": str(self.file2),
            "directory": str(self.source_dir),
            "filename": "track2.mp3",
            "title": "Track 2",
            "artist": "Artist 2",
            "bpm": 124.0,
            "camelot_key": "9A",
        })

    def tearDown(self):
        if hasattr(self, "file_manager") and self.file_manager:
            try:
                self.file_manager.clear_clipboard()
            except Exception:
                pass
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_cut_and_paste_moves_files_and_updates_db(self):
        """Cutting files moves them to target folder and updates filepath in DB."""
        self.file_manager.cut_files([str(self.file1)])
        self.assertEqual(self.file_manager.clipboard_mode, ClipboardMode.CUT)
        self.assertEqual(len(self.file_manager.clipboard_files), 1)

        result = self.file_manager.paste_files(str(self.dest_dir))
        self.assertEqual(len(result.processed_files), 1)
        self.assertEqual(len(result.errors), 0)

        expected_dest = self.dest_dir / "track1.mp3"
        self.assertFalse(self.file1.exists())
        self.assertTrue(expected_dest.exists())

        # DB should have updated path for Track 1
        old_track = self.db.get_track_by_path(str(self.file1))
        self.assertIsNone(old_track)

        new_track = self.db.get_track_by_path(str(expected_dest))
        self.assertIsNotNone(new_track)
        self.assertEqual(new_track["bpm"], 128.0)
        self.assertEqual(new_track["camelot_key"], "8A")

        # Clipboard should be cleared after cut & paste
        self.assertEqual(len(self.file_manager.clipboard_files), 0)

    def test_copy_and_paste_duplicates_files_and_db_entries(self):
        """Copying files duplicates them on disk and inserts new DB row."""
        self.file_manager.copy_files([str(self.file2)])
        self.assertEqual(self.file_manager.clipboard_mode, ClipboardMode.COPY)

        result = self.file_manager.paste_files(str(self.dest_dir))
        self.assertEqual(len(result.processed_files), 1)

        expected_dest = self.dest_dir / "track2.mp3"
        self.assertTrue(self.file2.exists())  # Source still exists
        self.assertTrue(expected_dest.exists())  # Dest created

        # Both records should exist in DB
        orig_track = self.db.get_track_by_path(str(self.file2))
        copy_track = self.db.get_track_by_path(str(expected_dest))
        self.assertIsNotNone(orig_track)
        self.assertIsNotNone(copy_track)
        self.assertEqual(copy_track["title"], "Track 2")
        self.assertEqual(copy_track["bpm"], 124.0)

        # Clipboard remains intact for further pastes in copy mode
        self.assertEqual(len(self.file_manager.clipboard_files), 1)

    def test_collision_rename_strategy(self):
        """CollisionStrategy.RENAME should generate unique filenames like 'track1 (1).mp3'."""
        existing_dest = self.dest_dir / "track1.mp3"
        existing_dest.write_text("already exists")

        self.file_manager.copy_files([str(self.file1)])
        result = self.file_manager.paste_files(str(self.dest_dir), collision_strategy=CollisionStrategy.RENAME)

        self.assertEqual(len(result.processed_files), 1)
        renamed_file = self.dest_dir / "track1 (1).mp3"
        self.assertTrue(renamed_file.exists())
        self.assertTrue(existing_dest.exists())

    def test_collision_skip_strategy(self):
        """CollisionStrategy.SKIP should leave existing destination file unchanged."""
        existing_dest = self.dest_dir / "track1.mp3"
        existing_dest.write_text("already exists")

        self.file_manager.copy_files([str(self.file1)])
        result = self.file_manager.paste_files(str(self.dest_dir), collision_strategy=CollisionStrategy.SKIP)

        self.assertEqual(len(result.skipped_files), 1)
        self.assertEqual(existing_dest.read_text(), "already exists")


if __name__ == "__main__":
    unittest.main()
