from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from score2gp.diagnostics import run_system_diagnostics, get_process_memory


def supported_manifest(tmp_path: Path) -> Path:
    # OUT-01 removes fabricated GP6/GP8 selections. Preserve all three source
    # payloads and round-trip checks using the retained GPIF-ZIP target.
    payloads = json.loads(Path("fixtures/public/test_system_integration_manifest.json").read_text())
    for payload in payloads:
        payload["target_version"] = "GP7"
    manifest = tmp_path / "supported_manifest.json"
    manifest.write_text(json.dumps(payloads))
    return manifest


def test_system_diagnostics_runner(tmp_path) -> None:
    manifest_path = supported_manifest(tmp_path)
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
    manifest_path = str(supported_manifest(tmp_path))
    workdir = tmp_path / "diagnose_cli_work"

    # Run the diagnose command via subprocess to verify CLI integration and output
    cmd = [
        sys.executable, "-m", "score2gp.cli", "diagnose",
        str(manifest_path),
        str(workdir),
        "--workers", "3"
    ]
    import os
    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_dir

    completed = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)

    # Validate that command returns JSON report
    report = json.loads(completed.stdout)
    assert report["total_payloads"] == 3
    assert report["success_count"] == 3
    assert report["roundtrip_success_count"] == 3
    assert report["failure_count"] == 0
