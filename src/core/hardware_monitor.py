"""
Hardware Resource Monitor for Musicat.

Provides lightweight, non-blocking CPU and RAM utilization metrics
without external dependencies (e.g. psutil), natively on Windows, macOS, and Linux.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional, Tuple


class HardwareMonitor:
    """Monitors system CPU and application RAM usage natively."""

    _last_idle: int = 0
    _last_total: int = 0
    _last_cpu_time: float = 0.0
    _last_calc_time: float = 0.0
    _last_cpu_val: float = 0.0

    @classmethod
    def _read_windows_system_times(cls) -> Tuple[int, int]:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        idle_ft = FILETIME()
        kernel_ft = FILETIME()
        user_ft = FILETIME()

        kernel32 = ctypes.windll.kernel32
        kernel32.GetSystemTimes(
            ctypes.byref(idle_ft),
            ctypes.byref(kernel_ft),
            ctypes.byref(user_ft),
        )

        def ft_to_int(ft: FILETIME) -> int:
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        idle = ft_to_int(idle_ft)
        total = ft_to_int(kernel_ft) + ft_to_int(user_ft)
        return idle, total

    @classmethod
    def get_cpu_percent(cls) -> float:
        """Returns CPU usage percentage [0.0 - 100.0]."""
        now = time.time()
        if now - cls._last_calc_time < 0.8:
            return cls._last_cpu_val

        try:
            if sys.platform == "win32":
                idle, total = cls._read_windows_system_times()
                if cls._last_total > 0 and total > cls._last_total:
                    idle_diff = idle - cls._last_idle
                    total_diff = total - cls._last_total
                    if total_diff > 0:
                        busy_diff = total_diff - idle_diff
                        pct = max(0.0, min(100.0, (busy_diff / total_diff) * 100.0))
                        cls._last_cpu_val = round(pct, 1)
                cls._last_idle = idle
                cls._last_total = total
            else:
                # macOS / Linux fallback via os.times()
                t = os.times()
                total_t = t.user + t.system
                if cls._last_cpu_time > 0 and now > cls._last_calc_time:
                    delta_proc = total_t - cls._last_cpu_time
                    delta_time = now - cls._last_calc_time
                    cores = os.cpu_count() or 1
                    pct = max(0.0, min(100.0, (delta_proc / (delta_time * cores)) * 100.0))
                    cls._last_cpu_val = round(pct, 1)
                cls._last_cpu_time = total_t

            cls._last_calc_time = now
            return cls._last_cpu_val
        except Exception:
            return 0.0

    @classmethod
    def get_process_memory_mb(cls) -> float:
        """Returns resident memory (RAM) used by the Musicat process in MB."""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t),
                    ]

                pmc = PROCESS_MEMORY_COUNTERS_EX()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                psapi = ctypes.windll.psapi
                kernel32 = ctypes.windll.kernel32
                psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
                psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
                if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                    return round(pmc.WorkingSetSize / (1024 * 1024), 1)
            else:
                import resource
                usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if sys.platform == "darwin":
                    # On macOS, ru_maxrss is in bytes
                    return round(usage / (1024 * 1024), 1)
                else:
                    # On Linux, ru_maxrss is in kilobytes
                    return round(usage / 1024, 1)
        except Exception:
            pass
        return 120.0

    @classmethod
    def get_total_system_memory_gb(cls) -> float:
        """Returns total physical system RAM in GB natively without dependencies."""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", wintypes.DWORD),
                        ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_uint64),
                        ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64),
                        ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64),
                        ("ullAvailVirtual", ctypes.c_uint64),
                        ("ullAvailExtendedVirtual", ctypes.c_uint64),
                    ]

                m = MEMORYSTATUSEX()
                m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                    return round(m.ullTotalPhys / (1024 ** 3), 1)
            elif sys.platform == "darwin":
                import subprocess
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
                return round(int(out.strip()) / (1024 ** 3), 1)
            else:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return round(kb / (1024 * 1024), 1)
        except Exception:
            pass
        return 16.0

    @classmethod
    def get_status_text(cls, cache_mb: Optional[int] = None) -> str:
        """Returns formatted hardware status string, e.g. 'CPU: 18% | RAM: 420 MB / 24 GB (Sistema)'."""
        cpu = cls.get_cpu_percent()
        ram_mb = cls.get_process_memory_mb()
        total_sys_gb = cls.get_total_system_memory_gb()
        return f"CPU: {int(cpu)}%  |  RAM: {int(ram_mb)} MB / {total_sys_gb:.0f} GB"

