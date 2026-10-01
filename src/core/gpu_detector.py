"""
Hardware GPU Detector for Musicat.

Detects graphics acceleration capabilities across:
- NVIDIA CUDA (via PyTorch, CuPy, or native driver IPC)
- Apple Silicon Metal / MPS (Metal Performance Shaders on macOS)
- DirectML on Windows (DirectX 12 Compute)
- Graceful transparent fallback to Multiprocessing CPU when no GPU is detected.
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


class GpuBackend:
    """Supported GPU compute backends."""

    CUDA = "CUDA"
    MPS = "MPS"
    DIRECTML = "DirectML"
    CPU = "CPU Fallback"


@dataclass
class GpuInfo:
    """Diagnostic information regarding available GPU acceleration."""

    is_available: bool
    backend: str  # "CUDA", "MPS", "DirectML", "Vulkan", "CPU Fallback"
    device_name: str
    device_memory_mb: int
    is_hardware_detected: bool
    status_message: str

    @property
    def name(self) -> str:
        """Alias for device_name."""
        return self.device_name

    @property
    def memory_total_mb(self) -> int:
        """Alias for device_memory_mb."""
        return self.device_memory_mb

    def to_dict(self) -> dict:
        return {
            "is_available": self.is_available,
            "backend": self.backend,
            "device_name": self.device_name,
            "device_memory_mb": self.device_memory_mb,
            "is_hardware_detected": self.is_hardware_detected,
            "status_message": self.status_message,
        }


class GpuDetector:
    """Detects GPU compute backends and hardware configuration."""

    _cached_info: Optional[GpuInfo] = None

    @classmethod
    def get_gpu_info(cls, force_refresh: bool = False) -> GpuInfo:
        """Returns detected GPU compute info, cached for speed."""
        if cls._cached_info is not None and not force_refresh:
            return cls._cached_info

        info = cls._detect_gpu()
        cls._cached_info = info
        return info

    @classmethod
    def get_best_device(cls) -> str:
        """Returns best device string ('cuda', 'mps', or 'cpu')."""
        info = cls.get_gpu_info()
        if info.is_available:
            if info.backend == GpuBackend.CUDA:
                return "cuda"
            elif info.backend == GpuBackend.MPS:
                return "mps"
        return "cpu"

    @classmethod
    def is_directml_available(cls) -> bool:
        """Checks if DirectML is usable."""
        try:
            import torch_directml
            return bool(torch_directml.is_available())
        except Exception:
            return False

    @classmethod
    def is_mps_available(cls) -> bool:
        """Checks if Apple Silicon MPS is usable."""
        try:
            import torch
            return bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
        except Exception:
            return False

    @classmethod
    def _detect_gpu(cls) -> GpuInfo:
        """Runs multi-tier GPU detection across frameworks and OS drivers."""
        # 1. Check PyTorch CUDA
        try:
            import torch

            if torch.cuda.is_available():
                dev_idx = torch.cuda.current_device()
                name = torch.cuda.get_device_name(dev_idx)
                mem = int(torch.cuda.get_device_properties(dev_idx).total_memory / (1024 * 1024))
                return GpuInfo(
                    is_available=True,
                    backend="CUDA",
                    device_name=name,
                    device_memory_mb=mem,
                    is_hardware_detected=True,
                    status_message=f"Accelerazione NVIDIA CUDA attiva ({name}, {mem} MB VRAM)",
                )

            # Check PyTorch Apple Silicon MPS
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return GpuInfo(
                    is_available=True,
                    backend="MPS",
                    device_name="Apple Silicon GPU (Metal)",
                    device_memory_mb=0,
                    is_hardware_detected=True,
                    status_message="Accelerazione Apple Silicon Metal (MPS) attiva",
                )
        except Exception:
            pass

        # 2. Check DirectML
        try:
            import torch_directml

            if torch_directml.is_available():
                name = torch_directml.device_name(0)
                return GpuInfo(
                    is_available=True,
                    backend="DirectML",
                    device_name=name,
                    device_memory_mb=0,
                    is_hardware_detected=True,
                    status_message=f"Accelerazione DirectX DirectML attiva ({name})",
                )
        except Exception:
            pass

        # 3. Detect physical hardware if torch is absent
        hardware_name, hardware_mem = cls._detect_native_hardware()

        if hardware_name:
            return GpuInfo(
                is_available=False,
                backend="CPU Fallback",
                device_name=hardware_name,
                device_memory_mb=hardware_mem,
                is_hardware_detected=True,
                status_message=f"Rilevata GPU {hardware_name} (librerie compute non installate, fallback su Multiprocessing CPU)",
            )

        return GpuInfo(
            is_available=False,
            backend="CPU Fallback",
            device_name="Standard CPU",
            device_memory_mb=0,
            is_hardware_detected=False,
            status_message="Nessuna GPU computazionale rilevata. Elaborazione affidata al Multiprocessing CPU.",
        )

    @classmethod
    def _detect_native_hardware(cls) -> tuple[str, int]:
        """Detects physical GPU presence via native OS drivers or system query."""
        # Windows native detection via DXGI or WMI
        if sys.platform == "win32":
            try:
                # Try NVIDIA driver ctypes
                try:
                    nvcuda = ctypes.windll.LoadLibrary("nvcuda.dll")
                    if nvcuda:
                        res = nvcuda.cuInit(0)
                        if res == 0:
                            dev = ctypes.c_int()
                            nvcuda.cuDeviceGet(ctypes.byref(dev), 0)
                            name_buf = ctypes.create_string_buffer(128)
                            nvcuda.cuDeviceGetName(name_buf, 128, dev)
                            return name_buf.value.decode("utf-8", errors="ignore"), 0
                except Exception:
                    pass

                # Fallback WMI query
                cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"'
                out = subprocess.check_output(cmd, shell=True, timeout=2.0).decode("utf-8", errors="ignore").strip()
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                # Exclude basic display adapter if dedicated card exists
                gpu_names = [l for l in lines if "Basic" not in l and "Virtual" not in l]
                if gpu_names:
                    return gpu_names[0], 0
                elif lines:
                    return lines[0], 0
            except Exception:
                pass

        elif sys.platform == "darwin":
            # macOS Apple Silicon or Intel GPU
            try:
                out = subprocess.check_output(["system_profiler", "SPDisplaysDataType"], timeout=2.0).decode("utf-8")
                for line in out.splitlines():
                    if "Chipset Model:" in line:
                        return line.split(":", 1)[1].strip(), 0
            except Exception:
                pass

        return "", 0
