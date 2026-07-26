from __future__ import annotations

import pytest

from score2gp.build_ir import BuildIrInputRiskError
from score2gp.ir import BoundingBox, DEFAULT_TICKS_PER_QUARTER
from score2gp.pdf_tab_bar_assembly import PdfTabBarAssemblyError, assemble_pdf_tab_bar
from score2gp.tabraw import TabCandidate


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
    # 1 note event (480 ticks = eighth note) + trailing rest (3360 ticks)
    assert len(bar.events) >= 1
    assert bar.events[0].is_rest is False
    assert bar.events[0].timing.duration_ticks == 480
    assert bar.events[0].notes[0].pitch == 69  # E4 (64) + 5

    # Check total ticks in bar sum strictly to 3840
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


def test_assemble_pdf_tab_bar_overcapacity_refusal() -> None:
    # 5 notes + 2 quarter rests in normal mode (N <= 8) -> grid 480
    # 5 * 480 + 2 * 960 = 2400 + 1920 = 4320 > 3840 ticks
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

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        assemble_pdf_tab_bar(
            candidates,
            output_bar_idx=1,
            track_id="gtr-1",
            error_factory=BuildIrInputRiskError,
        )

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"


def test_assemble_pdf_tab_bar_too_many_events_refusal() -> None:
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

    with pytest.raises(PdfTabBarAssemblyError) as exc_info:
        assemble_pdf_tab_bar(
            candidates,
            output_bar_idx=1,
            track_id="gtr-1",
            error_factory=PdfTabBarAssemblyError,
        )

    assert exc_info.value.category == "pdf_only_tab_grouping_unsafe"
