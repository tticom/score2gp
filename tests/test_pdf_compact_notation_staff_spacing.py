from __future__ import annotations

import pytest
from score2gp.pdf import _LineSegment, _tab_line_groups, classify_staff_line_group

class MockPage:
    def __init__(self, fret_evidence: bool):
        self.fret_evidence = fret_evidence
        
    def get_text(self, kind: str) -> list | dict:
        if kind == "words":
            if self.fret_evidence:
                return [
                    (150.0, 105.0, 160.0, 115.0, "3", 0, 0, 0)
                ]
            return []
        if kind == "dict":
            return {"blocks": []}
        return {}

def test_compact_notation_staff_is_detected() -> None:
    # Five horizontal lines with a spacing of 4.3pt (like compact GuitarPro export)
    lines = []
    y_start = 100.0
    spacing = 4.3
    for i in range(5):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 5
    
    # Notation staff detected cleanly when no fret evidence is present
    assert classify_staff_line_group(groups[0], page=MockPage(fret_evidence=False)) == "notation"

def test_compact_notation_is_ambiguous_with_fret_evidence() -> None:
    lines = []
    y_start = 100.0
    spacing = 4.3
    for i in range(5):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    groups = _tab_line_groups(lines)
    
    # If a compact 5-line staff has overlapping fret digits, it violates standard notation purity
    assert classify_staff_line_group(groups[0], page=MockPage(fret_evidence=True)) == "ambiguous"

def test_small_gap_ambiguous_rejection() -> None:
    # Five horizontal lines with extremely small spacing (e.g. 2.0pt) should be rejected
    lines = []
    y_start = 100.0
    spacing = 2.0
    for i in range(5):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
        
    groups = _tab_line_groups(lines)
    assert len(groups) == 0

def test_six_line_tab_behaviour_unchanged() -> None:
    # Six horizontal lines with a spacing of 6.0pt
    lines = []
    y_start = 100.0
    spacing = 6.0
    for i in range(6):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 6
    
    # 6-line groups with spacing 6.0 evaluate as 'tab'
    assert classify_staff_line_group(groups[0], page=MockPage(fret_evidence=False)) == "tab"
    assert classify_staff_line_group(groups[0], page=MockPage(fret_evidence=True)) == "tab"

def test_compact_six_line_rejected_to_prevent_ambiguous_grouping_corruption() -> None:
    lines = []
    y_start = 100.0
    spacing = 4.3
    for i in range(6):
        lines.append(_LineSegment(100.0, y_start + i * spacing, 600.0, y_start + i * spacing))
    
    groups = _tab_line_groups(lines)
    assert len(groups) == 1
    assert len(groups[0]) == 6
    
    # Codex fix: explicitly reject compact 6-line groups so they aren't mistaken for notation partners
    assert classify_staff_line_group(groups[0], page=MockPage(fret_evidence=False)) == "rejected"

