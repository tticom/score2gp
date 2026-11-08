"""Real-source TAB digits that were printed but never reached a bar (TABEXT-03).

Cause, on the real sources: a TAB system whose six rows are drawn in pieces under the 75 pt line filter (a narrow bar,
or a bar whose every row is interrupted by its own fret numbers) lost that stretch of the staff. The system then
ended before it, or was never detected, and the digits there lay outside every bar box: ungrouped text
(`tab_digits_printed_but_not_grouped`) or not seen at all (`bar_without_notation_or_tab_item`).

`PARANOID - BLACK SABBATH.pdf` has four systems of this kind whose legacy-row evidence is below the DUR-03 bar
(`_added_system_has_row_evidence`); they stay unread and the bars stay refused (reported unfinished, guard not loosened).
`Melodic_Expressions.pdf` pages 9 and 12 likewise stay at four systems (TABEXT-01 test).

A row is joined to the staff only where its drawn pieces cover the span except for gaps that each lie inside a printed
fret number on that row (`_row_continuous_but_for_digits`), and a drawn full-height vertical stands where it joins.

Synthetic tests carry no acceptance weight: none are used. Every assertion reads a genuine approved source.
Mutants (each fails a test below):
  DROP_DIGIT_CONTINUITY   rows broken at digits are not continuous: the 267 pt row of `7_Grateful_Dead_Melodies` is
                          never detected (fails the system tests).
  DROP_BRIDGE             `_bridged_tab_groups` joins nothing: the narrow-bar split of the Grateful 637 pt row stays.
  DROP_DIGIT_EXTENSION    `_digit_extended_tab_groups` extends nothing: the Grateful 165 pt and 743 pt rows end early.
  DROP_LEFT_RELAX         a left extension still needs all rows to start together: the leading narrow bar stays out.
"""
import json
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp import pdf
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
GRATEFUL = "7_Grateful_Dead_Melodies"
# Source bars of the Grateful sheet that print no digit (blank bars, a final empty bar, repeat/simile signs), read off the page.
GRATEFUL_NO_DIGITS = {16, 46, 49, 55, 56, 62, 66, 75}


def _path(source):
    path = PRIVATE / f"{source}.pdf"
    assert path.is_file(), "REQUIRED_TABEXT_03_SOURCE_MISSING"
    return path


def _systems(source, page_index):
    return pdf._detect_tab_systems(pymupdf.open(_path(source))[page_index], page_index + 1)


def _route(source, tmp_path):
    out = tmp_path / "o.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(_path(source)), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(tmp_path / "w")])
    return {b["source_bar_index"]: b for b in json.loads((tmp_path / "w/note-type-route.json").read_bytes())["bars"]}


@pytest.mark.parametrize("source,pages", [(GRATEFUL, (9, 3))])
def test_every_printed_system_spans_the_full_staff(source, pages):
    """Each staff row drawn on the page is one system over its whole width (rejects DROP_* mutants)."""
    for page_index, expected in enumerate(pages):
        systems = _systems(source, page_index)
        assert len(systems) == expected, f"{source[:9]}_PAGE_{page_index}_SYSTEMS"
    if source == GRATEFUL:
        for page_index in range(2):
            for system in _systems(source, page_index):
                # The first row ends at 739 pt: its last two bars print rests and no fret number, so no digit is lost.
                if not (page_index == 0 and system.system_index == 1):
                    assert system.barlines[-1] > 855.0, "GRATEFUL_SYSTEM_ENDS_EARLY"
                assert system.barlines[0] < 95.0, "GRATEFUL_SYSTEM_STARTS_LATE"


def test_grateful_digits_reach_their_bars(tmp_path):
    bars = _route(GRATEFUL, tmp_path)
    causes = {i: (b.get("refusal_evidence") or {}).get("cause") for i, b in bars.items() if b["status"] != "written"}
    assert "tab_digits_printed_but_not_grouped" not in causes.values(), "GRATEFUL_DIGITS_STILL_UNGROUPED"
    empty = {i for i, c in causes.items() if c == "bar_without_notation_or_tab_item"}
    assert empty == GRATEFUL_NO_DIGITS, "GRATEFUL_DIGIT_BAR_STILL_SEEN_AS_EMPTY"
    # 17 is the leading narrow bar of the "Outro" row: it was missing from the output altogether before.
    for bar in (8, 9, 12, 13, 14, 17, 27, 31, 39, 70, 71, 72, 73, 74):
        assert bars[bar]["tab_digits"] > 0, f"GRATEFUL_BAR_{bar}_HOLDS_NO_DIGITS"
