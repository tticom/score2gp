"""Real-source acceptance for PDF-GROUP-02: full-chord string-line gaps no longer split the TAB staff."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"


def _convert(name: str) -> tuple[subprocess.CompletedProcess, dict]:
    pdf = PRIVATE / name
    if not pdf.is_file():
        pytest.skip("private corpus absent")
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="pdf_group_02_", dir=work) as directory:
        scratch = Path(directory)
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf), "--pdf-only-tab",
             "--time-signature", "4/4", "--out", str(scratch / "output.gp"),
             "--work-dir", str(scratch / "work"), "--json-report", str(scratch / "report.json")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        report = json.loads((scratch / "report.json").read_text(encoding="utf-8"))
        ir_path = scratch / "work" / "score.ir.json"
        ir = json.loads(ir_path.read_text(encoding="utf-8")) if ir_path.is_file() else None
    return result, {"report": report, "ir": ir}


def test_a7_blues_lick_converts_with_every_digit_placed() -> None:
    result, out = _convert("A7-Blues-Lick.pdf")
    assert result.returncode == 0, result.stderr[-800:]
    ir = out["ir"]
    assert len(ir["bars"]) == 4
    assert out["report"]["summary_counts"]["matched_candidate_count"] == 46
    tuning = {s["number"]: s["pitch"] for s in ir["tracks"][0]["tuning"]["strings"]}
    notes = [n for bar in ir["bars"] for e in bar["events"] for n in e["notes"]]
    assert len(notes) == 46
    assert all(n["pitch"] == tuning[n["string"]] + n["fret"] for n in notes)
    for bar in ir["bars"]:
        assert sum(e["timing"]["duration_ticks"] for e in bar["events"]) == 3840


def test_e_chord_lick_chord_passes_layout_gating() -> None:
    result, out = _convert("E_Chord_Lick_Chord.pdf")
    report = out["report"]
    assert report.get("stage") != "layout-gating"
    assert report["pdf_only_diagnostics"]["pdf_grouping_status"] == "safe"
