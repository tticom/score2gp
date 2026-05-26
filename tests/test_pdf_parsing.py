from __future__ import annotations

import pytest
from score2gp.pdf import _TabSystem

def test_string_for_y_ambiguity_resolver() -> None:
    # Set up a compressed _TabSystem where line spacing is 6.0
    line_ys = [100.0, 106.0, 112.0, 118.0, 124.0, 130.0]
    system = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=line_ys,
        x0=50.0,
        x1=500.0,
        barlines=[50.0, 500.0],
    )
    
    # Under standard/default snap tolerance of 1.5, a note at y=103.0 falls:
    # abs(100 - 103) = 3.0 (outside cushion)
    # abs(106 - 103) = 3.0 (outside cushion)
    # But if we query it with a larger snap tolerance of 3.5, it falls inside BOTH line 1 (100) and line 2 (106) cushions.
    # The Staff Ambiguity Resolver should calculate absolute vertical distances (3.0 from both), sort, and pick the closest.
    line_idx, string, dist, warnings = system.string_for_y(103.0, height=8.0, string_snap_tolerance=3.5)
    
    # It should not return None
    assert line_idx is not None
    assert string is not None
    assert dist == 3.0
    assert "pdf_string_assignment_nearest_line" in warnings

def test_string_for_y_ambiguity_closer_snapping() -> None:
    line_ys = [100.0, 106.0, 112.0, 118.0, 124.0, 130.0]
    system = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=line_ys,
        x0=50.0,
        x1=500.0,
        barlines=[50.0, 500.0],
    )
    # A note at y=102.0 is distance 2.0 from 100.0, and 4.0 from 106.0.
    # Querying with snap tolerance 4.5, it falls inside cushions of BOTH lines (100 and 106).
    # Since 2.0 < 4.0, it should snap cleanly to string 1.
    line_idx, string, dist, warnings = system.string_for_y(102.0, height=8.0, string_snap_tolerance=4.5)
    assert line_idx == 1
    assert string == 1
    assert dist == 2.0

def test_bar_cushion_edge_snapping() -> None:
    line_ys = [100.0, 112.0, 124.0, 136.0, 148.0, 160.0]
    system = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=line_ys,
        x0=50.0,
        x1=500.0,
        barlines=[50.0, 200.0, 500.0],
    )
    # Candidate sitting 1.5 points outside left outer boundary of bar 1 at 50.0 (i.e. x=48.5)
    # With bar_cushion=0.0: it includes 'pdf_candidate_outside_bar' warning.
    bar_idx_no_cushion, bar_warns_no_cushion = system.bar_for_x(48.5, bar_cushion=0.0)
    assert bar_idx_no_cushion == 1
    assert "pdf_candidate_outside_bar" in bar_warns_no_cushion

    # With bar cushion >= 1.5 (e.g. 2.0): it maps cleanly without throwing 'pdf_candidate_outside_bar' warning!
    bar_idx_with_cushion, bar_warns_with_cushion = system.bar_for_x(48.5, bar_cushion=2.0)
    assert bar_idx_with_cushion == 1
    assert "pdf_candidate_outside_bar" not in bar_warns_with_cushion
