"""
Comprehensive unit tests for the 3 new feature sets:
1. Dynamic Hardware Progress Bars (CPU & RAM with dynamic color thresholds)
2. Advanced Mp3tag Toolset ($num(%track%,2), TrackNumberingWizardDialog, live preview dialogs, case actions)
3. Dynamic Genre ComboBox (editable QComboBox, alphabetical sorting, autocompletion, Vario fallback)
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.hardware_monitor import HardwareMonitor
from src.core.filter_engine import FilterCriteria, LiveFilterEngine, LiveFilterQueryBuilder
from src.tags.patterns import PatternEngine
from src.gui.table_model import TrackTableModel
from src.gui.live_filters import GenreMultiSelectWidget
from src.gui.mp3tag_workspace import (
    Mp3tagWorkspaceWindow,
    TrackNumberingWizardDialog,
    FilenameToTagDialog,
    TagToFilenameDialog,
)
from src.gui.main_view import HardwareProgressBar, MainWindow


app = QApplication.instance() or QApplication(sys.argv)


class TestDynamicHardwareMonitor(unittest.TestCase):
    """Verifies HardwareProgressBar dynamic coloring and HardwareMonitor telemetry."""

    def test_hardware_monitor_methods(self):
        cpu = HardwareMonitor.get_cpu_percent()
        self.assertIsInstance(cpu, float)
        self.assertGreaterEqual(cpu, 0.0)

        ram_used = HardwareMonitor.get_system_memory_used_gb()
        self.assertIsInstance(ram_used, float)
        self.assertGreater(ram_used, 0.0)

        ram_total = HardwareMonitor.get_total_system_memory_gb()
        self.assertIsInstance(ram_total, float)
        self.assertGreater(ram_total, 0.0)

        ram_pct = HardwareMonitor.get_system_memory_percent()
        self.assertIsInstance(ram_pct, float)
        self.assertGreaterEqual(ram_pct, 0.0)
        self.assertLessEqual(ram_pct, 100.0)

    def test_hardware_progress_bar_thresholds(self):
        bar = HardwareProgressBar("CPU")

        # 0% - 60%: Green (#28A745)
        bar.update_load(35.0, "CPU 35%")
        self.assertEqual(bar.value(), 35)
        self.assertIn("#28A745", bar.styleSheet())

        # 61% - 84%: Orange (#FD7E14)
        bar.update_load(72.0, "CPU 72%")
        self.assertEqual(bar.value(), 72)
        self.assertIn("#FD7E14", bar.styleSheet())

        # 85% - 100%: Red (#DC3545)
        bar.update_load(95.0, "CPU 95%")
        self.assertEqual(bar.value(), 95)
        self.assertIn("#DC3545", bar.styleSheet())

    def test_main_window_has_hardware_bars(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            db = Database(str(db_path))
            try:
                win = MainWindow(db=db)
                self.assertTrue(hasattr(win, "bar_cpu"))
                self.assertTrue(hasattr(win, "bar_ram"))
                self.assertIsInstance(win.bar_cpu, HardwareProgressBar)
                self.assertIsInstance(win.bar_ram, HardwareProgressBar)
                win.close()
                win.deleteLater()
            finally:
                db.close()


class TestAdvancedMp3tagToolset(unittest.TestCase):
    """Verifies track numbering wizard, $num token support, and conversion dialogs."""

    def setUp(self):
        self.sample_tracks = [
            {
                "id": 1,
                "filepath": "C:/Music/AlbumA/01 - ArtistA - TrackA.mp3",
                "filename": "01 - ArtistA - TrackA.mp3",
                "directory": "C:/Music/AlbumA",
                "title": "TrackA",
                "artist": "ArtistA",
                "album": "Album One",
                "genre": "Techno",
                "track_num": 1,
                "year": 2021,
                "bpm": 130.0,
            },
            {
                "id": 2,
                "filepath": "C:/Music/AlbumA/02 - ArtistA - TrackB.mp3",
                "filename": "02 - ArtistA - TrackB.mp3",
                "directory": "C:/Music/AlbumA",
                "title": "TrackB",
                "artist": "ArtistA",
                "album": "Album One",
                "genre": "Techno",
                "track_num": 2,
                "year": 2021,
                "bpm": 132.0,
            },
            {
                "id": 3,
                "filepath": "C:/Music/AlbumB/01 - ArtistB - TrackC.mp3",
                "filename": "01 - ArtistB - TrackC.mp3",
                "directory": "C:/Music/AlbumB",
                "title": "TrackC",
                "artist": "ArtistB",
                "album": "Album Two",
                "genre": "House",
                "track_num": 1,
                "year": 2022,
                "bpm": 124.0,
            },
        ]

    def test_pattern_engine_num_track_formatting_and_parsing(self):
        track = {"artist": "Test Artist", "title": "Test Title", "track_num": 7}
        pattern = "$num(%track%,2) - %title%"
        formatted = PatternEngine.format_tags_to_filename(track, pattern)
        self.assertEqual(formatted, "07 - Test Title")

        parsed = PatternEngine.parse_filename_to_tags("07 - Test Title.mp3", pattern)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("track_num"), 7)
        self.assertEqual(parsed.get("title"), "Test Title")

    def test_track_numbering_wizard_options(self):
        wizard = TrackNumberingWizardDialog(self.sample_tracks)

        # Default: 01, 02, 03
        nums = wizard.get_track_numbers()
        self.assertEqual(nums, ["01", "02", "03"])

        # With denominator (total = 3): 01/03, 02/03, 03/03
        wizard.chk_total_denominator.setChecked(True)
        nums_denom = wizard.get_track_numbers()
        self.assertEqual(nums_denom, ["01/03", "02/03", "03/03"])

        # Reset per folder: AlbumA has 2, AlbumB has 1 -> 01/02, 02/02, 01/01
        wizard.chk_reset_folder.setChecked(True)
        nums_folder = wizard.get_track_numbers()
        self.assertEqual(nums_folder, ["01/02", "02/02", "01/01"])

        wizard.close()

    def test_filename_to_tag_dialog_preview(self):
        dlg = FilenameToTagDialog(self.sample_tracks)
        dlg.txt_pattern.setText("%track% - %artist% - %title%")
        self.assertEqual(dlg.tbl_preview.rowCount(), 3)
        # Check column 1 (Artist) and 2 (Title)
        self.assertEqual(dlg.tbl_preview.item(0, 1).text(), "ArtistA")
        self.assertEqual(dlg.tbl_preview.item(0, 2).text(), "TrackA")
        dlg.close()

    def test_tag_to_filename_dialog_preview(self):
        dlg = TagToFilenameDialog(self.sample_tracks)
        dlg.txt_pattern.setText("$num(%track%,2) - %title%")
        self.assertEqual(dlg.tbl_preview.rowCount(), 3)
        self.assertEqual(dlg.tbl_preview.item(0, 1).text(), "01 - TrackA.mp3")
        self.assertEqual(dlg.tbl_preview.item(1, 1).text(), "02 - TrackB.mp3")
        dlg.close()

    def test_mp3tag_workspace_renumbering_application(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            db = Database(str(db_path))
            ws = Mp3tagWorkspaceWindow(db, self.sample_tracks)

            # Apply wizard programmatically
            wizard = TrackNumberingWizardDialog(self.sample_tracks)
            wizard.chk_leading_zero.setChecked(True)
            wizard.chk_total_denominator.setChecked(False)
            new_nums = wizard.get_track_numbers()

            ws.grid.selectAll()
            for r, n in enumerate(new_nums):
                ws.tracks[r]["track_num"] = n
                ws.grid.item(r, 4).setText(str(n))

            self.assertEqual(ws.tracks[0]["track_num"], "01")
            self.assertEqual(ws.tracks[1]["track_num"], "02")
            self.assertEqual(ws.tracks[2]["track_num"], "03")
            ws.close()


class TestDynamicGenreComboBoxAndVarioFallback(unittest.TestCase):
    """Verifies editable QComboBox, autocompletion, and Vario fallback for untagged tracks."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(str(self.db_path))

        # Insert sample tracks: one Techno, one House, one with empty genre
        self.db.insert_track({
            "filepath": "C:/Music/track1.mp3",
            "filename": "track1.mp3",
            "artist": "Artist1",
            "title": "Title1",
            "genre": "Techno",
        })
        self.db.insert_track({
            "filepath": "C:/Music/track2.mp3",
            "filename": "track2.mp3",
            "artist": "Artist2",
            "title": "Title2",
            "genre": "House",
        })
        self.db.insert_track({
            "filepath": "C:/Music/track3.mp3",
            "filename": "track3.mp3",
            "artist": "Artist3",
            "title": "Title3",
            "genre": "",  # Untagged
        })

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_genre_combobox_is_editable_and_has_all_genres(self):
        widget = GenreMultiSelectWidget(self.db)
        self.assertTrue(widget.isEditable())
        self.assertEqual(widget.itemText(0), "🏷️ Tutti i Generi")

        # Should contain "Vario"
        items = [widget.itemText(i) for i in range(widget.count())]
        self.assertIn("Vario", items)
        self.assertIn("Techno", items)
        self.assertIn("House", items)

        # Initial selection is all genres
        self.assertEqual(widget.selected_genres, set())

        # Select a genre
        widget.set_genres(["Techno"])
        self.assertEqual(widget.selected_genres, {"Techno"})

        # Clear selection
        widget.clear_selection()
        self.assertEqual(widget.selected_genres, set())
        self.assertEqual(widget.currentIndex(), 0)

        widget.close()

    def test_vario_table_model_fallback(self):
        tracks = [
            {"id": 1, "artist": "A", "title": "T1", "genre": "Tech House"},
            {"id": 2, "artist": "B", "title": "T2", "genre": ""},
            {"id": 3, "artist": "C", "title": "T3", "genre": None},
        ]
        model = TrackTableModel(tracks)

        # Col 8 is Genre
        genre_col_idx = 8
        self.assertEqual(model.data(model.index(0, genre_col_idx), Qt.ItemDataRole.DisplayRole), "Tech House")
        self.assertEqual(model.data(model.index(1, genre_col_idx), Qt.ItemDataRole.DisplayRole), "Vario")
        self.assertEqual(model.data(model.index(2, genre_col_idx), Qt.ItemDataRole.DisplayRole), "Vario")

    def test_vario_filter_engine_matching(self):
        engine = LiveFilterEngine(self.db)
        engine.warm_cache()

        # Filter by "Vario": should match track3 (empty genre)
        criteria = FilterCriteria(genres=["Vario"])
        results = engine.filter_in_memory(criteria)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "track3.mp3")

        # SQL query builder should include NULL/empty genre condition
        sql, params = LiveFilterQueryBuilder.build_sql(criteria)
        self.assertIn("genre IS NULL OR TRIM(genre) = ''", sql)
        self.assertIn("%vario%", params)


if __name__ == "__main__":
    unittest.main()
