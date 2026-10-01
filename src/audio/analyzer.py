"""
Acoustic Analyzer for Musicat.
Calculates BPM (tempo autocorrelation), Musical Key & Camelot Wheel notation
(Krumhansl-Schmuckler chroma correlation), and Loudness/Peak.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks, correlate


# Standard Pitch Classes (0 = C, 1 = C#, ..., 11 = B)
PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler Key Profiles
KRUMHANSL_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KRUMHANSL_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Camelot Wheel Mapping Table
# Musical Key -> Camelot Code
KEY_TO_CAMELOT = {
    # Minor Keys (A)
    "Abm": "1A", "G#m": "1A",
    "Ebm": "2A", "D#m": "2A",
    "Bbm": "3A", "A#m": "3A",
    "Fm": "4A",
    "Cm": "5A",
    "Gm": "6A",
    "Dm": "7A",
    "Am": "8A",
    "Em": "9A",
    "Bm": "10A",
    "F#m": "11A", "Gbm": "11A",
    "Dbm": "12A", "C#m": "12A",

    # Major Keys (B)
    "B": "1B", "B maj": "1B", "Bmaj": "1B",
    "F#": "2B", "Gb": "2B", "F# maj": "2B", "Gb maj": "2B", "F#maj": "2B",
    "Db": "3B", "C#": "3B", "Db maj": "3B", "C# maj": "3B", "Dbmaj": "3B",
    "Ab": "4B", "G#": "4B", "Ab maj": "4B", "Abmaj": "4B",
    "Eb": "5B", "D#": "5B", "Eb maj": "5B", "Ebmaj": "5B",
    "Bb": "6B", "A#": "6B", "Bb maj": "6B", "Bbmaj": "6B",
    "F": "7B", "F maj": "7B", "Fmaj": "7B",
    "C": "8B", "C maj": "8B", "Cmaj": "8B",
    "G": "9B", "G maj": "9B", "Gmaj": "9B",
    "D": "10B", "D maj": "10B", "Dmaj": "10B",
    "A": "11B", "A maj": "11B", "Amaj": "11B",
    "E": "12B", "E maj": "12B", "Emaj": "12B",
}

# Reverse Mapping Camelot -> (Musical Key, Relative Musical Key)
CAMELOT_TO_KEY = {
    "1A": ("G#m", "Abm"), "1B": ("B", "B maj"),
    "2A": ("D#m", "Ebm"), "2B": ("F#", "F# maj"),
    "3A": ("A#m", "Bbm"), "3B": ("C#", "Db maj"),
    "4A": ("Fm", "F min"), "4B": ("G#", "Ab maj"),
    "5A": ("Cm", "C min"), "5B": ("D#", "Eb maj"),
    "6A": ("Gm", "G min"), "6B": ("A#", "Bb maj"),
    "7A": ("Dm", "D min"), "7B": ("F", "F maj"),
    "8A": ("Am", "A min"), "8B": ("C", "C maj"),
    "9A": ("Em", "E min"), "9B": ("G", "G maj"),
    "10A": ("Bm", "B min"), "10B": ("D", "D maj"),
    "11A": ("F#m", "F# min"), "11B": ("A", "A maj"),
    "12A": ("C#m", "C# min"), "12B": ("E", "E maj"),
}


@dataclass
class AcousticProfile:
    bpm: float
    bpm_rounded: int
    musical_key: str
    camelot_key: str
    peak_db: float
    rms_db: float
    replay_gain_db: float
    duration: float


def key_to_camelot(key_str: str) -> str:
    """Converts a standard musical key string to Camelot notation (e.g. 'Am' -> '8A')."""
    if not key_str:
        return ""
    clean = key_str.strip()
    # Normalize common variations: 'A minor' -> 'Am', 'C Major' -> 'C'
    clean = re_replace_key(clean)
    return KEY_TO_CAMELOT.get(clean, "")


def camelot_to_key(camelot_str: str) -> str:
    """Converts a Camelot code to a standard musical key string (e.g. '8A' -> 'Am')."""
    code = camelot_str.strip().upper()
    info = CAMELOT_TO_KEY.get(code)
    return info[0] if info else ""


def get_harmonic_matches(camelot_str: str) -> List[str]:
    """
    Returns list of Camelot keys harmonically compatible with the given key:
    - Same key (e.g. 8A)
    - Relative Major/Minor (8A <-> 8B)
    - Adjacent steps (7A, 9A)
    - Energy Boost (+2, e.g. 10A)
    """
    code = camelot_str.strip().upper()
    if not code or len(code) < 2:
        return []

    num = int(code[:-1])
    letter = code[-1]
    other_letter = "B" if letter == "A" else "A"

    def wrap_key(n: int) -> int:
        return ((n - 1) % 12) + 1

    matches = [
        code,                                    # Perfect Match
        f"{num}{other_letter}",                  # Relative Key
        f"{wrap_key(num - 1)}{letter}",          # Energy -1
        f"{wrap_key(num + 1)}{letter}",          # Energy +1
        f"{wrap_key(num + 2)}{letter}",          # Energy Boost +2
    ]
    return matches


def re_replace_key(k: str) -> str:
    k = k.replace(" minor", "m").replace(" Minor", "m").replace(" min", "m")
    k = k.replace(" major", "").replace(" Major", "").replace(" maj", "")
    return k.strip()


class AcousticAnalyzer:
    """Performs fast BPM and Key detection on local audio tracks."""

    @classmethod
    def load_audio_sample(
        cls,
        filepath: Union[str, Path],
        target_sr: int = 22050,
        max_duration_sec: float = 60.0,
        offset_sec: float = 25.0,
    ) -> Tuple[np.ndarray, int, float]:
        """
        Loads an audio segment (middle window) to optimize speed and memory.
        Returns: (mono_signal, sample_rate, total_file_duration)
        """
        path_str = str(filepath)
        with sf.SoundFile(path_str) as sf_file:
            orig_sr = sf_file.samplerate
            total_frames = sf_file.frames
            total_duration = total_frames / orig_sr

            # Seek into track drop / chorus (skip introductory silence/ambient)
            start_frame = 0
            if total_duration > (offset_sec + 15.0):
                start_frame = int(offset_sec * orig_sr)
            sf_file.seek(start_frame)

            frames_to_read = min(int(max_duration_sec * orig_sr), total_frames - start_frame)
            data = sf_file.read(frames_to_read, dtype="float32")

        # Convert to mono
        if data.ndim > 1:
            signal = np.mean(data, axis=1)
        else:
            signal = data

        # Fast downsample if needed
        if orig_sr != target_sr:
            from scipy.signal import resample_poly
            from math import gcd
            common = gcd(target_sr, orig_sr)
            up = target_sr // common
            down = orig_sr // common
            signal = resample_poly(signal, up, down).astype(np.float32)
            sr = target_sr
        else:
            sr = orig_sr

        return signal, sr, total_duration

    @classmethod
    def estimate_bpm(cls, signal: np.ndarray, sr: int, min_bpm: float = 65.0, max_bpm: float = 185.0) -> float:
        """
        Detects BPM using onset envelope autocorrelation with dance music octave heuristics.
        """
        if len(signal) < sr * 2:
            return 0.0

        # Compute onset envelope (Spectral flux via STFT)
        hop_length = 512
        n_fft = 2048

        # Short-Time Fourier Transform
        window = np.hanning(n_fft)
        num_frames = (len(signal) - n_fft) // hop_length
        if num_frames <= 0:
            return 0.0

        frames = np.lib.stride_tricks.as_strided(
            signal,
            shape=(num_frames, n_fft),
            strides=(signal.strides[0] * hop_length, signal.strides[0]),
        )
        spec = np.abs(np.fft.rfft(frames * window, axis=1))

        # Half-wave rectified first difference (Onset strength)
        diff = np.diff(spec, axis=0)
        diff = np.maximum(0, diff)
        onset_env = np.mean(diff, axis=1)

        # Remove DC bias and normalize
        onset_env -= np.mean(onset_env)
        env_norm = np.std(onset_env)
        if env_norm > 1e-6:
            onset_env /= env_norm

        # Autocorrelation
        corr = correlate(onset_env, onset_env, mode="full")
        corr = corr[len(corr) // 2 :]

        # Frame rate of onset envelope
        fps = sr / hop_length

        # Convert BPM limits to lags
        min_lag = int(round(fps * 60.0 / max_bpm))
        max_lag = int(round(fps * 60.0 / min_bpm))

        if min_lag >= len(corr) or max_lag <= min_lag:
            return 0.0

        search_slice = corr[min_lag:max_lag]
        if len(search_slice) == 0:
            return 0.0

        # Find prominent peaks
        peaks, props = find_peaks(search_slice, height=0.05, distance=max(1, int(fps * 60.0 / 180)))

        if len(peaks) == 0:
            best_lag_rel = int(np.argmax(search_slice))
        else:
            best_peak_idx = np.argmax(props["peak_heights"])
            best_lag_rel = peaks[best_peak_idx]

        best_lag = min_lag + best_lag_rel

        # Parabolic interpolation for sub-sample precision
        if 0 < best_lag < len(corr) - 1:
            alpha = corr[best_lag - 1]
            beta = corr[best_lag]
            gamma = corr[best_lag + 1]
            denom = 2 * (2 * beta - alpha - gamma)
            if abs(denom) > 1e-6:
                delta = (alpha - gamma) / denom
                best_lag = best_lag + delta

        detected_bpm = (fps * 60.0) / best_lag

        # DJ Dance Music Octave Disambiguation:
        # Standard club music is predominantly 115-135 BPM (House/Techno) or 140-175 BPM (DnB/Dubstep/Hardstyle).
        # If detected BPM is ~60-80, check if double tempo (120-160) is more standard.
        if detected_bpm < 85.0:
            detected_bpm *= 2.0
        elif detected_bpm > 190.0:
            detected_bpm /= 2.0

        return round(float(detected_bpm), 1)

    @classmethod
    def estimate_key(cls, signal: np.ndarray, sr: int) -> Tuple[str, str]:
        """
        Detects musical key and Camelot Wheel code using Chromagram and
        Krumhansl-Schmuckler correlation profile.
        Returns: (musical_key, camelot_key), e.g. ("Am", "8A")
        """
        if len(signal) < sr:
            return ("Unknown", "")

        # Compute STFT
        n_fft = 4096
        hop_length = 1024
        window = np.hanning(n_fft)
        num_frames = (len(signal) - n_fft) // hop_length
        if num_frames <= 0:
            return ("Unknown", "")

        frames = np.lib.stride_tricks.as_strided(
            signal,
            shape=(num_frames, n_fft),
            strides=(signal.strides[0] * hop_length, signal.strides[0]),
        )
        spec = np.abs(np.fft.rfft(frames * window, axis=1))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)

        # Filter to musical range: C2 (~65 Hz) to C7 (~2093 Hz)
        valid_idx = (freqs >= 65.0) & (freqs <= 2100.0)
        freqs_filt = freqs[valid_idx]
        spec_filt = spec[:, valid_idx]

        # Map frequencies to 12 pitch classes: MIDI note = 69 + 12 * log2(f / 440)
        midi_notes = 69.0 + 12.0 * np.log2(freqs_filt / 440.0)
        pitch_classes = np.round(midi_notes).astype(int) % 12

        # Accumulate Chroma vector (12 bins)
        chroma = np.zeros(12, dtype=np.float64)
        for pc in range(12):
            mask = (pitch_classes == pc)
            if np.any(mask):
                chroma[pc] = np.sum(spec_filt[:, mask])

        # Normalize chroma profile
        chroma_std = np.std(chroma)
        if chroma_std > 1e-6:
            chroma = (chroma - np.mean(chroma)) / chroma_std
        else:
            return ("Unknown", "")

        # Standardize Krumhansl profiles
        major_prof = (KRUMHANSL_MAJOR - np.mean(KRUMHANSL_MAJOR)) / np.std(KRUMHANSL_MAJOR)
        minor_prof = (KRUMHANSL_MINOR - np.mean(KRUMHANSL_MINOR)) / np.std(KRUMHANSL_MINOR)

        best_score = -2.0
        best_key = "C"

        for shift in range(12):
            root_note = PITCH_CLASSES[shift]

            # Major correlation
            rot_major = np.roll(major_prof, shift)
            corr_maj = float(np.corrcoef(chroma, rot_major)[0, 1])
            if corr_maj > best_score:
                best_score = corr_maj
                best_key = f"{root_note}"

            # Minor correlation
            rot_minor = np.roll(minor_prof, shift)
            corr_min = float(np.corrcoef(chroma, rot_minor)[0, 1])
            if corr_min > best_score:
                best_score = corr_min
                best_key = f"{root_note}m"

        camelot = key_to_camelot(best_key)
        return best_key, camelot

    @classmethod
    def calculate_loudness(cls, signal: np.ndarray) -> Tuple[float, float, float]:
        """
        Calculates Peak dBFS, RMS dBFS, and estimated ReplayGain dB.
        Target: -14.0 dBFS ReplayGain standard.
        """
        if len(signal) == 0:
            return -99.0, -99.0, 0.0

        peak = float(np.max(np.abs(signal)))
        peak_db = 20.0 * math.log10(peak) if peak > 1e-5 else -99.0

        rms = float(np.sqrt(np.mean(signal**2)))
        rms_db = 20.0 * math.log10(rms) if rms > 1e-5 else -99.0

        # Suggested gain to reach -14.0 dBFS RMS
        target_rms_db = -14.0
        replay_gain = round(target_rms_db - rms_db, 1)

        return round(peak_db, 1), round(rms_db, 1), replay_gain

    @classmethod
    def analyze_file(cls, filepath: Union[str, Path]) -> AcousticProfile:
        """Runs complete acoustic analysis pipeline on audio file."""
        signal, sr, total_dur = cls.load_audio_sample(filepath)

        bpm = cls.estimate_bpm(signal, sr)
        musical_key, camelot = cls.estimate_key(signal, sr)
        peak_db, rms_db, rg_db = cls.calculate_loudness(signal)

        return AcousticProfile(
            bpm=bpm,
            bpm_rounded=int(round(bpm)),
            musical_key=musical_key,
            camelot_key=camelot,
            peak_db=peak_db,
            rms_db=rms_db,
            replay_gain_db=rg_db,
            duration=total_dur,
        )
