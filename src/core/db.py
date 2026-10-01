"""
High-Performance SQLite Database Engine for Musicat.
Optimized for 50,000+ tracks with WAL mode, prepared statements, and DJ-centric indexes.
"""

import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from .path_resolver import PathResolver


class Database:
    """Manages SQLite connection, schema migrations, and high-performance querying."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            data_dir = PathResolver.get_data_dir()
            self.db_path = str(data_dir / "musicat.db")
        else:
            self.db_path = str(db_path)

        self._init_db()

    @contextmanager
    def get_connection(self):
        """Yields an optimized SQLite connection and closes it upon exit."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # DJ Library optimization pragmas
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # 64 MB memory cache
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def close(self) -> None:
        """Forces SQLite checkpoint and frees locks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass

    def _init_db(self) -> None:
        """Creates tables and indexes if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE NOT NULL,
                    portable_path TEXT,
                    volume_id TEXT,
                    filename TEXT NOT NULL,
                    directory TEXT NOT NULL,
                    filesize INTEGER DEFAULT 0,
                    file_mtime REAL DEFAULT 0,
                    duration REAL DEFAULT 0,
                    bitrate INTEGER DEFAULT 0,
                    sample_rate INTEGER DEFAULT 0,
                    format TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    album_artist TEXT,
                    year INTEGER,
                    genre TEXT,
                    track_num INTEGER,
                    total_tracks INTEGER,
                    disc_num INTEGER,
                    bpm REAL,
                    musical_key TEXT,
                    camelot_key TEXT,
                    energy_level INTEGER,
                    rating INTEGER DEFAULT 0,
                    label TEXT,
                    remixer TEXT,
                    comment TEXT,
                    has_cover INTEGER DEFAULT 0,
                    waveform_peaks BLOB,
                    analyzed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_tracks_filepath ON tracks (filepath);
                CREATE INDEX IF NOT EXISTS idx_tracks_portable ON tracks (portable_path);
                CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks (artist);
                CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks (title);
                CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks (genre);
                CREATE INDEX IF NOT EXISTS idx_tracks_bpm ON tracks (bpm);
                CREATE INDEX IF NOT EXISTS idx_tracks_camelot ON tracks (camelot_key);
                CREATE INDEX IF NOT EXISTS idx_tracks_year ON tracks (year);
                CREATE INDEX IF NOT EXISTS idx_tracks_label ON tracks (label);
                CREATE INDEX IF NOT EXISTS idx_tracks_rating ON tracks (rating);

                -- FTS5 Full-Text Search Virtual Table
                CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    title,
                    artist,
                    album,
                    genre,
                    label,
                    remixer,
                    comment,
                    filename,
                    content='tracks',
                    content_rowid='id'
                );

                -- Synchronize FTS on Insert
                CREATE TRIGGER IF NOT EXISTS trg_tracks_ai AFTER INSERT ON tracks BEGIN
                    INSERT INTO tracks_fts(rowid, title, artist, album, genre, label, remixer, comment, filename)
                    VALUES (new.id, new.title, new.artist, new.album, new.genre, new.label, new.remixer, new.comment, new.filename);
                END;

                -- Synchronize FTS on Delete
                CREATE TRIGGER IF NOT EXISTS trg_tracks_ad AFTER DELETE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album, genre, label, remixer, comment, filename)
                    VALUES('delete', old.id, old.title, old.artist, old.album, old.genre, old.label, old.remixer, old.comment, old.filename);
                END;

                -- Synchronize FTS on Update
                CREATE TRIGGER IF NOT EXISTS trg_tracks_au AFTER UPDATE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album, genre, label, remixer, comment, filename)
                    VALUES('delete', old.id, old.title, old.artist, old.album, old.genre, old.label, old.remixer, old.comment, old.filename);
                    INSERT INTO tracks_fts(rowid, title, artist, album, genre, label, remixer, comment, filename)
                    VALUES (new.id, new.title, new.artist, new.album, new.genre, new.label, new.remixer, new.comment, new.filename);
                END;
            """)

    def insert_or_update_track(self, track_data: Dict[str, Any]) -> int:
        """Inserts or updates a single track record."""
        cols = list(track_data.keys())
        placeholders = [f":{col}" for col in cols]
        update_assignments = [f"{col}=excluded.{col}" for col in cols if col not in ("id", "filepath", "created_at")]

        sql = f"""
            INSERT INTO tracks ({', '.join(cols)}, updated_at)
            VALUES ({', '.join(placeholders)}, CURRENT_TIMESTAMP)
            ON CONFLICT(filepath) DO UPDATE SET
            {', '.join(update_assignments)}, updated_at = CURRENT_TIMESTAMP
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, track_data)
            return cur.lastrowid or 0

    def bulk_insert_or_update(self, track_list: List[Dict[str, Any]]) -> int:
        """Performs batch upsert in a single transaction."""
        if not track_list:
            return 0

        # Uniform columns across all dicts
        all_cols = set()
        for t in track_list:
            all_cols.update(t.keys())
        cols = sorted(list(all_cols))

        placeholders = [f":{col}" for col in cols]
        update_assignments = [f"{col}=excluded.{col}" for col in cols if col not in ("id", "filepath", "created_at")]

        sql = f"""
            INSERT INTO tracks ({', '.join(cols)}, updated_at)
            VALUES ({', '.join(placeholders)}, CURRENT_TIMESTAMP)
            ON CONFLICT(filepath) DO UPDATE SET
            {', '.join(update_assignments)}, updated_at = CURRENT_TIMESTAMP
        """

        # Ensure all records have identical keys
        normalized_records = []
        for t in track_list:
            rec = {col: t.get(col) for col in cols}
            normalized_records.append(rec)

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(sql, normalized_records)
            return cur.rowcount

    def update_track_tags(self, filepath: str, updates: Dict[str, Any]) -> bool:
        """Updates specific tag fields for a given filepath."""
        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [filepath]

        sql = f"UPDATE tracks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE filepath = ?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.rowcount > 0

    def update_tracks_batch(self, filepaths: List[str], updates: Dict[str, Any]) -> int:
        """Applies uniform tag updates to multiple tracks."""
        if not filepaths or not updates:
            return 0

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values())

        in_clause = ",".join("?" for _ in filepaths)
        sql = f"UPDATE tracks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE filepath IN ({in_clause})"

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params + filepaths)
            return cur.rowcount

    def get_track(self, track_id_or_path: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Retrieves a single track by ID or Filepath."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if isinstance(track_id_or_path, int):
                cur.execute("SELECT * FROM tracks WHERE id = ?", (track_id_or_path,))
            else:
                cur.execute("SELECT * FROM tracks WHERE filepath = ?", (str(track_id_or_path),))
            row = cur.fetchone()
            return dict(row) if row else None

    def search_tracks(
        self,
        query: str = "",
        genre: Optional[str] = None,
        bpm_min: Optional[float] = None,
        bpm_max: Optional[float] = None,
        camelot_key: Optional[str] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        rating_min: Optional[int] = None,
        order_by: str = "artist, title",
        ascending: bool = True,
        limit: int = 100000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Searches tracks with fast multi-attribute filtering.

        Args:
            query (str): Substring search across title, artist, album, filename, etc.
            genre (Optional[str]): Genre filter.
            bpm_min (Optional[float]): Minimum BPM.
            bpm_max (Optional[float]): Maximum BPM.
            camelot_key (Optional[str]): Camelot wheel key.
            year_min (Optional[int]): Earliest release year.
            year_max (Optional[int]): Latest release year.
            rating_min (Optional[int]): Minimum star rating.
            order_by (str): Comma separated column names for sorting.
            ascending (bool): Sort direction.
            limit (int): Max returned tracks.
            offset (int): Offset for pagination.

        Returns:
            List[Dict[str, Any]]: Filtered track records.
        """
        where_clauses = ["1=1"]
        params: List[Any] = []

        if query:
            q_clean = f"%{query.strip()}%"
            where_clauses.append(
                "(title LIKE ? OR artist LIKE ? OR album LIKE ? OR filename LIKE ? OR label LIKE ? OR remixer LIKE ? OR comment LIKE ?)"
            )
            params.extend([q_clean] * 7)

        if genre and genre.strip():
            where_clauses.append("genre LIKE ?")
            params.append(f"%{genre.strip()}%")

        if bpm_min is not None and bpm_min > 0:
            where_clauses.append("bpm >= ?")
            params.append(bpm_min)

        if bpm_max is not None and bpm_max > 0:
            where_clauses.append("bpm <= ?")
            params.append(bpm_max)

        if camelot_key and camelot_key.strip():
            where_clauses.append("camelot_key = ?")
            params.append(camelot_key.strip().upper())

        if year_min is not None and year_min > 0:
            where_clauses.append("year >= ?")
            params.append(year_min)

        if year_max is not None and year_max > 0:
            where_clauses.append("year <= ?")
            params.append(year_max)

        if rating_min is not None and rating_min > 0:
            where_clauses.append("rating >= ?")
            params.append(rating_min)

        # Sanitize order_by
        allowed_sort = {
            "id", "filepath", "filename", "artist", "title", "album", "year",
            "genre", "bpm", "camelot_key", "musical_key", "duration", "bitrate",
            "rating", "label", "remixer", "updated_at"
        }
        clean_sort = ", ".join([col for col in order_by.split(",") if col.strip() in allowed_sort]) or "artist, title"
        direction = "ASC" if ascending else "DESC"

        sql = f"""
            SELECT * FROM tracks
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {clean_sort} {direction}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def search_fts(self, query: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Executes high-speed Full-Text Search (FTS5) across track metadata.

        Args:
            query (str): Search terms or tokens.
            limit (int): Maximum records to return.

        Returns:
            List[Dict[str, Any]]: List of matching track records ordered by relevance.
        """
        if not query or not query.strip():
            return self.search_tracks(limit=limit)

        clean_query = query.strip()
        # Tokenize and format terms for FTS prefix matching e.g. "carl*" "cox*"
        terms = [re.sub(r'["\']', '', t) for t in clean_query.split() if t]
        if not terms:
            return self.search_tracks(limit=limit)

        fts_expr = " ".join([f'"{t}"*' for t in terms])
        sql = """
            SELECT t.* FROM tracks t
            JOIN tracks_fts fts ON t.id = fts.rowid
            WHERE tracks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (fts_expr, limit))
                rows = cur.fetchall()
                if rows:
                    return [dict(r) for r in rows]
        except Exception:
            pass

        # Fallback to standard LIKE search
        return self.search_tracks(query=query, limit=limit)

    def count_tracks(self) -> int:
        """Returns total track count."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tracks")
            return cur.fetchone()[0]

    def get_library_statistics(self) -> Dict[str, Any]:
        """Calculates DJ library statistics."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total_tracks,
                    COALESCE(SUM(duration), 0) as total_duration,
                    COUNT(DISTINCT artist) as unique_artists,
                    COUNT(DISTINCT genre) as unique_genres,
                    COUNT(DISTINCT label) as unique_labels,
                    COUNT(CASE WHEN bpm IS NOT NULL AND bpm > 0 THEN 1 END) as analyzed_bpm,
                    COUNT(CASE WHEN camelot_key IS NOT NULL AND camelot_key != '' THEN 1 END) as analyzed_keys
                FROM tracks
            """)
            stats = dict(cur.fetchone())

            # Top 10 Genres
            cur.execute("""
                SELECT genre, COUNT(*) as count
                FROM tracks
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre ORDER BY count DESC LIMIT 10
            """)
            stats["top_genres"] = [dict(row) for row in cur.fetchall()]

            # Camelot Key distribution
            cur.execute("""
                SELECT camelot_key, COUNT(*) as count
                FROM tracks
                WHERE camelot_key IS NOT NULL AND camelot_key != ''
                GROUP BY camelot_key ORDER BY count DESC
            """)
            stats["key_distribution"] = [dict(row) for row in cur.fetchall()]

            return stats

    def delete_missing_files(self) -> int:
        """Removes tracks whose files no longer exist on disk."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, filepath FROM tracks")
            rows = cur.fetchall()

            missing_ids = []
            for row in rows:
                resolved = PathResolver.to_absolute_path(row["filepath"])
                if not Path(resolved).exists():
                    missing_ids.append(row["id"])

            if missing_ids:
                in_c = ",".join("?" for _ in missing_ids)
                cur.execute(f"DELETE FROM tracks WHERE id IN ({in_c})", missing_ids)
                return len(missing_ids)
            return 0
