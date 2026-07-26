from __future__ import annotations

from pathlib import Path

import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
from score2gp.ir import BoundingBox, DEFAULT_TICKS_PER_QUARTER
from score2gp.pdf_tab_bar_assembler import PdfTabBarAssemblerError, assemble_pdf_tab_bar
from score2gp.tabraw import TabCandidate, TabRaw


def test_assemble_pdf_tab_bar_empty() -> None:
    bar = assemble_pdf_tab_bar([], output_bar_idx=1, track_id="gtr-1")

    assert bar.index == 1
    assert len(bar.events) == 1
    assert bar.events[0].is_rest is True
    assert bar.events[0].timing.duration_ticks == 3840
    assert bar.events[0].timing.notated_duration.value == "whole"


def test_assemble_pdf_tab_bar_single_note() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.9,
    )

    bar = assemble_pdf_tab_bar([c1], output_bar_idx=1, track_id="gtr-1")

    assert bar.index == 1
    assert len(bar.events) >= 1
    assert bar.events[0].is_rest is False
    assert bar.events[0].timing.duration_ticks == 480
    assert bar.events[0].notes[0].pitch == 69  # E4 (64) + 5

    total_ticks = sum(e.timing.duration_ticks for e in bar.events)
    assert total_ticks == 3840


def test_assemble_pdf_tab_bar_chord() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.9,
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="7",
        parsed_fret=7,
        x=10.0,
        y=20.0,
        string=3,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=20.0, x1=15.0, y1=25.0),
        confidence=0.8,
    )

    bar = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1")

    assert bar.events[0].is_rest is False
    assert len(bar.events[0].notes) == 2
    assert bar.events[0].notes[0].string == 1
    assert bar.events[0].notes[1].string == 3
    assert sum(e.timing.duration_ticks for e in bar.events) == 3840


def test_assemble_pdf_tab_bar_sequential_notes() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="3",
        parsed_fret=3,
        x=10.0,
        y=10.0,
        string=6,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=30.0,
        y=10.0,
        string=5,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=30.0, y0=10.0, x1=35.0, y1=15.0),
    )

    bar = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1")

    note_events = [e for e in bar.events if not e.is_rest]
    assert len(note_events) == 2
    assert note_events[0].timing.onset_ticks == 0
    assert note_events[0].notes[0].fret == 3
    assert note_events[1].timing.onset_ticks == 480
    assert note_events[1].notes[0].fret == 5
    assert sum(e.timing.duration_ticks for e in bar.events) == 3840


def test_assemble_pdf_tab_bar_duplicate_string_candidates() -> None:
    # Two candidates on the exact same string at the exact same x coordinate
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.9,
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="7",
        parsed_fret=7,
        x=10.0,
        y=12.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=12.0, x1=15.0, y1=17.0),
        confidence=0.7,
    )

    bar = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1")

    # Duplicate-string grouper splits duplicate strings into separate ordered subgroups
    note_events = [e for e in bar.events if not e.is_rest]
    assert len(note_events) == 2

    # Event 1: c-1 (fret 5 on string 1) at onset 0
    assert note_events[0].timing.onset_ticks == 0
    assert len(note_events[0].notes) == 1
    assert note_events[0].notes[0].fret == 5
    assert note_events[0].notes[0].string == 1
    assert note_events[0].notes[0].provenance[0].raw_token_id == "c-1"

    # Event 2: c-2 (fret 7 on string 1) at onset 480
    assert note_events[1].timing.onset_ticks == 480
    assert len(note_events[1].notes) == 1
    assert note_events[1].notes[0].fret == 7
    assert note_events[1].notes[0].string == 1
    assert note_events[1].notes[0].provenance[0].raw_token_id == "c-2"

    assert sum(e.timing.duration_ticks for e in bar.events) == 3840


def test_assemble_pdf_tab_bar_quarter_rest() -> None:
    c_rest = TabCandidate(
        id="c-rest",
        kind="fret",
        raw_text="quarter_rest",
        parsed_fret=None,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.95,
    )

    bar = assemble_pdf_tab_bar([c_rest], output_bar_idx=1, track_id="gtr-1")

    assert bar.events[0].is_rest is True
    assert bar.events[0].timing.duration_ticks == 960
    assert bar.events[0].timing.notated_duration.value == "quarter"
    assert sum(e.timing.duration_ticks for e in bar.events) == 3840


