from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .build_ir import build_ir_with_diagnostics_from_files, BuildIrInputRiskError
from .gp_package import write_gp


def run_single_payload(payload: dict[str, Any], base_work_dir: Path) -> dict[str, Any]:
    worker_id = payload.get("id") or str(uuid.uuid4())
    start_time = time.perf_counter()
    thread_id = threading.get_ident()
    process_id = os.getpid()

    # Sandboxed isolated workspace directory
    sandbox_dir = base_work_dir / f"batch_worker_{worker_id}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    musicxml = payload.get("musicxml")
    tabraw = payload.get("tabraw")
    
    out_val = payload.get("out")
    if out_val:
        out_path = Path(out_val)
    else:
        out_path = sandbox_dir / "output.gp"

    ascii_alignment = payload.get("ascii_alignment")
    allow_remediation = payload.get("allow_remediation", False)
    allow_skip_unboxed = payload.get("allow_skip_unboxed", False)
    template = payload.get("template")

    status = "failed"
    error = None
    error_code = None

    try:
        if not musicxml or not tabraw:
            raise ValueError("Both musicxml and tabraw paths must be provided in payload.")

        ir_path = sandbox_dir / "score.ir.json"

        # 1. Build IR
        score, diagnostics = build_ir_with_diagnostics_from_files(
            musicxml_path=Path(musicxml),
            tabraw_path=Path(tabraw),
            out_path=ir_path,
            ascii_alignment_path=Path(ascii_alignment) if ascii_alignment else None,
            allow_remediation=allow_remediation,
            allow_skip_unboxed=allow_skip_unboxed,
        )

        # 2. Write GP Package
        write_gp(score, out_path, template=Path(template) if template else None)
        status = "success"
    except BuildIrInputRiskError as exc:
        error = str(exc)
        error_code = exc.category
    except Exception as exc:
        error = str(exc)
        error_code = type(exc).__name__

    elapsed = time.perf_counter() - start_time
    return {
        "id": worker_id,
        "status": status,
        "error": error,
        "error_code": error_code,
        "elapsed_seconds": elapsed,
        "thread_id": thread_id,
        "process_id": process_id,
        "output_path": str(out_path),
    }


def run_batch_pipeline(manifest_path: str | Path, base_work_dir: str | Path, max_workers: int = 4) -> dict[str, Any]:
    start_time = time.perf_counter()
    manifest_file = Path(manifest_path)
    base_dir = Path(base_work_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    payloads = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payloads, list):
        raise ValueError("Manifest JSON must be a list of payloads.")

    results = []
    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_payload, payload, base_dir): payload for payload in payloads}
        for future in as_completed(futures):
            payload = futures[future]
            try:
                res = future.result()
                results.append(res)
                if res["status"] == "success":
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as exc:
                results.append({
                    "id": payload.get("id") or "escaped",
                    "status": "failed",
                    "error": str(exc),
                    "error_code": "supervisor_catch",
                    "elapsed_seconds": 0.0,
                    "thread_id": None,
                    "process_id": None,
                    "output_path": None,
                })
                failure_count += 1

    total_time = time.perf_counter() - start_time
    return {
        "total_runtime_seconds": total_time,
        "total_payloads": len(payloads),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }
