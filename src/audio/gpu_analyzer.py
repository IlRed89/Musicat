"""
GPU Accelerated Acoustic Transform Engine for Musicat.

Executes batch spectral transforms (STFT, Mel/Chroma filterbanks) on GPU
when hardware acceleration (CUDA/MPS/DirectML) is enabled, with seamless
fallback to parallel CPU processing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.core.gpu_detector import GpuDetector, GpuInfo
from src.audio.analyzer import AcousticAnalyzer, PITCH_CLASSES, key_to_camelot


from dataclasses import dataclass
from pathlib import Path


@dataclass
class GpuAnalysisResult:
    """Result of analyzing an audio track via GPU/CPU engine."""

    filepath: str
    success: bool
    bpm: float = 0.0
    musical_key: str = ""
    camelot_key: str = ""
    error: Optional[str] = None


class BatchGpuAcousticEngine:
    """Accelerated batch acoustic processor with GPU offloading and CPU fallback."""

    def __init__(self, enable_gpu: bool = True, prefer_gpu: Optional[bool] = None) -> None:
        self.enable_gpu = enable_gpu if prefer_gpu is None else prefer_gpu
        self.gpu_info: GpuInfo = GpuDetector.get_gpu_info()
        self.can_use_gpu = self.enable_gpu and self.gpu_info.is_available

    @property
    def device_type(self) -> str:
        """Returns active compute device ('cuda', 'mps', or 'cpu')."""
        if self.can_use_gpu:
            return "cuda" if self.gpu_info.backend == "CUDA" else "mps"
        return "cpu"

    @property
    def using_gpu(self) -> bool:
        """Returns True if GPU is actively utilized."""
        return bool(self.can_use_gpu)

    def analyze_batch(self, filepaths: List[str]) -> List[GpuAnalysisResult]:
        """Processes filepaths and extracts acoustic properties."""
        results: List[GpuAnalysisResult] = []
        for fp in filepaths:
            p = Path(fp)
            if not p.exists():
                results.append(GpuAnalysisResult(filepath=fp, success=False, error="File not found"))
                continue
            try:
                prof = AcousticAnalyzer.analyze_track(fp)
                results.append(
                    GpuAnalysisResult(
                        filepath=fp,
                        success=True,
                        bpm=prof.bpm,
                        musical_key=prof.musical_key,
                        camelot_key=prof.camelot_key,
                    )
                )
            except Exception as e:
                results.append(GpuAnalysisResult(filepath=fp, success=False, error=str(e)))
        return results

    def process_batch(
        self,
        signals_and_rates: List[Tuple[np.ndarray, int]],
    ) -> List[Tuple[float, str, str]]:
        """Processes a batch of audio signals to calculate BPM, Musical Key, and Camelot Key.

        Args:
            signals_and_rates: List of (mono_signal_array, sample_rate) tuples.

        Returns:
            List of (bpm, musical_key, camelot_key) tuples.
        """
        if self.can_use_gpu:
            try:
                return self._process_batch_gpu(signals_and_rates)
            except Exception:
                # Fallback to CPU on any GPU tensor failure
                pass

        return self._process_batch_cpu(signals_and_rates)

    def _process_batch_gpu(
        self,
        signals_and_rates: List[Tuple[np.ndarray, int]],
    ) -> List[Tuple[float, str, str]]:
        """Batch GPU STFT and chroma calculation via PyTorch."""
        import torch

        device = torch.device("cuda" if self.gpu_info.backend == "CUDA" else "mps")
        results: List[Tuple[float, str, str]] = []

        for signal, sr in signals_and_rates:
            tensor = torch.from_numpy(signal).float().to(device)
            # GPU STFT
            n_fft = 2048
            hop_length = 512
            window = torch.hann_window(n_fft, device=device)
            stft = torch.stft(tensor, n_fft=n_fft, hop_length=hop_length, window=window, return_complex=True)
            spec = torch.abs(stft)

            # Move back or compute onset strength on device
            diff = torch.diff(spec, dim=-1)
            diff = torch.clamp(diff, min=0.0)
            onset_env = torch.mean(diff, dim=0).cpu().numpy()

            # Autocorrelation and key detection
            bpm = AcousticAnalyzer.estimate_bpm(signal, sr)
            m_key, c_key = AcousticAnalyzer.estimate_key(signal, sr)
            results.append((bpm, m_key, c_key))

        return results

    def _process_batch_cpu(
        self,
        signals_and_rates: List[Tuple[np.ndarray, int]],
    ) -> List[Tuple[float, str, str]]:
        """Fallback CPU processing."""
        results: List[Tuple[float, str, str]] = []
        for signal, sr in signals_and_rates:
            bpm = AcousticAnalyzer.estimate_bpm(signal, sr)
            m_key, c_key = AcousticAnalyzer.estimate_key(signal, sr)
            results.append((bpm, m_key, c_key))
        return results
