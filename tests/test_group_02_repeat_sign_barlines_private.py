"""Real-source repeat-sign barlines (GROUP-02).

5_Grateful_Dead_Intros was refused at grouping (missing_pdf_barlines): four of its five systems start with a
drawn repeat sign (thin line, thick bar, thin bar, two dots) whose five strokes form one cluster that the
barline filter refused as mixed provenance, so the system start was not a barline. A repeat sign is accepted
as a system barline only where it is drawn: strokes spanning the whole TAB staff, in the start or end order,
with a dot in each of the 2nd-3rd and 4th-5th string gaps beside it. No threshold or gate is changed.

Oracle: the printed pages. Bar counts and per-bar TAB digit counts were read by eye from the page for the
holdout 7_Grateful_Dead_Melodies ("They Love Each Other Verse": 8 bars, digits 5,0,8,2,0,2,4,1; "Scarlet
Begonais Verse": 2 bars, digits 9,1). No reference .gp exists; nothing newly written is independently
verified. Synthetic tests carry no acceptance weight; none are used. Mutants:
  DROP_REPEAT_SIGN_RULE    `_repeat_sign_cluster_kind` returns None: every test below except the unchanged-system
                           one fails (system starts and the mid-system end repeat are refused again).
  ACCEPT_ANY_THICK_THIN    accept any thick+thin cluster without dots/position: the repeat sign after the clef of
                           the first system becomes a barline and test_sign_after_the_clef_is_not_a_barline fails.
"""
from pathlib import Path

import pymupdf
import pytest

from score2gp.pdf import _detect_tab_systems

PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"


def _systems(name, page):
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_GROUP_02_SOURCE_MISSING"
    with pymupdf.open(pdf) as doc:
        return _detect_tab_systems(doc[page], page + 1)


def test_every_repeat_start_system_begins_at_its_barline():
    """Rejects: leaving a drawn repeat-sign start outside the system's barlines (system 3 has one barline)."""
    systems = {s.system_index: s for s in _systems("5_Grateful_Dead_Intros", 0)}
    for index in (1, 2, 3, 5):
        assert abs(systems[index].barlines[0] - systems[index].x0) <= 2.0, f"START_{index}"
    assert [s.grouping_warnings for s in systems.values() if s.system_index == 3] == [[]]


def test_sign_after_the_clef_is_not_a_barline():
    """Rejects: accepting a thick-thin sign that is not at the system start (a clef-only first bar)."""
    first = _systems("5_Grateful_Dead_Intros", 0)[0]
    assert len(first.barlines) == 3
    assert not any(60.0 < b < 120.0 for b in first.barlines)


def test_holdout_end_repeat_splits_the_printed_bars():
    """Rejects: leaving the mid-system end repeat unaccepted (two printed bars merged into one)."""
    system = [s for s in _systems("7_Grateful_Dead_Melodies", 0) if s.system_index == 7][0]
    # TABEXT-03: the digit-interrupted row above it is now a system, so this row is system 7 (was 8).
    assert len(system.barlines) == 9  # 8 printed bars


def test_holdout_start_repeat_gives_two_bars():
    """Rejects: dropping the first bar of the repeated system (one bar holding all ten digits)."""
    system = [s for s in _systems("7_Grateful_Dead_Melodies", 1) if s.system_index == 2][0]
    assert len(system.barlines) == 3 and abs(system.barlines[0] - system.x0) <= 2.0
