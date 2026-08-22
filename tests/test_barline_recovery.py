from __future__ import annotations

from typing import Any
from score2gp.pdf import _LineSegment, filter_tab_barline_candidates, _detect_tab_systems
from score2gp.musicxml import parse_musicxml
from score2gp.tabraw import TabRaw
from score2gp.build_ir import build_ir_with_diagnostics_from_imports


def test_double_barline_clustering():
    # Candidates with spacing 9.0 (<= 12.0 clustering tolerance)
    c1 = _LineSegment(490.0, 100.0, 490.0, 200.0)
    c2 = _LineSegment(499.0, 100.0, 499.0, 200.0)
    
    line_ys = [100.0, 120.0, 140.0, 160.0, 180.0, 200.0]
    res = filter_tab_barline_candidates([c1, c2], 100.0, 200.0, line_ys, 50.0, 500.0)
    
    # Under our new logic, they should be clustered together.
    # Only the rightmost representative (499.0) is accepted.
    assert res["valid_barlines"] == [499.0]
    assert res["rejected_count"] == 1
    assert res["rejection_reasons"]["pdf_barline_double_secondary"] == 1


class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class MockPage:
    def __init__(self, drawings: list[dict[str, Any]], words: list[Any] | None = None):
        self.drawings = drawings
        self.words = words or []
        self.rect = type('MockRect', (object,), {'width': 600.0, 'height': 800.0})()
        
    def get_drawings(self) -> list[dict[str, Any]]:
        return self.drawings
        
    def get_text(self, kind: str) -> list[Any] | str:
        if kind == "words":
            return self.words
        return ""


def test_notation_to_tab_barline_inheritance():
    # 5 notation horizontal lines (gap 18)
    # 6 TAB horizontal lines (gap 27)
    drawings = []
    
    for y in [100.0, 118.0, 136.0, 154.0, 172.0]:
        drawings.append({
            "items": [("l", MockPoint(50.0, y), MockPoint(500.0, y))]
        })
        
    for y in [200.0, 227.0, 254.0, 281.0, 308.0, 335.0]:
        drawings.append({
            "items": [("l", MockPoint(50.0, y), MockPoint(500.0, y))]
        })
        
    # Vertical barlines:
    # Left boundary (x=50.0)
    drawings.append({
        "items": [("l", MockPoint(50.0, 80.0), MockPoint(50.0, 350.0))]
    })
    
    # Right boundary (x=500.0)
    drawings.append({
        "items": [("l", MockPoint(500.0, 80.0), MockPoint(500.0, 350.0))]
    })
    
    # Internal boundaries crossing notation only (x=200.0, x=350.0)
    drawings.append({
        "items": [("l", MockPoint(200.0, 80.0), MockPoint(200.0, 180.0))]
    })
    drawings.append({
        "items": [("l", MockPoint(350.0, 80.0), MockPoint(350.0, 180.0))]
    })
    
    mock_page = MockPage(drawings)
    systems = _detect_tab_systems(mock_page, 1)
    
    assert len(systems) == 1
    system = systems[0]
    
    # We should have inherited the internal barlines from the notation staff
    assert system.barlines == [50.0, 200.0, 350.0, 500.0]


def test_info_warning_does_not_skip_system():
    musicxml = parse_musicxml("tests/fixtures/musicxml/tiny_single_bar.musicxml")
    
    tabraw_dict = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "candidates": [
            {
                "id": "c1",
                "kind": "fret",
                "raw_text": "0",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "parsed_fret": 0,
                "x": 100.0,
                "y": 200.0,
                "confidence": 0.9,
                "raw": {
                    "grouping_version": "pdf-grouping.v0.1",
                    "tab_staff_bbox": {"page": 1, "x0": 50.0, "y0": 200.0, "x1": 500.0, "y1": 330.0},
                    "tab_line_ys": [200.0, 226.0, 252.0, 278.0, 304.0, 330.0],
                    "barline_xs": [50.0, 500.0],
                    "bar_boxes": [{"page": 1, "system_index": 1, "staff_index": 1, "bar_index": 1, "x0": 50.0, "y0": 200.0, "x1": 500.0, "y1": 330.0, "confidence": 0.9}]
                }
            }
        ],
        "warnings": [
            {
                "code": "pdf_barline_double_secondary",
                "message": "Double secondary ignored",
                "severity": "info",
                "page_index": 1,
                "system_index": 1
            },
            {
                "code": "pdf_bar_box_construction_not_enough_for_build_ir",
                "message": "Bar box construction failed",
                "severity": "warning",
                "page_index": 1,
                "system_index": 1
            }
        ]
    }
    
    tabraw = TabRaw.model_validate(tabraw_dict)
    score, _ = build_ir_with_diagnostics_from_imports(musicxml, tabraw, allow_skip_unboxed=True)
    
    # System (1, 1) should be recovered and not skipped
    assert len(score.bars) == 1
    assert score.bars[0].events
    assert any(event.notes for event in score.bars[0].events)
