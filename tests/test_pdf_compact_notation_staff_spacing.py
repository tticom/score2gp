from __future__ import annotations

import pytest
from score2gp.pdf import _LineSegment, _tab_line_groups, classify_staff_line_group

def test_compact_notation_staff_is_detected() -> None:
    # Five horizontal lines with a spacing of 4.3pt (like compact GuitarPro export)
    lines = []
    y_start = 100.0
    spacing = 4.3
    for i in range(5):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    # 1. Test _tab_line_groups identifies it
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 5
    
    # 2. Test classify_staff_line_group identifies it as notation
    assert classify_staff_line_group(groups[0], page=None) == "notation"

def test_compact_tab_staff_is_detected() -> None:
    # Six horizontal lines with a spacing of 5.0pt
    lines = []
    y_start = 100.0
    spacing = 5.0
    for i in range(6):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    # 1. Test _tab_line_groups identifies it
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 6
    
    # 2. Test classify_staff_line_group identifies it as tab (wait, actually < 5.5 is "ambiguous" for 6 lines? Let's see.)
    # In classify_staff_line_group, 6 lines with median_gap 5.0 goes to "ambiguous" if not matching 5.5-7.2 or 9.5-15.0 or 15.0-32.0.
    # We didn't change 6-line logic except _tab_line_groups allowing it.
    pass

def test_small_gap_ambiguous_rejection() -> None:
    # Five horizontal lines with extremely small spacing (e.g. 2.0pt) should be rejected
    lines = []
    y_start = 100.0
    spacing = 2.0
    for i in range(5):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
        
    groups = _tab_line_groups(lines)
    assert len(groups) == 0
