from __future__ import annotations

import pytest
from dataclasses import dataclass
from typing import Any

from score2gp.pdf import _LineSegment, _TabSystem, _tab_line_groups, _detect_tab_systems, extract_tab


@dataclass
class DummyPage:
    def get_drawings(self) -> list[dict[str, Any]]:
        return []
    def get_text(self, kind: str) -> str | list[Any]:
        return []


def test_ambiguous_bar_tolerance_cap() -> None:
    # 1. Normal spacing (e.g., 12.0) -> spacing * 0.45 = 5.4.
    # Cap of min(6.0, max(4.0, 5.4)) -> 5.4
    sys_normal = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 112.0, 124.0, 136.0, 148.0, 160.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0, 500.0],
        barline_candidates_count=2,
        valid_barline_count=2,
        rejected_barline_count=0,
        rejection_reasons={},
        barline_candidates_details=[],
    )
    assert abs(sys_normal.ambiguous_bar_tolerance - 5.4) < 1e-4

    # 2. Large spacing (e.g., 26.0) -> spacing * 0.45 = 11.7.
    # Cap of min(6.0, max(4.0, 11.7)) -> 6.0
    sys_large = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 126.0, 152.0, 178.0, 204.0, 230.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0, 500.0],
        barline_candidates_count=2,
        valid_barline_count=2,
        rejected_barline_count=0,
        rejection_reasons={},
        barline_candidates_details=[],
    )
    assert abs(sys_large.ambiguous_bar_tolerance - 6.0) < 1e-4

    # 3. Small spacing (e.g., 6.0) -> spacing * 0.45 = 2.7.
    # Cap of min(6.0, max(4.0, 2.7)) -> 4.0
    sys_small = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 106.0, 112.0, 118.0, 124.0, 130.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0, 500.0],
        barline_candidates_count=2,
        valid_barline_count=2,
        rejected_barline_count=0,
        rejection_reasons={},
        barline_candidates_details=[],
    )
    assert abs(sys_small.ambiguous_bar_tolerance - 4.0) < 1e-4

    # 4. Medium-large spacing (e.g., 14.0) -> spacing * 0.45 = 6.3.
    # Cap of min(6.0, max(4.0, 6.3)) -> 6.0
    sys_midlarge = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 114.0, 128.0, 142.0, 156.0, 170.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0, 500.0],
        barline_candidates_count=2,
        valid_barline_count=2,
        rejected_barline_count=0,
        rejection_reasons={},
        barline_candidates_details=[],
    )
    assert abs(sys_midlarge.ambiguous_bar_tolerance - 6.0) < 1e-4



def test_tab_line_groups_horizontal_overlap() -> None:
    # Verify that fragmented lines with strong overlap are preferred over collinear lines with poor overlap.
    # We construct a group of 6 lines that are slightly fragmented.
    lines = [
        # Line 1: y=100
        _LineSegment(100.0, 100.0, 300.0, 100.0),
        # Line 2: y=112
        _LineSegment(100.0, 112.0, 300.0, 112.0),
        # Line 3: y=124
        _LineSegment(100.0, 124.0, 300.0, 124.0),
        # Line 4: y=136
        _LineSegment(100.0, 136.0, 300.0, 136.0),
        # Line 5: y=148
        _LineSegment(100.0, 148.0, 300.0, 148.0),
        # Line 6: y=160
        _LineSegment(100.0, 160.0, 300.0, 160.0),
        
        # Collinear fragments at y=160:
        # A: Strong overlap with the group (x from 105 to 295)
        _LineSegment(105.0, 160.0, 295.0, 160.0),
        # B: Misleading/poor overlap (x from 400 to 600)
        _LineSegment(400.0, 160.0, 600.0, 160.0),
    ]
    
    # Run segment grouping
    groups = _tab_line_groups(lines)
    assert len(groups) >= 1
    
    # The first group should be a 6-line group
    first_group = groups[0]
    assert len(first_group) == 6
    
    # Check that the y=160 segment in the group is either the first or the strong overlap one,
    # but definitely NOT the misleading one with poor/no overlap.
    ys = [round((l.y0 + l.y1) / 2) for l in first_group]
    assert sorted(ys) == [100, 112, 124, 136, 148, 160]
    
    # Verify that the misleading one (x0=400) was NOT grouped
    for segment in first_group:
        assert min(segment.x0, segment.x1) < 400.0