def test_assemble_pdf_tab_bar_custom_chord_x_tolerance() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="3",
        parsed_fret=3,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=15.0,
        y=20.0,
        string=2,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=15.0, y0=20.0, x1=20.0, y1=25.0),
    )

    bar_separate = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1", chord_x_tolerance_pt=2.0)
    assert len([e for e in bar_separate.events if not e.is_rest]) == 2

    bar_chord = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1", chord_x_tolerance_pt=10.0)
    assert len(bar_chord.events[0].notes) == 2


def test_assemble_pdf_tab_bar_internal_error_raised() -> None:
    candidates: list[TabCandidate] = []
    for idx in range(5):
        candidates.append(
            TabCandidate(
                id=f"c-{idx}",
                kind="fret",
                raw_text="5",
                parsed_fret=5,
                x=float(idx * 10),
                y=10.0,
                string=1,
                bar_index=1,
                system_index=1,
                staff_index=1,
                page_index=1,
                bbox=BoundingBox(page=1, x0=float(idx * 10), y0=10.0, x1=float(idx * 10 + 5), y1=15.0),
            )
        )
    for idx in range(5, 7):
        candidates.append(
            TabCandidate(
                id=f"c-{idx}",
                kind="fret",
                raw_text="quarter_rest",
                parsed_fret=None,
                x=float(idx * 10),
                y=10.0,
                string=1,
                bar_index=1,
                system_index=1,
                staff_index=1,
                page_index=1,
                bbox=BoundingBox(page=1, x0=float(idx * 10), y0=10.0, x1=float(idx * 10 + 5), y1=15.0),
            )
        )

    with pytest.raises(PdfTabBarAssemblerError) as exc_info:
        assemble_pdf_tab_bar(candidates, output_bar_idx=1, track_id="gtr-1")

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"
    assert exc_info.value.stage == "measure-assembly"
    assert exc_info.value.details == {
        "bar_index": "1",
        "accumulated_ticks": "4320",
        "measure_capacity": "3840",
    }


def test_build_ir_grouping_unsafe_refusal_exact_payload(tmp_path: Path) -> None:
    candidates = [
        TabCandidate(
            id=f"c-{idx}",
            kind="fret",
            raw_text="1",
            parsed_fret=1,
            x=float(idx * 10),
            y=10.0,
            string=1,
            bar_index=1,
            system_index=1,
            staff_index=1,
            page_index=1,
            bbox=BoundingBox(page=1, x0=float(idx * 10), y0=10.0, x1=float(idx * 10 + 5), y1=15.0),
        )
        for idx in range(65)
    ]

    tabraw = TabRaw(candidates=candidates)
    tabraw_file = tmp_path / "tabraw.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file)

    assert exc_info.value.category == "pdf_only_tab_grouping_unsafe"
    assert exc_info.value.stage == "layout-gating"
    assert str(exc_info.value) == "PDF-only tab building refused: too many events (65) in bar 1."
    assert exc_info.value.details == {}


def test_build_ir_overcapacity_refusal_exact_payload(tmp_path: Path) -> None:
    candidates: list[TabCandidate] = []
    for idx in range(5):
        candidates.append(
            TabCandidate(
                id=f"c-{idx}",
                kind="fret",
                raw_text="5",
                parsed_fret=5,
                x=float(idx * 10),
                y=10.0,
                string=1,
                bar_index=1,
                system_index=1,
                staff_index=1,
                page_index=1,
                bbox=BoundingBox(page=1, x0=float(idx * 10), y0=10.0, x1=float(idx * 10 + 5), y1=15.0),
            )
        )
    for idx in range(5, 7):
        candidates.append(
            TabCandidate(
                id=f"c-{idx}",
                kind="fret",
                raw_text="quarter_rest",
                parsed_fret=None,
                x=float(idx * 10),
                y=10.0,
                string=1,
                bar_index=1,
                system_index=1,
                staff_index=1,
                page_index=1,
                bbox=BoundingBox(page=1, x0=float(idx * 10), y0=10.0, x1=float(idx * 10 + 5), y1=15.0),
            )
        )

    tabraw = TabRaw(candidates=candidates)
    tabraw_file = tmp_path / "tabraw.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file)

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"
    assert exc_info.value.stage == "measure-assembly"
    assert str(exc_info.value) == "Candidate note events in bar 1 exceed measure capacity 3840 ticks (accumulated 4320 ticks)."
    assert exc_info.value.details == {
        "bar_index": "1",
        "accumulated_ticks": "4320",
        "measure_capacity": "3840",
    }


