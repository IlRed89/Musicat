"""
macOS Spotlight & Metadata Search Engine for Musicat.

Interfaces with macOS Metadata Services via `mdfind` CLI utility for instant
sub-millisecond queries on APFS / HFS+ volumes.
Provides transparent fallback to SQLite FTS5 if Spotlight indexing is disabled
on external drives or if running on non-Darwin platforms.
"""

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .logger import MusicatLogger


AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".aac", ".ogg", ".opus", ".alac"}


@dataclass
class MacSearchResultItem:
    """Represents a file matched by macOS Spotlight or SQLite FTS."""

    filepath: str
    filename: str
    filesize: int
    modified_time: float
    source: str  # 'macos_spotlight' or 'sqlite_fts'


class DarwinSearchEngine:
    """macOS Spotlight search driver with transparent SQLite FTS5 fallback."""

    _mdfind_available: Optional[bool] = None

    @classmethod
    def is_available(cls) -> bool:
        """Checks if running on macOS and mdfind binary exists in system PATH."""
        if cls._mdfind_available is not None:
            return cls._mdfind_available

        if sys.platform != "darwin":
            cls._mdfind_available = False
            return False

        cls._mdfind_available = shutil.which("mdfind") is not None
        return cls._mdfind_available

    @classmethod
    def query_spotlight(
        cls,
        query: str,
        scope_dir: Optional[Union[str, Path]] = None,
        limit: int = 1000,
        timeout_sec: float = 3.0,
    ) -> List[str]:
        """Executes mdfind against macOS Spotlight metadata index.

        Args:
            query (str): Search token or keywords.
            scope_dir (Optional[Union[str, Path]]): Specific directory or volume to search.
            limit (int): Maximum results to return.
            timeout_sec (float): Process timeout in seconds.

        Returns:
            List[str]: Matching absolute filepaths.
        """
        if not cls.is_available() or not query.strip():
            return []

        clean_q = query.strip()
        cmd = ["mdfind"]

        if scope_dir and Path(scope_dir).exists():
            cmd.extend(["-onlyin", str(Path(scope_dir).resolve())])

        # Build spotlight query: name matching with audio content filter
        tokens = clean_q.split()
        if len(tokens) == 1:
            cmd.extend(["-name", clean_q])
        else:
            # Multi-token search across filename or metadata
            sub_clauses = [f'kMDItemDisplayName == "*{t}*"c' for t in tokens]
            query_expr = f"({' && '.join(sub_clauses)})"
            cmd.append(query_expr)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            if res.returncode != 0:
                MusicatLogger.warning("SEARCH:MAC", f"mdfind returned code {res.returncode}: {res.stderr}")
                return []

            matched_paths: List[str] = []
            for line in res.stdout.splitlines():
                p = line.strip()
                if p and Path(p).suffix.lower() in AUDIO_EXTENSIONS:
                    matched_paths.append(p)
                    if len(matched_paths) >= limit:
                        break

            return matched_paths
        except (subprocess.TimeoutExpired, Exception) as e:
            MusicatLogger.warning("SEARCH:MAC", f"Spotlight search failed: {e}")
            return []

    @classmethod
    def unified_search(
        cls,
        query: str,
        db: Any,
        limit: int = 1000,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Executes fast search, prioritizing Spotlight with transparent SQLite FTS fallback.

        Args:
            query (str): Search keywords.
            db: Musicat SQLite Database instance.
            limit (int): Max returned tracks.

        Returns:
            Tuple[List[Dict[str, Any]], str]: (Matching track records, Engine description string).
        """
        if not query or not query.strip():
            return db.search_tracks(limit=limit), "Database All"

        clean_q = query.strip()
        t0 = time.perf_counter()

        # 1. Attempt Spotlight search if on macOS
        if cls.is_available():
            spotlight_paths = cls.query_spotlight(clean_q, limit=limit)
            if spotlight_paths:
                # Resolve paths from SQLite indexed library
                with db.get_connection() as conn:
                    cur = conn.cursor()
                    placeholders = ",".join("?" for _ in spotlight_paths)
                    cur.execute(
                        f"SELECT * FROM tracks WHERE filepath IN ({placeholders}) LIMIT ?",
                        spotlight_paths + [limit],
                    )
                    rows = [dict(r) for r in cur.fetchall()]

                if rows:
                    latency = (time.perf_counter() - t0) * 1000.0
                    MusicatLogger.debug("SEARCH:MAC", f"Spotlight matched {len(rows)} tracks in {latency:.2f}ms")
                    return rows, "macOS Spotlight"

        # 2. Fallback to SQLite FTS5
        fts_results = db.search_fts(clean_q, limit=limit)
        latency = (time.perf_counter() - t0) * 1000.0
        MusicatLogger.debug("SEARCH:FTS", f"SQLite FTS matched {len(fts_results)} tracks in {latency:.2f}ms")
        return fts_results, "SQLite FTS"
