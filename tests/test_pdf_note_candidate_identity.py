import pytest
from pathlib import Path
import fitz
from typing import Any
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict, _extract_note_candidates
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics, NotationStaffGeometry, NotationStaffDiagnostics

class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

class MockRect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

class MockPage:
    def __init__(self, drawings: list[dict[str, Any]]):
        self.drawings = drawings
    
    def get_drawings(self) -> list[dict[str, Any]]:
        return self.drawings
    
    def get_text(self, kind: str) -> dict:
        return {}

def build_mock_quarter_note_drawing(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    # 4 curves only, bounding box distance to edge = 0
    items = []
    items.append(("c", MockPoint(x0, y0), MockPoint(x0+1, y0), MockPoint(x0+2, y0), MockPoint(x1, y0)))
    items.append(("c", MockPoint(x1, y0), MockPoint(x1, y0+1), MockPoint(x1, y0+2), MockPoint(x1, y1)))
    items.append(("c", MockPoint(x1, y1), MockPoint(x1-1, y1), MockPoint(x1-2, y1), MockPoint(x0, y1)))
    items.append(("c", MockPoint(x0, y1), MockPoint(x0, y1-1), MockPoint(x0, y1-2), MockPoint(x0, y0)))

    return {
        "rect": MockRect(x0, y0, x1, y1),
        "fill": (0, 0, 0),
        "items": items
    }

def test_note_candidate_identity_multi_staff() -> None:
    # We load the multi-staff fixture to get realistic multi-staff geometry
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")
    doc = fitz.open(pdf_path)
    page = doc[0]
    diags_dict = extract_notation_diagnostics_dict(page, 1)
    doc.close()
    
    diags = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)
    assert len(diags.staves) >= 2, "Expected multiple staves in multi_staff fixture"
    
    staff1 = diags.staves[0].staff
    staff2 = diags.staves[1].staff
    
    # staff1 and staff2 have different y-coordinates
    y_center1 = sum(staff1.line_y_coords) / len(staff1.line_y_coords)
    y_center2 = sum(staff2.line_y_coords) / len(staff2.line_y_coords)
    
    # We create two mock quarter notes exactly on those centers
    # aspect ratio 1.5 -> w=15, h=10
    drawings = [
        build_mock_quarter_note_drawing(100.0, y_center1 - 5.0, 115.0, y_center1 + 5.0),
        # add stem for note 1
        {
            "rect": MockRect(114.5, y_center1 - 25.0, 115.5, y_center1 + 5.0),
            "fill": (0, 0, 0),
            "items": [("l", MockPoint(115.0, y_center1 - 25.0), MockPoint(115.0, y_center1 + 5.0))]
        },
        build_mock_quarter_note_drawing(150.0, y_center2 - 5.0, 165.0, y_center2 + 5.0),
        # add stem for note 2
        {
            "rect": MockRect(164.5, y_center2 - 25.0, 165.5, y_center2 + 5.0),
            "fill": (0, 0, 0),
            "items": [("l", MockPoint(165.0, y_center2 - 25.0), MockPoint(165.0, y_center2 + 5.0))]
        }
    ]
    
    mock_page = MockPage(drawings)
    w, h, q = _extract_note_candidates(mock_page, diags.staves)
    
    assert len(q) == 2, "Expected 2 quarter notes"
    
    # The notes should be unambiguously assigned to staff1 and staff2
    assert q[0].staff_index == staff1.staff_index
    assert q[0].system_index == staff1.system_index
    assert q[1].staff_index == staff2.staff_index
    assert q[1].system_index == staff2.system_index

def test_note_candidate_identity_ledger_lines() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    doc = fitz.open(pdf_path)
    page = doc[0]
    diags_dict = extract_notation_diagnostics_dict(page, 1)
    doc.close()
    
    diags = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)
    assert diags.status == "success"
    
    notes = []
    if diags.quarter_note_candidates: notes.extend(diags.quarter_note_candidates)
    
    assert len(notes) > 0, "Expected to find note candidates with ledger lines"
    
    for n in notes:
        assert n.staff_index > 0
        assert len(n.bbox) == 4
