"""
Live DJ Crate & Advanced Filtering Engine for Musicat.

Designed for high-performance, live DJ performance queries (<15ms latency across 50,000+ tracks).
Supports multi-genre selection (OR), BPM range & tolerance percentage (Target ± %),
Harmonic Camelot Wheel matching (Exact, Adjacent ±1, Relative Major/Minor, Energy Boost +2, Semitone +7),
Decade/Year ranges, Energy Level / Star Ratings, Voidtools Everything MFT parametric queries,
in-memory microsecond caching, and Smart Crates with M3U/M3U8 export.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .db import Database
from .path_resolver import PathResolver
from .logger import MusicatLogger
from ..audio.camelot import CamelotWheel, CAMELOT_KEYS_ORDERED


@dataclass
class FilterCriteria:
    """Encapsulates all active multi-criteria DJ filter rules."""

    query_text: str = ""
    genres: List[str] = field(default_factory=list)  # Multiple genres with OR logic
    target_bpm: Optional[float] = None              # Baseline DJ deck BPM (e.g. 126.0)
    bpm_tolerance_pct: Optional[float] = None       # Tolerance percentage (e.g. 2.0 or 4.0)
    bpm_min: Optional[float] = None                 # Explicit minimum BPM
    bpm_max: Optional[float] = None                 # Explicit maximum BPM
    camelot_key: Optional[str] = None               # Active deck Camelot key (e.g. '8A')
    harmonic_matches_only: bool = False             # If True, matches wheel-compatible keys
    include_energy_boost: bool = True               # Include +2 step energy boost
    include_semitone_shift: bool = False            # Include +7 semitone lift
    year_min: Optional[int] = None                  # Release year start
    year_max: Optional[int] = None                  # Release year end
    rating_min: Optional[int] = None                # Minimum star rating (1-5)
    energy_levels: List[int] = field(default_factory=list) # e.g. [1, 2, 3, 4, 5]
    tags: List[str] = field(default_factory=list)   # e.g. ['Intro', 'Vocal', 'Acapella']
    quality_filter: Optional[str] = None            # 'clipping', 'low_volume', 'brickwall', 'problematic', 'ok'
    folder_path: Optional[str] = None               # Root drive or folder prefix (e.g. 'D:/Music')
    cover_filter: Optional[str] = None              # 'with_cover', 'without_cover'
    order_by: str = "artist, title"
    ascending: bool = True
    limit: int = 50000
    offset: int = 0

    def is_empty(self) -> bool:
        """Checks if all filter rules are at default (show entire library)."""
        return (
            not self.query_text.strip()
            and not self.genres
            and self.target_bpm is None
            and self.bpm_min is None
            and self.bpm_max is None
            and not self.camelot_key
            and not self.harmonic_matches_only
            and self.year_min is None
            and self.year_max is None
            and self.rating_min is None
            and not self.energy_levels
            and not self.tags
            and not self.quality_filter
            and not self.folder_path
            and not self.cover_filter
        )

    def effective_bpm_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Calculates effective (min_bpm, max_bpm) considering target BPM and tolerance.

        Returns:
            Tuple[Optional[float], Optional[float]]: Calculated lower and upper BPM limits.
        """
        if self.target_bpm is not None and self.target_bpm > 0:
            tol = self.bpm_tolerance_pct if self.bpm_tolerance_pct is not None else 4.0
            return CamelotWheel.calculate_bpm_tolerance_range(self.target_bpm, tol)

        min_b = self.bpm_min if (self.bpm_min is not None and self.bpm_min > 0) else None
        max_b = self.bpm_max if (self.bpm_max is not None and self.bpm_max > 0) else None
        return (min_b, max_b)

    def effective_camelot_keys(self) -> List[str]:
        """Calculates list of acceptable Camelot keys based on harmonic settings.

        Returns:
            List[str]: List of allowed Camelot keys (empty list means all keys allowed).
        """
        if not self.camelot_key or not self.camelot_key.strip():
            return []

        norm = CamelotWheel.normalize_key(self.camelot_key)
        if not norm:
            return []

        if not self.harmonic_matches_only:
            return [norm]

        return CamelotWheel.get_harmonic_matches(
            current_key=norm,
            include_exact=True,
            include_adjacent=True,
            include_relative=True,
            include_energy_boost=self.include_energy_boost,
            include_semitone=self.include_semitone_shift,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes criteria to dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterCriteria":
        """Deserializes criteria from dictionary."""
        valid_fields = cls.__dataclass_fields__.keys()
        clean = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**clean)


