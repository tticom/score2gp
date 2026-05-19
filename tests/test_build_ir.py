from __future__ import annotations

from pathlib import Path

from score2gp.build_ir import build_ir_from_files
from score2gp.ir import validate_score_ir_file

MUSICXML = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")


def test_build_ir_creates_valid_scoreir_from_synthetic_musicxml_and_tabraw(tmp_path) -> None:
    out = tmp_path / "built.ir.json"

    score = build_ir_from_files(MUSICXML, TABRAW, out)
    validated, errors = validate_score_ir_file(out)

    assert errors == []
    assert validated is not None
    assert score.schema_version == "0.1.0"
    assert score.metadata.title == "Tiny MusicXML Test"
    assert score.tempo.bpm == 96
    assert score.tracks[0].tuning.name == "Standard guitar"
    assert len(score.bars) == 1

    events = score.bars[0].events
    assert [event.timing.onset_ticks for event in events] == [0, 960, 1920]
    assert [event.timing.duration_ticks for event in events] == [960, 960, 1920]
    assert [event.timing.voice for event in events] == [1, 1, 1]
    assert events[0].notes[0].pitch == 64
    assert events[0].notes[0].string == 1
    assert events[0].notes[0].fret == 0
    assert events[1].notes[0].pitch == 66
    assert events[1].notes[0].techniques[0].kind == "tie"
    assert events[2].is_rest is True


def test_build_ir_records_warning_for_unaligned_musicxml_note(tmp_path) -> None:
    empty_tabraw = tmp_path / "empty_tabraw.json"
    empty_tabraw.write_text(
        '{"schema_version": "tabraw.v0.1", "source_pdf": "synthetic", "candidates": [], "warnings": []}',
        encoding="utf-8",
    )

    score = build_ir_from_files(MUSICXML, empty_tabraw)

    codes = [warning.code for warning in score.warnings]
    assert "tab-candidate-missing" in codes
    assert "scoreir-event-skipped" in codes
    assert score.bars[0].events[-1].is_rest is True
