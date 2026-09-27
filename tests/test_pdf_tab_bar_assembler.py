"""Bars from note-type records and TAB digits: every duration from its note type, positions from the TAB.

DUR-02 replaced ``assemble_pdf_tab_bar`` (durations from the event count, trailing rests to fill the
bar, sub-bars split at floating TAB barlines) with ``assemble_note_type_bars``. Each old test has a
replacement here, named in its docstring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import score2gp.pdf_tab_bar_assembler as assembler
from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
from score2gp.ir import Bar, DEFAULT_TICKS_PER_QUARTER, Event, NotatedDuration, Note, TimeSignature, Timing, Tuplet
from score2gp.pdf_tab_bar_assembler import PdfTabBarAssemblerError, assemble_note_type_bars, place_tab_digits
from score2gp.tabraw import TabRaw

_spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)
note, rest, digit, records = support.note, support.rest, support.digit, support.records
QUARTERS = [note(20.0), note(60.0), note(100.0), note(140.0)]


def _assemble(pages, digits, **kwargs):
    return assemble_note_type_bars(digits, records(pages, **kwargs), track_id="gtr-1")


def _quarter_digits(bar=0, page=0, fret=5):
    return [digit(f"p{page}b{bar}e{i}", bar, 20.0 + 40.0 * i, 3, fret + i, page=page) for i in range(4)]


def test_a_bar_with_no_notation_event_is_refused_never_given_a_whole_rest() -> None:
    """Replaces test_assemble_pdf_tab_bar_empty (which invented a whole rest)."""
    bars, route = _assemble([[[], QUARTERS]], _quarter_digits(bar=1))
    assert bars[0].events == [] and route["bars"][0]["reason"] == "bar_without_notation_event"
    assert route["bars"][1]["status"] == "written"


def test_a_printed_whole_rest_is_written_as_the_notation_prints_it() -> None:
    bars, route = _assemble([[[rest(20.0, "whole")]]], [])
    assert route["bars"][0]["status"] == "written"
    assert [(e.is_rest, e.timing.notated_duration.value, e.timing.duration_ticks) for e in bars[0].events] == [
        (True, "whole", 3840)]


def test_a_single_note_bar() -> None:
    """Replaces test_assemble_pdf_tab_bar_single_note (which made the note an eighth and padded the bar)."""
    bars, route = _assemble([[[note(20.0, "whole")]]], [digit("c-1", 0, 20.0, 1, 5)])
    (event,) = bars[0].events
    assert (event.timing.notated_duration.value, event.timing.duration_ticks) == ("whole", 3840)
    assert [(n.string, n.fret, n.pitch) for n in event.notes] == [(1, 5, 69)]
    assert route["bars"][0]["events"][0]["match"] == {"kind": "tab_column", "candidate_ids": ["c-1"], "dx_spaces": 0.0}


def test_a_chord_bar() -> None:
    """Replaces test_assemble_pdf_tab_bar_chord."""
    digits = [digit("c-1", 0, 20.0, 1, 3), digit("c-2", 0, 20.0, 2, 5)]
    bars, _ = _assemble([[[note(20.0, "whole", heads=2)]]], digits)
    assert [(n.string, n.fret) for n in bars[0].events[0].notes] == [(1, 3), (2, 5)]


def test_sequential_notes_take_their_onsets_from_the_note_types_before_them() -> None:
    """Replaces test_assemble_pdf_tab_bar_sequential_notes (onsets 0 and 480 from the count rule)."""
    specs = [note(20.0, "quarter", dots=1), note(60.0, "eighth"), note(100.0, "half")]
    digits = [digit(f"c-{i}", 0, s["x"], 3, i) for i, s in enumerate(specs)]
    bars, _ = _assemble([[specs]], digits)
    assert [(e.timing.onset_ticks, e.timing.duration_ticks) for e in bars[0].events] == [(0, 1440), (1440, 480), (1920, 1920)]


def test_two_digits_on_one_string_in_one_column_are_refused() -> None:
    """Replaces test_assemble_pdf_tab_bar_duplicate_string_candidates (which split them into two eighths)."""
    digits = [digit("c-1", 0, 20.0, 1, 5), digit("c-2", 0, 20.0, 1, 7)]
    bars, route = _assemble([[[note(20.0, "whole", heads=2)]]], digits)
    assert bars[0].events == []
    assert (route["bars"][0]["reason"], route["bars"][0]["location"]["event_index"]) == ("notehead_digit_count_mismatch", 0)


def test_a_rest_comes_from_the_notation_and_a_tab_rest_candidate_adds_nothing() -> None:
    """Replaces test_assemble_pdf_tab_bar_quarter_rest (a TAB rest glyph and trailing rest padding)."""
    specs = [rest(20.0), note(60.0), note(100.0, "half")]
    bars, _ = _assemble([[specs]], [digit("c-1", 0, 60.0, 3, 2), digit("c-2", 0, 100.0, 3, 4)])
    assert [(e.is_rest, e.timing.notated_duration.value) for e in bars[0].events] == [
        (True, "quarter"), (False, "quarter"), (False, "half")]


def test_digits_are_one_column_within_three_quarters_of_a_staff_space() -> None:
    """Replaces test_assemble_pdf_tab_bar_custom_chord_x_tolerance: the tolerance is in staff spaces."""
    near = [digit("c-1", 0, 20.0, 1, 3), digit("c-2", 0, 20.0 + 0.5 * support.SPACE, 2, 5)]
    bars, route = _assemble([[[note(21.0, "whole", heads=2)]]], near)
    assert route["bars"][0]["status"] == "written" and len(bars[0].events[0].notes) == 2
    apart = [digit("c-1", 0, 20.0, 1, 3), digit("c-2", 0, 20.0 + 3 * support.SPACE, 2, 5)]
    bars, route = _assemble([[[note(20.0, "half"), note(20.0 + 3 * support.SPACE, "half")]]], apart)
    assert route["bars"][0]["status"] == "written" and [len(e.notes) for e in bars[0].events] == [1, 1]


def test_an_overfull_bar_is_refused_and_the_other_bars_are_written() -> None:
    """Replaces test_assemble_pdf_tab_bar_internal_error_raised (a whole-score overcapacity error)."""
    overfull = [note(10.0 + 30.0 * i) for i in range(5)]
    digits = [digit(f"c-{i}", 0, s["x"], 3, i) for i, s in enumerate(overfull)] + _quarter_digits(bar=1)
    bars, route = _assemble([[overfull, QUARTERS]], digits)
    assert (route["bars"][0]["status"], route["bars"][0]["reason"]) == ("refused", "bar_total_mismatch")
    assert bars[0].events == [] and len(bars[1].events) == 4
    assert route["summary"] == {"source_bars": 2, "written_bars": 1, "refused_bars": 1,
                                "refusal_reasons": {"bar_total_mismatch": 1}, "match_kinds": {"tab_column": 4},
                                "tab_digits": 9, "unplaced_tab_digits": 0}


def _tabraw_file(tmp_path, digits):
    path = tmp_path / "tabraw.json"
    TabRaw(candidates=digits).to_json_file(path)
    return path


def test_build_ir_grouping_unsafe_refusal_exact_payload(tmp_path: Path) -> None:
    """Kept: more than 64 events in one bar is refused as unsafe grouping."""
    specs = [note(1.0 + 3.0 * i, "64th") for i in range(65)]
    digits = [digit(f"c-{i}", 0, s["x"], 1, 1) for i, s in enumerate(specs)]
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(_tabraw_file(tmp_path, digits), note_durations=records([[specs]]))
    assert exc_info.value.category == "pdf_only_tab_grouping_unsafe"
    assert exc_info.value.stage == "layout-gating"
    assert str(exc_info.value) == "PDF-only tab building refused: too many events (65) in bar 1."
    assert exc_info.value.details == {}


def test_build_ir_overfull_bar_refusal_exact_payload(tmp_path: Path) -> None:
    """Replaces test_build_ir_overcapacity_refusal_exact_payload: the bar is refused, located, and written empty."""
    overfull = [note(10.0 + 30.0 * i) for i in range(5)]
    digits = [digit(f"c-{i}", 0, s["x"], 3, i) for i, s in enumerate(overfull)] + _quarter_digits(bar=1)
    score, diagnostics = build_ir_from_tabraw_only(_tabraw_file(tmp_path, digits), note_durations=records([[overfull, QUARTERS]]))
    refused = [w for w in score.warnings if w.code == "pdf_only_tab_bar_refused"]
    assert [w.message for w in refused] == ["Bar 1 refused (bar_total_mismatch) at page 1, bar 1; written empty."]
    assert diagnostics.note_type_route["bars"][0]["location"] == {"page_index": 0, "system_index": 0, "bar_index": 0}
    assert diagnostics.note_type_route["bars"][0]["detail"] == "5 of 4 quarters"
    assert [len(b.events) for b in score.bars] == [0, 4]


def test_normalized_bar_equivalence() -> None:
    """Replaces the four test_normalized_bar_equivalence_* tests: one bar with a single note, a chord,
    a printed rest and a triplet, compared field for field with a bar built independently."""
    specs = [note(10.0, "quarter"), note(50.0, "quarter", heads=2), rest(90.0, "quarter"),
             note(130.0, "eighth", tuplet=(3, 2)), note(150.0, "eighth", tuplet=(3, 2)), note(170.0, "eighth", tuplet=(3, 2))]
    digits = [digit("a", 0, 10.0, 1, 5), digit("b1", 0, 50.0, 2, 3), digit("b2", 0, 50.0, 3, 2),
              digit("c", 0, 130.0, 1, 0), digit("d", 0, 150.0, 1, 1), digit("e", 0, 170.0, 1, 3)]
    bars, _ = _assemble([[specs]], digits)
    by_id = {d.id: d for d in digits}

    def ev(i, onset, ticks, written, ids, tuplet=None, is_rest=False):
        notes = [Note(string=by_id[c].string, fret=by_id[c].parsed_fret,
                      pitch={1: 64, 2: 59, 3: 55}[by_id[c].string] + by_id[c].parsed_fret,
                      confidence=0.9, provenance=[by_id[c].to_provenance()]) for c in ids]
        return Event(id=f"bar-1-event-{i}", track_id="gtr-1",
                     timing=Timing(bar_index=1, onset_ticks=onset, duration_ticks=ticks, ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                                   notated_duration=NotatedDuration(value=written, dots=0), tuplet=tuplet),
                     is_rest=is_rest, notes=notes, confidence=0.9 if ids else 1.0,
                     provenance=[by_id[c].to_provenance() for c in ids])

    triplet = Tuplet(actual_notes=3, normal_notes=2)
    expected = Bar(index=1, time_signature=TimeSignature(numerator=4, denominator=4), events=[
        ev(1, 0, 960, "quarter", ["a"]), ev(2, 960, 960, "quarter", ["b1", "b2"]),
        ev(3, 1920, 960, "quarter", [], is_rest=True), ev(4, 2880, 320, "eighth", ["c"], triplet),
        ev(5, 3200, 320, "eighth", ["d"], triplet), ev(6, 3520, 320, "eighth", ["e"], triplet)])
    assert bars[0].model_dump(mode="json") == expected.model_dump(mode="json")


def test_pdf_tab_helpers_isolation() -> None:
    """Kept: the synthetic helpers return fresh objects, so a caller's mutation cannot leak."""
    c1, c2 = digit("x", 0, 20.0, 1, 5), digit("x", 0, 20.0, 1, 5)
    assert c1 is not c2 and c1.bbox is not c2.bbox
    c1.x = 999.0
    c1.bbox.x0 = 999.0
    assert c2.x == support.event_x(0, 20.0) and c2.bbox.x0 == support.event_x(0, 18.0)
    r1, r2 = records([[QUARTERS]]), records([[QUARTERS]])
    r1["events"][0]["written"] = "half"
    assert r2["events"][0]["written"] == "quarter"


