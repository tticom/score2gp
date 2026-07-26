from __future__ import annotations

from score2gp.ir import BoundingBox
from score2gp.pdf_tab_event_factory import (
    build_pdf_tab_editable_draft_annotation_text,
    build_pdf_tab_event_from_subgroup,
    determine_pdf_tab_event_duration,
)
from score2gp.tabraw import TabCandidate


def test_build_pdf_tab_editable_draft_annotation_text() -> None:
    text_default = build_pdf_tab_editable_draft_annotation_text(120.0, tempo_is_explicit=False)
    assert "Tempo defaulted to 120 bpm." in text_default
    assert "Editable draft generated from PDF tablature." in text_default

    text_explicit = build_pdf_tab_editable_draft_annotation_text(140.5, tempo_is_explicit=True)
    assert "Tempo set to 140.5 bpm." in text_explicit


def test_determine_pdf_tab_event_duration() -> None:
    c_note = TabCandidate(
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
    )
    c_rest = TabCandidate(
        id="c-rest",
        kind="fret",
        raw_text="quarter_rest",
        parsed_fret=None,
        x=20.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=20.0, y0=10.0, x1=25.0, y1=15.0),
    )

    assert determine_pdf_tab_event_duration([c_note], 480, "eighth") == (False, 480, "eighth")
    assert determine_pdf_tab_event_duration([c_rest], 480, "eighth") == (True, 960, "quarter")


def test_build_pdf_tab_event_from_subgroup_single_note() -> None:
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

    event = build_pdf_tab_event_from_subgroup(
        [c1],
        output_bar_idx=1,
        event_idx=0,
        onset_ticks=0,
        grid_spacing=480,
        duration_name="eighth",
    )

    assert event.id == "bar-1-event-1"
    assert event.is_rest is False
    assert len(event.notes) == 1
    assert event.notes[0].string == 1
    assert event.notes[0].fret == 5
    assert event.notes[0].pitch == 69  # E4 (64) + 5 = 69
    assert event.confidence == 0.9
    assert event.timing.onset_ticks == 0
    assert event.timing.duration_ticks == 480
    assert event.timing.notated_duration.value == "eighth"
    assert event.text is None


def test_build_pdf_tab_event_from_subgroup_chord() -> None:
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
        confidence=0.8,
    )
    c2 = TabCandidate(
        id="c-2",
        kind="fret",
        raw_text="3",
        parsed_fret=3,
        x=10.0,
        y=20.0,
        string=6,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=20.0, x1=15.0, y1=25.0),
        confidence=1.0,
    )

    event = build_pdf_tab_event_from_subgroup(
        [c1, c2],
        output_bar_idx=2,
        event_idx=1,
        onset_ticks=480,
        grid_spacing=480,
        duration_name="eighth",
    )

    assert event.id == "bar-2-event-2"
    assert event.is_rest is False
    assert len(event.notes) == 2
    assert event.confidence == 0.9  # (0.8 + 1.0) / 2
    assert len(event.provenance) == 2


def test_build_pdf_tab_event_from_subgroup_quarter_rest() -> None:
    c_rest = TabCandidate(
        id="c-rest",
        kind="fret",
        raw_text="quarter_rest",
        parsed_fret=None,
        x=20.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=20.0, y0=10.0, x1=25.0, y1=15.0),
        confidence=0.95,
    )

    event = build_pdf_tab_event_from_subgroup(
        [c_rest],
        output_bar_idx=1,
        event_idx=2,
        onset_ticks=960,
        grid_spacing=480,
        duration_name="eighth",
    )

    assert event.id == "bar-1-event-3"
    assert event.is_rest is True
    assert event.notes == []
    assert event.timing.duration_ticks == 960
    assert event.timing.notated_duration.value == "quarter"


def test_build_pdf_tab_event_from_subgroup_editable_first_event_text() -> None:
    c1 = TabCandidate(
        id="c-1",
        kind="fret",
        raw_text="0",
        parsed_fret=0,
        x=10.0,
        y=10.0,
        string=1,
        bar_index=1,
        system_index=1,
        staff_index=1,
        page_index=1,
        bbox=BoundingBox(page=1, x0=10.0, y0=10.0, x1=15.0, y1=15.0),
        confidence=1.0,
    )

    event = build_pdf_tab_event_from_subgroup(
        [c1],
        output_bar_idx=1,
        event_idx=0,
        onset_ticks=0,
        grid_spacing=960,
        duration_name="quarter",
        editable_draft=True,
        tempo_bpm=120.0,
        tempo_is_explicit=False,
    )

    assert event.text is not None
    assert "Editable draft generated from PDF tablature." in event.text
    assert "Tempo defaulted to 120 bpm." in event.text
