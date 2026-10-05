"""
Unit tests for UI Streamlining, In-App Preview Playback, OAuth Login & Folder Sync Fix.
"""

import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.filter_engine import FilterCriteria, LiveFilterEngine
from src.core.oauth_manager import OAuthManager
from src.core.settings import SettingsManager
from src.gui.live_filters import LiveFilterBar
from src.gui.main_view import MainWindow
from src.gui.settings_dialog import SettingsDialog
from src.gui.views.home_view import TrendingTrack, TrendingTrackCard


class TestUIStreamliningAndFolderSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_musicat.db")
        self.db = Database(self.db_path)
        self.settings = SettingsManager.get_instance()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_view_is_library(self):
        """Requirement 3: Default view on startup must be Library (Index 0)."""
        window = MainWindow(db=self.db)
        try:
            self.assertEqual(window.view_stack.currentIndex(), 0)
            self.assertEqual(window.view_stack.currentWidget(), window.library_container)
            self.assertEqual(window.btn_nav_library.text(), "📁  Libreria")
            self.assertIn("Top Charts", window.btn_nav_trends.text())
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_live_ram_badge_and_folder_input_removed_from_header(self):
        """Requirements 2 & 5: Live RAM Index badge and Cartella text input removed from library header."""
        bar = LiveFilterBar(self.db)
        try:
            # lbl_search_engine is not visible in header
            self.assertFalse(bar.lbl_search_engine.isVisible())
            # cmb_folder is not visible in header
            self.assertFalse(bar.cmb_folder.isVisible())
        finally:
            bar.deleteLater()
            self.app.processEvents()

    def test_oauth_manager_state_persistence(self):
        """Requirement 4: OAuth manager connect, disconnect, and status check."""
        oauth = OAuthManager.get_instance()
        oauth.set_account_connected("spotify", "TestDJ", "test_tok_123")
        self.assertTrue(oauth.is_connected("spotify"))
        status = oauth.get_account_status("spotify")
        self.assertEqual(status["username"], "TestDJ")

        oauth.disconnect_account("spotify")
        self.assertFalse(oauth.is_connected("spotify"))
        status_after = oauth.get_account_status("spotify")
        self.assertFalse(status_after["connected"])

    def test_settings_dialog_has_accounts_page(self):
        """Requirement 4: Settings dialog includes Account & Servizi category with 4 cards."""
        dlg = SettingsDialog(parent=None)
        try:
            self.assertIn("spotify", dlg.account_widgets)
            self.assertIn("soundcloud", dlg.account_widgets)
            self.assertIn("youtube", dlg.account_widgets)
            self.assertIn("discogs", dlg.account_widgets)

            # Test set_active_category
            dlg.set_active_category("accounts")
            self.assertEqual(dlg.sidebar.currentRow(), 3)
            self.assertEqual(dlg.stack.currentIndex(), 3)
        finally:
            dlg.deleteLater()
            self.app.processEvents()

    def test_folder_slash_normalization_filter(self):
        """Requirement 6: Filter engine matches Windows slashes and forward slashes seamlessly."""
        # Insert track with forward slash
        track_path = "C:/Music/Commerciale/track1.mp3"
        self.db.insert_or_update_track({
            "filepath": track_path,
            "filename": "track1.mp3",
            "directory": "C:/Music/Commerciale",
            "title": "Track One",
            "artist": "Artist",
        })

        engine = LiveFilterEngine(self.db)
        engine.warm_cache(self.db.search_tracks())

        # Test filtering with backslashes
        crit_win = FilterCriteria(folder_path="C:\\Music\\Commerciale")
        res_win = engine.query(crit_win)
        self.assertEqual(len(res_win), 1)

        # Test filtering with forward slashes
        crit_unix = FilterCriteria(folder_path="C:/Music/Commerciale")
        res_unix = engine.query(crit_unix)
        self.assertEqual(len(res_unix), 1)

    def test_trending_track_card_preview_playback(self):
        """Requirement 1: Card preview play signal handles preview URL or emits signal."""
        t = TrendingTrack(
            rank=1,
            title="Dance Song",
            artist="DJ Master",
            category="dance_electro",
            preview_url="https://audio-ssl.itunes.apple.com/preview.mp3",
        )
        card = TrendingTrackCard(t)
        try:
            received = []
            card.play_requested.connect(lambda d: received.append(d))
            card._on_play_or_preview_clicked()
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["filepath"], "https://audio-ssl.itunes.apple.com/preview.mp3")
            self.assertIn("Dance Song", received[0]["title"])
            self.assertIn("Preview 30s", received[0]["title"])
        finally:
            card.cleanup()
            card.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
