from __future__ import annotations

import json
from pathlib import Path
import pytest

from score2gp.build_ir import build_ir_from_files, build_ir_with_diagnostics_from_files
from score2gp.ir import validate_score_ir_file

MUSICXML = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")


def test_chord_symbol_attachment_cases(tmp_path) -> None:
    # 1. Unambiguous chord symbol above safely timed bar (x is None) - attaches to first event
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            {
                "id": "tab-001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "2",
                "parsed_fret": 2,
                "x": 180.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "chord-001",
                "kind": "chord-symbol",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "Cmaj7",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_chord_none.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    assert len(score.bars) == 1
    events = score.bars[0].events
    assert len(events) == 3  # Two playable notes and one rest

    # Cmaj7 attaches to first event
    assert events[0].chord_symbol == "Cmaj7"
    assert events[0].provenance[-1].raw_token_id == "chord-001"
    assert events[1].chord_symbol is None
    assert score.warnings == []

    # Check diagnostic counters
    assert diagnostics.symbol_attachment_chord_candidates_found == 1
    assert diagnostics.symbol_attachment_chord_candidates_attached == 1
    assert diagnostics.symbol_attachment_chord_candidates_unattached == 0

    # 2. Unambiguous chord symbol near second event (x = 175.0) - attaches to second event
    tabraw_data["candidates"][-1]["x"] = 175.0
    tabraw_file = tmp_path / "tabraw_chord_near.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    assert events[0].chord_symbol is None
    assert events[1].chord_symbol == "Cmaj7"
    assert events[1].provenance[-1].raw_token_id == "chord-001"
    assert score.warnings == []

    # 3. Ambiguous chord symbol between two events (x = 140.0) - tie/close range ambiguity
    tabraw_data["candidates"][-1]["x"] = 140.0
    tabraw_file = tmp_path / "tabraw_chord_ambiguous.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    assert events[0].chord_symbol is None
    assert events[1].chord_symbol is None
    
    # Ambiguous warning is emitted
    warning_codes = [w.code for w in score.warnings]
    assert "ambiguous_chord_symbol_attachment" in warning_codes
    assert diagnostics.symbol_attachment_chord_candidates_found == 1
    assert diagnostics.symbol_attachment_chord_candidates_attached == 0
    assert diagnostics.symbol_attachment_chord_candidates_unattached == 1


def test_technique_attachment_cases(tmp_path) -> None:
    # 1. Supported technique vibrato near exactly one note target (attached)
    # Let's keep only one fret candidate so there is exactly one note target
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            {
                "id": "tab-001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "vib",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_vibrato.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    # The first event is playable (others skipped/rest)
    playable_events = [e for e in events if not e.is_rest]
    assert len(playable_events) == 1
    note = playable_events[0].notes[0]
    
    assert len(note.techniques) == 1
    assert note.techniques[0].kind == "vibrato"
    assert note.provenance[-1].raw_token_id == "tech-001"

    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 1
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 0

    # 2. Ambiguous technique near multiple note targets
    # Let's add back the second fret candidate so there are two note targets
    tabraw_data["candidates"].insert(1, {
        "id": "tab-002",
        "kind": "fret",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bar_index": 1,
        "line_index": 1,
        "string": 1,
        "raw_text": "2",
        "parsed_fret": 2,
        "x": 180.0,
        "y": 40.0,
        "confidence": 0.95,
    })
    tabraw_file = tmp_path / "tabraw_tech_ambiguous.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    
    # Both notes should not have vibrato technique
    events = score.bars[0].events
    for ev in events:
        if not ev.is_rest:
            for note in ev.notes:
                # Vibrato was not attached because there are two notes in the bar
                assert not any(t.kind == "vibrato" for t in note.techniques)

    warning_codes = [w.code for w in score.warnings]
    assert "ambiguous_technique_attachment" in warning_codes
    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 0
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 1


def test_unsupported_technique_text(tmp_path) -> None:
    # Technique text of unsupported notation emits warning
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            {
                "id": "tab-001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "release",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_unsupported.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    warning_codes = [w.code for w in score.warnings]
    assert "unsupported_technique_text" in warning_codes


def test_span_technique_attachment_cases(tmp_path) -> None:
    # 1. Unambiguous hammer-on with exactly two sequential notes
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            {
                "id": "tab-001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "2",
                "parsed_fret": 2,
                "x": 180.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "h",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_ho.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    note1 = events[0].notes[0]
    note2 = events[1].notes[0]

    assert len(note1.techniques) == 1
    assert note1.techniques[0].kind == "hammer-on"
    assert note1.techniques[0].target_event_id == events[1].id
    assert note1.provenance[-1].raw_token_id == "tech-001"
    assert score.warnings == []

    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 1
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 0