class LiveFilterQueryBuilder:
    """Builds optimized SQLite SQL queries and Everything SDK filter strings."""

    @classmethod
    def build_sql(cls, criteria: FilterCriteria) -> Tuple[str, List[Any]]:
        """Constructs parameterized SQL WHERE clause utilizing composite B-tree indexes.

        Args:
            criteria (FilterCriteria): Filter rules.

        Returns:
            Tuple[str, List[Any]]: (SQL SELECT statement, parameters list).
        """
        where_clauses: List[str] = ["1=1"]
        params: List[Any] = []

        # 1. Text Search (FTS-style LIKE over core fields)
        if criteria.query_text and criteria.query_text.strip():
            q_clean = f"%{criteria.query_text.strip()}%"
            where_clauses.append(
                "(title LIKE ? OR artist LIKE ? OR album LIKE ? OR filename LIKE ? "
                "OR label LIKE ? OR remixer LIKE ? OR comment LIKE ?)"
            )
            params.extend([q_clean] * 7)

        # 2. Multi-Genre OR Filter: (genre LIKE ? OR genre LIKE ?)
        if criteria.genres:
            genre_conditions = []
            for g in criteria.genres:
                clean_g = g.strip()
                if clean_g:
                    if clean_g.lower() == "vario":
                        genre_conditions.append("(genre IS NULL OR TRIM(genre) = '' OR genre LIKE ?)")
                        params.append("%vario%")
                    else:
                        genre_conditions.append("genre LIKE ?")
                        params.append(f"%{clean_g}%")
            if genre_conditions:
                where_clauses.append(f"({' OR '.join(genre_conditions)})")

        # 3. BPM Range (B-Tree index idx_bpm / idx_dj_lookup)
        bpm_min, bpm_max = criteria.effective_bpm_range()
        if bpm_min is not None:
            where_clauses.append("bpm >= ?")
            params.append(bpm_min)
        if bpm_max is not None:
            where_clauses.append("bpm <= ?")
            params.append(bpm_max)

        # 4. Camelot Harmonic Key Filtering (B-Tree index idx_key)
        keys = criteria.effective_camelot_keys()
        if keys:
            placeholders = ",".join("?" for _ in keys)
            where_clauses.append(f"UPPER(camelot_key) IN ({placeholders})")
            params.extend([k.upper() for k in keys])

        # 5. Year / Decades Range
        if criteria.year_min is not None and criteria.year_min > 0:
            where_clauses.append("year >= ?")
            params.append(criteria.year_min)
        if criteria.year_max is not None and criteria.year_max > 0:
            where_clauses.append("year <= ?")
            params.append(criteria.year_max)

        # 6. Star Rating (1-5)
        if criteria.rating_min is not None and criteria.rating_min > 0:
            where_clauses.append("rating >= ?")
            params.append(criteria.rating_min)

        # 7. Energy Levels (e.g. 1, 2, 3, 4, 5)
        if criteria.energy_levels:
            placeholders = ",".join("?" for _ in criteria.energy_levels)
            where_clauses.append(f"energy_level IN ({placeholders})")
            params.extend(criteria.energy_levels)

        # 8. Quick Tags (Intro, Vocal, Acapella) matching comment or title
        if criteria.tags:
            tag_conds = []
            for t in criteria.tags:
                clean_t = f"%{t.strip()}%"
                tag_conds.append("(comment LIKE ? OR title LIKE ?)")
                params.extend([clean_t, clean_t])
            if tag_conds:
                where_clauses.append(f"({' OR '.join(tag_conds)})")

        # 9. Audio Quality Filter (Clipping, Low Volume, Brickwall, Conformance)
        if criteria.quality_filter:
            qf = criteria.quality_filter.lower().strip()
            if qf == "clipping":
                where_clauses.append("(audio_status = 'CLIPPING' OR true_peak > 0.0)")
            elif qf == "low_volume":
                where_clauses.append("(audio_status = 'LOW_VOLUME' OR (lufs IS NOT NULL AND lufs < -18.0))")
            elif qf == "brickwall":
                where_clauses.append("(audio_status = 'BRICKWALL' OR (lra IS NOT NULL AND lra < 3.0))")
            elif qf == "problematic":
                where_clauses.append(
                    "(audio_status IN ('CLIPPING', 'LOW_VOLUME', 'BRICKWALL') "
                    "OR true_peak > 0.0 OR (lufs IS NOT NULL AND lufs < -18.0))"
                )
            elif qf == "ok":
                where_clauses.append("audio_status = 'OK'")

        # 10. Folder / Drive Filter
        if criteria.folder_path and criteria.folder_path.strip():
            raw_fp = criteria.folder_path.strip()
            fp_slash = raw_fp.replace("\\", "/").rstrip("/")
            fp_back = raw_fp.replace("/", "\\").rstrip("\\")
            where_clauses.append("(filepath LIKE ? OR filepath LIKE ? OR directory LIKE ? OR directory LIKE ?)")
            params.extend([f"{fp_slash}%", f"{fp_back}%", f"{fp_slash}%", f"{fp_back}%"])

        # 11. Cover Art Filter
        if criteria.cover_filter:
            cf = criteria.cover_filter.lower().strip()
            if cf == "with_cover":
                where_clauses.append("has_cover = 1")
            elif cf == "without_cover":
                where_clauses.append("(has_cover = 0 OR has_cover IS NULL)")

        # Sorting sanitation
        allowed_sort = {
            "id", "filepath", "filename", "artist", "title", "album", "year",
            "genre", "bpm", "camelot_key", "musical_key", "duration", "bitrate",
            "rating", "energy_level", "label", "remixer", "updated_at",
            "lufs", "true_peak", "lra", "audio_status"
        }
        sort_cols = [c.strip() for c in criteria.order_by.split(",") if c.strip() in allowed_sort]
        clean_sort = ", ".join(sort_cols) if sort_cols else "artist, title"
        direction = "ASC" if criteria.ascending else "DESC"

        sql = f"""
            SELECT * FROM tracks
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {clean_sort} {direction}
            LIMIT ? OFFSET ?
        """
        params.extend([criteria.limit, criteria.offset])

        return sql, params

    @classmethod
    def build_everything_query(cls, criteria: FilterCriteria) -> str:
        """Constructs an Everything SDK command query string.

        Args:
            criteria (FilterCriteria): Filter rules.

        Returns:
            str: Parametric search string for Everything64.dll.
        """
        tokens: List[str] = []

        if criteria.query_text:
            tokens.append(criteria.query_text.strip())

        if criteria.genres:
            # Everything supports genre tag or filename match
            g_tokens = [f'genre:"{g}"' for g in criteria.genres]
            tokens.append(f"({' | '.join(g_tokens)})")

        if criteria.year_min and criteria.year_max:
            tokens.append(f"year:{criteria.year_min}-{criteria.year_max}")
        elif criteria.year_min:
            tokens.append(f"year:>={criteria.year_min}")
        elif criteria.year_max:
            tokens.append(f"year:<={criteria.year_max}")

        return " ".join(tokens)


