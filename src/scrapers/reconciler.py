"""
Metadata Reconciler & Discrepancy Engine for Musicat.

Aggregates scraped results from multiple DJ and web platforms,
detects conflicting metadata across sources (e.g. differing genres or release years),
and provides selective field-by-field resolution for precision auto-tagging.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.logger import MusicatLogger


@dataclass
class FieldDiscrepancy:
    """Represents the values and conflict state of an individual metadata attribute."""

    field_name: str
    has_conflict: bool
    values_by_source: Dict[str, Any]  # source_name -> value
    recommended_value: Any


@dataclass
class DiscrepancyReport:
    """Complete multi-source comparison report for a single track."""

    track_query: str
    fields: Dict[str, FieldDiscrepancy]
    sources_participated: List[str]
    raw_results: List[Dict[str, Any]]


class MetadataReconciler:
    """Detects discrepancies between multiple metadata providers and orchestrates field selection."""

    # Priority ordering for electronic & DJ club tracks
    DEFAULT_SOURCE_PRIORITY = ["Beatport", "Traxsource", "Discogs", "MusicBrainz", "Web/YouTube", "Apple Music / iTunes (Studio HD)"]

    # Field-specific domain authority ranking:
    # 1. Discogs is gold standard for: original release year (Master Release), record label, catalog number, format, artist.
    # 2. Beatport / Traxsource are primary authorities for electronic subgenres, official BPM, and Camelot keys.
    # 3. MusicBrainz provides canonical community tags and release dates.
    # 4. Web/YouTube provides fallback for obscure or unreleased tracks.
    FIELD_AUTHORITY_PRIORITY = {
        "year": ["Discogs", "MusicBrainz", "Beatport", "Traxsource", "Web/YouTube", "YouTube Music"],
        "label": ["Discogs", "Beatport", "Traxsource", "MusicBrainz", "Web/YouTube"],
        "catalog_number": ["Discogs", "Beatport", "Traxsource"],
        "format": ["Discogs", "MusicBrainz"],
        "artist": ["Discogs", "MusicBrainz", "Beatport", "Traxsource", "Web/YouTube"],
        "bpm": ["Beatport", "Traxsource", "Discogs"],
        "camelot_key": ["Beatport", "Traxsource"],
        "musical_key": ["Beatport", "Traxsource"],
        "remixer": ["Beatport", "Traxsource", "Discogs"],
        "genre": ["Beatport", "Traxsource", "Discogs", "MusicBrainz", "Web/YouTube", "YouTube Music"],
        "artwork_url": ["Apple Music / iTunes (Studio HD)", "Beatport", "Discogs", "Traxsource"],
    }

    GENERIC_GENRES = {
        "other", "unknown", "soundtrack", "general", "various", "vario",
        "misc", "miscellaneous", "music", "audio", "n/a", "none", "untagged",
        "soundtracks", "ost", "original soundtrack"
    }

    BROAD_GENRES = {
        "electronic", "dance", "dance & edm", "club", "dance/electronic",
        "club/dance", "edm", "dance / edm"
    }

    @classmethod
    def clean_and_normalize_genre(cls, genre_val: Any) -> Optional[str]:
        """Cleans and standardizes a genre string, filtering out generic placeholders.

        Rules:
        - Rejects meaningless tags (e.g. 'Other', 'Unknown', 'Soundtrack', 'General', 'Audio').
        - Splits composite genre strings separated by delimiters (',', '/', ';', '|').
        - Prioritizes granular electronic subgenres (e.g. 'Tech House', 'Afro House')
          over overly broad umbrellas ('Electronic', 'Dance').

        Args:
            genre_val (Any): Raw genre input from tag header or scraped JSON.

        Returns:
            Optional[str]: Title-cased canonical genre name, or None if invalid/generic.
        """
        if not genre_val:
            return None
        text = str(genre_val).strip()
        if not text or text.lower() in cls.GENERIC_GENRES:
            return None
        parts = [p.strip() for p in re.split(r'[,/;|]', text) if p.strip()]
        valid_parts = [p for p in parts if p.lower() not in cls.GENERIC_GENRES]
        if not valid_parts:
            return None
        # Prefer specific subgenres (not in BROAD_GENRES)
        specific = [p for p in valid_parts if p.lower() not in cls.BROAD_GENRES]
        if specific:
            return specific[0].title()
        return valid_parts[0].title()

    @classmethod
    def _select_recommended_genre(cls, source_vals: Dict[str, Any]) -> str:
        """Picks the optimal genre candidate using cascading authority and subgenre specificity.

        Cascade:
        1. Specific subgenres from primary DJ authorities (Beatport, Traxsource, Discogs).
        2. Specific subgenres from secondary web/YouTube sources.
        3. Broad umbrella genres from primary authorities.
        4. Fallback default 'Vario' if no informative genre is available.

        Args:
            source_vals (Dict[str, Any]): Mapping of source name to raw genre value.

        Returns:
            str: Resolved consensus genre string.
        """
        candidates_by_source: Dict[str, str] = {}
        for src, raw_g in source_vals.items():
            cleaned = cls.clean_and_normalize_genre(raw_g)
            if cleaned:
                candidates_by_source[src] = cleaned

        if not candidates_by_source:
            return "Vario"

        priority = cls.FIELD_AUTHORITY_PRIORITY.get("genre", [])

        # 1. Prefer specific subgenres from highest priority authority
        for p_src in priority:
            if p_src in candidates_by_source:
                val = candidates_by_source[p_src]
                if val.lower() not in cls.BROAD_GENRES:
                    return val

        # 2. Check any other candidate source for specific subgenre
        for val in candidates_by_source.values():
            if val.lower() not in cls.BROAD_GENRES:
                return val

        # 3. Otherwise pick first valid broad genre from priority source
        for p_src in priority:
            if p_src in candidates_by_source:
                return candidates_by_source[p_src]

        return list(candidates_by_source.values())[0]

    @classmethod
    def _select_recommended_year(cls, source_vals: Dict[str, Any]) -> Optional[int]:
        """Picks the earliest valid original release year from priority sources.

        Prioritizes Discogs Master Releases and MusicBrainz original release groups,
        falling back to minimum valid four-digit year (1920..2030) across all sources.

        Args:
            source_vals (Dict[str, Any]): Mapping of source name to candidate release years.

        Returns:
            Optional[int]: Valid 4-digit release year integer, or None.
        """
        priority = cls.FIELD_AUTHORITY_PRIORITY.get("year", [])
        for p_src in priority:
            if p_src in source_vals:
                raw_y = source_vals[p_src]
                if raw_y and str(raw_y).isdigit():
                    y_int = int(raw_y)
                    if 1920 <= y_int <= 2030:
                        return y_int

        valid_years = []
        for v in source_vals.values():
            if v and str(v).isdigit() and 1920 <= int(v) <= 2030:
                valid_years.append(int(v))
        if valid_years:
            return min(valid_years)
        return None

    COMPARABLE_FIELDS = [
        "title",
        "artist",
        "remixer",
        "label",
        "genre",
        "year",
        "bpm",
        "musical_key",
        "camelot_key",
        "catalog_number",
        "format",
        "artwork_url",
    ]

    @classmethod
    def analyze_discrepancies(
        cls,
        track_query: str,
        results_from_sources: List[Dict[str, Any]],
        current_file_tags: Optional[Dict[str, Any]] = None,
    ) -> DiscrepancyReport:
        """Analyzes scraped metadata records to detect concordances and conflicts.

        Discrepancy Resolution Algorithm:
        1. Gap Analysis: Evaluates whether critical attributes (valid 4-digit release year,
           distinct electronic subgenre) are absent across primary responses.
        2. Autonomous Web Fallback: If gaps exist, triggers `WebEnricher.search_genre_and_year`
           (Wikipedia / YouTube) to fill missing fields.
        3. Field-by-Field Domain Consensus: For each field in `COMPARABLE_FIELDS`, pools
           candidate values, normalizes formatting (e.g. case insensitivity, float BPM rounding),
           and flags discrepancies if multiple distinct values are asserted.
        4. Authority Prioritization: Applies `FIELD_AUTHORITY_PRIORITY` to recommend the single
           most trustworthy value (e.g. Discogs for label/year, Beatport for BPM/Key/subgenre).

        Args:
            track_query (str): Normalized search query string (e.g. 'Artist - Title').
            results_from_sources (List[Dict[str, Any]]): Raw scraped payloads from online providers.
            current_file_tags (Optional[Dict[str, Any]]): Existing ID3/Vorbis tags on disk for delta comparison.

        Returns:
            DiscrepancyReport: Structured object containing per-field conflicts and recommended consensus values.
        """
        # Check if year or specific subgenre are missing across primary results, and trigger web fallback if so
        has_specific_genre = any(
            cls.clean_and_normalize_genre(r.get("genre")) and
            cls.clean_and_normalize_genre(r.get("genre")).lower() not in cls.BROAD_GENRES
            for r in results_from_sources
        )
        has_year = any(
            r.get("year") and str(r.get("year")).isdigit() and 1920 <= int(r.get("year")) <= 2030
            for r in results_from_sources
        )

        if (not has_specific_genre or not has_year) and track_query:
            artist = (current_file_tags.get("artist") if current_file_tags else "") or ""
            title = (current_file_tags.get("title") if current_file_tags else "") or track_query
            if not artist and " - " in track_query:
                parts = track_query.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()

            from .web_enricher import WebEnricher
            try:
                web_res = WebEnricher.search_genre_and_year(artist=artist, title=title)
                if web_res:
                    results_from_sources.append(web_res)
            except Exception as e:
                MusicatLogger.debug("RECONCILER:WEB", f"Web fallback error: {e}")

        sources = [r.get("source", "Unknown") for r in results_from_sources]
        field_reports: Dict[str, FieldDiscrepancy] = {}

        for fld in cls.COMPARABLE_FIELDS:
            source_vals: Dict[str, Any] = {}

            if current_file_tags and current_file_tags.get(fld):
                source_vals["Current File"] = current_file_tags[fld]

            for item in results_from_sources:
                src_name = item.get("source", "Source")
                val = item.get(fld)
                if val is not None and str(val).strip() != "":
                    source_vals[src_name] = val

            unique_normalized_vals = set()
            for v in source_vals.values():
                if isinstance(v, (int, float)):
                    unique_normalized_vals.add(round(float(v), 0) if fld == "bpm" else v)
                else:
                    unique_normalized_vals.add(str(v).strip().lower())

            has_conflict = len(unique_normalized_vals) > 1

            # --- Consensus Recommendation Algorithm ---
            if fld == "genre":
                recommended = cls._select_recommended_genre(source_vals)
            elif fld == "year":
                recommended = cls._select_recommended_year(source_vals)
            else:
                recommended = None
                if source_vals:
                    priority_list = cls.FIELD_AUTHORITY_PRIORITY.get(fld, cls.DEFAULT_SOURCE_PRIORITY)
                    for p_src in priority_list:
                        if p_src in source_vals:
                            recommended = source_vals[p_src]
                            break

                    if recommended is None:
                        counts = Counter([str(v).strip() for v in source_vals.values() if v])
                        most_common = counts.most_common(1)
                        if most_common:
                            for orig_v in source_vals.values():
                                if str(orig_v).strip() == most_common[0][0]:
                                    recommended = orig_v
                                    break

            field_reports[fld] = FieldDiscrepancy(
                field_name=fld,
                has_conflict=has_conflict,
                values_by_source=source_vals,
                recommended_value=recommended,
            )

        MusicatLogger.get_logger().info(
            f"[RECONCILER] Analyzed '{track_query}' across {len(sources)} sources. "
            f"Conflicts found in: {[k for k, v in field_reports.items() if v.has_conflict]}"
        )

        return DiscrepancyReport(
            track_query=track_query,
            fields=field_reports,
            sources_participated=sources,
            raw_results=results_from_sources,
        )

    @classmethod
    def merge_selected_metadata(
        cls,
        report: DiscrepancyReport,
        user_selections: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merges metadata based on user-selected field values.

        Args:
            report (DiscrepancyReport): The discrepancy report.
            user_selections (Dict[str, Any]): Dictionary mapping field_name to chosen value or source.

        Returns:
            Dict[str, Any]: Final clean metadata dictionary ready for tag writing.
        """
        final_tags: Dict[str, Any] = {}

        for fld in cls.COMPARABLE_FIELDS:
            if fld in user_selections:
                val = user_selections[fld]
                # If user passed a source name e.g. "Beatport", look up its value
                disc_field = report.fields.get(fld)
                if disc_field and val in disc_field.values_by_source:
                    final_tags[fld] = disc_field.values_by_source[val]
                else:
                    final_tags[fld] = val
            else:
                # Fall back to recommended consensus value
                disc_field = report.fields.get(fld)
                if disc_field and disc_field.recommended_value is not None:
                    final_tags[fld] = disc_field.recommended_value

        return final_tags
