"""
Unified Cross-Platform Search Engine Factory for Musicat.

Selects and instantiates the optimal high-speed indexing engine based on OS:
- Windows (win32): WindowsSearchEngine (Voidtools Everything SDK IPC / SQLite FTS5 fallback)
- macOS (darwin): DarwinSearchEngine (macOS Spotlight Metadata mdfind / SQLite FTS5 fallback)
- Linux / Other: FtsSearchEngine (Native SQLite FTS5 Virtual Table)
"""

import sys
from typing import Any, Dict, List, Optional, Tuple

from .everything_search import EverythingSearchEngine
from .search_mac import DarwinSearchEngine


# Aliases as specified in architectural requirements
WindowsSearchEngine = EverythingSearchEngine


class FtsSearchEngine:
    """Fallback engine using SQLite FTS5 full-text search directly."""

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def unified_search(cls, query: str, db: Any, limit: int = 1000) -> Tuple[List[Dict[str, Any]], str]:
        if not query or not query.strip():
            return db.search_tracks(limit=limit), "Database All"
        return db.search_fts(query.strip(), limit=limit), "SQLite FTS"


class SearchFactory:
    """Factory determining the platform-specific search driver."""

    @classmethod
    def get_search_engine(cls):
        """Returns the platform-specific search engine class.

        Returns:
            Type: WindowsSearchEngine on Windows, DarwinSearchEngine on macOS,
                  or FtsSearchEngine on other platforms.
        """
        if sys.platform == "win32":
            return WindowsSearchEngine
        elif sys.platform == "darwin":
            return DarwinSearchEngine
        else:
            return FtsSearchEngine

    @classmethod
    def unified_search(
        cls,
        query: str,
        db: Any,
        limit: int = 1000,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Dispatches search to the active OS engine with automatic SQLite FTS fallback.

        Args:
            query (str): Search token or keywords.
            db: Musicat SQLite Database instance.
            limit (int): Max returned tracks.

        Returns:
            Tuple[List[Dict[str, Any]], str]: (Matching track records, Active engine name).
        """
        engine = cls.get_search_engine()
        return engine.unified_search(query, db, limit=limit)

    @classmethod
    def is_fast_search_available(cls) -> bool:
        """Checks if native fast-indexing (Everything on Windows, Spotlight on macOS) is active."""
        engine = cls.get_search_engine()
        return engine.is_available()

    @classmethod
    def get_engine_badge(cls) -> str:
        """Returns a short UI badge string indicating active search technology."""
        if sys.platform == "win32":
            return "Everything MFT" if WindowsSearchEngine.is_available() else "SQLite FTS"
        elif sys.platform == "darwin":
            return "Spotlight" if DarwinSearchEngine.is_available() else "SQLite FTS"
        return "SQLite FTS"


# Top-level unified SearchEngine interface
SearchEngine = SearchFactory
