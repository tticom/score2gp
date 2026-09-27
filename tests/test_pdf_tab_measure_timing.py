"""Ticks for a note-type duration, and the refusals that replace the deleted count and padding rules.

DUR-02 deleted ``select_pdf_tab_grid_spacing_and_duration_name`` (a duration from the event count),
``is_within_pdf_tab_measure_capacity`` and ``decompose_pdf_tab_measure_remainder_to_rests`` (rests
added to fill a bar). Each old test is replaced here: the same event count gives whatever durations
the note types say, an overfull or underfull bar is refused, and a remainder is never filled.
"""

from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

import score2gp.pdf_tab_measure_timing as timing
from score2gp.pdf_tab_bar_assembler import assemble_note_type_bars
from score2gp.pdf_tab_measure_timing import PdfTabBarAssemblerError, ticks_for_quarters

_spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)


def _bar(specs):
    digits = [support.digit(f"d{i}", 0, s["x"], 3, i) for i, s in enumerate(specs) if s["kind"] != "rest"]
    bars, route = assemble_note_type_bars(digits, support.records([[specs]]), track_id="t")
    return bars[0], route["bars"][0]


def test_ticks_for_every_written_value_dot_and_tuplet() -> None:
    assert [ticks_for_quarters(q) for q in (Fraction(4), Fraction(2), Fraction(1), Fraction(1, 2), Fraction(1, 4),
                                            Fraction(1, 8), Fraction(1, 16))] == [3840, 1920, 960, 480, 240, 120, 60]
    assert ticks_for_quarters(Fraction(3, 2)) == 1440  # dotted quarter
    assert ticks_for_quarters(Fraction(7, 4)) == 1680  # double-dotted quarter
    assert ticks_for_quarters(Fraction(1, 3)) == 320  # eighth in a 3:2 triplet


@pytest.mark.parametrize("quarters", [Fraction(1, 7), Fraction(1, 1920), Fraction(0), Fraction(-1)])
def test_a_duration_off_the_tick_grid_or_not_positive_is_refused(quarters) -> None:
    with pytest.raises(PdfTabBarAssemblerError) as err:
        ticks_for_quarters(quarters)
    assert err.value.category == "pdf_only_tab_duration_off_tick_grid"


def test_the_event_count_never_selects_a_duration() -> None:
    """Replaces test_select_pdf_tab_grid_spacing_and_duration_name: four events are whatever their
    note types say (the count rule would have made them eighths), and so are nine."""
    four = [support.note(20.0, "half"), support.note(60.0, "quarter"), support.note(100.0, "eighth"),
            support.note(140.0, "eighth")]
    bar, entry = _bar(four)
    assert entry["status"] == "written"
    assert [e.timing.notated_duration.value for e in bar.events] == ["half", "quarter", "eighth", "eighth"]
    nine = [support.note(10.0 + 20.0 * i, "16th") for i in range(8)] + [support.note(180.0, "half")]
    bar, entry = _bar(nine)
    assert entry["status"] == "written"
    assert [e.timing.duration_ticks for e in bar.events] == [240] * 8 + [1920]
    for name in ("select_pdf_tab_grid_spacing_and_duration_name", "is_within_pdf_tab_measure_capacity",
                 "decompose_pdf_tab_measure_remainder_to_rests", "RestDurationDescriptor", "REST_DURATION_HIERARCHY"):
        assert not hasattr(timing, name)


def test_an_overfull_bar_is_refused_not_truncated() -> None:
    """Replaces test_is_within_pdf_tab_measure_capacity: five quarters in 4/4 are refused."""
    bar, entry = _bar([support.note(10.0 + 35.0 * i) for i in range(5)])
    assert entry["status"] == "refused" and entry["reason"] == "bar_total_mismatch"
    assert entry["detail"] == "5 of 4 quarters"
    assert bar.events == []


@pytest.mark.parametrize(
    ("specs", "detail"),
    [
        ([support.note(20.0, "half")], "2 of 4 quarters"),  # the old rule added a half rest
        ([support.note(20.0, "quarter"), support.note(60.0, "eighth")], "3/2 of 4 quarters"),  # old: half + eighth rests
        ([support.note(20.0, "64th")], "1/16 of 4 quarters"),  # old: half + quarter + ... + 64th rests
    ],
)
def test_an_underfull_bar_is_refused_and_never_padded_with_rests(specs, detail) -> None:
    """Replaces the three decompose_pdf_tab_measure_remainder_to_rests tests: a remainder is never filled."""
    bar, entry = _bar(specs)
    assert entry["status"] == "refused" and entry["reason"] == "bar_total_mismatch" and entry["detail"] == detail
    assert bar.events == []


def test_a_rest_is_written_only_where_the_notation_prints_one() -> None:
    bar, entry = _bar([support.note(20.0, "half"), support.rest(100.0, "quarter"), support.note(150.0, "quarter")])
    assert entry["status"] == "written"
    assert [(e.is_rest, e.timing.notated_duration.value, e.timing.onset_ticks) for e in bar.events] == [
        (False, "half", 0), (True, "quarter", 1920), (False, "quarter", 2880)]
