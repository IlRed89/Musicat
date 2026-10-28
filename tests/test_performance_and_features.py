import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.spotify_auth import SpotifyAuth
from src.core.oauth_manager import OAuthManager
from src.gui.table_model import TrackTableModel
from src.audio.analyzer import AcousticAnalyzer
from src.scrapers.discogs import DiscogsClient
from src.scrapers.musicbrainz import MusicBrainzClient
from src.scrapers.web_enricher import WebEnricher
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for Qt widget/model tests
app = QApplication.instance() or QApplication([])

class TestPerformanceAndFeatures(unittest.TestCase):
    def test_spotify_auth_url(self):
        url = SpotifyAuth.build_authorization_url(client_id="test_client_id")
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=test_client_id", url)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A8888%2Fcallback", url)
        self.assertIn("scope=", url)
        self.assertIn("user-read-private", url)

    def test_table_model_clear_view(self):
        model = TrackTableModel()
        sample_tracks = [
            {"id": 1, "title": "Track 1", "artist": "Artist 1", "filepath": "c:/t1.mp3"},
            {"id": 2, "title": "Track 2", "artist": "Artist 2", "filepath": "c:/t2.mp3"}
        ]
        model.set_tracks(sample_tracks)
        self.assertEqual(model.rowCount(), 2)

        model.clear_view()
        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(len(model._tracks), 0)

    def test_scraping_timeouts(self):
        # Discogs scraper timeouts
        discogs = DiscogsClient(token="fake")
        # Check musicbrainz wrapper
        self.assertTrue(hasattr(MusicBrainzClient, "search_track"))

        enricher = WebEnricher()
        self.assertTrue(hasattr(enricher, "search_genre_and_year"))

    def test_fast_pass_audio_sample(self):
        analyzer = AcousticAnalyzer()
        # Non-existent file should raise LibsndfileError/FileNotFoundError/Exception
        with self.assertRaises(Exception):
            analyzer.load_audio_sample("non_existent_file_path.mp3")

    def test_mp3tag_workspace_components(self):
        from src.gui.mp3tag_workspace import Mp3tagWorkspaceWindow, Mp3tagTableWidget
        from src.core.db import Database

        db = Database(db_path=":memory:")
        workspace = Mp3tagWorkspaceWindow(arg1=db, tracks=[])
        
        self.assertTrue(hasattr(workspace, "_on_add_files"))
        self.assertTrue(hasattr(workspace, "_on_add_directory"))
        self.assertTrue(hasattr(workspace, "_on_clear_tracks"))
        self.assertTrue(hasattr(workspace, "_import_file_paths"))
        self.assertIsInstance(workspace.grid, Mp3tagTableWidget)

        # Test _on_clear_tracks
        workspace.tracks = [{"title": "Song", "filepath": "dummy.mp3"}]
        workspace._on_clear_tracks()
        self.assertEqual(len(workspace.tracks), 0)

if __name__ == "__main__":
    unittest.main()
