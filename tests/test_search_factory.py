"""
Unit Tests for Cross-Platform Search Factory and macOS Spotlight Driver.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from src.core.db import Database
from src.core.search_factory import (
    SearchEngine,
    SearchFactory,
    WindowsSearchEngine,
    DarwinSearchEngine,
    FtsSearchEngine,
)


class TestSearchFactory(unittest.TestCase):
    """Tests cross-platform search engine selection and fallback behavior."""

    def test_search_engine_selection(self):
        """Verifies correct engine class is picked based on sys.platform."""
        with patch("sys.platform", "win32"):
            engine = SearchFactory.get_search_engine()
            self.assertEqual(engine, WindowsSearchEngine)
            badge = SearchFactory.get_engine_badge()
            self.assertIn("Everything", badge) if WindowsSearchEngine.is_available() else self.assertIn("FTS", badge)

        with patch("sys.platform", "darwin"):
            engine = SearchFactory.get_search_engine()
            self.assertEqual(engine, DarwinSearchEngine)

        with patch("sys.platform", "linux"):
            engine = SearchFactory.get_search_engine()
            self.assertEqual(engine, FtsSearchEngine)

    def test_darwin_engine_availability_on_non_darwin(self):
        """DarwinSearchEngine should report False on non-darwin platforms."""
        if sys.platform != "darwin":
            self.assertFalse(DarwinSearchEngine.is_available())
            # Spotlight queries should safely return empty list without crashing
            res = DarwinSearchEngine.query_spotlight("test query")
            self.assertEqual(res, [])

    @patch("shutil.which", return_value="/usr/bin/mdfind")
    def test_darwin_engine_mock_spotlight(self, mock_which):
        """Tests DarwinSearchEngine with mocked mdfind binary."""
        with patch("sys.platform", "darwin"):
            DarwinSearchEngine._mdfind_available = None
            self.assertTrue(DarwinSearchEngine.is_available())

    def test_fts_fallback_search(self):
        """Tests that FtsSearchEngine fallback operates cleanly."""
        mock_db = MagicMock()
        mock_db.search_fts.return_value = [{"title": "Test Track", "artist": "DJ Test"}]

        results, engine_name = FtsSearchEngine.unified_search("Techno", mock_db)
        self.assertEqual(len(results), 1)
        self.assertEqual(engine_name, "SQLite FTS")


if __name__ == "__main__":
    unittest.main()
