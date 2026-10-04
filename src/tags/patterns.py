"""
Pattern Engine for Musicat.
Provides Mp3tag-compatible conversions:
- Filename -> Tag
- Tag -> Filename
- Tag -> Tag manipulations
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple


# Mapping of pattern placeholder to normalized metadata key
TAG_PATTERNS = {
    "%artist%": "artist",
    "%title%": "title",
    "%album%": "album",
    "%albumartist%": "album_artist",
    "%album artist%": "album_artist",
    "%year%": "year",
    "%genre%": "genre",
    "%track%": "track_num",
    "%tracknum%": "track_num",
    "%totaltracks%": "total_tracks",
    "%disc%": "disc_num",
    "%bpm%": "bpm",
    "%key%": "musical_key",
    "%musicalkey%": "musical_key",
    "%camelot%": "camelot_key",
    "%camelotkey%": "camelot_key",
    "%initialkey%": "camelot_key",
    "%label%": "label",
    "%remixer%": "remixer",
    "%comment%": "comment",
    "%energy%": "energy_level",
    "%energylevel%": "energy_level",
}

# Regex to find all %placeholder% tokens
TOKEN_REGEX = re.compile(r"%([a-zA-Z0-9_\s]+)%")

# Windows invalid filename characters
INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str, allow_separators: bool = False) -> str:
    """Sanitizes a string for use as a valid Windows filename."""
    if allow_separators:
        # Allow / and \ for path structures
        clean = re.sub(r'[<>:"|?*]', "_", name)
    else:
        clean = INVALID_WIN_CHARS.sub("_", name)
    # Strip trailing dots and spaces (Windows restriction)
    clean = clean.strip(". ")
    return clean if clean else "Untitled"


class PatternEngine:
    """Mp3tag-style pattern engine for bidirectional tag conversions."""

    @classmethod
    def compile_filename_pattern(cls, pattern: str) -> Tuple[re.Pattern, List[str]]:
        """
        Converts a pattern like '%artist% - %title% (%bpm% BPM)'
        into a regular expression capturing groups.
        """
        # Normalize Mp3tag-style $num(%token%, digits) to %token%
        normalized_pattern = re.sub(r"\$num\(%([a-zA-Z0-9_\s]+)%,\s*\d+\)", r"%\1%", pattern, flags=re.IGNORECASE)

        keys_order = []

        # Split pattern by tokens and escape literal text
        regex_parts = []
        last_end = 0
        for match in TOKEN_REGEX.finditer(normalized_pattern):
            literal = normalized_pattern[last_end : match.start()]
            regex_parts.append(re.escape(literal))
            token = match.group(0).lower()
            key = TAG_PATTERNS.get(token)
            if key:
                keys_order.append(key)
                if key in ("year", "track_num", "total_tracks", "disc_num", "energy_level"):
                    regex_parts.append(r"(\d+)")
                elif key == "bpm":
                    regex_parts.append(r"(\d+(?:\.\d+)?)")
                else:
                    regex_parts.append(r"(.+?)")
            else:
                regex_parts.append(re.escape(match.group(0)))
            last_end = match.end()

        regex_parts.append(re.escape(normalized_pattern[last_end:]))
        full_regex = "^" + "".join(regex_parts) + "$"
        return re.compile(full_regex, re.IGNORECASE), keys_order

    @classmethod
    def parse_filename_to_tags(cls, filename_or_path: str, pattern: str) -> Optional[Dict[str, Any]]:
        """
        Extracts metadata dictionary from filename or path according to pattern.
        """
        # If pattern has no path separators, match against filename only (without extension)
        has_slash = "/" in pattern or "\\" in pattern
        clean_input = filename_or_path
        if not has_slash:
            base = os.path.basename(filename_or_path)
            clean_input = os.path.splitext(base)[0]
        else:
            # Normalize path slashes
            clean_input = filename_or_path.replace("\\", "/")
            pattern = pattern.replace("\\", "/")
            # Strip extension from input if pattern doesn't end with extension
            if not pattern.endswith((".mp3", ".flac", ".wav", ".aiff", ".m4a", ".ogg")):
                clean_input = os.path.splitext(clean_input)[0]

        compiled_re, keys_order = cls.compile_filename_pattern(pattern)
        m = compiled_re.match(clean_input)
        if not m:
            return None

        result: Dict[str, Any] = {}
        for idx, key in enumerate(keys_order):
            raw_val = m.group(idx + 1).strip()
            if key in ("year", "track_num", "total_tracks", "disc_num", "energy_level"):
                result[key] = int(raw_val) if raw_val.isdigit() else None
            elif key == "bpm":
                try:
                    result[key] = float(raw_val)
                except ValueError:
                    result[key] = None
            else:
                result[key] = raw_val

        return result

    @classmethod
    def format_tags_to_filename(cls, tags: Dict[str, Any], pattern: str, extension: str = "") -> str:
        """
        Generates a filename or relative directory path from metadata tags and pattern.
        """
        has_slash = "/" in pattern or "\\" in pattern

        # Expand Mp3tag $num(%token%, digits) functions first
        def num_replacer(m: re.Match) -> str:
            token = m.group(1).lower()
            digits = int(m.group(2))
            key = TAG_PATTERNS.get(f"%{token}%")
            if not key:
                return m.group(0)
            val = tags.get(key)
            if val is None or val == "":
                return ""
            try:
                num_val = int(val)
                return f"{num_val:0{digits}d}"
            except (ValueError, TypeError):
                return str(val)

        pattern = re.sub(r"\$num\(%([a-zA-Z0-9_\s]+)%,\s*(\d+)\)", num_replacer, pattern, flags=re.IGNORECASE)

        def replacer(match):
            token = match.group(0).lower()
            key = TAG_PATTERNS.get(token)
            if not key:
                return match.group(0)

            val = tags.get(key)
            if val is None or val == "":
                return ""
            if key == "bpm" and isinstance(val, (int, float)):
                # If integer float like 128.0, format as 128 or 128.0 depending on value
                return f"{val:.1f}".rstrip("0").rstrip(".") if isinstance(val, float) else str(val)
            if key == "track_num" and isinstance(val, int):
                return f"{val:02d}"
            return str(val)

        formatted = TOKEN_REGEX.sub(replacer, pattern)

        # Sanitize parts while keeping folder structure intact if slashes are present
        if has_slash:
            parts = re.split(r"[\\/]", formatted)
            sanitized_parts = [sanitize_filename(p) for p in parts if p.strip()]
            final_path = os.sep.join(sanitized_parts)
        else:
            final_path = sanitize_filename(formatted)

        if extension:
            ext = "." + extension.lstrip(".")
            if not final_path.lower().endswith(ext.lower()):
                final_path += ext

        return final_path

    @classmethod
    def apply_tag_to_tag(cls, source_record: Dict[str, Any], rule_type: str, source_field: str, dest_field: str, format_template: str = "") -> Dict[str, Any]:
        """
        Copies, swaps, or combines fields:
        - rule_type: 'copy', 'swap', 'combine'
        """
        updated = dict(source_record)
        if rule_type == "copy":
            if source_field in updated:
                updated[dest_field] = updated[source_field]
        elif rule_type == "swap":
            val_a = updated.get(source_field)
            val_b = updated.get(dest_field)
            updated[source_field] = val_b
            updated[dest_field] = val_a
        elif rule_type == "combine":
            if format_template:
                # E.g. template '%artist% (%label%)' -> dest_field
                val = cls.format_tags_to_filename(updated, format_template)
                updated[dest_field] = val
        return updated
