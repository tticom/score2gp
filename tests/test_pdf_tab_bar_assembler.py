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
        raw_text="5",
        parsed_fret=5,
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

    # Duplicate-string grouper behavior retains one note for string 1
    assert len(bar.events[0].notes) == 1
    assert bar.events[0].notes[0].string == 1
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

    # Tight tolerance (2.0 pt) -> separate events; Wide tolerance (10.0 pt) -> chord
    bar_separate = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1", chord_x_tolerance_pt=2.0)
    assert len([e for e in bar_separate.events if not e.is_rest]) == 2

    bar_chord = assemble_pdf_tab_bar([c1, c2], output_bar_idx=1, track_id="gtr-1", chord_x_tolerance_pt=10.0)
    assert len(bar_chord.events[0].notes) == 2


def test_assemble_pdf_tab_bar_internal_error_raised() -> None:
    # 5 notes + 2 quarter rests -> overcapacity
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


def test_build_ir_exception_translation_exact_payload(tmp_path: Path) -> None:
    # Test build_ir_from_tabraw_only translates internal PdfTabBarAssemblerError into BuildIrInputRiskError with exact payload
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


def test_assemble_pdf_tab_bar_normalized_bar_equivalence() -> None:
    # Baseline/head normalized Bar characterization test
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
        x=10.0,
        y=20.0,
        string=5,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=20.0, x1=15.0, y1=25.0),
    )

    bar = assemble_pdf_tab_bar([c1, c2], output_bar_idx=2, track_id="gtr-1")

    assert bar.index == 2
    assert bar.time_signature.numerator == 4
    assert bar.time_signature.denominator == 4

    # First event: Power chord on onset 0, duration 480 ticks
    ev1 = bar.events[0]
    assert ev1.id == "bar-2-event-1"
    assert ev1.track_id == "gtr-1"
    assert ev1.timing.bar_index == 2
    assert ev1.timing.onset_ticks == 0
    assert ev1.timing.duration_ticks == 480
    assert ev1.timing.ticks_per_quarter == DEFAULT_TICKS_PER_QUARTER
    assert ev1.timing.notated_duration.value == "eighth"
    assert len(ev1.notes) == 2
    assert ev1.notes[0].fret == 5 and ev1.notes[0].string == 5
    assert ev1.notes[1].fret == 3 and ev1.notes[1].string == 6

    # Remainder rests sum to 3360 ticks (half_dotted: 2880 + quarter: 960... wait: 3360 = 2880 + 480 (half_dotted + eighth))
    total_duration = sum(e.timing.duration_ticks for e in bar.events)
    assert total_duration == 3840