# Complete Normalized Bar Equivalence Tests for all 4 required scenarios:
# Each test compares full bar.model_dump(mode="json") against fixed baseline data.

def test_normalized_bar_equivalence_single_event() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.9,
    )

    bar = assemble_pdf_tab_bar([c1], output_bar_idx=1, track_id="gtr-1")

    expected_baseline_bar = {
        "index": 1,
        "time_signature": {"numerator": 4, "denominator": 4},
        "key_signature": None,
        "events": [
            {
                "id": "bar-1-event-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 1,
                    "onset_ticks": 0,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 1,
                        "fret": 5,
                        "pitch": 69,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.9,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                                "raw_token_id": "c-1",
                                "raw": {"kind": "fret", "raw_text": "5", "parsed_fret": 5, "string": 1, "x": 10.0, "y": 10.0},
                                "confidence": 0.9,
                            }
                        ],
                        "expression_controller": None,
                    }
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.9,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                        "raw_token_id": "c-1",
                        "raw": {"kind": "fret", "raw_text": "5", "parsed_fret": 5, "string": 1, "x": 10.0, "y": 10.0},
                        "confidence": 0.9,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-1-rest-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 1,
                    "onset_ticks": 480,
                    "duration_ticks": 1920,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "half", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
            {
                "id": "bar-1-rest-2",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 1,
                    "onset_ticks": 2400,
                    "duration_ticks": 960,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "quarter", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
            {
                "id": "bar-1-rest-3",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 1,
                    "onset_ticks": 3360,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
        ],
        "tempo": None,
        "layout_break": None,
        "anacrusis": False,
        "barline": None,
        "repeat_count": None,
        "measure_layout": None,
        "bar_numbering": None,
        "directions": None,
        "marker": None,
        "marker_color": None,
        "alternate_ending_passes": None,
        "alternate_ending_is_stop": None,
        "multi_measure_rest_count": None,
        "repeat_count_overlay": None,
        "tempo_automation": None,
    }

    assert bar.model_dump(mode="json") == expected_baseline_bar


def test_normalized_bar_equivalence_chord() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="5",
        parsed_fret=5,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.9,
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="7",
        parsed_fret=7,
        x=10.0,
        y=20.0,
        string=3,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=20.0, x1=15.0, y1=25.0),
        confidence=0.8,
    )

    bar = assemble_pdf_tab_bar([c1, c2], output_bar_idx=2, track_id="gtr-1")

    expected_baseline_bar = {
        "index": 2,
        "time_signature": {"numerator": 4, "denominator": 4},
        "key_signature": None,
        "events": [
            {
                "id": "bar-2-event-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 2,
                    "onset_ticks": 0,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 1,
                        "fret": 5,
                        "pitch": 69,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.9,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                                "raw_token_id": "c-1",
                                "raw": {"kind": "fret", "raw_text": "5", "parsed_fret": 5, "string": 1, "x": 10.0, "y": 10.0},
                                "confidence": 0.9,
                            }
                        ],
                        "expression_controller": None,
                    },
                    {
                        "string": 3,
                        "fret": 7,
                        "pitch": 62,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.8,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 10.0, "y0": 20.0, "x1": 15.0, "y1": 25.0},
                                "raw_token_id": "c-2",
                                "raw": {"kind": "fret", "raw_text": "7", "parsed_fret": 7, "string": 3, "x": 10.0, "y": 20.0},
                                "confidence": 0.8,
                            }
                        ],
                        "expression_controller": None,
                    },
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": (0.9 + 0.8) / 2.0,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                        "raw_token_id": "c-1",
                        "raw": {"kind": "fret", "raw_text": "5", "parsed_fret": 5, "string": 1, "x": 10.0, "y": 10.0},
                        "confidence": 0.9,
                    },
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 10.0, "y0": 20.0, "x1": 15.0, "y1": 25.0},
                        "raw_token_id": "c-2",
                        "raw": {"kind": "fret", "raw_text": "7", "parsed_fret": 7, "string": 3, "x": 10.0, "y": 20.0},
                        "confidence": 0.8,
                    },
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-2-rest-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 2,
                    "onset_ticks": 480,
                    "duration_ticks": 1920,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "half", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
            {
                "id": "bar-2-rest-2",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 2,
                    "onset_ticks": 2400,
                    "duration_ticks": 960,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "quarter", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
            {
                "id": "bar-2-rest-3",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 2,
                    "onset_ticks": 3360,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
        ],
        "tempo": None,
        "layout_break": None,
        "anacrusis": False,
        "barline": None,
        "repeat_count": None,
        "measure_layout": None,
        "bar_numbering": None,
        "directions": None,
        "marker": None,
        "marker_color": None,
        "alternate_ending_passes": None,
        "alternate_ending_is_stop": None,
        "multi_measure_rest_count": None,
        "repeat_count_overlay": None,
        "tempo_automation": None,
    }

    assert bar.model_dump(mode="json") == expected_baseline_bar


