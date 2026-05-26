from __future__ import annotations

import json
import subprocess
from pathlib import Path

from score2gp.diagnostics import run_system_diagnostics, get_process_memory


def test_system_diagnostics_runner(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_system_integration_manifest.json")
    workdir = tmp_path / "diagnostics_work"

    # Execute system diagnostics orchestrator
    report = run_system_diagnostics(manifest_path, workdir, max_workers=3)

    # Validate report metrics
    assert report["total_payloads"] == 3
    assert report["success_count"] == 3
    assert report["failure_count"] == 0
    assert report["roundtrip_success_count"] == 3
    assert report["roundtrip_failure_count"] == 0
    assert report["total_runtime_seconds"] > 0.0
    assert report["peak_memory_bytes"] >= 0

    results_by_id = {res["id"]: res for res in report["results"]}
    assert len(results_by_id) == 3

    # Assert strict bidirectional roundtrip validity on every generated target package
    for pid in ("stress_gp6_rests", "stress_gp7_two_voice", "stress_gp8_single_bar"):
        res = results_by_id[pid]
        assert res["status"] == "success"
        assert res["roundtrip_valid"] is True
        assert len(res["roundtrip_errors"]) == 0
        assert res["payload_hash"] is not None


def test_cli_diagnose_command(tmp_path) -> None:
    manifest_path = "fixtures/public/test_system_integration_manifest.json"
    workdir = tmp_path / "diagnose_cli_work"

    # Run the diagnose command via subprocess to verify CLI integration and output
    cmd = [
        "python", "-m", "score2gp.cli", "diagnose",
        str(manifest_path),
        str(workdir),
        "--workers", "3"
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Validate that command returns JSON report
    report = json.loads(completed.stdout)
    assert report["total_payloads"] == 3
    assert report["success_count"] == 3
    assert report["roundtrip_success_count"] == 3
    assert report["failure_count"] == 0
