from __future__ import annotations
import pytest
from score2gp.pdf import _LineSegment
from score2gp.pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    PdfStaffNotationGeometryDiagnostics
)
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics

def test_build_notation_diagnostics_mock() -> None:
    group = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]

    class MockPoint:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    drawings = [
        {
            "rect": (100.0, 100.0, 200.0, 130.0),
            "items": [
                ("l", MockPoint(100.0, 100.0), MockPoint(200.0, 130.0))
            ]
        },
        {
            "rect": (150.0, 110.0, 250.0, 120.0),
            "items": [
                ("c", MockPoint(150.0, 110.0), MockPoint(180.0, 115.0), MockPoint(220.0, 115.0), MockPoint(250.0, 120.0))
            ]
        },
        {
            "rect": (300.0, 105.0, 310.0, 125.0),
            "items": [
                ("re",)
            ]
        },
        {
            "rect": (100.0, 400.0, 200.0, 430.0),
            "items": [
                ("l", MockPoint(100.0, 400.0), MockPoint(200.0, 430.0))
            ]
        }
    ]

    text_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "text": " trebleClef ",
                                "bbox": (60.0, 95.0, 80.0, 115.0),
                                "font": "GPBravuraRegular"
                            },
                            {
                                "text": " 4 ",
                                "bbox": (110.0, 105.0, 120.0, 115.0),
                                "font": "Times-Roman"
                            },
                            {
                                "text": " Page 1 ",
                                "bbox": (100.0, 500.0, 150.0, 510.0),
                                "font": "Times-Roman"
                            },
                            {
                                "text": "   ",
                                "bbox": (70.0, 100.0, 90.0, 120.0),
                                "font": "GPBravuraRegular"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            if kind == "dict":
                return text_dict
            return []

    page = MockPage()
    notation_diags = build_notation_diagnostics(page, page_index=1, notation_groups=[group])

    assert len(notation_diags.staves) == 1
    diag = notation_diags.staves[0]
    
    assert diag.staff.page_index == 1
    assert diag.staff.system_index == 1
    assert diag.staff.x0 == 50.0
    assert diag.staff.y0 == 100.0
    assert diag.staff.x1 == 500.0
    assert diag.staff.y1 == 132.0
    assert diag.staff.line_y_coords == [100.0, 108.0, 116.0, 124.0, 132.0]

    assert diag.primitives.line_count == 1
    assert diag.primitives.curve_count == 1
    assert diag.primitives.rect_count == 1
    
    assert diag.primitives.text_span_count_by_font == {
        "GPBravuraRegular": 1,
        "Times-Roman": 1
    }
