"""
Waveform Generator for Musicat Mini-Player.
Downsamples audio to 200-500 peak points for rapid UI rendering and cue navigation.
"""

import json
from pathlib import Path
from typing import List, Union

import numpy as np
import soundfile as sf


class WaveformGenerator:
    """Extracts downsampled peak envelope for audio waveform rendering."""

    @classmethod
    def generate_peaks(cls, filepath: Union[str, Path], num_points: int = 300) -> List[float]:
        """
        Reads audio file and produces a normalized list of peak heights [0.0 - 1.0].
        """
        path_str = str(filepath)
        try:
            with sf.SoundFile(path_str) as sf_file:
                total_frames = sf_file.frames
                if total_frames <= 0:
                    return [0.0] * num_points

                # Downsample step
                step = max(1, total_frames // (num_points * 20))
                # Read frames in chunks or subsample
                frames_to_read = min(total_frames, num_points * 100)
                data = sf_file.read(frames_to_read, dtype="float32")

                if data.ndim > 1:
                    data = np.mean(np.abs(data), axis=1)
                else:
                    data = np.abs(data)

                # Divide into buckets
                bucket_size = max(1, len(data) // num_points)
                peaks = []
                for i in range(num_points):
                    start = i * bucket_size
                    end = start + bucket_size
                    chunk = data[start:end]
                    peak = float(np.max(chunk)) if len(chunk) > 0 else 0.0
                    peaks.append(peak)

                # Normalize to [0.0, 1.0]
                max_val = max(peaks) if peaks else 1.0
                if max_val > 1e-4:
                    peaks = [round(p / max_val, 3) for p in peaks]
                else:
                    peaks = [0.0] * num_points

                return peaks
        except Exception:
            # Fallback placeholder envelope
            return [0.1 + 0.8 * abs(np.sin(i / 10.0)) for i in range(num_points)]

    @classmethod
    def serialize_peaks(cls, peaks: List[float]) -> str:
        """Serializes peaks list to JSON string for SQLite storage."""
        return json.dumps(peaks)

    @classmethod
    def deserialize_peaks(cls, json_str: str) -> List[float]:
        """Deserializes peaks list from JSON string."""
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except Exception:
            return []
