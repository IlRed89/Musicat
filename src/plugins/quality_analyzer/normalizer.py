"""
Audio Volume Normalizer & ReplayGain Tagging Engine.

Provides:
1. Non-destructive ReplayGain / Sound Check tagging:
   - Writes REPLAYGAIN_TRACK_GAIN and REPLAYGAIN_TRACK_PEAK metadata
   - Generates Apple iTunNORM Sound Check hex tags
   - Updates SQLite database without modifying PCM stream
2. Physical Normalization (FFmpeg loudnorm Two-Pass / De-Clipping):
   - Two-pass ITU-R BS.1770 / EBU R128 loudness normalization
   - Target parameters: I = -10.0 LUFS (configurable), TP = -1.0 dBTP headroom, LRA = 7.0 LU
   - Creates '_fixed.ext' or backs up to '_original/' before overwriting
   - Preserves high quality encoding (320kbps MP3 or lossless PCM).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from src.core.db import Database
from src.tags.editor import AudioTagEditor
from .analyzer import AcousticQualityAnalyzer, QualityReport


@dataclass
class NormalizationResult:
    """Result of track volume normalization or ReplayGain tagging."""

    filepath: str
    output_filepath: str
    mode: str  # "replaygain" or "ffmpeg_loudnorm"
    original_lufs: float
    target_lufs: float
    gain_applied_db: float
    success: bool
    backup_path: Optional[str] = None
    error_message: Optional[str] = None


class VolumeNormalizer:
    """Orchestrates non-destructive metadata tagging and physical loudnorm re-encoding."""

    DEFAULT_TARGET_LUFS = -10.0  # DJ Club baseline
    DEFAULT_MAX_TRUE_PEAK = -1.0  # -1.0 dBTP safety headroom to prevent DAC inter-sample clipping
    DEFAULT_TARGET_LRA = 7.0

    def __init__(self, db: Optional[Database] = None, ffmpeg_path: str = "ffmpeg") -> None:
        self.db = db
        self.ffmpeg_path = ffmpeg_path

    # -------------------------------------------------------------
    # Strategy A: Non-Destructive ReplayGain Tagging
    # -------------------------------------------------------------
    def apply_replaygain(
        self,
        filepath: str,
        target_lufs: float = DEFAULT_TARGET_LUFS,
        report: Optional[QualityReport] = None,
    ) -> NormalizationResult:
        """Calculates differential gain offset and writes ReplayGain tags.

        Args:
            filepath: Path to the target audio file.
            target_lufs: Target reference loudness (e.g. -10.0 LUFS or -14.0 LUFS).
            report: Pre-calculated QualityReport, or None to analyze immediately.

        Returns:
            NormalizationResult with details of tags written.
        """
        p = Path(filepath)
        if not p.exists():
            return NormalizationResult(
                filepath=filepath,
                output_filepath=filepath,
                mode="replaygain",
                original_lufs=-70.0,
                target_lufs=target_lufs,
                gain_applied_db=0.0,
                success=False,
                error_message=f"File not found: {filepath}",
            )

        try:
            if report is None:
                report = AcousticQualityAnalyzer.analyze_file(filepath, target_lufs=target_lufs)

            gain_db = target_lufs - report.integrated_lufs
            peak_linear = 10.0 ** (report.true_peak_dbtp / 20.0) if report.true_peak_dbtp > -100.0 else 0.0

            # 1. Format standard ReplayGain strings
            gain_str = f"{gain_db:+.2f} dB"
            peak_str = f"{peak_linear:.6f}"

            # 2. Write metadata tags via AudioTagEditor / Mutagen
            tags = {
                "replaygain_track_gain": gain_str,
                "replaygain_track_peak": peak_str,
                "r128_track_gain": str(int(round(gain_db * 256))),  # Q7.8 fixed point for R128
            }
            AudioTagEditor.write_metadata(filepath, tags)

            # 3. Write Apple Sound Check iTunNORM tag if supported (M4A/MP3)
            self._write_itunnorm_soundcheck(filepath, gain_db, peak_linear)

            # 4. Synchronize SQLite database
            if self.db:
                db_updates = {
                    "lufs": report.integrated_lufs,
                    "true_peak": report.true_peak_dbtp,
                    "lra": report.loudness_range_lra,
                    "audio_status": report.status,
                    "replaygain_track_gain": gain_str,
                    "replaygain_track_peak": peak_str,
                }
                self.db.update_track_tags(filepath, db_updates)

            return NormalizationResult(
                filepath=filepath,
                output_filepath=filepath,
                mode="replaygain",
                original_lufs=report.integrated_lufs,
                target_lufs=target_lufs,
                gain_applied_db=gain_db,
                success=True,
            )

        except Exception as exc:
            return NormalizationResult(
                filepath=filepath,
                output_filepath=filepath,
                mode="replaygain",
                original_lufs=report.integrated_lufs if report else -70.0,
                target_lufs=target_lufs,
                gain_applied_db=0.0,
                success=False,
                error_message=str(exc),
            )

    def _write_itunnorm_soundcheck(self, filepath: str, gain_db: float, peak_linear: float) -> None:
        """Writes Apple Sound Check 'iTunNORM' hex metadata for native DJ gear compatibility."""
        try:
            import mutagen
            from mutagen.id3 import COMM, ID3
            from mutagen.mp4 import MP4

            p = Path(filepath)
            ext = p.suffix.lower()

            # Apple 1000 = -10 dBFS reference standard
            # 1000 * 10^(-gain_db / 10)
            power = 10.0 ** (-gain_db / 10.0)
            val = int(round(1000.0 * power))
            hex_val = f"{val:08X}"
            peak_val = int(round(peak_linear * 32767.0))
            hex_peak = f"{peak_val:08X}"

            itunnorm_str = f" 00000{hex_val} 00000{hex_val} 0000{hex_peak} 0000{hex_peak} 00000000 00000000 00000000 00000000 00000000 00000000"

            if ext == ".mp3":
                audio = ID3(filepath)
                audio.add(COMM(encoding=3, lang="eng", desc="iTunNORM", text=[itunnorm_str]))
                audio.save(filepath)
            elif ext in (".m4a", ".aac"):
                mp4 = MP4(filepath)
                mp4["----:com.apple.iTunes:iTunNORM"] = itunnorm_str.encode("utf-8")
                mp4.save(filepath)
        except Exception:
            pass

    # -------------------------------------------------------------
    # Strategy B: Physical Re-Encoding with FFmpeg loudnorm
    # -------------------------------------------------------------
    def apply_physical_loudnorm(
        self,
        filepath: str,
        target_lufs: float = DEFAULT_TARGET_LUFS,
        max_true_peak: float = DEFAULT_MAX_TRUE_PEAK,
        target_lra: float = DEFAULT_TARGET_LRA,
        create_backup: bool = True,
        save_as_fixed: bool = False,
        output_filepath: Optional[str] = None,
    ) -> NormalizationResult:
        """Applies physical Two-Pass EBU R128 loudnorm filtering via FFmpeg, encoding to MP3 320kbps.

        Args:
            filepath: Path to the audio file.
            target_lufs: Integrated loudness target (default -10.0 LUFS).
            max_true_peak: Maximum true peak safety ceiling (default -1.0 dBTP).
            target_lra: Target loudness range (default 7.0 LU).
            create_backup: If True, copies original file to '_original/' when overwriting.
            save_as_fixed: If True, saves to 'filename_normalized.mp3' instead of overwriting.
            output_filepath: Optional explicit path for exported file.

        Returns:
            NormalizationResult with output file path and status.
        """
        src_path = Path(filepath).resolve()
        if not src_path.exists():
            return NormalizationResult(
                filepath=filepath,
                output_filepath=filepath,
                mode="ffmpeg_loudnorm",
                original_lufs=-70.0,
                target_lufs=target_lufs,
                gain_applied_db=0.0,
                success=False,
                error_message=f"File not found: {filepath}",
            )

        # Check FFmpeg availability
        ffmpeg_bin = self._find_ffmpeg_executable()
        if not ffmpeg_bin:
            # Fallback to pure Python linear peak limiter
            return self._apply_python_pcm_normalizer(
                filepath, target_lufs, max_true_peak, save_as_fixed, create_backup, output_filepath
            )

        # Output target determination: physical normalization exports as MP3
        if output_filepath:
            out_path = Path(output_filepath).resolve()
            backup_path = None
        elif save_as_fixed:
            out_path = src_path.parent / f"{src_path.stem}_normalized.mp3"
            backup_path = None
        else:
            out_path = src_path.parent / f"{src_path.stem}_tmp_norm.mp3"
            backup_path = src_path.parent / "_original" / src_path.name if create_backup else None

        try:
            # ---------------------------------------------------------
            # PASS 1: Measurement pass with loudnorm filter
            # ---------------------------------------------------------
            cmd_pass1 = [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-i",
                str(src_path),
                "-af",
                f"loudnorm=I={target_lufs}:TP={max_true_peak}:LRA={target_lra}:print_format=json",
                "-f",
                "null",
                "-",
            ]

            proc1 = subprocess.run(cmd_pass1, capture_output=True, text=True, timeout=120)
            stdout_stderr = proc1.stderr + "\n" + proc1.stdout
            stats = self._parse_loudnorm_json(stdout_stderr)

            # ---------------------------------------------------------
            # PASS 2: Application pass with linear normalization
            # ---------------------------------------------------------
            if stats:
                filter_str = (
                    f"loudnorm=I={target_lufs}:TP={max_true_peak}:LRA={target_lra}:"
                    f"measured_I={stats.get('input_i', target_lufs)}:"
                    f"measured_TP={stats.get('input_tp', max_true_peak)}:"
                    f"measured_LRA={stats.get('input_lra', target_lra)}:"
                    f"measured_thresh={stats.get('input_thresh', -20.0)}:"
                    f"offset={stats.get('target_offset', 0.0)}:linear=true"
                )
            else:
                filter_str = f"loudnorm=I={target_lufs}:TP={max_true_peak}:LRA={target_lra}"

            # Encode directly to MP3 320k (libmp3lame) or match explicit extension
            if out_path.suffix.lower() == ".mp3":
                codec_args = ["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"]
            else:
                codec_args = self._get_codec_arguments(out_path.suffix.lower())

            cmd_pass2 = [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-i",
                str(src_path),
                "-af",
                filter_str,
            ] + codec_args + [str(out_path)]

            proc2 = subprocess.run(cmd_pass2, capture_output=True, text=True, timeout=180)
            if proc2.returncode != 0 or not out_path.exists():
                raise RuntimeError(f"FFmpeg loudnorm failed: {proc2.stderr[:300]}")

            final_output = str(out_path)

            # Overwrite logic with safety backup
            if not save_as_fixed and not output_filepath:
                if create_backup and backup_path:
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_path), str(backup_path))

                if src_path.suffix.lower() == ".mp3":
                    out_path.replace(src_path)
                    final_output = str(src_path)
                else:
                    target_mp3 = src_path.with_suffix(".mp3")
                    out_path.replace(target_mp3)
                    try:
                        if target_mp3 != src_path and src_path.exists():
                            src_path.unlink()
                    except Exception:
                        pass
                    final_output = str(target_mp3)

            # Preserve and copy original ID3 tags and cover artwork
            self._copy_tags_and_artwork(src_path, Path(final_output))

            # Auto-index into SQLite database immediately so table has full metadata
            if self.db:
                try:
                    from ...core.scanner import LibraryScanner
                    scanner = LibraryScanner(self.db)
                    scanner.scan_file(final_output)
                except Exception:
                    pass

            # Analyze normalized file to get post-loudnorm metrics
            post_report = AcousticQualityAnalyzer.analyze_file(final_output, target_lufs=target_lufs)

            if self.db:
                self.db.update_track_tags(
                    final_output,
                    {
                        "lufs": post_report.integrated_lufs,
                        "true_peak": post_report.true_peak_dbtp,
                        "lra": post_report.loudness_range_lra,
                        "audio_status": post_report.status,
                    },
                )

            return NormalizationResult(
                filepath=str(src_path),
                output_filepath=final_output,
                mode="ffmpeg_loudnorm",
                original_lufs=float(stats.get("input_i", -14.0)) if stats else -14.0,
                target_lufs=target_lufs,
                gain_applied_db=target_lufs - float(stats.get("input_i", target_lufs)) if stats else 0.0,
                success=True,
                backup_path=str(backup_path) if backup_path and backup_path.exists() else None,
            )

        except Exception as exc:
            # Clean up temp file on failure
            if not save_as_fixed and not output_filepath and out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass

            return NormalizationResult(
                filepath=str(src_path),
                output_filepath=str(src_path),
                mode="ffmpeg_loudnorm",
                original_lufs=-70.0,
                target_lufs=target_lufs,
                gain_applied_db=0.0,
                success=False,
                error_message=str(exc),
            )

    def _copy_tags_and_artwork(self, src_path: Path, dst_path: Path) -> None:
        """Transfers all metadata tags and album cover art intact from source audio to exported MP3."""
        try:
            # 1. Read metadata from source
            meta = AudioTagEditor.read_metadata(src_path)
            tags_dict = meta.to_dict()

            # Ensure essential fallback fields are populated
            if not tags_dict.get("title") or not str(tags_dict.get("title")).strip():
                stem = src_path.stem
                if " - " in stem:
                    parts = stem.split(" - ", 1)
                    tags_dict["title"] = parts[1].strip()
                    if not tags_dict.get("artist") or not str(tags_dict.get("artist")).strip():
                        tags_dict["artist"] = parts[0].strip()
                else:
                    tags_dict["title"] = stem

            if not tags_dict.get("artist") or not str(tags_dict.get("artist")).strip():
                tags_dict["artist"] = "-"

            # Write tags to destination
            AudioTagEditor.write_metadata(dst_path, tags_dict)

            # 2. Extract and write album cover art
            cover = AudioTagEditor.get_artwork(src_path)
            if cover and cover.data:
                AudioTagEditor.set_artwork(
                    dst_path,
                    cover.data,
                    mime_type=cover.mime_type or "image/jpeg",
                    description=cover.description or "Front Cover",
                )
        except Exception:
            pass

    def _find_ffmpeg_executable(self) -> Optional[str]:
        """Resolves path to working ffmpeg executable."""
        # 1. Custom path configured
        if self.ffmpeg_path and shutil.which(self.ffmpeg_path):
            return self.ffmpeg_path

        # 2. PATH resolution
        found = shutil.which("ffmpeg")
        if found:
            return found

        # 3. Application directory / bundled / portable bin
        try:
            from ...core.path_resolver import PathResolver
            app_root = PathResolver.get_app_root()
            app_candidates = [
                app_root / "bin" / "ffmpeg.exe",
                app_root / "ffmpeg.exe",
                Path(sys.executable).parent / "bin" / "ffmpeg.exe",
                Path(sys.executable).parent / "ffmpeg.exe",
            ]
            for c in app_candidates:
                if c.exists():
                    return str(c)
        except Exception:
            pass

        # 4. Common Windows locations & Winget Packages
        if sys.platform == "win32":
            candidates = [
                Path(__file__).resolve().parents[3] / "bin" / "ffmpeg.exe",
                Path("C:/ffmpeg/bin/ffmpeg.exe"),
                Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
                Path.home() / "scoop/shims/ffmpeg.exe",
                Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe",
            ]
            winget_pkgs = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
            if winget_pkgs.exists():
                for found_ff in winget_pkgs.glob("**/ffmpeg.exe"):
                    candidates.append(found_ff)
                    break

            for c in candidates:
                if c.exists():
                    return str(c)

        return None

    def _parse_loudnorm_json(self, output: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON output block from FFmpeg loudnorm first pass."""
        try:
            start_idx = output.rfind("{")
            end_idx = output.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = output[start_idx : end_idx + 1]
                data = json.loads(json_str)
                return {k: float(v) for k, v in data.items() if isinstance(v, (int, float, str)) and v.replace(".", "", 1).replace("-", "", 1).isdigit()}
        except Exception:
            pass
        return None

    def _get_codec_arguments(self, ext: str) -> List[str]:
        """Returns optimal encoding parameters preserving source format and high quality."""
        if ext == ".mp3":
            return ["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"]
        elif ext in (".flac", ".wav", ".aif", ".aiff"):
            return ["-c:a", "flac" if ext == ".flac" else "pcm_s16le"]
        elif ext in (".m4a", ".aac"):
            return ["-c:a", "aac", "-b:a", "320k"]
        elif ext == ".ogg":
            return ["-c:a", "libvorbis", "-qscale:a", "8"]
        return ["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100"]

    def _apply_python_pcm_normalizer(
        self,
        filepath: str,
        target_lufs: float = DEFAULT_TARGET_LUFS,
        max_true_peak: float = DEFAULT_MAX_TRUE_PEAK,
        save_as_fixed: bool = True,
        create_backup: bool = True,
        output_filepath: Optional[str] = None,
    ) -> NormalizationResult:
        """Pure Python fallback for volume normalization if FFmpeg is not installed."""
        try:
            import scipy.io.wavfile as wavfile
            from src.audio.analyzer import AcousticAnalyzer

            src_path = Path(filepath)
            report = AcousticQualityAnalyzer.analyze_file(filepath, target_lufs=target_lufs)
            gain_db = target_lufs - report.integrated_lufs
            linear_gain = 10.0 ** (gain_db / 20.0)

            signal, sr = AcousticQualityAnalyzer.read_audio(filepath)
            if signal is None:
                raise ValueError("Could not read PCM audio data")

            # Apply linear gain
            scaled = signal * linear_gain

            # Soft-knee peak ceiling limiter to avoid clipping
            ceiling_linear = 10.0 ** (max_true_peak / 20.0)
            max_val = np.max(np.abs(scaled)) if len(scaled) > 0 else 1.0
            if max_val > ceiling_linear:
                scaled = np.tanh(scaled / ceiling_linear) * ceiling_linear

            # Save as normalized file
            if output_filepath:
                out_path = Path(output_filepath).resolve()
            elif save_as_fixed:
                out_path = src_path.parent / f"{src_path.stem}_fixed.wav"
            else:
                out_path = src_path.parent / f"{src_path.stem}_tmp.wav"

            # Convert to int16 for WAV storage
            int16_audio = (scaled * 32767.0).astype(np.int16)

            # If out_path is .mp3 and we have ffmpeg, write temp wav and encode
            ffmpeg_bin = self._find_ffmpeg_executable()
            if out_path.suffix.lower() == ".mp3" and ffmpeg_bin:
                tmp_wav = src_path.parent / f"{src_path.stem}_tmp_encode.wav"
                wavfile.write(str(tmp_wav), sr, int16_audio)
                subprocess.run([ffmpeg_bin, "-y", "-i", str(tmp_wav), "-c:a", "libmp3lame", "-b:a", "320k", str(out_path)], capture_output=True)
                try:
                    tmp_wav.unlink()
                except Exception:
                    pass
            else:
                # If mp3 cannot be encoded without ffmpeg, write wav
                if out_path.suffix.lower() == ".mp3":
                    out_path = out_path.with_suffix(".wav")
                wavfile.write(str(out_path), sr, int16_audio)

            if not save_as_fixed and not output_filepath:
                if create_backup:
                    backup_path = src_path.parent / "_original" / src_path.name
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_path), str(backup_path))
                out_path.replace(src_path)
                out_path = src_path

            self._copy_tags_and_artwork(src_path, Path(out_path))

            if self.db:
                try:
                    from ...core.scanner import LibraryScanner
                    LibraryScanner(self.db).scan_file(str(out_path))
                except Exception:
                    pass

            return NormalizationResult(
                filepath=filepath,
                output_filepath=str(out_path),
                mode="python_pcm",
                original_lufs=report.integrated_lufs,
                target_lufs=target_lufs,
                gain_applied_db=gain_db,
                success=True,
            )

        except Exception as exc:
            return NormalizationResult(
                filepath=filepath,
                output_filepath=filepath,
                mode="python_pcm",
                original_lufs=-70.0,
                target_lufs=target_lufs,
                gain_applied_db=0.0,
                success=False,
                error_message=str(exc),
            )