def test_normalized_bar_equivalence_explicit_rest() -> None:
    c_rest = TabCandidate(
        id="c-rest",
        kind="fret",
        raw_text="quarter_rest",
        parsed_fret=None,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=0.95,
    )

    bar = assemble_pdf_tab_bar([c_rest], output_bar_idx=3, track_id="gtr-1")

    expected_baseline_bar = {
        "index": 3,
        "time_signature": {"numerator": 4, "denominator": 4},
        "key_signature": None,
        "events": [
            {
                "id": "bar-3-event-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 3,
                    "onset_ticks": 0,
                    "duration_ticks": 960,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "quarter", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.95,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                        "raw_token_id": "c-rest",
                        "raw": {"kind": "fret", "raw_text": "quarter_rest", "parsed_fret": None, "string": 1, "x": 10.0, "y": 10.0},
                        "confidence": 0.95,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-3-rest-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 3,
                    "onset_ticks": 960,
                    "duration_ticks": 1920,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "half", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
            {
                "id": "bar-3-rest-2",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 3,
                    "onset_ticks": 2880,
                    "duration_ticks": 960,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "quarter", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
        ],
        "tempo": None,
        "layout_break": None,
        "anacrusis": False,
        "barline": None,
        "repeat_count": None,
        "measure_layout": None,
        "bar_numbering": None,
        "directions": None,
        "marker": None,
        "marker_color": None,
        "alternate_ending_passes": None,
        "alternate_ending_is_stop": None,
        "multi_measure_rest_count": None,
        "repeat_count_overlay": None,
        "tempo_automation": None,
    }

    assert bar.model_dump(mode="json") == expected_baseline_bar


def test_normalized_bar_equivalence_multi_event_sequential() -> None:
    c_seq1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="0",
        parsed_fret=0,
        x=10.0,
        y=10.0,
        string=6,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
    )
    c_seq2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="2",
        parsed_fret=2,
        x=30.0,
        y=10.0,
        string=5,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=30.0, y0=10.0, x1=35.0, y1=15.0),
    )
    c_seq3 = TabCandidate(
        id="c-3",
        kind="fret",
        raw_text="2",
        parsed_fret=2,
        x=50.0,
        y=10.0,
        string=4,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=50.0, y0=10.0, x1=55.0, y1=15.0),
    )
    c_seq4 = TabCandidate(
        id="c-4",
        kind="fret",
        raw_text="1",
        parsed_fret=1,
        x=70.0,
        y=10.0,
        string=3,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=70.0, y0=10.0, x1=75.0, y1=15.0),
    )

    bar = assemble_pdf_tab_bar([c_seq1, c_seq2, c_seq3, c_seq4], output_bar_idx=4, track_id="gtr-1")

    expected_baseline_bar = {
        "index": 4,
        "time_signature": {"numerator": 4, "denominator": 4},
        "key_signature": None,
        "events": [
            {
                "id": "bar-4-event-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 4,
                    "onset_ticks": 0,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 6,
                        "fret": 0,
                        "pitch": 40,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.5,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                                "raw_token_id": "c-1",
                                "raw": {"kind": "fret", "raw_text": "0", "parsed_fret": 0, "string": 6, "x": 10.0, "y": 10.0},
                                "confidence": 0.5,
                            }
                        ],
                        "expression_controller": None,
                    }
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.5,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 10.0, "y0": 10.0, "x1": 15.0, "y1": 15.0},
                        "raw_token_id": "c-1",
                        "raw": {"kind": "fret", "raw_text": "0", "parsed_fret": 0, "string": 6, "x": 10.0, "y": 10.0},
                        "confidence": 0.5,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-4-event-2",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 4,
                    "onset_ticks": 480,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 5,
                        "fret": 2,
                        "pitch": 47,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.5,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 30.0, "y0": 10.0, "x1": 35.0, "y1": 15.0},
                                "raw_token_id": "c-2",
                                "raw": {"kind": "fret", "raw_text": "2", "parsed_fret": 2, "string": 5, "x": 30.0, "y": 10.0},
                                "confidence": 0.5,
                            }
                        ],
                        "expression_controller": None,
                    }
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.5,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 30.0, "y0": 10.0, "x1": 35.0, "y1": 15.0},
                        "raw_token_id": "c-2",
                        "raw": {"kind": "fret", "raw_text": "2", "parsed_fret": 2, "string": 5, "x": 30.0, "y": 10.0},
                        "confidence": 0.5,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-4-event-3",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 4,
                    "onset_ticks": 960,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 4,
                        "fret": 2,
                        "pitch": 52,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.5,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 50.0, "y0": 10.0, "x1": 55.0, "y1": 15.0},
                                "raw_token_id": "c-3",
                                "raw": {"kind": "fret", "raw_text": "2", "parsed_fret": 2, "string": 4, "x": 50.0, "y": 10.0},
                                "confidence": 0.5,
                            }
                        ],
                        "expression_controller": None,
                    }
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.5,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 50.0, "y0": 10.0, "x1": 55.0, "y1": 15.0},
                        "raw_token_id": "c-3",
                        "raw": {"kind": "fret", "raw_text": "2", "parsed_fret": 2, "string": 4, "x": 50.0, "y": 10.0},
                        "confidence": 0.5,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-4-event-4",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 4,
                    "onset_ticks": 1440,
                    "duration_ticks": 480,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "eighth", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [
                    {
                        "string": 3,
                        "fret": 1,
                        "pitch": 56,
                        "is_dead": False,
                        "articulations": [],
                        "techniques": [],
                        "left_hand_fingering": None,
                        "right_hand_fingering": None,
                        "confidence": 0.5,
                        "provenance": [
                            {
                                "source_stage": "pdf-text",
                                "page": 1,
                                "system_id": "system-1",
                                "staff_id": "staff-1",
                                "bar_index": 1,
                                "bbox": {"page": 1, "x0": 70.0, "y0": 10.0, "x1": 75.0, "y1": 15.0},
                                "raw_token_id": "c-4",
                                "raw": {"kind": "fret", "raw_text": "1", "parsed_fret": 1, "string": 3, "x": 70.0, "y": 10.0},
                                "confidence": 0.5,
                            }
                        ],
                        "expression_controller": None,
                    }
                ],
                "is_rest": False,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 0.5,
                "provenance": [
                    {
                        "source_stage": "pdf-text",
                        "page": 1,
                        "system_id": "system-1",
                        "staff_id": "staff-1",
                        "bar_index": 1,
                        "bbox": {"page": 1, "x0": 70.0, "y0": 10.0, "x1": 75.0, "y1": 15.0},
                        "raw_token_id": "c-4",
                        "raw": {"kind": "fret", "raw_text": "1", "parsed_fret": 1, "string": 3, "x": 70.0, "y": 10.0},
                        "confidence": 0.5,
                    }
                ],
                "expression_controller": None,
            },
            {
                "id": "bar-4-rest-1",
                "track_id": "gtr-1",
                "timing": {
                    "bar_index": 4,
                    "onset_ticks": 1920,
                    "duration_ticks": 1920,
                    "ticks_per_quarter": DEFAULT_TICKS_PER_QUARTER,
                    "voice": 1,
                    "notated_duration": {"value": "half", "dots": 0},
                    "tuplet": None,
                    "grace": None,
                },
                "notes": [],
                "is_rest": True,
                "chord_symbol": None,
                "chord_diagram": None,
                "dynamic": None,
                "hairpin": None,
                "fermata": None,
                "arpeggio": None,
                "arpeggio_duration": None,
                "brush": None,
                "brush_duration": None,
                "text": None,
                "techniques": [],
                "confidence": 1.0,
                "provenance": [],
                "expression_controller": None,
            },
        ],
        "tempo": None,
        "layout_break": None,
        "anacrusis": False,
        "barline": None,
        "repeat_count": None,
        "measure_layout": None,
        "bar_numbering": None,
        "directions": None,
        "marker": None,
        "marker_color": None,
        "alternate_ending_passes": None,
        "alternate_ending_is_stop": None,
        "multi_measure_rest_count": None,
        "repeat_count_overlay": None,
        "tempo_automation": None,
    }

    assert bar.model_dump(mode="json") == expected_baseline_bar
