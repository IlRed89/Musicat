"""
Unit tests for Mp3tag Workbench: Converters, Action Groups, and Batch Tag Writing.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.batch_io import BatchTagWriter, TagWriteTask
from src.tags.patterns import PatternEngine
from src.gui.mp3tag_workspace import Mp3tagWorkspaceWindow


app = QApplication.instance() or QApplication(sys.argv)


class TestMp3tagWorkspaceLogic(unittest.TestCase):
    """Tests Mp3tag workbench conversion algorithms and action groups."""

    def setUp(self):
        from unittest.mock import patch
        self.patcher_info = patch("PySide6.QtWidgets.QMessageBox.information")
        self.patcher_warn = patch("PySide6.QtWidgets.QMessageBox.warning")
        self.patcher_crit = patch("PySide6.QtWidgets.QMessageBox.critical")
        self.mock_info = self.patcher_info.start()
        self.mock_warn = self.patcher_warn.start()
        self.mock_crit = self.patcher_crit.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(str(self.db_path))

        self.sample_tracks = [
            {
                "id": 1,
                "filepath": "C:/Music/Daft Punk - One More Time [Club Mix].mp3",
                "filename": "Daft Punk - One More Time [Club Mix].mp3",
                "directory": "C:/Music",
                "title": "One More Time [FREE DOWNLOAD]",
                "artist": "Daft Punk",
                "album": "Discovery",
                "genre": "French House",
                "track_num": "1",
                "year": 2001,
            },
            {
                "id": 2,
                "filepath": "C:/Music/Stardust - Music Sounds Better With You.mp3",
                "filename": "Stardust - Music Sounds Better With You.mp3",
                "directory": "C:/Music",
                "title": "music sounds better with you",
                "artist": "stardust",
                "album": "roule",
                "genre": "house",
                "track_num": "5",
                "year": 1998,
            },
        ]
        for t in self.sample_tracks:
            self.db.insert_track(t)

        self.window = Mp3tagWorkspaceWindow(self.db, self.sample_tracks)

    def tearDown(self):
        self.window.close()
        self.temp_dir.cleanup()
        self.patcher_info.stop()
        self.patcher_warn.stop()
        self.patcher_crit.stop()

    def test_workbench_grid_and_cell_edit(self):
        """Grid reflects tracks and inline edit updates in-memory model."""
        self.assertEqual(self.window.grid.rowCount(), 2)

        # In-place edit of title for row 0
        # Column 0: filename, 1: title, 2: artist
        item = self.window.grid.item(0, 1)
        self.assertIsNotNone(item)
        item.setText("One More Time (2026 Remaster)")

        # Verify cell change propagated to track dictionary
        self.assertEqual(self.window.tracks[0]["title"], "One More Time (2026 Remaster)")
        self.assertIn(self.window.tracks[0]["filepath"], self.window.dirty_files)

    def test_action_case_conversion(self):
        """Action Group: Case Conversion to Title Case."""
        track2 = self.window.tracks[1]
        self.assertEqual(track2["title"], "music sounds better with you")
        self.assertEqual(track2["artist"], "stardust")

        # Select all and apply Title Case
        self.window.grid.selectAll()
        self.window._apply_case_action("title")

        updated_track2 = self.window.tracks[1]
        self.assertEqual(updated_track2["title"], "Music Sounds Better With You")
        self.assertEqual(updated_track2["artist"], "Stardust")
        self.assertEqual(updated_track2["genre"], "House")

    def test_action_strip_promo_tags(self):
        """Action Group: Strips promo tags like [FREE DOWNLOAD] from title."""
        self.window.grid.selectAll()
        self.window._apply_strip_promo_tags()

        t0 = self.window.tracks[0]
        self.assertNotIn("FREE DOWNLOAD", t0.get("title", ""))
        self.assertEqual(t0.get("title"), "One More Time")

    def test_action_pad_track_numbers(self):
        """Action Group: Pads single digit tracks to 2 digits (1 -> 01, 5 -> 05)."""
        self.window.grid.selectAll()
        self.window._apply_pad_track_numbers()

        t0 = self.window.tracks[0]
        t1 = self.window.tracks[1]
        self.assertEqual(t0.get("track_num"), "01")
        self.assertEqual(t1.get("track_num"), "05")

    def test_converter_filename_to_tag(self):
        """Converter 1: Filename -> Tag pattern parser."""
        fn = "Deadmau5 - Strobe.mp3"
        pattern = "%artist% - %title%"
        res = PatternEngine.parse_filename_to_tags(fn, pattern)
        self.assertEqual(res.get("artist"), "Deadmau5")
        self.assertEqual(res.get("title"), "Strobe")

    def test_converter_tag_to_filename(self):
        """Converter 2: Tag -> Filename pattern generation."""
        track = {
            "artist": "Eric Prydz",
            "title": "Opus",
            "bpm": 126.0,
            "camelot_key": "4A",
            "filepath": "C:/Music/old.mp3",
        }
        pattern = "%artist% - %title% [%bpm% BPM]"
        new_fn = PatternEngine.format_tags_to_filename(track, pattern)
        self.assertEqual(new_fn, "Eric Prydz - Opus [126 BPM]")


class TestBatchTagWriter(unittest.TestCase):
    """Tests non-blocking batch tag writing."""

    def test_batch_writer_task_execution(self):
        """BatchTagWriter executes write tasks without failing."""
        writer = BatchTagWriter(max_workers=2)
        tasks = [
            TagWriteTask(filepath="fake/path1.mp3", tags={"title": "Test 1"}),
            TagWriteTask(filepath="fake/path2.mp3", tags={"title": "Test 2"}),
        ]
        results = writer.write_sync(tasks)
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].success)
        self.assertIn("File not found", results[0].error_message)


if __name__ == "__main__":
    unittest.main()
