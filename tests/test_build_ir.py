from __future__ import annotations

from pathlib import Path

from score2gp.build_ir import build_ir_from_files
from score2gp.ir import validate_score_ir_file

MUSICXML = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")
RICH_MUSICXML = Path("tests/fixtures/musicxml/rich_guitar_cases.musicxml")
RICH_TABRAW = Path("tests/fixtures/tabraw/rich_guitar_cases_tabraw.json")


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


def test_build_ir_handles_chords_tuplets_harmony_and_technique_diagnostics(tmp_path) -> None:
    out = tmp_path / "rich.ir.json"

    score = build_ir_from_files(RICH_MUSICXML, RICH_TABRAW, out)
    validated, errors = validate_score_ir_file(out)

    assert errors == []
    assert validated is not None
    assert score.metadata.title == "Rich Guitar Cases"
    assert score.tempo.bpm == 72
    assert len(score.bars) == 2

    first_bar_events = score.bars[0].events
    assert first_bar_events[0].chord_symbol == "E7"
    assert len(first_bar_events[0].notes) == 2
    assert [note.fret for note in first_bar_events[0].notes] == [0, 3]
    assert first_bar_events[1].notes[0].fret == 2
    assert {technique.kind for technique in first_bar_events[1].notes[0].techniques} == {"slide", "hammer-on"}

    triplet_events = first_bar_events[2:5]
    assert [event.timing.onset_ticks for event in triplet_events] == [1920, 2240, 2560]
    assert all(event.timing.duration_ticks == 320 for event in triplet_events)
    assert all(event.timing.tuplet is not None for event in triplet_events)
    assert triplet_events[0].notes[0].techniques[0].kind == "bend"
    assert triplet_events[0].notes[0].techniques[0].semitones == 0.5
    assert triplet_events[1].notes[0].techniques[0].kind == "vibrato"
    assert triplet_events[2].notes[0].techniques[0].kind == "slur"

    assert score.bars[1].events[0].chord_symbol == "Gmaj7"
    assert score.bars[1].events[0].notes[0].fret == 8
    assert score.bars[1].events[1].is_rest is True

    codes = [warning.code for warning in score.warnings]
    assert "tab-candidate-unused" in codes
    assert "tabraw-chord-symbol-not-aligned" in codes
    assert "tabraw-technique-text-not-aligned" in codes
    assert "synthetic-tabraw-note" in codes

    tab_provenance = first_bar_events[0].notes[0].provenance[-1]
    assert tab_provenance.raw["alignment_strategy"] == "bar-x-order"
    assert tab_provenance.raw["pitch_matched"] is True
