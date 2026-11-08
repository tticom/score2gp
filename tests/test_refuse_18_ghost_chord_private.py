"""Real-source ghost chords: one tall parenthesis pair around a stacked chord (REFUSE-18).

Measured with the normal CLI over every approved PDF: `note_duration_event_unread` led the refusals at 120 bars.
The largest classes were TAB with no printed rhythm (58 bars, only a spacing guess could settle them, so they stay
refused) and `rest_glyph_unidentified` (18 bars). Viewing the printed pages, none of those 18 glyphs is a rest: 9 are the strokes of a parenthesis pair (4 tall
pairs around a stacked chord, 5 single-head pairs whose left stroke abuts an unrecognised arrow-accidental or a
dotted head), 3 are flats at a bar start, 3 are diamond heads, 2 are a meter digit and 1 is an accidental piece. The
4 tall pairs are read as ghost chords (every head of the event is enclosed, as REFUSE-14 reads a single enclosed
head): two bars that nothing else held back are written; the other bars of the class stay refused with their
located reasons. Only `Melodic_Expressions.pdf` has such pairs: its other bars are byte-identical. There is no reference `.gp`
for it: the two bars are checked against the printed page (not independently verified).
Synthetic tests carry no acceptance weight: none are used. The two-page cut below is made from the approved source.
Mutants (each run, each fails a test below):
  DROP_CHORD_PAREN_RULE  `_chord_parentheses` finds no pair: the two bars stay refused (`test_dropping_the_rule...`).
  GHOST_ON_PRESERVED_BAR the ghost flag is kept on an already written bar: the 5-head bar gains ghost notes.
"""
import json
import tempfile
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/private/Melodic_Expressions.pdf"
PAGES = (20, 22, 32)  # 0-based pages holding the tall pairs
# source bar of the cut -> (heads in the ghost chord, ghost notes the written bar must hold)
NEWLY_WRITTEN = {28: (2, 2), 58: (3, 3)}
PRESERVED = 64  # a 5-head ghost chord in a bar the base reader already wrote: its notes stay un-ghosted


def _convert(tmp_path):
    assert SOURCE.is_file(), "REQUIRED_REFUSE_18_SOURCE_MISSING"
    cut = pymupdf.open()
    source = pymupdf.open(SOURCE)
    for page in PAGES:
        cut.insert_pdf(source, from_page=page, to_page=page)
    # pdf.py treats any input path containing "test" as a generated test PDF, so the cut is written to a
    # neutral directory rather than pytest's tmp_path (whose name carries the test's name).
    with tempfile.TemporaryDirectory(prefix="r18_") as neutral:
        pdf = Path(neutral) / "cut.pdf"
        assert "test" not in str(pdf).lower(), "CUT_PDF_PATH_MUST_NOT_NAME_A_TEST"
        cut.save(pdf)
        return _run(pdf, tmp_path)


def _run(pdf, tmp_path):
    build = tmp_path / "build"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(tmp_path / "o.gp"),
                             "--work-dir", str(build)])
    route = {b["source_bar_index"]: b for b in json.loads((build / "note-type-route.json").read_bytes())["bars"]}
    ir = json.loads((build / "score.ir.json").read_bytes())
    ghosts = {bar["index"]: sum(1 for e in bar["events"] for n in e.get("notes", []) if n.get("is_ghost"))
              for bar in ir["bars"]}
    return route, ghosts, json.loads((build / "note-durations.json").read_bytes())


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    return _convert(tmp_path_factory.mktemp("refuse18"))


def test_tall_pairs_are_read_as_ghost_chords(converted):
    route, ghosts, durations = converted
    chords = {e["location"]["bar_index"]: e["notehead"]["count"] for e in durations["events"]
              if e.get("ghost") and e["kind"] == "chord"}
    for bar, (heads, _) in NEWLY_WRITTEN.items():
        assert chords.get(bar) == heads, f"BAR_{bar}_CHORD_NOT_READ_AS_GHOST_CHORD"
    assert chords.get(PRESERVED) == 5


def test_newly_written_bars_hold_one_ghost_note_per_chord_head(converted):
    route, ghosts, _ = converted
    for bar, (_, expected) in NEWLY_WRITTEN.items():
        assert route[bar]["status"] == "written", f"BAR_{bar}_STILL_REFUSED"
        assert ghosts[route[bar]["output_bar_index"]] == expected, f"BAR_{bar}_GHOST_NOTE_COUNT"


def test_an_already_written_bar_keeps_its_notes_unghosted(converted):
    route, ghosts, _ = converted
    assert route[PRESERVED]["status"] == "written"
    assert ghosts.get(route[PRESERVED]["output_bar_index"], 0) == 0, "PRESERVED_BAR_GAINED_GHOST_NOTES"


def test_a_bar_with_another_unread_event_stays_refused(converted):
    route, _, _ = converted
    assert route[9]["status"] == "refused" and route[9]["reason"] == "note_duration_event_unread"


def test_dropping_the_rule_leaves_the_bars_refused(tmp_path, monkeypatch):
    """Mutant DROP_CHORD_PAREN_RULE: with no chord pair found, the same bars are refused (the test above would fail)."""
    monkeypatch.setattr(nd, "_chord_parentheses", lambda *args, **kwargs: {})
    route, _, _ = _convert(tmp_path)
    for bar in NEWLY_WRITTEN:
        assert route[bar]["status"] == "refused" and route[bar]["reason"] == "note_duration_event_unread"
