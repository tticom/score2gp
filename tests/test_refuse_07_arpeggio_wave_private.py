"""Real-source rolled-chord wave columns (REFUSE-07).

A rolled-chord (arpeggio) mark is printed as a vertical stack of identical narrow curved strokes ending in
an arrowhead. The reader used to take the strokes standing inside the staff band for unclassified rests
(`symbol_unclassified`) or for an overlapping form, refusing a whole bar whose notes were all readable. A
stack of three or more identical strokes sharing one left edge and touching one another is a wave column;
it carries no duration, so it is recorded as a located non-event (`wave_column_stroke`) and the bar is read
from its notes and rests. A lone narrow stroke, or a stack with a gap, is not matched.

Sources: `Hey Joe.pdf` (bars 3 and 7) and `Pride and Joy.pdf` (bar 7). Neither has a reference .gp in the
approved corpus, so the oracle is the PRINTED PAGE, read by the author: the expected event sequences below
were counted from the engraved note values on the page and each totals its bar's meter (4/4 and 12/8). They
are NOT independently verified against a reference file. Synthetic tests carry no acceptance weight; none
are used. Mutants:
  DROP_WAVE_COLUMN_RULE   `_wave_column_ids` returns nothing: the three bars stay refused.
  ARROWHEAD_NOT_CONSUMED  the column's arrowhead is not recognised: Hey Joe bar 7 and Pride and Joy bar 7
                          stay refused (unsupported_overlapping_form).
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# (written value, dot count) per event, in order, read off the printed page.
EXPECTED = {
    "Hey Joe": {3: [("quarter", 0), ("quarter", 0), ("eighth", 0), ("quarter", 1)],
                7: [("quarter", 0), ("half", 1)]},
    "Pride and Joy": {7: [("quarter", 1), ("quarter", 0), ("eighth", 0), ("eighth", 0), ("eighth", 0),
                          ("eighth", 0), ("16th", 0), ("16th", 0), ("eighth", 0), ("eighth", 0)]},
}


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_07_SOURCE_MISSING"
    build = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(tmp_path / "output.gp"), "--work-dir", str(build)])
    assert result.exit_code == 0, f"REFUSE_07_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    durations = json.loads((build / "note-durations.json").read_bytes())
    return route, durations


def _check(source, tmp_path):
    route, durations = _convert(source, tmp_path)
    by_source = {b["source_bar_index"]: b for b in route["bars"]}
    for bar, expected in EXPECTED[source].items():
        assert by_source[bar]["status"] == "written", f"BAR_REFUSED_{bar}"
        events = sorted((e for e in durations["events"] if e["bar_index"] == bar), key=lambda e: e["event_index"])
        assert [(e["written"], e["dots"]["count"]) for e in events] == expected, f"EVENTS_{bar}"
    strokes = [n for n in durations["diagnostics"]["non_events"] if n["reason"] == "wave_column_stroke"]
    assert strokes, "NO_WAVE_STROKE_RECORDED"
    # The wave is located, never silently dropped: every stroke has a bar and a box.
    assert all(n["bar_index"] is not None and n["bbox"] for n in strokes)


@pytest.mark.parametrize("source", sorted(EXPECTED))
def test_wave_column_bars_are_read_and_match_the_printed_page(source, tmp_path):
    """Rejects a bar refused for its wave column, or a wrong value/dot count against the printed page."""
    _check(source, tmp_path)


@pytest.mark.parametrize("source", sorted(EXPECTED))
def test_mutant_drop_wave_column_rule_fails(source, tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_wave_column_ids", lambda glyphs, space: set())
    with pytest.raises(AssertionError):
        _check(source, tmp_path)


def test_mutant_arrowhead_not_consumed_fails(tmp_path, monkeypatch):
    real = nd._wave_column_ids

    def strokes_only(glyphs, space):
        ids = real(glyphs, space)
        return {i for i in ids if any(g.ident == i and g.curved for g in glyphs)}

    monkeypatch.setattr(nd, "_wave_column_ids", strokes_only)
    with pytest.raises(AssertionError):
        _check("Pride and Joy", tmp_path)
