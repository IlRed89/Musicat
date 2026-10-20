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
import glob
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
        """Checks if DirectML is usable via onnxruntime or torch_directml."""
        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" in ort.get_available_providers():
                return True
        except Exception:
            pass
        try:
            import torch_directml
            return bool(torch_directml.is_available())
        except Exception:
            pass
        return False

    @classmethod
    def is_mps_available(cls) -> bool:
        """Checks if Apple Silicon MPS is usable."""
        try:
            import torch
            return bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
        except Exception:
            pass
        return False

    @classmethod
    def is_cuda_available(cls) -> bool:
        """Checks if CUDA is usable via PyTorch, ONNX Runtime, or CuPy."""
        try:
            import torch
            if torch.cuda.is_available():
                return True
        except Exception:
            pass
        try:
            import onnxruntime as ort
            if "CUDAExecutionProvider" in ort.get_available_providers():
                return True
        except Exception:
            pass
        try:
            import cupy
            if cupy.cuda.is_available() and cupy.cuda.runtime.getDeviceCount() > 0:
                return True
        except Exception:
            pass
        return False

    @classmethod
    def get_diagnostic_details(cls) -> dict:
        """Returns deep diagnostic breakdown of all compute runtimes and physical GPU."""
        cls._ensure_external_compute_paths()

        hw_name, hw_mem = cls._detect_native_hardware()

        pytorch_info = {"installed": False, "version": "", "cuda": False, "mps": False, "device_name": ""}
        try:
            import torch
            pytorch_info["installed"] = True
            pytorch_info["version"] = str(torch.__version__)
            if torch.cuda.is_available():
                pytorch_info["cuda"] = True
                pytorch_info["device_name"] = torch.cuda.get_device_name(0)
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                pytorch_info["mps"] = True
        except Exception:
            pass

        ort_info = {"installed": False, "version": "", "providers": [], "directml": False, "cuda": False}
        try:
            import onnxruntime as ort
            ort_info["installed"] = True
            ort_info["version"] = str(ort.__version__)
            provs = ort.get_available_providers()
            ort_info["providers"] = provs
            ort_info["directml"] = "DmlExecutionProvider" in provs
            ort_info["cuda"] = "CUDAExecutionProvider" in provs
        except Exception:
            pass

        cupy_info = {"installed": False, "version": "", "cuda": False}
        try:
            import cupy
            cupy_info["installed"] = True
            cupy_info["version"] = str(cupy.__version__)
            cupy_info["cuda"] = bool(cupy.cuda.is_available() and cupy.cuda.runtime.getDeviceCount() > 0)
        except Exception:
            pass

        current_info = cls.get_gpu_info()

        return {
            "hardware_gpu": hw_name or "Nessuna GPU dedicata rilevata",
            "hardware_memory_mb": hw_mem,
            "pytorch": pytorch_info,
            "onnxruntime": ort_info,
            "cupy": cupy_info,
            "active_backend": current_info.backend,
            "active_device": current_info.device_name,
            "is_available": current_info.is_available,
            "status_message": current_info.status_message,
        }

    @classmethod
    def _ensure_external_compute_paths(cls) -> None:
        """If running frozen (e.g. PyInstaller standalone) or if PyTorch is not yet in sys.path,
        discover host PyTorch / CUDA libraries and make them dynamically available."""
        try:
            import torch
            if torch.cuda.is_available():
                return
        except Exception:
            pass

        if sys.platform != "win32":
            return

        candidates: list[str] = []

        # 1. Active virtualenv or conda environment
        for env_var in ("VIRTUAL_ENV", "CONDA_PREFIX"):
            val = os.environ.get(env_var)
            if val:
                sp = os.path.join(val, "Lib", "site-packages")
                if os.path.isdir(sp) and sp not in candidates:
                    candidates.append(sp)

        # 2. LocalAppData Python installations (e.g. %LOCALAPPDATA%\\Programs\\Python\\Python3*\\Lib\\site-packages)
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            found = glob.glob(os.path.join(local_app, "Programs", "Python", "Python3*", "Lib", "site-packages"))
            for p in sorted(found, reverse=True):
                if p not in candidates:
                    candidates.append(p)

        # 3. Program Files Python installations
        prog_files = os.environ.get("ProgramFiles", "")
        if prog_files:
            found = glob.glob(os.path.join(prog_files, "Python3*", "Lib", "site-packages"))
            for p in sorted(found, reverse=True):
                if p not in candidates:
                    candidates.append(p)

        # 4. System Drive Python installations (e.g. C:\\Python3*)
        sys_drive = os.environ.get("SystemDrive", "C:")
        found = glob.glob(os.path.join(sys_drive + "\\", "Python3*", "Lib", "site-packages"))
        for p in sorted(found, reverse=True):
            if p not in candidates:
                candidates.append(p)

        # Try to locate torch and its DLLs in candidate directories
        for sp in candidates:
            torch_dir = os.path.join(sp, "torch")
            torch_lib = os.path.join(torch_dir, "lib")
            if os.path.isdir(torch_lib):
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(torch_lib)
                    os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
                    if sp not in sys.path:
                        sys.path.insert(0, sp)
                    import torch
                    if torch.cuda.is_available():
                        return
                except Exception:
                    continue

    @classmethod
    def _detect_gpu(cls) -> GpuInfo:
        """Runs multi-tier GPU detection across frameworks and OS drivers."""
        cls._ensure_external_compute_paths()

        # 1. Check PyTorch CUDA
        try:
            import torch

            if torch.cuda.is_available():
                dev_idx = torch.cuda.current_device()
                name = torch.cuda.get_device_name(dev_idx)
                mem = int(torch.cuda.get_device_properties(dev_idx).total_memory / (1024 * 1024))
                return GpuInfo(
                    is_available=True,
                    backend=GpuBackend.CUDA,
                    device_name=name,
                    device_memory_mb=mem,
                    is_hardware_detected=True,
                    status_message=f"Accelerazione NVIDIA CUDA attiva ({name}, {mem} MB VRAM)",
                )

            # Check PyTorch Apple Silicon MPS
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return GpuInfo(
                    is_available=True,
                    backend=GpuBackend.MPS,
                    device_name="Apple Silicon GPU (Metal)",
                    device_memory_mb=0,
                    is_hardware_detected=True,
                    status_message="Accelerazione Apple Silicon Metal (MPS) attiva",
                )
        except Exception:
            pass

        # 2. Check ONNX Runtime CUDA
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in providers:
                hw_name, hw_mem = cls._detect_native_hardware()
                name = hw_name or "NVIDIA CUDA GPU"
                return GpuInfo(
                    is_available=True,
                    backend=GpuBackend.CUDA,
                    device_name=name,
                    device_memory_mb=hw_mem,
                    is_hardware_detected=True,
                    status_message=f"Accelerazione NVIDIA CUDA (ONNX Runtime) attiva ({name})",
                )
        except Exception:
            pass

        # 3. Check CuPy CUDA
        try:
            import cupy
            if cupy.cuda.is_available() and cupy.cuda.runtime.getDeviceCount() > 0:
                hw_name, hw_mem = cls._detect_native_hardware()
                name = hw_name or "NVIDIA GPU (CuPy)"
                return GpuInfo(
                    is_available=True,
                    backend=GpuBackend.CUDA,
                    device_name=name,
                    device_memory_mb=hw_mem,
                    is_hardware_detected=True,
                    status_message=f"Accelerazione NVIDIA CUDA (CuPy) attiva ({name})",
                )
        except Exception:
            pass

        # 4. Check DirectML (via onnxruntime or torch_directml)
        if cls.is_directml_available():
            hw_name, hw_mem = cls._detect_native_hardware()
            name = hw_name or "DirectML DirectX 12 Compute"
            return GpuInfo(
                is_available=True,
                backend=GpuBackend.DIRECTML,
                device_name=name,
                device_memory_mb=hw_mem,
                is_hardware_detected=True,
                status_message=f"Accelerazione DirectX DirectML attiva ({name})",
            )

        # 5. Detect physical hardware if compute frameworks are absent
        hardware_name, hardware_mem = cls._detect_native_hardware()

        if hardware_name:
            return GpuInfo(
                is_available=False,
                backend=GpuBackend.CPU,
                device_name=hardware_name,
                device_memory_mb=hardware_mem,
                is_hardware_detected=True,
                status_message=f"Accelerazione GPU: CPU Fallback Attivo ({hardware_name} Rilevata)",
            )

        return GpuInfo(
            is_available=False,
            backend=GpuBackend.CPU,
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
