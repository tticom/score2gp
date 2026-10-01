"""Public engraved vector controls for OMIT-04 recognition and refusal."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pymupdf

from test_dur_02_oracle import read_gp_arpeggios
from score2gp.ir import ScoreIR
from score2gp.gp_package import extract_score_ir_from_gp
from score2gp.gpif import build_gpif
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf_arpeggios import _marks, attach_pdf_arpeggios


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/pdf/omit_04"


def test_vector_marks_and_nearby_non_marks() -> None:
    for name, count, direction in (("chord", 1, "down"), ("tab_only", 1, "down"),
                                   ("down", 1, "up"),
                                   ("ambiguous", 1, "down"), ("negative", 0, None)):
        with pymupdf.open(FIXTURES / f"{name}.pdf") as document:
            marks = [mark for page in document for mark in _marks(page)]
        assert len(marks) == count, name
        if direction:
            assert marks[0]["direction"] == direction, name
            assert len(marks[0]["stroke_indices"]) == 6, name


def test_printed_chord_mark_reaches_gpif() -> None:
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        source = scratch / "input.pdf"
        shutil.copyfile(FIXTURES / "chord.pdf", source)
        output = scratch / "written.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        assert read_gp_arpeggios(output) == [(3, 1, "Down")]
        report = json.loads((scratch / "build/arpeggios.json").read_text())
        assert report["counts_by_reason"] == {"pdf_arpeggio_attached": 1}
        assert report["decisions"][0]["stroke_indices"]


def test_source_chord_attachment_and_refusal() -> None:
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        baseline_source = scratch / "input.pdf"
        shutil.copyfile(ROOT / "tests/fixtures/pdf/omit_03/engraved_text_labels.pdf", baseline_source)
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf",
             str(baseline_source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "base.gp"),
             "--work-dir", str(scratch / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        original = ScoreIR.model_validate(json.loads((scratch / "build/score.ir.json").read_text()))
        # The engraved public variant adds a second head and TAB digit to beat 1.
        for name, expected, direction in (("tab_only", "pdf_arpeggio_attached", "down"),
                                          ("down", "pdf_arpeggio_attached", "up"),
                                          ("ambiguous", "pdf_arpeggio_chord_ambiguous", None),
                                          ("negative", None, None)):
            score = copy.deepcopy(original)
            score.bars[0].events[0].notes.append(copy.deepcopy(score.bars[0].events[0].notes[0]))
            source = FIXTURES / f"{name}.pdf"
            durations = read_note_durations(source, time_signature=(4, 4))
            result = attach_pdf_arpeggios(source, durations, score)
            assert result["counts_by_reason"] == ({expected: 1} if expected else {}), name
            assert score.bars[0].events[0].arpeggio == direction, name
            assert all(event.arpeggio is None for event in score.bars[0].events[1:]), name
            if direction:
                assert result["decisions"][0]["bar_index"] == 1
                assert result["decisions"][0]["beat_index"] == 1
                assert score.bars[0].events[0].provenance[-1].raw["stroke_indices"]
                marks = ET.fromstring(build_gpif(score)).findall(".//Arpeggio")
                assert [(mark.text, mark.attrib) for mark in marks] == [
                    ("Up" if direction == "up" else "Down", {}),
                ]
            if name == "ambiguous":
                assert score.warnings[-1].code == "pdf_arpeggio_chord_ambiguous"
                assert score.warnings[-1].provenance[0].page == 1
                assert score.warnings[-1].provenance[0].raw["stroke_indices"]

FIXTURE_IR = ROOT / "fixtures/public/test_gpif_beat_symbols.ir.json"

# build_gpif switches to a classic test-only layout while pytest is loaded, so the production
# (relational) package that Guitar Pro reads must be written by a process without pytest.
_WRITE_SCRIPT = """
import sys
from score2gp.gp_package import write_gp
from score2gp.ir import ScoreIR
ir_path, out_path, direction = sys.argv[1:4]
score = ScoreIR.from_json_file(ir_path)
for bar in score.bars:
    for event in bar.events:
        event.arpeggio = None if direction == "none" else (direction if event.arpeggio else None)
assert write_gp(score, out_path) == []
"""


def _write_production_gp(directory: Path, name: str, direction: str) -> Path:
    out = directory / name
    run = subprocess.run(
        [sys.executable, "-c", _WRITE_SCRIPT, str(FIXTURE_IR), str(out), direction],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
    )
    assert run.returncode == 0, run.stderr[-1200:]
    return out


def _arpeggios(score: ScoreIR) -> list[str | None]:
    return [event.arpeggio for bar in score.bars for event in bar.events if event.arpeggio]


def test_gp_reader_round_trips_both_arpeggio_directions() -> None:
    assert _arpeggios(ScoreIR.from_json_file(FIXTURE_IR)) == ["up"]
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        for direction, text in (("up", "Up"), ("down", "Down")):
            written = _write_production_gp(Path(directory), f"{direction}.gp", direction)
            with zipfile.ZipFile(written) as package:
                gpif = package.read("Content/score.gpif")
            assert f"<Arpeggio>{text}</Arpeggio>".encode() in gpif
            assert extract_score_ir_from_gp(written) is not None
            assert _arpeggios(extract_score_ir_from_gp(written)) == [direction]


def test_gp_reader_tolerates_absent_and_empty_arpeggio_elements() -> None:
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        absent = _write_production_gp(Path(directory), "absent.gp", "none")
        assert b"<Arpeggio" not in zipfile.ZipFile(absent).read("Content/score.gpif")
        assert _arpeggios(extract_score_ir_from_gp(absent)) == []

        written = _write_production_gp(Path(directory), "up.gp", "up")
        emptied = Path(directory) / "empty.gp"
        with zipfile.ZipFile(written) as zin, zipfile.ZipFile(emptied, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "Content/score.gpif":
                    assert b"<Arpeggio>Up</Arpeggio>" in data
                    data = data.replace(b"<Arpeggio>Up</Arpeggio>", b"<Arpeggio />")
                zout.writestr(item, data)
        assert _arpeggios(extract_score_ir_from_gp(emptied)) == []