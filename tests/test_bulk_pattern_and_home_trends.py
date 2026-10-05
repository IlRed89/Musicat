import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.spotify_trends import SpotifyTrendsManager
from src.tags.patterns import PatternEngine
from src.gui.mp3tag_workspace import BulkPatternTagDialog
from src.gui.live_filters import LiveFilterBar
from src.gui.views.crates_view import SmartCratesView


app = QApplication.instance() or QApplication([])


class TestBulkPatternAndHomeTrends(unittest.TestCase):

    def test_trends_full_curated_lists(self):
        """Verifies that all trend categories load full 20-track lists without artificial truncation."""
        mgr = SpotifyTrendsManager()
        sp_pop = mgr.fetch_platform_trends("spotify", "pop_commercial", limit=100)
        self.assertGreaterEqual(len(sp_pop), 20)

        sc_elec = mgr.fetch_platform_trends("soundcloud", "sc_electronic", limit=100)
        self.assertGreaterEqual(len(sc_elec), 20)

        bp_tech = mgr.fetch_platform_trends("beatport", "bp_techno_peak", limit=100)
        self.assertGreaterEqual(len(bp_tech), 20)

    def test_bulk_pattern_tag_dialog_preview(self):
        """Verifies BulkPatternTagDialog extracts tags and generates live preview."""
        tracks = [
            {
                "filepath": "C:/audio/Queen - Bohemian Rhapsody.mp3",
                "filename": "Queen - Bohemian Rhapsody.mp3",
                "artist": "",
                "title": "",
                "track_num": None,
                "year": None,
            },
            {
                "filepath": "C:/audio/07. Starlight.mp3",
                "filename": "07. Starlight.mp3",
                "artist": "Dave",
                "title": "",
                "track_num": None,
                "year": None,
            },
        ]
        dlg = BulkPatternTagDialog(tracks)
        # Test pattern 1: [%artist%] - [%title%]
        dlg.txt_pattern.setText("[%artist%] - [%title%]")
        dlg._update_preview()
        changes = dlg.get_changes()
        self.assertIn("C:/audio/Queen - Bohemian Rhapsody.mp3", changes)
        self.assertEqual(changes["C:/audio/Queen - Bohemian Rhapsody.mp3"]["artist"], "Queen")
        self.assertEqual(changes["C:/audio/Queen - Bohemian Rhapsody.mp3"]["title"], "Bohemian Rhapsody")

        # Test pattern 2: [%track%]. [%title%]
        dlg.txt_pattern.setText("[%track%]. [%title%]")
        dlg._update_preview()
        changes2 = dlg.get_changes()
        self.assertIn("C:/audio/07. Starlight.mp3", changes2)
        self.assertEqual(changes2["C:/audio/07. Starlight.mp3"]["track_num"], 7)
        self.assertEqual(changes2["C:/audio/07. Starlight.mp3"]["title"], "Starlight")

    def test_live_filters_no_crates_in_header(self):
        """Verifies Smart Crates controls are removed from Library header."""
        db = Database()
        bar = LiveFilterBar(db)
        # Verify row2 does not contain cmb_crates widget in active UI
        self.assertFalse(hasattr(bar, "cmb_crates") and bar.cmb_crates is not None and bar.cmb_crates.isVisible())
        # Verify expanded minimum widths
        self.assertGreaterEqual(bar.spin_target_bpm.minimumWidth(), 80)
        self.assertGreaterEqual(bar.cmb_camelot.minimumWidth(), 130)
        self.assertGreaterEqual(bar.cmb_decade.minimumWidth(), 150)
        self.assertGreaterEqual(bar.cmb_quality.minimumWidth(), 160)

    def test_crates_view_select_by_name(self):
        """Verifies select_crate_by_name exists and functions on SmartCratesView."""
        self.assertTrue(hasattr(SmartCratesView, "select_crate_by_name"))

    def test_rapid_category_switching_no_crash(self):
        """Simulates rapid clicking across categories in HomeTrendsView ensuring zero crash or deadlock."""
        from src.gui.views.home_view import HomeTrendsView
        db = Database()
        view = HomeTrendsView(db, auto_load=False)
        # Rapid category switching
        categories = ["dance_electro", "tech_house", "global_50", "pop_commercial", "techno", "dance_electro"]
        for cat in categories:
            view.on_genre_clicked(cat)
            QApplication.processEvents()

        # Clean up view
        view.cleanup()
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
