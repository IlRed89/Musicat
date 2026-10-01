"""
Musicat Core Module - Path resolving, SQLite storage, Scanner, Logging, and Everything MFT Search.
"""

from .path_resolver import PathResolver
from .db import Database
from .scanner import LibraryScanner
from .logger import MusicatLogger, GuiLogHandler
from .everything_search import EverythingSearchEngine
from .search_mac import DarwinSearchEngine
from .search_factory import SearchEngine, SearchFactory, WindowsSearchEngine
from .filter_engine import FilterCriteria, LiveFilterQueryBuilder, LiveFilterEngine
from .memory_cache import AnalysisMemoryCache, WaveformMemoryCache

__all__ = [
    "PathResolver",
    "Database",
    "LibraryScanner",
    "MusicatLogger",
    "GuiLogHandler",
    "EverythingSearchEngine",
    "DarwinSearchEngine",
    "WindowsSearchEngine",
    "SearchEngine",
    "SearchFactory",
    "FilterCriteria",
    "LiveFilterQueryBuilder",
    "LiveFilterEngine",
    "AnalysisMemoryCache",
    "WaveformMemoryCache",
]
