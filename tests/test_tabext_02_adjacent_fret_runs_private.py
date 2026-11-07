"""Real-source runs of adjacent fret digits that arrive as one PDF word (TABEXT-02).

A PDF word such as "1110" or "107" is not one fret (no fret is above 24). Where the printed glyph pitch settles
it, the word is split into its frets: within one fret the pitch is the font's own pitch for that digit pair, between
two frets it is larger. Both sources below have no reference .gp: they are labelled NOT independently verified
against a file; the bars are checked against the printed page (read off the page, counts and frets only).

* `The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf` source bars 18 and 93 ("1314" = 13, 14):
  bar 18: "1110" is the frets 11 and 10 (a
  hammer-on / pull-off group "10 11 10"); the bar is written, 11 events, frets read off the page.
* `Back In Black.pdf` source bar 7: "107" is the frets 10 and 7. The bar is then matched in full but holds a 22-note
  tuplet (1/11 quarter) the 960-tick grid cannot hold, so it is refused for that bar alone (representation gap);
  without the bar-level refusal the whole source would stop (exit 2) and its seven written bars would be lost.

Synthetic tests carry no acceptance weight: none are used.
Mutants (each fails a test below):
  DROP_RUN_SPLIT     a run is never split: EXACT bar 18 stays refused, and the Back In Black run stays one word.
  DROP_BAR_TICK_REFUSAL  the off-grid duration refuses the whole source again: Back In Black writes nothing.
  IGNORE_PAIR_PITCH  the page's own in-fret pitch of a digit pair is ignored (glyph width only): the kerned "11"
                     is not told from a break, so "1110" is no longer cut at 11|10 and bar 18 stays refused.
"""
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf
from score2gp.cli import app

sys.path.insert(0, str(Path(__file__).parent))
from test_tabext_01_fret_digits_private import _gpif_bars  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
EXACT = "The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord"
BLACK = "Back In Black"

# Frets of EXACT source bar 18 in printed order (read off the page): the run "1110" is the 16th group 10, 11, 10.
EXACT_BAR_18_FRETS = [12, 13, 11, 10, 13, 10, 11, 10, 13, 10, 11]
# Source bar 93 (page 4): the run "1314" is the frets 13 and 14, on a page after the first (word y carries the
# cumulative page offset), read off the printed page in order.
EXACT_BAR_93_FRETS = [14, 12, 13, 14, 12, 11, 14]


def _convert(source, tmp_path):
    pdf_path = PRIVATE / f"{source}.pdf"
    assert pdf_path.is_file(), "REQUIRED_TABEXT_02_SOURCE_MISSING"
    build = tmp_path / "build"
    out = tmp_path / "output.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf_path), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    tabraw = json.loads((build / "tab" / "tab_raw.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, out, tabraw


def _check_exact_bar(tmp_path):
    bars, out, _tabraw = _convert(EXACT, tmp_path)
    assert bars[18]["status"] == "written", "EXACT_BAR_18_REFUSED"
    written = _gpif_bars(out)[bars[18]["output_bar_index"] - 1]
    frets = [fret for _value, notes in written for _string, fret in notes]
    assert frets == EXACT_BAR_18_FRETS, "EXACT_BAR_18_FRETS_WRONG"
    assert bars[93]["status"] == "written", "EXACT_BAR_93_REFUSED"
    written = _gpif_bars(out)[bars[93]["output_bar_index"] - 1]
    assert [fret for _value, notes in written for _string, fret in notes] == EXACT_BAR_93_FRETS, "EXACT_BAR_93_FRETS_WRONG"


def _check_black_run(tmp_path):
    bars, _out, tabraw = _convert(BLACK, tmp_path)
    texts = sorted(c["raw_text"] for c in tabraw["candidates"]
                   if c["page_index"] == 1 and c["kind"] == "fret"
                   and 304 <= c["bbox"]["x0"] <= 318 and 600 <= c["bbox"]["y0"] <= 612)
    assert texts == ["10", "7"], "BLACK_RUN_NOT_SPLIT_10_7"
    # With the run read, bar 7 holds a 22-note tuplet the tick grid cannot hold: that bar alone is refused with its
    # located reason; the other seven bars of the source stay written (the source is not refused whole).
    assert (bars[7]["status"], bars[7]["reason"]) == ("refused", "duration_off_tick_grid"), "BLACK_BAR_7_REASON"
    assert sum(b["status"] == "written" for b in bars.values()) == 7, "BLACK_OTHER_BARS_CHANGED"


def test_run_of_adjacent_frets_is_split_into_written_bar(tmp_path):
    """Rejects "1110" staying one word (bar refused) or being cut at the wrong glyph (wrong frets written)."""
    _check_exact_bar(tmp_path)


def test_three_digit_run_is_split_at_the_pitch_break(tmp_path):
    """Rejects "107" staying one unreadable word, or cut as 1|07 / 1|0|7 instead of 10|7."""
    _check_black_run(tmp_path)


def test_mutant_drop_run_split_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "_split_adjacent_fret_run", lambda *a, **k: None)
    with pytest.raises(AssertionError):
        _check_exact_bar(tmp_path)
    with pytest.raises(AssertionError):
        _check_black_run(tmp_path / "b")


def test_mutant_ignore_pair_pitch_fails(tmp_path, monkeypatch):
    original = pdf._split_adjacent_fret_run
    monkeypatch.setattr(pdf, "_split_adjacent_fret_run",
                        lambda rw, census, system, y_offset=0.0: original(rw, {**census, "pitch": {}}, system, y_offset))
    with pytest.raises(AssertionError):
        _check_exact_bar(tmp_path)
