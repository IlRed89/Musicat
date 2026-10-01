"""
Musicat Audio Module - Acoustic analysis, BPM/Key detection, Waveform extraction.
"""

from .analyzer import (
    AcousticAnalyzer,
    AcousticProfile,
    key_to_camelot,
    camelot_to_key,
    get_harmonic_matches,
    KEY_TO_CAMELOT,
    CAMELOT_TO_KEY,
)
from .waveform import WaveformGenerator
from .camelot import CamelotWheel, CAMELOT_KEYS_ORDERED
from .worker import (
    WorkerAnalysisResult,
    analyze_single_track,
    analyze_track_batch_worker,
    load_partial_audio_window,
    extract_high_energy_chroma,
)
from .parallel_analyzer import ParallelAnalyzer

__all__ = [
    "AcousticAnalyzer",
    "AcousticProfile",
    "key_to_camelot",
    "camelot_to_key",
    "get_harmonic_matches",
    "KEY_TO_CAMELOT",
    "CAMELOT_TO_KEY",
    "WaveformGenerator",
    "CamelotWheel",
    "CAMELOT_KEYS_ORDERED",
    "WorkerAnalysisResult",
    "analyze_single_track",
    "analyze_track_batch_worker",
    "load_partial_audio_window",
    "extract_high_energy_chroma",
    "ParallelAnalyzer",
]
