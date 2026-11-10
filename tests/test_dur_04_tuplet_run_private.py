"""Real-source tuplet runs: a bare tuplet number over a longer beam group counts only its own notes (DUR-04).

Measured with the normal CLI over every approved PDF (before): `bar_total_mismatch` held 6 bars (reader gap). Viewing the
printed pages, 4 of them (3 in one source, 1 in another) print a "3" under a beam group of 4 or 5 notes: the number
spans the 3 notes it stands over, and the neighbouring notes are untupleted 16ths or eighths. The reader scaled the whole beam group, so the
bar totalled 23/6 or 47/12 instead of 4. The number states how many notes it spans, so the run of that many notes whose ends
enclose the number is the tuplet; the bar total is never consulted. The 4 bars are now written; the other bars of both
sources are unchanged. The other `bar_total_mismatch` bars stay refused with their located reason (a 22-note tuplet
whose normal count is not printed, and a source whose pages are not among those cut here).
There is no reference `.gp` for either source: the 4 bars were checked against the printed page, not independently verified.
Synthetic tests carry no acceptance weight: none are used. The one-page cuts below are made from the approved sources.
Mutants (each run, each fails a test below):
  WHOLE_GROUP_RUN  (rule dropped) the run is the whole beam group: the 4 bars stay refused.
  FIRST_RUN        the run is always the first `count` notes: the bars whose number stands over later notes are refused.
"""
import json
import tempfile
from fractions import Fraction
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# source -> (page, {source bar: tuplet members the number stands over})
SOURCES = {
    "Brown Sugar.pdf": (0, {7: 3}),
    "Hey Joe.pdf": (0, {5: 3, 8: 3, 9: 3}),
}
STILL_REFUSED = ("Castles Made of Sand.pdf", 0, 4)  # a 22-note tuplet: its normal count is not printed


def _convert(name, page, tmp_path):
    source = PRIVATE / name
    assert source.is_file(), f"REQUIRED_DUR_04_SOURCE_MISSING:{name}"
    cut = pymupdf.open()
    cut.insert_pdf(pymupdf.open(source), from_page=page, to_page=page)
    with tempfile.TemporaryDirectory(prefix="d04_") as neutral:  # pdf.py treats a path naming a test specially
        pdf = Path(neutral) / "cut.pdf"
        cut.save(pdf)
        build = tmp_path / "build"
        CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(tmp_path / "o.gp"),
                                 "--work-dir", str(build)])
    route = {b["source_bar_index"]: b for b in json.loads((build / "note-type-route.json").read_bytes())["bars"]}
    durations = json.loads((build / "note-durations.json").read_bytes())
    return route, durations


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    return {name: _convert(name, page, tmp_path_factory.mktemp("dur04"))
            for name, (page, _) in SOURCES.items()}


def _bar_events(durations, bar):
    return [e for e in durations["events"] if e["location"]["bar_index"] == bar]


def test_the_four_bars_are_written_with_the_meter_total(converted):
    for name, (_, bars) in SOURCES.items():
        route, durations = converted[name]
        for bar in bars:
            assert route[bar]["status"] == "written", f"{name}:BAR_{bar}_STILL_REFUSED"
            total = sum(Fraction(e["duration_quarters"]) for e in _bar_events(durations, bar))
            assert total == 4, f"{name}:BAR_{bar}_TOTAL"


def test_each_number_scales_exactly_the_notes_it_stands_over(converted):
    for name, (_, bars) in SOURCES.items():
        _, durations = converted[name]
        for bar, members in bars.items():
            events = _bar_events(durations, bar)
            scaled = [e for e in events if e.get("tuplet")]
            assert len(scaled) == members, f"{name}:BAR_{bar}_TUPLET_MEMBERS"
            assert all((e["tuplet"]["actual"], e["tuplet"]["normal"]) == (3, 2) for e in scaled)
            # the tuplet's notes are consecutive events inside one beam group longer than the number
            indices = [e["event_index"] for e in scaled]
            assert indices == list(range(indices[0], indices[0] + members)), f"{name}:BAR_{bar}_RUN_NOT_CONSECUTIVE"
            groups = {e["beams"].get("group") for e in scaled}
            assert len(groups) == 1 and sum(1 for e in events if e["beams"].get("group") in groups) > members


# offset of the first tuplet note inside its beam group, per bar (read from the printed pages)
RUN_OFFSET = {"Brown Sugar.pdf": {7: 0}, "Hey Joe.pdf": {5: 1, 8: 0, 9: 2}}


def test_the_run_is_taken_where_the_number_stands_not_at_the_start(converted):
    """Mutant FIRST_RUN: the run is always the first notes of the group, wrong for Hey Joe bars 5 and 9."""
    for name, offsets in RUN_OFFSET.items():
        _, durations = converted[name]
        for bar, offset in offsets.items():
            events = _bar_events(durations, bar)
            scaled = [e for e in events if e.get("tuplet")]
            group = scaled[0]["beams"]["group"]
            in_group = [e["event_index"] for e in events if e["beams"].get("group") == group]
            assert scaled[0]["event_index"] - in_group[0] == offset, f"{name}:BAR_{bar}_RUN_POSITION"


def test_a_22_note_tuplet_bar_stays_refused_with_its_located_reason(tmp_path):
    name, page, bar = STILL_REFUSED
    route, _ = _convert(name, page, tmp_path)
    assert route[bar]["status"] == "refused" and route[bar]["reason"] == "bar_total_mismatch"
    assert route[bar]["refusal_evidence"]["cause"] == "notation_total_above_meter"


def test_whole_group_mutant_leaves_the_bars_refused(tmp_path, monkeypatch):
    """Mutant WHOLE_GROUP_RUN (rule dropped): the whole beam group is scaled and the 3 bars stay refused."""
    monkeypatch.setattr(nd, "_run_under_number", lambda digit, members, count, space: members)
    page, bars = SOURCES["Hey Joe.pdf"]
    route, _ = _convert("Hey Joe.pdf", page, tmp_path)
    assert {bar for bar in bars if route[bar]["status"] != "written"} == set(bars)
    assert all(route[bar]["reason"] == "bar_total_mismatch" for bar in bars)


def test_first_notes_mutant_misplaces_the_run(tmp_path, monkeypatch):
    """Mutant FIRST_RUN: the totals still match (all sixteenths) but the run sits on the wrong notes, so the
    position test above would fail: bars 5 and 9 put the tuplet at offset 0 instead of 1 and 2."""
    monkeypatch.setattr(nd, "_run_under_number",
                        lambda digit, members, count, space: sorted(members, key=lambda e: e["_cx"])[:count])
    route, durations = _convert("Hey Joe.pdf", SOURCES["Hey Joe.pdf"][0], tmp_path)
    for bar, offset in RUN_OFFSET["Hey Joe.pdf"].items():
        events = _bar_events(durations, bar)
        scaled = [e for e in events if e.get("tuplet")]
        group = scaled[0]["beams"]["group"]
        first_in_group = min(e["event_index"] for e in events if e["beams"].get("group") == group)
        assert scaled[0]["event_index"] - first_in_group == 0
        assert offset == 0 or scaled[0]["event_index"] - first_in_group != offset
