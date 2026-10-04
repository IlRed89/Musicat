"""
Tests for genre click crash prevention, thread safety, and localization audit.
"""

import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.i18n import _t, I18n
from src.core.spotify_trends import TrendingTrack
from src.gui.views.home_view import HomeTrendsView, TrendingTrackCard
from src.gui.main_view import MainWindow
from src.gui.views.organizer_view import OrganizerView
from src.gui.sorter_dialog import SorterDialog


class TestGenreCrashPreventionAndI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_db_path = Path("test_temp_crash_prevention.db")
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()
        self.db = Database(str(self.temp_db_path))

    def tearDown(self):
        self.db.close()
        if self.temp_db_path.exists():
            try:
                self.temp_db_path.unlink()
            except Exception:
                pass

    def test_on_genre_clicked_invalid_and_edge_inputs(self):
        """Ensures on_genre_clicked does not crash on None, booleans, empty strings or unknown categories."""
        home_view = HomeTrendsView(self.db, auto_load=False)
        try:
            # None input
            home_view.on_genre_clicked(None)
            # Boolean-like strings or booleans
            home_view.on_genre_clicked(False)
            home_view.on_genre_clicked("False")
            home_view.on_genre_clicked("")
            home_view.on_genre_clicked("   ")
            # Unknown category
            home_view.on_genre_clicked("non_existent_category_xyz")
        finally:
            home_view.cleanup()

    def test_on_genre_clicked_with_zero_tracks_in_db(self):
        """Ensures selecting a valid genre when DB has 0 tracks does not crash."""
        home_view = HomeTrendsView(self.db, auto_load=False)
        try:
            self.assertEqual(len(self.db.search_tracks(limit=10)), 0)
            home_view.on_genre_clicked("house_deep")
            home_view.on_genre_clicked("techno_melodic")
            self.app.processEvents()
        finally:
            home_view.cleanup()

    def test_rapid_reentrant_genre_clicks(self):
        """Simulates rapid double/triple clicks on category buttons."""
        home_view = HomeTrendsView(self.db, auto_load=False)
        try:
            for _ in range(5):
                home_view.on_genre_clicked("dance_electro")
                home_view.on_genre_clicked("tech_house")
            self.app.processEvents()
        finally:
            home_view.cleanup()

    def test_card_cleanup_stops_threads(self):
        """Verifies TrendingTrackCard.cleanup safely terminates background thumbnail loaders."""
        track = TrendingTrack(
            id="test1",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            cover_url="https://example.com/cover.jpg",
            category="dance_electro",
        )
        card = TrendingTrackCard(track)
        # Verify card theme update
        card.update_theme("light")
        card.update_theme("dark")
        # Cleanup should cleanly terminate without C++ crash
        card.cleanup()

    def test_home_view_theme_update(self):
        """Verifies HomeTrendsView switches seamlessly between light and dark themes."""
        home_view = HomeTrendsView(self.db, auto_load=False)
        try:
            home_view.update_theme("light")
            self.assertEqual(home_view.current_theme, "light")
            home_view.update_theme("dark")
            self.assertEqual(home_view.current_theme, "dark")
        finally:
            home_view.cleanup()

    def test_main_view_home_genre_filter_empty_library(self):
        """Tests that _on_home_genre_filter_requested handles empty library safely without crashing."""
        main_win = MainWindow(db=self.db)
        try:
            main_win.all_tracks = []
            # Should safely log and handle empty library without crash
            main_win._on_home_genre_filter_requested("Techno")
            self.app.processEvents()
        finally:
            main_win.cleanup()
            main_win.close()

    def test_organizer_view_instantiation_and_i18n(self):
        """Ensures OrganizerView (SorterDialog) instantiates with Italian localization keys."""
        sorter = OrganizerView(tracks=[], parent=None)
        try:
            # Check Italian title or localization
            self.assertIn("Organizzatore", sorter.windowTitle())
        finally:
            sorter.close()

    def test_i18n_locales_completeness(self):
        """Verifies critical keys exist in it.json and en.json."""
        it_dict = I18n.get_instance()._load_locale("it")
        en_dict = I18n.get_instance()._load_locale("en")

        required_keys = [
            "sorter_title",
            "sorter_heading",
            "sorter_btn_dry_run",
            "sorter_btn_execute",
            "home_title",
            "home_empty_genre_title",
            "home_empty_genre_msg",
            "home_card_in_library",
            "home_card_missing",
            "genre_filter_applied",
        ]
        for key in required_keys:
            self.assertIn(key, it_dict, f"Key '{key}' missing from it.json")
            self.assertIn(key, en_dict, f"Key '{key}' missing from en.json")


if __name__ == "__main__":
    unittest.main()
