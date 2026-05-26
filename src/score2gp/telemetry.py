from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

# Native platform fallbacks when psutil is missing
if psutil is None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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
            ]

        def get_platform_rss() -> int:
            try:
                GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
                GetProcessMemoryInfo.argtypes = [
                    wintypes.HANDLE,
                    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                    wintypes.DWORD
                ]
                GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
                GetCurrentProcess.restype = wintypes.HANDLE

                process_handle = GetCurrentProcess()
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                if GetProcessMemoryInfo(process_handle, ctypes.byref(counters), counters.cb):
                    return counters.WorkingSetSize
            except Exception:
                pass
            return 0
    else:
        try:
            import resource

            def get_platform_rss() -> int:
                try:
                    # ru_maxrss is in kilobytes on Linux, bytes on macOS
                    usage = resource.getrusage(resource.RUSAGE_SELF)
                    factor = 1024 if sys.platform != "darwin" else 1
                    return usage.ru_maxrss * factor
                except Exception:
                    pass
                return 0
        except ImportError:
            def get_platform_rss() -> int:
                return 0
else:
    def get_platform_rss() -> int:
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except Exception:
            return 0


class PipelineTelemetryTracker:
    def __init__(self, output_path: str | Path = "work/telemetry_footprint.json"):
        self.output_path = Path(output_path)
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.start_time = time.perf_counter()
            self.peak_rss_bytes = 0
            self.total_runs = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.worker_latencies: dict[str, float] = {}

    def record_run(self, worker_id: str, elapsed_seconds: float, cache_status: str) -> None:
        with self.lock:
            self.worker_latencies[worker_id] = elapsed_seconds
            self.total_runs += 1
            if cache_status == "hit":
                self.cache_hits += 1
            else:
                self.cache_misses += 1

            current_rss = get_platform_rss()
            if current_rss > self.peak_rss_bytes:
                self.peak_rss_bytes = current_rss

    def generate_report(self) -> dict[str, Any]:
        with self.lock:
            total_time = time.perf_counter() - self.start_time
            cache_ratio = 0.0
            total_cache_attempts = self.cache_hits + self.cache_misses
            if total_cache_attempts > 0:
                cache_ratio = self.cache_hits / total_cache_attempts

            report = {
                "total_runtime_seconds": total_time,
                "peak_memory_rss_bytes": self.peak_rss_bytes,
                "total_runs": self.total_runs,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_efficiency_ratio": cache_ratio,
                "worker_latencies": self.worker_latencies.copy(),
            }

            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    def __enter__(self) -> PipelineTelemetryTracker:
        self.reset()
        self.peak_rss_bytes = get_platform_rss()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.generate_report()
