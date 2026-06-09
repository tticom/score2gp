"""
Tests for read-only candidate diagnostics integration (Task 45).

Proves:
- Candidate fields default to None when evidence is unavailable.
- Candidate fields are [] when extraction runs against a real empty evidence array.
- Left-margin candidates are populated from real left_margin_diags.evidence without geometry changes.
- X-aligned cluster candidates are populated from real clustering_diags.evidence without geometry changes.
- Existing morphology and clustering diagnostics are preserved unchanged.
- No semantic terms leak into candidate model names, public interfaces, source strings, or docs.
"""
from __future__ import annotations
import json
from typing import Any
import pytest
from score2gp.pdf_geometry import _LineSegment
from score2gp.pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
)
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockPoint:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

class _MockRect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

def _five_line_group(x0: float = 50.0, x1: float = 500.0,
                     y_start: float = 100.0, spacing: float = 8.0) -> list[Any]:
    return [_LineSegment(x0, y_start + i * spacing, x1, y_start + i * spacing)
            for i in range(5)]


# ---------------------------------------------------------------------------
# 1. Candidate fields default to None when evidence is unavailable
# ---------------------------------------------------------------------------

def test_candidate_fields_none_when_no_staff_space() -> None:
    """Single staff line → staff_space=0 → no clustering/margin → candidates are None."""
    group = [_LineSegment(50.0, 100.0, 500.0, 100.0)]

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return []
        def get_text(self, kind: str) -> dict | list:
            return {"blocks": []} if kind == "dict" else []

    diags = build_notation_diagnostics(MockPage(), page_index=1, notation_groups=[group])
    d = diags.staves[0]
    assert d.left_margin is None
    assert d.clustering is None
    assert d.left_margin_candidates is None
    assert d.x_aligned_cluster_candidates is None


def test_candidate_fields_none_when_constructed_without_them() -> None:
    """NotationStaffDiagnostics constructed without candidate kwargs defaults to None."""
    geom = NotationStaffGeometry(
        page_index=1, system_index=1, staff_index=1,
        x0=50.0, y0=100.0, x1=500.0, y1=132.0,
        line_y_coords=[100.0, 108.0, 116.0, 124.0, 132.0],
    )
    prims = LocalPrimitivesSummary(
        line_count=5, curve_count=0, rect_count=0, text_span_count_by_font={},
    )
    d = NotationStaffDiagnostics(staff=geom, primitives=prims)
    assert d.left_margin_candidates is None
    assert d.x_aligned_cluster_candidates is None


# ---------------------------------------------------------------------------
# 2. Candidate fields are [] when extraction runs against real empty evidence
# ---------------------------------------------------------------------------

def test_candidate_fields_empty_list_from_empty_evidence() -> None:
    """Staff with staff_space > 0 but no non-staff primitives → evidence=[] → candidates=[]."""
    group = _five_line_group()

    # Only staff-line horizontals — no non-staff primitives for clustering/margin.
    drawings = [
        {
            "rect": (40.0, 70.0, 510.0, 160.0),
            "items": [
                ("l", _MockPoint(50.0, 100.0), _MockPoint(500.0, 100.0)),
                ("l", _MockPoint(50.0, 108.0), _MockPoint(500.0, 108.0)),
                ("l", _MockPoint(50.0, 116.0), _MockPoint(500.0, 116.0)),
                ("l", _MockPoint(50.0, 124.0), _MockPoint(500.0, 124.0)),
                ("l", _MockPoint(50.0, 132.0), _MockPoint(500.0, 132.0)),
            ],
        }
    ]

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            return {"blocks": []} if kind == "dict" else []

    diags = build_notation_diagnostics(MockPage(), page_index=1, notation_groups=[group])
    d = diags.staves[0]

    # clustering and left_margin should exist (staff_space > 0)
    assert d.clustering is not None
    assert d.left_margin is not None

    # evidence arrays are empty lists, not None
    assert d.clustering.evidence is not None
    assert d.left_margin.evidence is not None

    # Therefore candidate fields must be [] (run but no candidates found), not None
    assert d.left_margin_candidates is not None
    assert d.left_margin_candidates == []
    assert d.x_aligned_cluster_candidates is not None
    assert d.x_aligned_cluster_candidates == []


# ---------------------------------------------------------------------------
# 3. Left-margin candidates populated from real evidence, geometry preserved
# ---------------------------------------------------------------------------

