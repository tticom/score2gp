"""Real-source TAB left edge (GROUP-01).

Hey Joe and Pride and Joy were refused whole (ambiguous_bar_assignment) because the first bar of each
page-1 system draws its six TAB lines as a short piece before the clef/time signature, a piece under the
75 pt line filter. The system then began after that piece, the system-start barline lay outside it, and
every digit of the first bar lay outside every bar box. `_left_extended_tab_groups` extends a TAB group
left only where all six lines continue to one common start and a drawn full-height vertical stands on
it. No threshold is changed.

Oracle: the printed pages (bar counts read by the notation reader, per-bar digit counts checked by
eye for Pride and Joy bars 1-5). No reference .gp exists for these sources; every newly written bar is
NOT independently verified. Synthetic tests carry no acceptance weight; none are used. Mutant:
  DROP_LEFT_EDGE_RULE   `_left_extended_tab_groups` returns []: Hey Joe and Pride and Joy are refused
                        again with pdf_only_tab_grouping_unsafe, and the 12 Bar Blues first bar is
                        refused with note_duration_event_unread.
"""
import json
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.pdf import _detect_tab_systems

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

# source -> (source bars, bars written, {source bar: TAB digits placed in it} for the checked bars)
CASES = {
    "Hey Joe": (12, {0, 1, 4, 10}, {0: 12, 1: 13, 4: 15, 10: 28}),
    "Pride and Joy": (14, {0, 1, 2, 3, 6, 9, 13}, {0: 4, 1: 4, 2: 9, 3: 16, 4: 10}),
}


def _convert(tmp_path, name):
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_GROUP_01_SOURCE_MISSING"
    build = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(tmp_path / "o.gp"), "--work-dir", str(build)])
    assert result.exit_code == 0, f"GROUP_01_CLI_EXIT_{result.exit_code}"
    return json.loads((build / "note-type-route.json").read_bytes())


@pytest.mark.parametrize("name", sorted(CASES))
def test_first_bar_boxed_and_bars_written(tmp_path, name):
    """Rejects: leaving the system start outside the system (the source is refused whole)."""
    source_bars, written, digits = CASES[name]
    route = _convert(tmp_path, name)
    assert route["summary"]["source_bars"] == source_bars
    assert route["summary"]["unplaced_tab_digits"] == 0
    got = {b["source_bar_index"] for b in route["bars"] if b["status"] == "written"}
    assert got == written
    by = {b["source_bar_index"]: b for b in route["bars"]}
    for bar, count in digits.items():
        assert by[bar]["tab_digits"] == count, f"DIGITS_{bar}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_page_one_system_starts_at_its_barline(name):
    """Rejects: a system whose first barline lies outside the system, left of its staff lines."""
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_GROUP_01_SOURCE_MISSING"
    with pymupdf.open(pdf) as doc:
        systems = _detect_tab_systems(doc[0], 1)
    assert len(systems) == 4
    for system in systems:
        assert abs(system.barlines[0] - system.x0) <= 2.0


def test_converted_source_first_bar_now_written(tmp_path):
    """Rejects: the first system of 12 Bar Blues staying outside the staff (bar 1 refused, 0 digits)."""
    route = _convert(tmp_path, "12 Bar Blues Solo Guitar Jam")
    first = route["bars"][0]
    assert first["status"] == "written" and first["tab_digits"] == 6
