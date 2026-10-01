"""
Audio Quality Normalizer & Distortion Detector Plugin for Musicat.

Modular EBU R128 / ITU-R BS.1770 diagnostic analyzer and loudness normalizer.
Supports ReplayGain tagging and physical FFmpeg loudnorm re-encoding.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.plugins.base import BasePlugin
from .analyzer import AcousticQualityAnalyzer, QualityReport
from .normalizer import VolumeNormalizer, NormalizationResult


class AudioQualityNormalizerPlugin(BasePlugin):
    """Native Musicat plugin for audio quality diagnostics and loudness normalization."""

    @property
    def plugin_id(self) -> str:
        return "audio_quality_normalizer"

    @property
    def name(self) -> str:
        return "Audio Quality & Loudnorm Assistant"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def author(self) -> str:
        return "Musicat DSP Team"

    @property
    def description(self) -> str:
        return (
            "Diagnostica acustica EBU R128 / ITU-R BS.1770-4 (LUFS, True Peak dBTP, LRA), "
            "rilevamento clipping/distorsione e correzione del volume (ReplayGain o FFmpeg loudnorm)."
        )

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "target_lufs",
                "label": "Target Loudness (LUFS)",
                "type": "choice",
                "default": "-10.0 LUFS (DJ Club)",
                "choices": [
                    "-10.0 LUFS (DJ Club)",
                    "-14.0 LUFS (Streaming/AES)",
                    "-16.0 LUFS (Apple/Podcast)",
                    "-23.0 LUFS (EBU R128 Broadcast)",
                ],
                "description": "Livello target di riferimento per DJ mix o broadcast",
            },
            {
                "key": "max_true_peak",
                "label": "True Peak Limiter (dBTP)",
                "type": "choice",
                "default": "-1.0 dBTP (Standard Headroom)",
                "choices": [
                    "-1.0 dBTP (Standard Headroom)",
                    "-0.5 dBTP (Club Push)",
                    "-2.0 dBTP (Broadcast Sicuro)",
                ],
                "description": "Soglia di sicurezza per evitare clipping inter-sample nei convertitori DAC",
            },
            {
                "key": "correction_mode",
                "label": "Modalità di Normalizzazione Preferita",
                "type": "choice",
                "default": "ReplayGain Non Distruttivo (Tagging)",
                "choices": [
                    "ReplayGain Non Distruttivo (Tagging)",
                    "FFmpeg loudnorm (Genera file _fixed)",
                    "FFmpeg loudnorm (Sovrascrivi con backup _original)",
                ],
                "description": "Strategia predefinita applicata dal pulsante rapido nel player",
            },
            {
                "key": "auto_scan_quality",
                "label": "Analizza qualità durante la scansione libreria",
                "type": "bool",
                "default": False,
                "description": "Calcola metriche EBU R128 durante l'indicizzazione dei file",
            },
            {
                "key": "ffmpeg_path",
                "label": "Percorso Eseguibile FFmpeg",
                "type": "str",
                "default": "ffmpeg",
                "description": "Comando o percorso assoluto all'eseguibile FFmpeg",
            },
        ]

    @staticmethod
    def get_target_lufs(choice_str: str) -> float:
        """Extracts float LUFS value from config choice string (e.g. '-10.0 LUFS' -> -10.0)."""
        match = re.search(r"(-?\d+(?:\.\d+)?)", choice_str)
        return float(match.group(1)) if match else -10.0

    @staticmethod
    def get_max_true_peak(choice_str: str) -> float:
        """Extracts float dBTP value from config choice string (e.g. '-1.0 dBTP' -> -1.0)."""
        match = re.search(r"(-?\d+(?:\.\d+)?)", choice_str)
        return float(match.group(1)) if match else -1.0

    def initialize(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Initializes plugin and stores context references."""
        self._context = context or {}
        return True

    def run_hook(self, hook_name: str, *args, **kwargs) -> Any:
        """Dispatches audio analysis or normalization tasks."""
        if hook_name == "analyze_quality":
            filepath = args[0] if args else kwargs.get("filepath", "")
            target_lufs = kwargs.get("target_lufs", -10.0)
            return AcousticQualityAnalyzer.analyze_file(filepath, target_lufs=target_lufs)

        elif hook_name == "normalize_track":
            filepath = args[0] if args else kwargs.get("filepath", "")
            mode = kwargs.get("mode", "replaygain")
            target_lufs = kwargs.get("target_lufs", -10.0)
            db = self._context.get("db")
            normalizer = VolumeNormalizer(db=db)

            if "ffmpeg" in mode.lower():
                save_fixed = "fixed" in mode.lower()
                return normalizer.apply_physical_loudnorm(
                    filepath, target_lufs=target_lufs, save_as_fixed=save_fixed
                )
            else:
                return normalizer.apply_replaygain(filepath, target_lufs=target_lufs)

        return None


__all__ = [
    "AudioQualityNormalizerPlugin",
    "AcousticQualityAnalyzer",
    "VolumeNormalizer",
    "QualityReport",
    "NormalizationResult",
]