class LiveFilterEngine:
    """High-Performance Live DJ Filter Engine with in-memory caching and Smart Crates."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._in_memory_cache: List[Dict[str, Any]] = []
        self._cache_timestamp: float = 0.0

    def warm_cache(self, tracks: Optional[List[Dict[str, Any]]] = None) -> None:
        """Pre-loads or refreshes the in-memory track cache for microsecond querying.

        Args:
            tracks (Optional[List[Dict[str, Any]]]): If given, populates directly.
        """
        if tracks is not None:
            self._in_memory_cache = list(tracks)
        else:
            self._in_memory_cache = self.db.search_tracks(limit=100000)
        self._cache_timestamp = time.time()
        MusicatLogger.debug("FILTER", f"Warmed in-memory cache with {len(self._in_memory_cache):,} tracks.")

    def filter_in_memory(self, criteria: FilterCriteria) -> List[Dict[str, Any]]:
        """Filters cached tracks in RAM with <15ms latency across 50,000+ tracks.

        Args:
            criteria (FilterCriteria): Active filter parameters.

        Returns:
            List[Dict[str, Any]]: Filtered list of track dictionaries.
        """
        t0 = time.perf_counter()

        if criteria.is_empty():
            return list(self._in_memory_cache)

        # Pre-calculate filter parameters for fast loop execution
        q_text = criteria.query_text.strip().lower() if criteria.query_text else ""
        bpm_min, bpm_max = criteria.effective_bpm_range()
        allowed_keys = set(criteria.effective_camelot_keys())
        genres_lower = [g.strip().lower() for g in criteria.genres if g.strip()]
        tags_lower = [t.strip().lower() for t in criteria.tags if t.strip()]
        energy_set = set(criteria.energy_levels) if criteria.energy_levels else None
        rating_min = criteria.rating_min
        year_min = criteria.year_min
        year_max = criteria.year_max
        quality_filter = criteria.quality_filter.lower().strip() if criteria.quality_filter else None
        folder_filter = criteria.folder_path.strip().lower() if criteria.folder_path else None
        cover_filter = criteria.cover_filter.lower().strip() if criteria.cover_filter else None

        filtered: List[Dict[str, Any]] = []

        for tr in self._in_memory_cache:
            # 1. Text Query
            if q_text:
                title = (tr.get("title") or "").lower()
                artist = (tr.get("artist") or "").lower()
                album = (tr.get("album") or "").lower()
                filename = (tr.get("filename") or "").lower()
                remixer = (tr.get("remixer") or "").lower()
                label = (tr.get("label") or "").lower()
                if not (q_text in title or q_text in artist or q_text in album or
                        q_text in filename or q_text in remixer or q_text in label):
                    continue

            # 2. Multi-Genre (OR)
            if genres_lower:
                tr_genre = (tr.get("genre") or "").strip().lower()
                matched = False
                for g in genres_lower:
                    if g == "vario":
                        if not tr_genre or "vario" in tr_genre:
                            matched = True
                            break
                    elif g in tr_genre:
                        matched = True
                        break
                if not matched:
                    continue

            # 3. BPM Range
            if bpm_min is not None or bpm_max is not None:
                tr_bpm = tr.get("bpm")
                if tr_bpm is None or tr_bpm <= 0:
                    continue
                if bpm_min is not None and tr_bpm < bpm_min:
                    continue
                if bpm_max is not None and tr_bpm > bpm_max:
                    continue

            # 4. Camelot Key
            if allowed_keys:
                tr_key = (tr.get("camelot_key") or "").upper()
                if tr_key not in allowed_keys:
                    continue

            # 5. Year Range
            if year_min is not None or year_max is not None:
                tr_year = tr.get("year")
                if tr_year is None or tr_year <= 0:
                    continue
                if year_min is not None and tr_year < year_min:
                    continue
                if year_max is not None and tr_year > year_max:
                    continue

            # 6. Rating
            if rating_min is not None and rating_min > 0:
                tr_rating = tr.get("rating") or 0
                if tr_rating < rating_min:
                    continue

            # 7. Energy Level
            if energy_set:
                tr_energy = tr.get("energy_level")
                if tr_energy is None or tr_energy not in energy_set:
                    continue

            # 8. Custom Tags
            if tags_lower:
                comm = (tr.get("comment") or "").lower()
                ttl = (tr.get("title") or "").lower()
                if not any(t in comm or t in ttl for t in tags_lower):
                    continue

            # 9. Audio Quality Filter
            if quality_filter:
                status = (tr.get("audio_status") or "").upper()
                tp = tr.get("true_peak")
                lufs = tr.get("lufs")
                lra = tr.get("lra")
                if quality_filter == "clipping":
                    if not (status == "CLIPPING" or (tp is not None and tp > 0.0)):
                        continue
                elif quality_filter == "low_volume":
                    if not (status == "LOW_VOLUME" or (lufs is not None and lufs < -18.0)):
                        continue
                elif quality_filter == "brickwall":
                    if not (status == "BRICKWALL" or (lra is not None and lra < 3.0)):
                        continue
                elif quality_filter == "problematic":
                    is_prob = (
                        status in ("CLIPPING", "LOW_VOLUME", "BRICKWALL")
                        or (tp is not None and tp > 0.0)
                        or (lufs is not None and lufs < -18.0)
                    )
                    if not is_prob:
                        continue
                elif quality_filter == "ok":
                    if status != "OK":
                        continue

            # 10. Folder / Drive Filter
            if folder_filter:
                f_norm = folder_filter.replace("\\", "/").rstrip("/").lower()
                tr_dir_norm = (tr.get("directory") or "").replace("\\", "/").lower()
                tr_fp_norm = (tr.get("filepath") or "").replace("\\", "/").lower()
                if not (tr_fp_norm.startswith(f_norm) or tr_dir_norm.startswith(f_norm)):
                    continue

            # 11. Cover Art Filter
            if cover_filter:
                has_cov = bool(tr.get("has_cover"))
                if cover_filter == "with_cover" and not has_cov:
                    continue
                elif cover_filter == "without_cover" and has_cov:
                    continue

            filtered.append(tr)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        MusicatLogger.debug("FILTER:RAM", f"Matched {len(filtered):,} tracks in {latency_ms:.2f}ms")
        return filtered

    def filter_database(self, criteria: FilterCriteria) -> List[Dict[str, Any]]:
        """Filters tracks directly via SQLite indexed queries.

        Args:
            criteria (FilterCriteria): Filter rules.

        Returns:
            List[Dict[str, Any]]: Filtered records.
        """
        t0 = time.perf_counter()
        sql, params = LiveFilterQueryBuilder.build_sql(criteria)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            results = [dict(row) for row in cur.fetchall()]

        latency_ms = (time.perf_counter() - t0) * 1000.0
        MusicatLogger.debug("FILTER:SQL", f"Query executed in {latency_ms:.2f}ms. Returned {len(results):,} rows.")
        return results

    def query(self, criteria: FilterCriteria, prefer_ram: bool = True) -> List[Dict[str, Any]]:
        """Unified query dispatcher choosing optimal execution engine.

        Args:
            criteria (FilterCriteria): Active filter criteria.
            prefer_ram (bool): Use in-memory cache if warmed.

        Returns:
            List[Dict[str, Any]]: Filtered tracks.
        """
        if prefer_ram and self._in_memory_cache:
            return self.filter_in_memory(criteria)
        return self.filter_database(criteria)

    # =========================================================================
    # SMART CRATES MANAGEMENT
    # =========================================================================

    def save_smart_crate(self, name: str, criteria: FilterCriteria, icon: str = "crate") -> int:
        """Saves a filter criteria configuration as a dynamic Smart Crate.

        Args:
            name (str): Crate name (e.g. 'Peak Time Tech House 126-128').
            criteria (FilterCriteria): Rule definition.
            icon (str): Visual icon tag.

        Returns:
            int: Inserted Smart Crate database ID.
        """
        payload = json.dumps(criteria.to_dict())
        crate_id = self.db.save_smart_crate(name=name, rules_json=payload, icon=icon)
        MusicatLogger.info("SMART_CRATE", f"Saved Smart Crate '{name}' (ID: {crate_id})")
        return crate_id

    def get_smart_crates(self) -> List[Dict[str, Any]]:
        """Retrieves list of all saved Smart Crates.

        Returns:
            List[Dict[str, Any]]: List of Smart Crate descriptors.
        """
        return self.db.get_smart_crates()

    def load_smart_crate_criteria(self, crate_id_or_name: Union[int, str]) -> Optional[FilterCriteria]:
        """Loads and deserializes the filter rules of a Smart Crate.

        Args:
            crate_id_or_name (Union[int, str]): Crate ID or name.

        Returns:
            Optional[FilterCriteria]: Parsed criteria or None.
        """
        row = self.db.get_smart_crate(crate_id_or_name)
        if not row:
            return None
        try:
            data = json.loads(row["rules_json"])
            return FilterCriteria.from_dict(data)
        except Exception as e:
            MusicatLogger.error("SMART_CRATE", f"Error parsing criteria for crate {crate_id_or_name}: {e}")
            return None

    def evaluate_smart_crate(self, crate_id_or_name: Union[int, str]) -> List[Dict[str, Any]]:
        """Dynamically evaluates a Smart Crate against current library tracks.

        Args:
            crate_id_or_name (Union[int, str]): Crate ID or name.

        Returns:
            List[Dict[str, Any]]: Matching tracks.
        """
        crit = self.load_smart_crate_criteria(crate_id_or_name)
        if not crit:
            return []
        return self.query(crit)

    def delete_smart_crate(self, crate_id_or_name: Union[int, str]) -> bool:
        """Deletes a Smart Crate."""
        return self.db.delete_smart_crate(crate_id_or_name)

    def rename_smart_crate(self, crate_id_or_name: Union[int, str], new_name: str) -> bool:
        """Renames a Smart Crate."""
        return self.db.rename_smart_crate(crate_id_or_name, new_name)

    def duplicate_smart_crate(self, crate_id_or_name: Union[int, str], new_name: Optional[str] = None) -> Optional[int]:
        """Duplicates a Smart Crate."""
        return self.db.duplicate_smart_crate(crate_id_or_name, new_name)

    # =========================================================================
    # PLAYLIST EXPORT (M3U / M3U8)
    # =========================================================================

    @staticmethod
    def export_m3u(
        tracks: List[Dict[str, Any]],
        output_filepath: Union[str, Path],
        relative_paths: bool = False,
    ) -> str:
        """Exports a list of tracks as standard Extended M3U8 playlist.

        Compatible with Rekordbox, Traktor Pro, Serato DJ, and Denon Engine DJ.

        Args:
            tracks (List[Dict[str, Any]]): Tracks to include.
            output_filepath (Union[str, Path]): Destination playlist file (.m3u or .m3u8).
            relative_paths (bool): Convert paths to relative to playlist location.

        Returns:
            str: Resolved path to the exported playlist.
        """
        out_path = Path(output_filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = ["#EXTM3U\n"]

        for tr in tracks:
            raw_path = tr.get("filepath", "")
            resolved_path = PathResolver.to_absolute_path(raw_path)

            duration = int(round(tr.get("duration") or 0))
            artist = tr.get("artist") or "Unknown Artist"
            title = tr.get("title") or Path(resolved_path).stem

            # Extended M3U track entry: #EXTINF:<duration>,<artist> - <title>
            lines.append(f"#EXTINF:{duration},{artist} - {title}\n")

            if relative_paths:
                try:
                    rel = os.path.relpath(resolved_path, out_path.parent)
                    lines.append(f"{rel}\n")
                except ValueError:
                    lines.append(f"{resolved_path}\n")
            else:
                lines.append(f"{resolved_path}\n")

        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        MusicatLogger.info("EXPORT:M3U", f"Exported {len(tracks):,} tracks to '{out_path}'")
        return str(out_path)