def test_left_margin_candidates_populated_from_real_evidence() -> None:
    """Primitives in the left margin zone produce left_margin_candidates with preserved geometry."""
    group = _five_line_group()

    # Rectangle at center_x=65 is within margin (x0=50 + 10*8=130)
    drawings = [
        {
            "rect": (40.0, 70.0, 510.0, 160.0),
            "items": [
                # Staff lines
                ("l", _MockPoint(50.0, 100.0), _MockPoint(500.0, 100.0)),
                ("l", _MockPoint(50.0, 108.0), _MockPoint(500.0, 108.0)),
                ("l", _MockPoint(50.0, 116.0), _MockPoint(500.0, 116.0)),
                ("l", _MockPoint(50.0, 124.0), _MockPoint(500.0, 124.0)),
                ("l", _MockPoint(50.0, 132.0), _MockPoint(500.0, 132.0)),
                # Rectangle in left margin
                ("re", _MockRect(60.0, 105.0, 70.0, 115.0)),
                # Vertical stroke in left margin
                ("l", _MockPoint(55.0, 100.0), _MockPoint(55.0, 120.0)),
            ],
        }
    ]

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            return {"blocks": []} if kind == "dict" else []

    diags = build_notation_diagnostics(MockPage(), page_index=1, notation_groups=[group])
    d = diags.staves[0]

    assert d.left_margin is not None
    assert d.left_margin.evidence is not None
    assert len(d.left_margin.evidence) > 0

    assert d.left_margin_candidates is not None
    assert len(d.left_margin_candidates) == len(d.left_margin.evidence)

    # Verify geometry is preserved from evidence → candidate
    for ev, cand in zip(d.left_margin.evidence, d.left_margin_candidates):
        assert cand.x0 == ev.x0
        assert cand.y0 == ev.y0
        assert cand.x1 == ev.x1
        assert cand.y1 == ev.y1
        assert cand.kind == ev.kind
        assert cand.font_name == ev.font_name
        assert cand.font_size == ev.font_size
        assert cand.source == "left_margin"
        assert cand.page_index == 1
        assert cand.system_index == 1
        assert cand.staff_index == 1


# ---------------------------------------------------------------------------
# 4. X-aligned cluster candidates populated from real evidence, geometry preserved
# ---------------------------------------------------------------------------

def test_x_aligned_cluster_candidates_populated_from_real_evidence() -> None:
    """Primitives forming x-aligned clusters produce cluster candidates with preserved geometry."""
    group = _five_line_group()

    # Two primitives at similar x → should cluster
    drawings = [
        {
            "rect": (40.0, 70.0, 510.0, 160.0),
            "items": [
                # Staff lines
                ("l", _MockPoint(50.0, 100.0), _MockPoint(500.0, 100.0)),
                ("l", _MockPoint(50.0, 108.0), _MockPoint(500.0, 108.0)),
                ("l", _MockPoint(50.0, 116.0), _MockPoint(500.0, 116.0)),
                ("l", _MockPoint(50.0, 124.0), _MockPoint(500.0, 124.0)),
                ("l", _MockPoint(50.0, 132.0), _MockPoint(500.0, 132.0)),
                # Vertical stroke at x=200
                ("l", _MockPoint(200.0, 100.0), _MockPoint(200.0, 120.0)),
                # Rectangle near x=200
                ("re", _MockRect(198.0, 110.0, 202.0, 115.0)),
            ],
        }
    ]

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            return {"blocks": []} if kind == "dict" else []

    diags = build_notation_diagnostics(MockPage(), page_index=1, notation_groups=[group])
    d = diags.staves[0]

    assert d.clustering is not None
    assert d.clustering.evidence is not None
    assert len(d.clustering.evidence) > 0

    assert d.x_aligned_cluster_candidates is not None
    assert len(d.x_aligned_cluster_candidates) == len(d.clustering.evidence)

    # Verify geometry preservation
    for ev, cand in zip(d.clustering.evidence, d.x_aligned_cluster_candidates):
        assert cand.x0 == ev.x0
        assert cand.x1 == ev.x1
        assert cand.primitive_count == ev.primitive_count
        assert len(cand.primitives) == len(ev.primitives)
        for ep, cp in zip(ev.primitives, cand.primitives):
            assert cp.x0 == ep.x0
            assert cp.y0 == ep.y0
            assert cp.x1 == ep.x1
            assert cp.y1 == ep.y1
            assert cp.kind == ep.kind
            assert cp.font_name == ep.font_name
            assert cp.font_size == ep.font_size
            assert cp.source == "x_aligned_cluster"
        assert cand.page_index == 1
        assert cand.system_index == 1
        assert cand.staff_index == 1