def test_digits_are_placed_in_notation_bars_by_the_notation_barlines() -> None:
    """Replaces test_split_tab_candidates_by_floating_barlines: the notation's barlines divide the TAB."""
    digits = [digit("a", 0, 20.0, 1, 1), digit("b", 0, 150.0, 1, 2), digit("c", 1, 30.0, 1, 3), digit("d", 2, 60.0, 1, 4)]
    placed, unplaced = place_tab_digits(digits, records([[[], [], []]]))
    assert {bar: [c.id for c in cands] for bar, cands in placed.items()} == {0: ["a", "b"], 1: ["c"], 2: ["d"]}
    assert unplaced == []


def test_a_bar_with_no_digits_and_a_digit_outside_every_bar() -> None:
    """Replaces test_split_tab_candidates_by_floating_barlines_empty_submeasures."""
    digits = [digit("a", 0, 20.0, 1, 1), digit("b", 2, 60.0, 1, 4), digit("out", 3, 100.0, 1, 5)]
    placed, unplaced = place_tab_digits(digits, records([[[], [], []]]))
    assert {bar: [c.id for c in cands] for bar, cands in placed.items()} == {0: ["a"], 2: ["b"]}
    assert [c.id for c in unplaced] == ["out"]


def test_the_count_rule_assembler_is_gone() -> None:
    for name in ("assemble_pdf_tab_bar", "split_tab_candidates_by_floating_barlines"):
        assert not hasattr(assembler, name)


def test_incompatible_note_duration_records_are_refused() -> None:
    old = {**records([[QUARTERS]]), "schema": "note-duration-records.v0.1"}
    with pytest.raises(PdfTabBarAssemblerError) as err:
        assemble_note_type_bars([], old, track_id="t")
    assert err.value.category == "pdf_only_tab_note_durations_incompatible"