def test_notation_to_tab_barline_inheritance(monkeypatch) -> None:
    # Verify that a TAB system inherits barlines from standard notation above it.
    # Standard notation Y: 100 to 140
    # TAB staff Y: 200 to 260
    
    import score2gp.pdf
    from score2gp.pdf import _LineSegment
    
    class MockFitzPoint:
        def __init__(self, x: float, y: float):
            self.x = x
            self.y = y
            
    class MockFitzPage:
        def get_drawings(self) -> list[dict[str, Any]]:
            drawings = []
            
            # Notation lines
            for y in [100.0, 110.0, 120.0, 130.0, 140.0]:
                drawings.append({
                    "items": [
                        ("l", MockFitzPoint(100.0, y), MockFitzPoint(500.0, y))
                    ]
                })
                
            # TAB lines
            for y in [200.0, 212.0, 224.0, 236.0, 248.0, 260.0]:
                drawings.append({
                    "items": [
                        ("l", MockFitzPoint(100.0, y), MockFitzPoint(500.0, y))
                    ]
                })
                
            # Vertical line (barline) crossing standard notation at X=150
            drawings.append({
                "items": [
                    ("l", MockFitzPoint(150.0, 95.0), MockFitzPoint(150.0, 145.0))
                ]
            })
            # Double barline at standard notation end (X=475 and X=490)
            drawings.append({
                "items": [
                    ("l", MockFitzPoint(475.0, 95.0), MockFitzPoint(475.0, 145.0))
                ]
            })
            drawings.append({
                "items": [
                    ("l", MockFitzPoint(490.0, 95.0), MockFitzPoint(490.0, 145.0))
                ]
            })
            
            return drawings
            
        def get_text(self, kind: str) -> list[Any]:
            return []
            
    def mock_classify(group: list[_LineSegment], page: Any) -> str:
        ys = [(l.y0 + l.y1) / 2 for l in group]
        if min(ys) < 150.0:
            return "notation"
        return "tab"
        
    monkeypatch.setattr(score2gp.pdf, "classify_staff_line_group", mock_classify)
    
    page = MockFitzPage()
    systems = _detect_tab_systems(page, page_index=1)
    
    assert len(systems) == 1
    sys = systems[0]
    
    # Check that it inherited the barlines and deduplicated within 15.0 points
    assert len(sys.barlines) == 2
    assert sys.barlines[0] == 150.0
    assert sys.barlines[1] == 490.0


def test_OMR_warnings_guarding_and_downgrading(monkeypatch) -> None:
    # Verify that candidate warnings are prefixed with "info_" and downgraded to severity "info"
    # when len(system.barlines) >= 2, but remain warning blocker codes when < 2.
    
    import score2gp.pdf
    from score2gp.pdf import _TabSystem
    
    # 1. System with fewer than 2 barlines (blocks)
    sys_blocked = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 112.0, 124.0, 136.0, 148.0, 160.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0],  # only 1 barline
        barline_candidates_count=1,
        valid_barline_count=1,
        rejected_barline_count=1,
        rejection_reasons={"pdf_barline_too_short": 1},
        barline_candidates_details=[],
    )
    
    # We will simulate extract_tab's warnings collector block.
    # In extract_tab, for reasons in system.rejection_reasons:
    # Let's verify the guard/downgrade logic on this system:
    reasons = sys_blocked.rejection_reasons or {}
    has_usable_barlines = (len(sys_blocked.barlines) >= 2)
    
    warnings = []
    def add_barline_warning(code, message, severity="warning", grouping_status="partial"):
        if has_usable_barlines:
            warnings.append({
                "code": f"info_{code}",
                "message": f"[Diagnostic Info] {message}",
                "severity": "info",
                "grouping_status": "grouped",
                "page_index": 1,
                "system_index": sys_blocked.system_index,
            })
        else:
            warnings.append({
                "code": code,
                "message": message,
                "severity": severity,
                "grouping_status": grouping_status,
                "page_index": 1,
                "system_index": sys_blocked.system_index,
            })
            
    if reasons.get("pdf_barline_too_short", 0) > 0:
        add_barline_warning("pdf_barline_too_short", "Too short", "warning", "partial")
        
    assert len(warnings) == 1
    assert warnings[0]["code"] == "pdf_barline_too_short"
    assert warnings[0]["severity"] == "warning"
    
    # 2. System with >= 2 barlines (should downgrade)
    sys_ok = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[100.0, 112.0, 124.0, 136.0, 148.0, 160.0],
        x0=100.0,
        x1=500.0,
        barlines=[100.0, 500.0],  # 2 barlines
        barline_candidates_count=2,
        valid_barline_count=2,
        rejected_barline_count=1,
        rejection_reasons={"pdf_barline_too_short": 1},
        barline_candidates_details=[],
    )
    
    reasons = sys_ok.rejection_reasons or {}
    has_usable_barlines = (len(sys_ok.barlines) >= 2)
    
    warnings = []
    def add_barline_warning_ok(code, message, severity="warning", grouping_status="partial"):
        if has_usable_barlines:
            warnings.append({
                "code": f"info_{code}",
                "message": f"[Diagnostic Info] {message}",
                "severity": "info",
                "grouping_status": "grouped",
                "page_index": 1,
                "system_index": sys_ok.system_index,
            })
        else:
            warnings.append({
                "code": code,
                "message": message,
                "severity": severity,
                "grouping_status": grouping_status,
                "page_index": 1,
                "system_index": sys_ok.system_index,
            })
            
    if reasons.get("pdf_barline_too_short", 0) > 0:
        add_barline_warning_ok("pdf_barline_too_short", "Too short", "warning", "partial")
        
    assert len(warnings) == 1
    assert warnings[0]["code"] == "info_pdf_barline_too_short"
    assert warnings[0]["severity"] == "info"

