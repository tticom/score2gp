from __future__ import annotations

import json
import zipfile
from pathlib import Path

from score2gp.batch import run_batch_pipeline
from score2gp.telemetry import PipelineTelemetryTracker


def test_pipeline_telemetry_metrics_and_footprint(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_telemetry_manifest.json")
    workdir = tmp_path / "batch_work"
    footprint_path = tmp_path / "telemetry_footprint.json"

    # Initialize custom telemetry tracker targeting our test footprint file path
    tracker = PipelineTelemetryTracker(output_path=footprint_path)

    # 1. Run 1: Cache Miss Run
    result = run_batch_pipeline(
        manifest_path=manifest_path,
        base_work_dir=workdir,
        max_workers=2,
        use_cache=True,
        telemetry_tracker=tracker,
    )

    assert result["total_payloads"] == 2
    assert result["success_count"] == 2
    assert result["failure_count"] == 0

    # Ensure footprint file is written and correct
    assert footprint_path.exists()
    report = json.loads(footprint_path.read_text(encoding="utf-8"))

    assert report["total_runs"] == 2
    assert report["cache_hits"] == 0
    assert report["cache_misses"] == 2
    assert report["cache_efficiency_ratio"] == 0.0
    assert report["total_runtime_seconds"] > 0.0
    assert report["peak_memory_rss_bytes"] > 0
    assert len(report["worker_latencies"]) == 2
    assert "tel_payload_1" in report["worker_latencies"]
    assert "tel_payload_2" in report["worker_latencies"]

    # 2. Run 2: Cache Hit Run
    tracker_hit = PipelineTelemetryTracker(output_path=footprint_path)
    result_hit = run_batch_pipeline(
        manifest_path=manifest_path,
        base_work_dir=workdir,
        max_workers=2,
        use_cache=True,
        telemetry_tracker=tracker_hit,
    )

    assert result_hit["total_payloads"] == 2
    assert result_hit["success_count"] == 2
    assert result_hit["cache_hit_count"] == 2

    report_hit = json.loads(footprint_path.read_text(encoding="utf-8"))
    assert report_hit["total_runs"] == 2
    assert report_hit["cache_hits"] == 2
    assert report_hit["cache_misses"] == 0
    assert report_hit["cache_efficiency_ratio"] == 1.0
