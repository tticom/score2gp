from __future__ import annotations

import json
import zipfile
from pathlib import Path

from score2gp.batch import run_batch_pipeline


def test_batch_parallelization_concurrency(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_batch_concurrency_manifest.json")
    workdir = tmp_path / "batch_work"

    # Run the batch pipeline with 2 concurrent workers
    result = run_batch_pipeline(manifest_path, workdir, max_workers=2)

    # Centralized batch status execution report assertions
    assert result["total_payloads"] == 2
    assert result["success_count"] == 2
    assert result["failure_count"] == 0
    assert len(result["results"]) == 2

    # Thread/process execution footprints
    for res in result["results"]:
        assert res["status"] == "success"
        assert res["error"] is None
        assert res["error_code"] is None
        assert res["elapsed_seconds"] > 0.0
        assert res["thread_id"] is not None
        assert res["process_id"] is not None

        # Verify output zip package exists and is valid
        out_gp = Path(res["output_path"])
        assert out_gp.exists()
        assert zipfile.is_zipfile(out_gp)


def test_batch_parallelization_graceful_failures(tmp_path) -> None:
    # Build a bad manifest payload designed to fail
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(
        json.dumps([
            {
                "id": "bad_payload",
                "musicxml": "tests/fixtures/musicxml/timing_overfull_measure.musicxml",  # Should trigger timing risk refusal
                "tabraw": "tests/fixtures/tabraw/tiny_single_bar_tabraw.json"
            }
        ]),
        encoding="utf-8"
    )

    workdir = tmp_path / "batch_work_fail"

    # Execute batch pipeline containing the bad payload
    result = run_batch_pipeline(bad_manifest, workdir, max_workers=1)

    assert result["total_payloads"] == 1
    assert result["success_count"] == 0
    assert result["failure_count"] == 1

    res = result["results"][0]
    assert res["status"] == "failed"
    assert res["error_code"] == "musicxml_timing_risk"
    assert "overfull" in res["error"].lower() or "exceeds" in res["error"].lower()