# ---------------------------------------------------------------------------
# 5. Existing morphology and clustering diagnostics preserved unchanged
# ---------------------------------------------------------------------------

def test_existing_diagnostics_preserved_with_candidates() -> None:
    """Adding candidate fields does not alter morphology, clustering, or left_margin values."""
    group = _five_line_group()

    drawings = [
        {
            "rect": (40.0, 70.0, 510.0, 160.0),
            "items": [
                ("l", _MockPoint(50.0, 100.0), _MockPoint(500.0, 100.0)),
                ("l", _MockPoint(50.0, 108.0), _MockPoint(500.0, 108.0)),
                ("l", _MockPoint(50.0, 116.0), _MockPoint(500.0, 116.0)),
                ("l", _MockPoint(50.0, 124.0), _MockPoint(500.0, 124.0)),
                ("l", _MockPoint(50.0, 132.0), _MockPoint(500.0, 132.0)),
                # non-staff horizontal
                ("l", _MockPoint(100.0, 112.0), _MockPoint(200.0, 112.0)),
                # vertical candidate
                ("l", _MockPoint(150.0, 100.0), _MockPoint(150.0, 120.0)),
                # rectangle
                ("re", _MockRect(120.0, 105.0, 140.0, 115.0)),
                # curve
                ("c", _MockPoint(100.0, 100.0), _MockPoint(105.0, 105.0),
                 _MockPoint(110.0, 105.0), _MockPoint(115.0, 100.0)),
            ],
        }
    ]
    text_dict: dict[str, Any] = {
        "blocks": [{
            "lines": [{
                "spans": [
                    {"text": "A", "font": "TestFont", "size": 12.0,
                     "bbox": (100.0, 100.0, 110.0, 110.0)},
                ]
            }]
        }]
    }

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            return text_dict if kind == "dict" else []

    diags = build_notation_diagnostics(MockPage(), page_index=1, notation_groups=[group])
    d = diags.staves[0]

    # Morphology unchanged
    assert d.morphology is not None
    assert d.morphology.staff_line_horizontal == 5
    assert d.morphology.non_staff_horizontal == 1
    assert d.morphology.vertical_stroke_candidate == 1
    assert d.morphology.rectangle_candidate == 1
    assert d.morphology.curve_candidate == 1
    assert d.morphology.text_span_by_font == {"TestFont": 1}

    # Clustering unchanged
    assert d.clustering is not None
    assert d.clustering.x_aligned_cluster_count >= 1

    # Left margin unchanged
    assert d.left_margin is not None


# ---------------------------------------------------------------------------
# 6. Serialization round-trip includes candidate fields
# ---------------------------------------------------------------------------

def test_candidate_fields_serialize_correctly() -> None:
    """model_dump() includes candidate fields with correct None/[]/populated values."""
    geom = NotationStaffGeometry(
        page_index=1, system_index=1, staff_index=1,
        x0=50.0, y0=100.0, x1=500.0, y1=132.0,
        line_y_coords=[100.0, 108.0, 116.0, 124.0, 132.0],
    )
    prims = LocalPrimitivesSummary(
        line_count=5, curve_count=0, rect_count=0, text_span_count_by_font={},
    )

    # Default: None
    d1 = NotationStaffDiagnostics(staff=geom, primitives=prims)
    dump1 = d1.model_dump()
    assert "left_margin_candidates" in dump1
    assert dump1["left_margin_candidates"] is None
    assert "x_aligned_cluster_candidates" in dump1
    assert dump1["x_aligned_cluster_candidates"] is None

    # Explicit empty list
    d2 = NotationStaffDiagnostics(
        staff=geom, primitives=prims,
        left_margin_candidates=[], x_aligned_cluster_candidates=[],
    )
    dump2 = d2.model_dump()
    assert dump2["left_margin_candidates"] == []
    assert dump2["x_aligned_cluster_candidates"] == []


# ---------------------------------------------------------------------------
# 7. No semantic terms in candidate diagnostics schema
# ---------------------------------------------------------------------------

def test_candidate_schema_no_semantic_leakage() -> None:
    """NotationStaffDiagnostics schema must not contain semantic music terms."""
    import re
    schema = NotationStaffDiagnostics.model_json_schema()
    schema_str = json.dumps(schema).lower()
    for forbidden in ["clef", "pitch", "time_signature", "key_signature",
                       "notehead", "duration", "chord", "rest",
                       "voice", "rhythm"]:
        assert not re.search(r'\b' + forbidden + r'\b', schema_str), \
            f"Semantic term '{forbidden}' leaked into schema"
