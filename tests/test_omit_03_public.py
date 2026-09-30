"""Public engraved PDF through the complete PDF-only route."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from test_dur_02_oracle import read_gp_free_text
from score2gp.pdf_text_labels import _classify
from score2gp.pdf_text_labels import attach_pdf_text_labels
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.ir import ScoreIR


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/pdf/omit_03/engraved_text_labels.pdf"


def test_printed_labels_reach_their_source_beats() -> None:
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        source = scratch / "input.pdf"
        shutil.copyfile(SOURCE, source)
        output = scratch / "written.gp"
        report = scratch / "report.json"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build"), "--json-report", str(report)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        assert read_gp_free_text(output) == [(1, 1, "Example A - [0:13]"),
                                             (3, 1, "Bridge passage")]
        counts = json.loads(report.read_text())["summary_counts"]["pdf_text_candidate_counts_by_reason"]
        assert counts["pdf_text_label"] == 2
        assert counts == {"pdf_text_label": 2, "pdf_text_non_label_glyph": 12}


def test_annotation_classifier_refuses_other_text_roles() -> None:
    assert _classify("H", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("sl.", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("P.M.", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("mf", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("rit.", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("Am7", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("A 7", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("Bø", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("Gm7\ue2605", "Arial", 9, True) == "pdf_text_music_symbol"
    assert _classify("= 120", "Arial", 9, True) == "pdf_text_tempo"
    assert _classify("Q=120", "Arial", 9, True) == "pdf_text_tempo"
    assert _classify("Music by Ada", "Arial", 9, True) == "pdf_text_page_furniture"
    assert _classify("Tuning: E A D G B E", "Arial", 9, True) == "pdf_text_page_furniture"
    assert _classify("Study in Motion", "Arial", 25, True) == "pdf_text_title_or_subtitle"
    assert _classify("Bridge passage", "Arial", 9, False) == "pdf_text_outside_annotation_band"
    assert _classify("[1:23]", "Helvetica", 9, True) == "pdf_text_label"
    assert _classify("[1:23]", "Helvetica", 9, False) == "pdf_text_outside_annotation_band"
    assert _classify("[1:23]", "Bravura", 9, True) == "pdf_text_music_symbol"
    assert _classify("[1:23]", "Helvetica", 18, True) == "pdf_text_title_or_subtitle"
    assert _classify("[1:23] - [1:45]", "Helvetica", 9, True) == "pdf_text_non_label_glyph"


def test_source_beat_rule_and_refusals() -> None:
    for name, expected_text, expected_reason in (
        ("nonfirst", [(1, 2, "Second beat")], "pdf_text_label"),
        ("tie", [], "pdf_text_beat_ambiguous"),
        ("occupied", [(1, 2, "First label")], "pdf_text_beat_occupied"),
        ("unavailable", [], "pdf_text_beat_unavailable"),
        ("boundary", [], "pdf_text_bar_ambiguous"),
    ):
        scratch_root = ROOT / "work"
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
            scratch = Path(directory)
            output = scratch / "written.gp"
            report = scratch / "report.json"
            result = subprocess.run(
                [sys.executable, "-m", "score2gp.cli", "convert", "--pdf",
                 str(ROOT / f"tests/fixtures/pdf/omit_03/{name}.pdf"),
                 "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
                 "--work-dir", str(scratch / "build"), "--json-report", str(report)],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
            )
            assert result.returncode == 0, (name, result.stderr[-1200:])
            assert read_gp_free_text(output) == expected_text, name
            details = json.loads((scratch / "build/text-labels.json").read_text())
            matching = [row for row in details["decisions"] if row["code"] == expected_reason]
            assert matching, name
            assert all(row["page_index"] == 0 and row["block_index"] >= 0 and row["line_index"] >= 0
                       for row in matching), name


def test_source_event_count_mismatch_refuses_engraved_label() -> None:
    source = ROOT / "tests/fixtures/pdf/omit_03/nonfirst.pdf"
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "written.gp"),
             "--work-dir", str(scratch / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        score = ScoreIR.model_validate(json.loads((scratch / "build/score.ir.json").read_text()))
        score.bars[0].events[1].text = None
        note_durations = read_note_durations(source, time_signature=(4, 4))
        note_durations["events"] = [event for event in note_durations["events"]
                                    if not (event["bar_index"] == 0 and event["status"] == "read"
                                            and event["location"]["bbox"][0] < 70)]
        details = attach_pdf_text_labels(source, note_durations, score)
        assert details["counts_by_reason"]["pdf_text_beat_unavailable"] == 1
        assert not any(event.text for event in score.bars[0].events)
