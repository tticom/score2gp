"""Real-source refusal roles; no reference text enters the converter.

Mutants rejected: remove the rotated-text reason; widen five spaces to seven
without a source-role rule. Both must fail this end-to-end test.
"""

from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from test_dur_02_oracle import read_gp_free_text


ROOT = Path(__file__).resolve().parents[1]


def test_lesson4_rotated_text_and_outer_band_stay_located(tmp_path: Path) -> None:
    source = ROOT / "fixtures/private/Lesson-4.pdf"
    if not source.is_file():
        pytest.skip("private corpus absent")
    output = tmp_path / "written.gp"
    build = tmp_path / "build"
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
         "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
         "--work-dir", str(build), "--json-report", str(report)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr[-1200:]
    details = json.loads((build / "text-labels.json").read_text())
    located = {(row["page_index"], row["block_index"], row["line_index"]): row
               for row in details["decisions"]}
    # Source inspection: rotated staff furniture beside the tab clef, not a
    # horizontal annotation. The other line is above the five-space band.
    rotated = located[0, 6, 0]
    outer = located[3, 15, 1]
    assert rotated["code"] == "pdf_text_rotated_text"
    assert outer["code"] == "pdf_text_outside_annotation_band"
    assert len(rotated["bbox"]) == len(outer["bbox"]) == 4
    assert "text" not in rotated and "text" not in outer
    counts = json.loads(report.read_text())["summary_counts"]["pdf_text_candidate_counts_by_reason"]
    assert counts["pdf_text_rotated_text"] == 1
    assert counts["pdf_text_label"] == 17
    assert len(read_gp_free_text(output)) == 17
