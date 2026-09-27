"""One event from a note-type record and its TAB digits.

DUR-02 replaced ``build_pdf_tab_event_from_subgroup`` and ``determine_pdf_tab_event_duration`` (a
duration from TAB-side evidence or a caller's grid default) with ``build_note_type_event``: the
duration is the note-duration record's, the positions are the TAB's. The editable-draft annotation
went with the editable-draft quarter default.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import score2gp.pdf_tab_event_factory as factory
from score2gp.ir import DEFAULT_TICKS_PER_QUARTER, Event, NotatedDuration, Note, TieTechnique, Timing, Tuplet
from score2gp.pdf_tab_event_factory import build_note_type_event

_spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)


def _record(spec):
    return support.records([[[spec]]], time_signature=None)["events"][0]


def _event(spec, candidates, positions=None, onset=0):
    positions = positions if positions is not None else [(c.string, c.parsed_fret) for c in candidates]
    return build_note_type_event(_record(spec), positions=positions, candidates=candidates, output_bar_idx=1,
                                 event_idx=0, onset_ticks=onset, track_id="gtr-1")


def test_a_single_note_takes_its_duration_from_the_record_and_its_position_from_the_tab() -> None:
    digit = support.digit("c-1", 0, 20.0, 1, 5)
    event = _event(support.note(20.0, "eighth"), [digit])
    assert event.id == "bar-1-event-1" and event.is_rest is False
    assert [(n.string, n.fret, n.pitch) for n in event.notes] == [(1, 5, 69)]  # E4 (64) + 5
    assert event.notes[0].provenance[0].raw_token_id == "c-1"
    assert event.confidence == 0.9
    assert (event.timing.onset_ticks, event.timing.duration_ticks) == (0, 480)
    assert event.timing.notated_duration == NotatedDuration(value="eighth", dots=0)
    assert event.timing.tuplet is None and event.text is None


def test_a_chord_carries_one_note_per_tab_digit() -> None:
    digits = [support.digit("c-1", 0, 20.0, 1, 5), support.digit("c-2", 0, 20.0, 2, 6)]
    event = _event(support.note(20.0, "half", heads=2), digits)
    assert [(n.string, n.fret, n.pitch) for n in event.notes] == [(1, 5, 69), (2, 6, 65)]
    assert event.timing.duration_ticks == 1920 and event.timing.notated_duration.value == "half"
    assert [p.raw_token_id for p in event.provenance] == ["c-1", "c-2"]


@pytest.mark.parametrize(("written", "ticks"), [("whole", 3840), ("half", 1920), ("quarter", 960), ("eighth", 480),
                                                ("16th", 240), ("32nd", 120), ("64th", 60)])
def test_a_rest_is_the_notations_rest_with_no_notes(written, ticks) -> None:
    event = _event(support.rest(20.0, written), [])
    assert event.is_rest is True and event.notes == []
    assert (event.timing.notated_duration.value, event.timing.duration_ticks) == (written, ticks)
    assert event.confidence == 1.0


@pytest.mark.parametrize(("dots", "ticks"), [(1, 1440), (2, 1680)])
def test_dots_come_from_the_record(dots, ticks) -> None:
    event = _event(support.note(20.0, "quarter", dots=dots), [support.digit("c-1", 0, 20.0, 3, 2)])
    assert event.timing.notated_duration == NotatedDuration(value="quarter", dots=dots)
    assert event.timing.duration_ticks == ticks


def test_a_tuplet_comes_from_the_record() -> None:
    event = _event(support.note(20.0, "eighth", tuplet=(3, 2)), [support.digit("c-1", 0, 20.0, 3, 2)], onset=320)
    assert event.timing.tuplet == Tuplet(actual_notes=3, normal_notes=2)
    assert (event.timing.onset_ticks, event.timing.duration_ticks) == (320, 320)
    assert event.timing.notated_duration.value == "eighth"


@pytest.mark.parametrize(("tie", "state"), [((True, False), "start"), ((False, True), "stop"), ((True, True), "continue")])
def test_a_tie_comes_from_the_record(tie, state) -> None:
    event = _event(support.note(20.0, tie=tie), [support.digit("c-1", 0, 20.0, 3, 2)])
    assert event.notes[0].techniques == [TieTechnique(state=state)]


def test_a_tie_continuation_without_its_own_digit_keeps_the_tied_position() -> None:
    event = _event(support.note(20.0, tie=(False, True)), [], positions=[(3, 2)])
    assert [(n.string, n.fret, n.pitch) for n in event.notes] == [(3, 2, 57)]
    assert event.notes[0].provenance == [] and event.provenance == []


def test_the_whole_event_equals_an_independently_built_one() -> None:
    """Replaces test_pdf_tab_event_factory_normalized_before_after_equivalence, field for field."""
    digit = support.digit("c-1", 0, 20.0, 1, 5)
    expected = Event(
        id="bar-1-event-1",
        track_id="gtr-1",
        timing=Timing(bar_index=1, onset_ticks=480, duration_ticks=1440, ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                      notated_duration=NotatedDuration(value="quarter", dots=1)),
        is_rest=False,
        notes=[Note(string=1, fret=5, pitch=69, confidence=0.9, provenance=[digit.to_provenance()])],
        text=None,
        confidence=0.9,
        provenance=[digit.to_provenance()],
    )
    assert _event(support.note(20.0, "quarter", dots=1), [digit], onset=480) == expected


def test_the_evidence_default_and_draft_annotation_paths_are_gone() -> None:
    """Replaces test_determine_pdf_tab_event_duration(_all_rest_types) and the two editable-draft tests."""
    for name in ("determine_pdf_tab_event_duration", "build_pdf_tab_event_from_subgroup",
                 "build_pdf_tab_editable_draft_annotation_text", "_infer_dots_from_duration", "_REST_CANDIDATE_MAP"):
        assert not hasattr(factory, name)
