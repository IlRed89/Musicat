"""
Metadata Reconciler & Discrepancy Engine for Musicat.

Aggregates scraped results from multiple DJ and web platforms,
detects conflicting metadata across sources (e.g. differing genres or release years),
and provides selective field-by-field resolution for precision auto-tagging.
"""

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
    DEFAULT_SOURCE_PRIORITY = ["Beatport", "Traxsource", "Discogs", "MusicBrainz", "Apple Music / iTunes (Studio HD)"]

    # Field-specific domain authority ranking:
    # Discogs is primary gold standard for: release year, record label, catalog number, release format, and artist credits.
    FIELD_AUTHORITY_PRIORITY = {
        "year": ["Discogs", "MusicBrainz", "Beatport", "Traxsource"],
        "label": ["Discogs", "Beatport", "Traxsource", "MusicBrainz"],
        "catalog_number": ["Discogs", "Beatport", "Traxsource"],
        "format": ["Discogs", "MusicBrainz"],
        "artist": ["Discogs", "MusicBrainz", "Beatport", "Traxsource"],
        "bpm": ["Beatport", "Traxsource", "Discogs"],
        "camelot_key": ["Beatport", "Traxsource"],
        "musical_key": ["Beatport", "Traxsource"],
        "remixer": ["Beatport", "Traxsource", "Discogs"],
        "genre": ["Beatport", "Traxsource", "Discogs", "MusicBrainz"],
        "artwork_url": ["Apple Music / iTunes (Studio HD)", "Beatport", "Discogs", "Traxsource"],
    }

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
        """Analyzes a collection of scraped records to identify concordances and conflicts.

        Args:
            track_query (str): The search query used.
            results_from_sources (List[Dict[str, Any]]): Track dictionaries returned by various scrapers.
            current_file_tags (Optional[Dict[str, Any]]): Existing tags from the local file.

        Returns:
            DiscrepancyReport: Detailed report with conflict flags and source mappings per field.
        """
        sources = [r.get("source", "Unknown") for r in results_from_sources]
        field_reports: Dict[str, FieldDiscrepancy] = {}

        for fld in cls.COMPARABLE_FIELDS:
            source_vals: Dict[str, Any] = {}

            # Include current local file value as a reference baseline if present
            if current_file_tags and current_file_tags.get(fld):
                source_vals["Current File"] = current_file_tags[fld]

            for item in results_from_sources:
                src_name = item.get("source", "Source")
                val = item.get(fld)
                if val is not None and str(val).strip() != "":
                    source_vals[src_name] = val

            # --- Conflict Detection Algorithm ---
            # Normalizes strings (case-insensitive, whitespace trimmed) and rounds floats
            # (e.g. BPM within ±0.5 is considered concordant rather than conflicting)
            unique_normalized_vals = set()
            for v in source_vals.values():
                if isinstance(v, (int, float)):
                    # For BPM allow 0.5 threshold difference
                    unique_normalized_vals.add(round(float(v), 0) if fld == "bpm" else v)
                else:
                    unique_normalized_vals.add(str(v).strip().lower())

            has_conflict = len(unique_normalized_vals) > 1

            # --- Consensus Recommendation Algorithm ---
            # 1. Authority Hierarchy Priority (Discogs primary for year, label, catno, format, artist)
            recommended: Any = None
            if source_vals:
                priority_list = cls.FIELD_AUTHORITY_PRIORITY.get(fld, cls.DEFAULT_SOURCE_PRIORITY)
                for p_src in priority_list:
                    if p_src in source_vals:
                        recommended = source_vals[p_src]
                        break

                # 2. If not found in priority sources, pick most common via frequency vote
                if recommended is None:
                    counts = Counter([str(v).strip() for v in source_vals.values() if v])
                    most_common = counts.most_common(1)
                    if most_common:
                        # Find original representation matching most common
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
