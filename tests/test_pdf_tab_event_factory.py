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
        track_id="gtr-1",
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
        track_id="gtr-1",
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
        track_id="gtr-1",
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
        track_id="gtr-1",
        editable_draft=True,
        tempo_bpm=120.0,
        tempo_is_explicit=False,
    )

    assert event.text is not None
    assert "Editable draft generated from PDF tablature." in event.text
    assert "Tempo defaulted to 120 bpm." in event.text


def test_pdf_tab_event_factory_normalized_before_after_equivalence() -> None:
    """Verify field-for-field normalized equivalence for representative public scenarios:
    1. Single-note event
    2. Multi-note chord event
    3. Explicit quarter-rest event
    4. Editable-draft first-event text annotation
    against independent baseline expectations.
    """
    from score2gp.ir import DEFAULT_TICKS_PER_QUARTER, Event, NotatedDuration, Note, Timing

    # 1. Representative single-note event
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
    ev_note = build_pdf_tab_event_from_subgroup(
        [c1],
        output_bar_idx=1,
        event_idx=0,
        onset_ticks=0,
        grid_spacing=480,
        duration_name="eighth",
        track_id="gtr-1",
    )
    expected_note_event = Event(
        id="bar-1-event-1",
        track_id="gtr-1",
        timing=Timing(
            bar_index=1,
            onset_ticks=0,
            duration_ticks=480,
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value="eighth", dots=0),
        ),
        is_rest=False,
        notes=[
            Note(
                string=1,
                fret=5,
                pitch=69,  # E4 (64) + 5
                confidence=0.9,
                provenance=[c1.to_provenance()],
            )
        ],
        text=None,
        confidence=0.9,
        provenance=[c1.to_provenance()],
    )
    assert ev_note == expected_note_event

    # 2. Representative chord event (string 1 fret 5 & string 3 fret 7)
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
        confidence=0.7,
    )
    ev_chord = build_pdf_tab_event_from_subgroup(
        [c1, c2],
        output_bar_idx=1,
        event_idx=1,
        onset_ticks=480,
        grid_spacing=480,
        duration_name="eighth",
        track_id="gtr-1",
    )
    expected_chord_event = Event(
        id="bar-1-event-2",
        track_id="gtr-1",
        timing=Timing(
            bar_index=1,
            onset_ticks=480,
            duration_ticks=480,
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value="eighth", dots=0),
        ),
        is_rest=False,
        notes=[
            Note(
                string=1,
                fret=5,
                pitch=69,
                confidence=0.9,
                provenance=[c1.to_provenance()],
            ),
            Note(
                string=3,
                fret=7,
                pitch=62,  # G3 (55) + 7
                confidence=0.7,
                provenance=[c2.to_provenance()],
            ),
        ],
        text=None,
        confidence=0.8,  # (0.9 + 0.7) / 2
        provenance=[c1.to_provenance(), c2.to_provenance()],
    )
    assert ev_chord == expected_chord_event

    # 3. Representative explicit quarter-rest event
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
    ev_rest = build_pdf_tab_event_from_subgroup(
        [c_rest],
        output_bar_idx=1,
        event_idx=2,
        onset_ticks=960,
        grid_spacing=480,
        duration_name="eighth",
        track_id="gtr-1",
    )
    expected_rest_event = Event(
        id="bar-1-event-3",
        track_id="gtr-1",
        timing=Timing(
            bar_index=1,
            onset_ticks=960,
            duration_ticks=960,
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value="quarter", dots=0),
        ),
        is_rest=True,
        notes=[],
        text=None,
        confidence=0.95,
        provenance=[c_rest.to_provenance()],
    )
    assert ev_rest == expected_rest_event

    # 4. Representative editable-draft first-event text annotation
    ev_editable = build_pdf_tab_event_from_subgroup(
        [c1],
        output_bar_idx=1,
        event_idx=0,
        onset_ticks=0,
        grid_spacing=960,
        duration_name="quarter",
        track_id="gtr-1",
        editable_draft=True,
        tempo_bpm=120.0,
        tempo_is_explicit=False,
    )
    expected_editable_text = (
        "Editable draft generated from PDF tablature. "
        "Rhythms defaulted to quarter notes; timing was not recognised. "
        "Tuning defaulted to E Standard unless corrected by the user. "
        "Time signature defaulted to 4/4. "
        "Tempo defaulted to 120 bpm. "
        "Standard notation and notation/tab alignment were skipped. "
        "Rests/silence may be omitted."
    )
    assert ev_editable.text == expected_editable_text
    assert ev_editable.timing.duration_ticks == 960
    assert ev_editable.timing.notated_duration.value == "quarter"
