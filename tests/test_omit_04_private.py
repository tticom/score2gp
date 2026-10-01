"""OMIT-04 reference comparison through the independent GPIF reader."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

import pytest

from test_dur_02_oracle import read_gp_arpeggios


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("number,expected", [(3, 2), (4, 1), (5, 0), (6, 0), (7, 0)])
def test_lesson_arpeggios(number: int, expected: int) -> None:
    reference = ROOT / "fixtures/private" / f"Lesson-{number}.gp"
    source = ROOT / "fixtures/private" / f"Lesson-{number}.pdf"
    if not reference.is_file() or not source.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        produced = Path(directory) / "written.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(produced),
             "--work-dir", str(Path(directory) / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        truth, written = read_gp_arpeggios(reference), read_gp_arpeggios(produced)
        assert len(truth) == expected
        assert written == truth


def test_other_reference_arpeggios_have_located_refusals() -> None:
    name = "Can't Find My Way Home (open chord shenanigans)"
    source = ROOT / "fixtures/private" / f"{name}.pdf"
    reference = ROOT / "fixtures/private" / f"{name}.gp"
    if not source.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "written.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        assert len(read_gp_arpeggios(reference)) == 5
        assert read_gp_arpeggios(output) == []
        report = json.loads((scratch / "build/arpeggios.json").read_text())
        assert report["counts_by_reason"] == {
            "pdf_arpeggio_beat_unavailable": 5, "pdf_arpeggio_tab_duplicate": 5,
        }
        refusals = [item for item in report["decisions"]
                    if item["code"] == "pdf_arpeggio_beat_unavailable"]
        assert len(refusals) == 5
        assert all(item["page_index"] >= 0 and item["stroke_indices"] for item in refusals)
