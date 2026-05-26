from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .batch import run_batch_pipeline
from .gp_package import validate_roundtrip
from .ir import validate_score_ir_file, ScoreIR


def get_process_memory() -> int:
    """
    Retrieves the resident set size (RSS) memory of the current process in bytes.
    Uses psutil if available, falls back to Windows-native APIs via ctypes,
    and returns 0 on failure.
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss
    except ImportError:
        try:
            import ctypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            
            get_current_process = ctypes.windll.kernel32.GetCurrentProcess
            get_current_process.restype = ctypes.c_void_p
            
            get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_process_memory_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_ulong]
            get_process_memory_info.restype = ctypes.c_int
            
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            
            handle = get_current_process()
            if get_process_memory_info(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize
            return 0
        except Exception:
            return 0


def run_system_diagnostics(manifest_path: str | Path, base_work_dir: str | Path, max_workers: int = 4) -> dict[str, Any]:
    """
    Orchestrates complex parallelized score generation streams using full incremental caching,
    capturing thread-pool and workspace memory statistics, and executing strict bidirectional
    round-trip validation checks on every compiled GP7 package artifact.
    """
    start_time = time.perf_counter()
    initial_memory = get_process_memory()

    # 1. Run the batch pipeline with caching enabled
    batch_result = run_batch_pipeline(manifest_path, base_work_dir, max_workers=max_workers, use_cache=True)

    mid_memory = get_process_memory()

    diagnostics_results = []
    roundtrip_successes = 0
    roundtrip_failures = 0

    # 2. Extract and run round-trip validation assertions
    for res in batch_result["results"]:
        worker_id = res["id"]
        status = res["status"]
        output_path = res["output_path"]

        roundtrip_valid = False
        roundtrip_errors = []

        if status == "success" and output_path:
            gp_path = Path(output_path)
            # Locate sandboxed ScoreIR generated during compilation
            sandbox_dir = Path(base_work_dir) / f"batch_worker_{worker_id}"
            ir_path = sandbox_dir / "score.ir.json"

            if ir_path.exists() and gp_path.exists():
                try:
                    score, errors = validate_score_ir_file(ir_path)
                    if not errors and isinstance(score, ScoreIR):
                        # Validate bidirectional roundtrip
                        rt_res = validate_roundtrip(gp_path, score)
                        roundtrip_valid = rt_res.get("valid", False)
                        roundtrip_errors = rt_res.get("errors", [])
                    else:
                        roundtrip_errors = errors or ["Invalid original ScoreIR file format"]
                except Exception as exc:
                    roundtrip_errors = [f"Roundtrip check exception: {str(exc)}"]
            else:
                roundtrip_errors = [f"Missing original ScoreIR file ({ir_path.exists()}) or GP package ({gp_path.exists()})"]

        if roundtrip_valid:
            roundtrip_successes += 1
        else:
            if status == "success":
                roundtrip_failures += 1

        diagnostics_results.append({
            "id": worker_id,
            "status": status,
            "cache_status": res.get("cache_status", "miss"),
            "payload_hash": res.get("payload_hash"),
            "elapsed_seconds": res.get("elapsed_seconds", 0.0),
            "roundtrip_valid": roundtrip_valid,
            "roundtrip_errors": roundtrip_errors,
        })

    final_memory = get_process_memory()
    peak_memory = max(initial_memory, mid_memory, final_memory)
    total_time = time.perf_counter() - start_time

    return {
        "total_runtime_seconds": total_time,
        "peak_memory_bytes": peak_memory,
        "memory_overhead_bytes": max(0, final_memory - initial_memory),
        "total_payloads": batch_result["total_payloads"],
        "success_count": batch_result["success_count"],
        "failure_count": batch_result["failure_count"],
        "cache_hit_count": batch_result["cache_hit_count"],
        "cache_miss_count": batch_result["cache_miss_count"],
        "roundtrip_success_count": roundtrip_successes,
        "roundtrip_failure_count": roundtrip_failures,
        "results": diagnostics_results,
    }
