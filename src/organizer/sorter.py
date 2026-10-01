"""
Smart Organizer & File Dispatcher for Musicat.
Sorts tracks into organized physical directories based on Year, Genre, BPM Range,
Camelot Wheel Key, or custom folder hierarchy patterns with Dry Run preview.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..tags.editor import AudioTagEditor, SUPPORTED_EXTENSIONS
from ..tags.patterns import sanitize_filename, PatternEngine


@dataclass
class SortPlanItem:
    source_path: str
    target_path: str
    relative_target: str
    action: str  # 'copy' or 'move'
    status: str  # 'OK', 'COLLISION', 'MISSING_TAG', 'SKIPPED', 'ERROR'
    message: str = ""
    tags: Dict[str, Any] = None


class SmartOrganizer:
    """Dispatches and reorganizes audio files across physical folder structures."""

    PRESET_RULES = {
        "genre_artist": "{genre}/{artist} - {title}{ext}",
        "year_artist": "{year}/{artist} - {title}{ext}",
        "bpm_range": "BPM {bpm_range}/{artist} - {title}{ext}",
        "camelot_key": "Key {camelot_key}/{artist} - {title}{ext}",
        "genre_bpm": "{genre}/BPM {bpm_range}/{artist} - {title}{ext}",
        "genre_year_bpm": "{genre}/{year}/BPM {bpm_range}/{artist} - {title}{ext}",
        "camelot_bpm": "Key {camelot_key}/BPM {bpm_range}/{artist} - {title}{ext}",
        "artist_album": "{artist}/{album}/{track_num} - {title}{ext}",
    }

    @staticmethod
    def get_bpm_range(bpm: Optional[float], step: int = 5) -> str:
        """
        Calculates bucket for BPM.
        Example: 124 BPM with step 5 -> '120-124'
        """
        if bpm is None or bpm <= 0:
            return "Unknown BPM"
        bpm_int = int(round(bpm))
        lower = (bpm_int // step) * step
        upper = lower + (step - 1)
        return f"{lower}-{upper} BPM"

    @classmethod
    def resolve_target_path(
        cls,
        tags: Dict[str, Any],
        dest_dir: str,
        rule_pattern: str,
        ext: str,
        bpm_step: int = 5,
    ) -> Tuple[str, str, List[str]]:
        """
        Resolves destination path from tags and rule pattern.
        Returns: (absolute_target_path, relative_target_path, missing_tags_list)
        """
        missing: List[str] = []

        artist = tags.get("artist") or "Unknown Artist"
        title = tags.get("title") or Path(tags.get("filepath", "Unknown")).stem
        album = tags.get("album") or "Unknown Album"
        year = str(tags.get("year")) if tags.get("year") else "Unknown Year"
        genre = tags.get("genre") or "Unknown Genre"
        bpm_val = tags.get("bpm")
        bpm_str = f"{bpm_val:.1f}" if bpm_val else "0"
        bpm_range = cls.get_bpm_range(bpm_val, bpm_step)
        camelot = tags.get("camelot_key") or "Unknown Key"
        musical_key = tags.get("musical_key") or "Unknown"
        track_num = f"{tags.get('track_num'):02d}" if tags.get("track_num") else "01"
        label = tags.get("label") or "Unknown Label"
        remixer = tags.get("remixer") or ""

        # Check for missing essential tags in rule
        if "{artist}" in rule_pattern and not tags.get("artist"):
            missing.append("artist")
        if "{title}" in rule_pattern and not tags.get("title"):
            missing.append("title")
        if "{year}" in rule_pattern and not tags.get("year"):
            missing.append("year")
        if "{genre}" in rule_pattern and not tags.get("genre"):
            missing.append("genre")
        if ("{bpm}" in rule_pattern or "{bpm_range}" in rule_pattern) and not tags.get("bpm"):
            missing.append("bpm")
        if "{camelot_key}" in rule_pattern and not tags.get("camelot_key"):
            missing.append("camelot_key")

        # Normalize extension
        clean_ext = "." + ext.lstrip(".") if ext else ""

        # Map template variables
        variables = {
            "artist": sanitize_filename(artist),
            "title": sanitize_filename(title),
            "album": sanitize_filename(album),
            "year": sanitize_filename(year),
            "genre": sanitize_filename(genre),
            "bpm": sanitize_filename(bpm_str),
            "bpm_range": sanitize_filename(bpm_range),
            "camelot_key": sanitize_filename(camelot),
            "musical_key": sanitize_filename(musical_key),
            "track_num": track_num,
            "label": sanitize_filename(label),
            "remixer": sanitize_filename(remixer),
            "ext": clean_ext,
        }

        # Substitute tokens
        resolved_rel = rule_pattern
        for var_name, var_val in variables.items():
            resolved_rel = resolved_rel.replace(f"{{{var_name}}}", var_val)

        # Sanitize path segments
        segments = [sanitize_filename(seg) for seg in resolved_rel.replace("\\", "/").split("/") if seg]
        final_rel = os.sep.join(segments)
        final_abs = str((Path(dest_dir) / final_rel).resolve())

        return final_abs, final_rel, missing

    @classmethod
    def build_plan(
        cls,
        source_items: List[Union[str, Dict[str, Any]]],
        dest_dir: str,
        rule_pattern: str,
        action: str = "copy",  # 'copy' or 'move'
        bpm_step: int = 5,
        collision_mode: str = "rename",  # 'rename', 'overwrite', 'skip'
    ) -> List[SortPlanItem]:
        """
        Generates a Dry Run plan for sorting tracks.
        source_items can be a list of filepaths or track dictionaries from DB.
        """
        plan: List[SortPlanItem] = []
        dest_root = Path(dest_dir).resolve()

        planned_destinations: Dict[str, int] = {}

        for item in source_items:
            if isinstance(item, str):
                src_path = item
                tags = AudioTagEditor.read_metadata(src_path).to_dict()
            else:
                src_path = item.get("filepath", "")
                tags = dict(item)

            if not src_path or not Path(src_path).exists():
                plan.append(
                    SortPlanItem(
                        source_path=src_path,
                        target_path="",
                        relative_target="",
                        action=action,
                        status="ERROR",
                        message="Source file does not exist",
                        tags=tags,
                    )
                )
                continue

            ext = Path(src_path).suffix
            target_abs, target_rel, missing = cls.resolve_target_path(
                tags=tags,
                dest_dir=str(dest_root),
                rule_pattern=rule_pattern,
                ext=ext,
                bpm_step=bpm_step,
            )

            status = "OK"
            msg = ""

            if missing:
                status = "MISSING_TAG"
                msg = f"Missing tags: {', '.join(missing)}"

            # Check collision
            target_obj = Path(target_abs)
            has_existing = target_obj.exists() or (target_abs in planned_destinations)

            if has_existing:
                if collision_mode == "skip":
                    status = "SKIPPED"
                    msg = "File exists in target location (Skipped)"
                elif collision_mode == "overwrite":
                    status = "COLLISION"
                    msg = "File will overwrite existing destination"
                elif collision_mode == "rename":
                    # Generate auto-incremented filename
                    parent_dir = target_obj.parent
                    stem = target_obj.stem
                    suffix = target_obj.suffix

                    counter = 1
                    candidate = parent_dir / f"{stem} ({counter}){suffix}"
                    while candidate.exists() or str(candidate) in planned_destinations:
                        counter += 1
                        candidate = parent_dir / f"{stem} ({counter}){suffix}"

                    target_abs = str(candidate)
                    target_rel = str(candidate.relative_to(dest_root))
                    status = "COLLISION"
                    msg = f"Collision resolved with auto-rename ({counter})"

            planned_destinations[target_abs] = 1

            plan.append(
                SortPlanItem(
                    source_path=src_path,
                    target_path=target_abs,
                    relative_target=target_rel,
                    action=action,
                    status=status,
                    message=msg,
                    tags=tags,
                )
            )

        return plan

    @classmethod
    def execute_plan(
        cls,
        plan: List[SortPlanItem],
        progress_callback: Optional[Callable[[int, int, SortPlanItem], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the planned copy/move operations physically on disk.
        Returns summary statistics: {'success': N, 'skipped': S, 'failed': F, 'errors': [...]}
        """
        total = len(plan)
        success = 0
        skipped = 0
        failed = 0
        errors = []

        for idx, item in enumerate(plan):
            if progress_callback:
                progress_callback(idx + 1, total, item)

            if item.status == "SKIPPED":
                skipped += 1
                continue
            if item.status == "ERROR" or not item.target_path:
                failed += 1
                continue

            try:
                src = Path(item.source_path)
                dst = Path(item.target_path)

                # Ensure destination folder exists
                dst.parent.mkdir(parents=True, exist_ok=True)

                if item.action == "move":
                    shutil.move(str(src), str(dst))
                else:  # copy
                    shutil.copy2(str(src), str(dst))

                success += 1
            except Exception as e:
                failed += 1
                errors.append({"item": item.source_path, "error": str(e)})

        return {
            "total": total,
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
        }
