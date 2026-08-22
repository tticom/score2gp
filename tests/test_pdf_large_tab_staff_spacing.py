from __future__ import annotations

import pytest
from score2gp.pdf import _LineSegment, _is_coherent_large_tab_group, _tab_line_groups, classify_staff_line_group
from score2gp.tabraw import _candidate_kind

def test_large_spaced_tab_staff_is_detected() -> None:
    # Six horizontal lines with a spacing of 27.0pt
    lines = []
    y_start = 100.0
    spacing = 27.0
    for i in range(6):
        # x0=100.0, x1=600.0 (width 500.0)
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    # 1. Test helper directly
    assert _is_coherent_large_tab_group(lines) is True
    
    # 2. Test _tab_line_groups
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 6
    
    # 3. Test classify_staff_line_group
    assert classify_staff_line_group(groups[0], page=None) == "tab"


def test_inconsistent_large_lines_are_rejected() -> None:
    # Six horizontal lines with inconsistent gaps: 20.0, 32.0, 15.0, 28.0, 22.0
    ys = [100.0, 120.0, 152.0, 167.0, 195.0, 217.0]
    lines = []
    for y in ys:
        lines.append(_LineSegment(100.0, y, 600.0, y))
        
    assert _is_coherent_large_tab_group(lines) is False
    
    # Classification should be ambiguous
    assert classify_staff_line_group(lines, page=None) == "ambiguous"


def test_large_spaced_lines_with_poor_overlap_are_rejected() -> None:
    # Consistent spacing (27.0pt) but staggered x ranges so overlap ratio is low
    # overlap: min(x1) - max(x0) = 400.0 - 300.0 = 100.0
    # min_w: 300.0
    # overlap ratio: 100.0 / 300.0 = 0.33 < 0.80
    lines = [
        _LineSegment(100.0, 100.0, 400.0, 100.0),
        _LineSegment(150.0, 127.0, 450.0, 127.0),
        _LineSegment(200.0, 154.0, 500.0, 154.0),
        _LineSegment(250.0, 181.0, 550.0, 181.0),
        _LineSegment(300.0, 208.0, 600.0, 208.0),
        _LineSegment(350.0, 235.0, 650.0, 235.0),
    ]
    
    assert _is_coherent_large_tab_group(lines) is False
    assert classify_staff_line_group(lines, page=None) == "ambiguous"


def test_technique_text_non_playable_preservation() -> None:
    # Test technique texts return "technique-text" kind and fret digits return "fret"
    assert _candidate_kind("5", 5) == "fret"
    assert _candidate_kind("7", 7) == "fret"
    assert _candidate_kind("H", None) == "technique-text"
    assert _candidate_kind("P", None) == "technique-text"
    assert _candidate_kind("sl.", None) == "technique-text"
    assert _candidate_kind("full", None) == "technique-text"
