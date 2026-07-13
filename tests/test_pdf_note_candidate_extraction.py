from __future__ import annotations

import pytest
from dataclasses import dataclass
from typing import Any
from score2gp.pdf_staff_notation_diagnostics import _extract_note_candidates

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

def test_extract_filled_compound_no_stem_whole_note() -> None:
    # Simulates GuitarPro filled compound open notehead without a stem (whole note)
    # Aspect ratio ~ 1.7 (e.g. w=7, h=4)
    items = []
    # Outer bounds
    for _ in range(2):
        items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(7, 0)))
        items.append(("c", MockPoint(7, 0), MockPoint(7, 1), MockPoint(7, 2), MockPoint(7, 4)))
        items.append(("c", MockPoint(7, 4), MockPoint(6, 4), MockPoint(5, 4), MockPoint(0, 4)))
        items.append(("c", MockPoint(0, 4), MockPoint(0, 3), MockPoint(0, 2), MockPoint(0, 0)))
    # Inner hole (distance to edge = 1.0, max_dist > 4 * 0.2 = 0.8)
    for _ in range(2):
        items.append(("c", MockPoint(1, 1), MockPoint(2, 1), MockPoint(3, 1), MockPoint(6, 1)))
        items.append(("c", MockPoint(6, 1), MockPoint(6, 2), MockPoint(6, 3), MockPoint(6, 3)))
        items.append(("c", MockPoint(6, 3), MockPoint(5, 3), MockPoint(4, 3), MockPoint(1, 3)))
        items.append(("c", MockPoint(1, 3), MockPoint(1, 2), MockPoint(1, 1), MockPoint(1, 1)))

    drawings = [{
        "rect": MockRect(0.0, 0.0, 7.0, 4.0),
        "fill": (0, 0, 0),
        "items": items
    }]
    
    page = MockPage(drawings)
    whole, half, quarter, dots = _extract_note_candidates(page)
    assert len(whole) == 1
    assert len(half) == 0
    assert len(quarter) == 0

def test_extract_filled_compound_stemmed_half_note() -> None:
    # Simulates GuitarPro filled compound open notehead with a stem (half note)
    items = []
    for _ in range(2):
        items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(7, 0)))
        items.append(("c", MockPoint(7, 0), MockPoint(7, 1), MockPoint(7, 2), MockPoint(7, 4)))
        items.append(("c", MockPoint(7, 4), MockPoint(6, 4), MockPoint(5, 4), MockPoint(0, 4)))
        items.append(("c", MockPoint(0, 4), MockPoint(0, 3), MockPoint(0, 2), MockPoint(0, 0)))
    # Inner hole
    for _ in range(2):
        items.append(("c", MockPoint(1, 1), MockPoint(2, 1), MockPoint(3, 1), MockPoint(6, 1)))
        items.append(("c", MockPoint(6, 1), MockPoint(6, 2), MockPoint(6, 3), MockPoint(6, 3)))
        items.append(("c", MockPoint(6, 3), MockPoint(5, 3), MockPoint(4, 3), MockPoint(1, 3)))
        items.append(("c", MockPoint(1, 3), MockPoint(1, 2), MockPoint(1, 1), MockPoint(1, 1)))

    drawings = [
        {
            "rect": MockRect(0.0, 0.0, 7.0, 4.0),
            "fill": (0, 0, 0),
            "items": items
        },
        {
            "rect": MockRect(6.5, -15.0, 7.5, 2.0),
            "fill": (0, 0, 0),
            "items": [("l", MockPoint(7.0, -15.0), MockPoint(7.0, 2.0))]
        }
    ]
    
    page = MockPage(drawings)
    whole, half, quarter, dots = _extract_note_candidates(page)
    assert len(whole) == 0
    assert len(half) == 1
    assert len(quarter) == 0

def test_extract_solid_stemmed_quarter_note() -> None:
    # Simulates regular solid quarter note
    # 4 curves only, bounding box distance to edge = 0
    items = []
    items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(7, 0)))
    items.append(("c", MockPoint(7, 0), MockPoint(7, 1), MockPoint(7, 2), MockPoint(7, 4)))
    items.append(("c", MockPoint(7, 4), MockPoint(6, 4), MockPoint(5, 4), MockPoint(0, 4)))
    items.append(("c", MockPoint(0, 4), MockPoint(0, 3), MockPoint(0, 2), MockPoint(0, 0)))

    drawings = [
        {
            "rect": MockRect(0.0, 0.0, 7.0, 4.0),
            "fill": (0, 0, 0),
            "items": items
        },
        {
            "rect": MockRect(6.5, -15.0, 7.5, 2.0),
            "fill": (0, 0, 0),
            "items": [("l", MockPoint(7.0, -15.0), MockPoint(7.0, 2.0))]
        }
    ]
    
    page = MockPage(drawings)
    whole, half, quarter, dots = _extract_note_candidates(page)
    assert len(whole) == 0
    assert len(half) == 0
    assert len(quarter) == 1

def test_reject_rest_like_filled_compound_symbol() -> None:
    # Simulates GuitarPro whole rest.
    # It has 8 curves, but it's a solid block. All points are on the edge.
    items = []
    items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(5, 0)))
    items.append(("c", MockPoint(5, 0), MockPoint(5, 0.5), MockPoint(5, 1), MockPoint(5, 3)))
    items.append(("c", MockPoint(5, 3), MockPoint(4, 3), MockPoint(3, 3), MockPoint(0, 3)))
    items.append(("c", MockPoint(0, 3), MockPoint(0, 2), MockPoint(0, 1), MockPoint(0, 0)))
    # Add a few more lines on the perimeter to get c_count >= 8
    items.append(("c", MockPoint(0, 0), MockPoint(0.1, 0), MockPoint(0.2, 0), MockPoint(0.3, 0)))
    items.append(("c", MockPoint(5, 3), MockPoint(4.9, 3), MockPoint(4.8, 3), MockPoint(4.7, 3)))
    items.append(("c", MockPoint(5, 0), MockPoint(5, 0.1), MockPoint(5, 0.2), MockPoint(5, 0.3)))
    items.append(("c", MockPoint(0, 3), MockPoint(0, 2.9), MockPoint(0, 2.8), MockPoint(0, 2.7)))

    drawings = [{
        "rect": MockRect(0.0, 0.0, 5.0, 3.0),
        "fill": (0, 0, 0),
        "items": items
    }]
    
    page = MockPage(drawings)
    whole, half, quarter, dots = _extract_note_candidates(page)
    assert len(whole) == 0
    assert len(half) == 0
    assert len(quarter) == 0

def test_extract_existing_hollow_whole_note() -> None:
    # Standard hollow open notehead without stem
    items = []
    items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(7, 0)))
    items.append(("c", MockPoint(7, 0), MockPoint(7, 1), MockPoint(7, 2), MockPoint(7, 4)))
    items.append(("c", MockPoint(7, 4), MockPoint(6, 4), MockPoint(5, 4), MockPoint(0, 4)))
    items.append(("c", MockPoint(0, 4), MockPoint(0, 3), MockPoint(0, 2), MockPoint(0, 0)))

    drawings = [{
        "rect": MockRect(0.0, 0.0, 7.0, 4.0),
        "fill": None,
        "items": items
    }]
    
    page = MockPage(drawings)
    whole, half, quarter, dots = _extract_note_candidates(page)
    assert len(whole) == 1
    assert len(half) == 0
    assert len(quarter) == 0
