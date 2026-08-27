import pytest
from pydantic import ValidationError
from score2gp.pdf_geometry_candidate_extractor import PdfGeometryCandidateExtractor
from score2gp.pdf_staff_geometry import PrimitiveGeometryEvidence, XAlignedPrimitiveClusterEvidence
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate

def test_extract_left_margin_candidates_empty() -> None:
    extractor = PdfGeometryCandidateExtractor()
    assert extractor.extract_left_margin_candidates(1, 1, 1, []) == []

def test_extract_left_margin_candidates_single_rectangle() -> None:
    extractor = PdfGeometryCandidateExtractor()
    evidence = [
        PrimitiveGeometryEvidence(
            x0=10.0,
            y0=20.0,
            x1=30.0,
            y1=40.0,
            kind="rectangle",
            font_name=None,
            font_size=None
        )
    ]
    candidates = extractor.extract_left_margin_candidates(1, 2, 3, evidence)
    assert len(candidates) == 1

    c = candidates[0]
    assert c.page_index == 1
    assert c.system_index == 2
    assert c.staff_index == 3
    assert c.x0 == 10.0
    assert c.y0 == 20.0
    assert c.x1 == 30.0
    assert c.y1 == 40.0
    assert c.kind == "rectangle"
    assert c.font_name is None
    assert c.font_size is None
    assert c.source == "left_margin"

def test_extract_left_margin_candidates_text_span_preserves_font() -> None:
    extractor = PdfGeometryCandidateExtractor()
    evidence = [
        PrimitiveGeometryEvidence(
            x0=10.0,
            y0=20.0,
            x1=30.0,
            y1=40.0,
            kind="text_span",
            font_name="Helvetica",
            font_size=12.0
        )
    ]
    candidates = extractor.extract_left_margin_candidates(1, 1, 1, evidence)
    assert len(candidates) == 1
    assert candidates[0].kind == "text_span"
    assert candidates[0].font_name == "Helvetica"
    assert candidates[0].font_size == 12.0
    assert candidates[0].source == "left_margin"

def test_extract_left_margin_candidates_preserves_order() -> None:
    extractor = PdfGeometryCandidateExtractor()
    evidence = [
        PrimitiveGeometryEvidence(
            x0=10.0, y0=20.0, x1=30.0, y1=40.0,
            kind="rectangle", font_name=None, font_size=None
        ),
        PrimitiveGeometryEvidence(
            x0=15.0, y0=25.0, x1=35.0, y1=45.0,
            kind="vertical_stroke", font_name=None, font_size=None
        ),
    ]
    candidates = extractor.extract_left_margin_candidates(1, 1, 1, evidence)
    assert len(candidates) == 2
    assert candidates[0].x0 == 10.0
    assert candidates[1].x0 == 15.0

def test_extract_left_margin_candidates_validation_error_not_swallowed() -> None:
    extractor = PdfGeometryCandidateExtractor()
    # Create an evidence item that will cause a validation error when converted to candidate.
    # For example, missing font_name when kind="text_span" is rejected by LeftMarginPrimitiveCandidate.
    evidence = [
        PrimitiveGeometryEvidence(
            x0=10.0,
            y0=20.0,
            x1=30.0,
            y1=40.0,
            kind="rectangle",
            font_name="Helvetica", # Rectangle cannot have font_name
            font_size=None
        )
    ]

    with pytest.raises(ValidationError):
        extractor.extract_left_margin_candidates(1, 1, 1, evidence)

def test_extract_x_aligned_cluster_candidates_empty() -> None:
    extractor = PdfGeometryCandidateExtractor()
    assert extractor.extract_x_aligned_cluster_candidates(1, 1, 1, []) == []

def test_extract_x_aligned_cluster_candidates_single_cluster() -> None:
    extractor = PdfGeometryCandidateExtractor()
    cluster_evidence = [
        XAlignedPrimitiveClusterEvidence(
            x0=10.0,
            x1=30.0,
            primitive_count=1,
            primitives=[
                PrimitiveGeometryEvidence(
                    x0=15.0,
                    y0=20.0,
                    x1=25.0,
                    y1=40.0,
                    kind="vertical_stroke",
                    font_name=None,
                    font_size=None
                )
            ]
        )
    ]
    candidates = extractor.extract_x_aligned_cluster_candidates(2, 3, 4, cluster_evidence)
    assert len(candidates) == 1

    cluster_cand = candidates[0]
    assert cluster_cand.page_index == 2
    assert cluster_cand.system_index == 3
    assert cluster_cand.staff_index == 4
    assert cluster_cand.x0 == 10.0
    assert cluster_cand.x1 == 30.0
    assert cluster_cand.primitive_count == 1
    assert len(cluster_cand.primitives) == 1

    prim_cand = cluster_cand.primitives[0]
    assert prim_cand.page_index == 2
    assert prim_cand.system_index == 3
    assert prim_cand.staff_index == 4
    assert prim_cand.x0 == 15.0
    assert prim_cand.y0 == 20.0
    assert prim_cand.x1 == 25.0
    assert prim_cand.y1 == 40.0
    assert prim_cand.kind == "vertical_stroke"
    assert prim_cand.source == "x_aligned_cluster"
    assert prim_cand.font_name is None
    assert prim_cand.font_size is None

def test_extract_x_aligned_cluster_candidates_preserves_order_and_multi_primitives() -> None:
    extractor = PdfGeometryCandidateExtractor()
    cluster_evidence = [
        XAlignedPrimitiveClusterEvidence(
            x0=10.0,
            x1=30.0,
            primitive_count=2,
            primitives=[
                PrimitiveGeometryEvidence(
                    x0=15.0, y0=20.0, x1=25.0, y1=30.0,
                    kind="text_span", font_name="Helvetica", font_size=12.0
                ),
                PrimitiveGeometryEvidence(
                    x0=10.0, y0=40.0, x1=30.0, y1=50.0,
                    kind="rectangle", font_name=None, font_size=None
                )
            ]
        )
    ]
    candidates = extractor.extract_x_aligned_cluster_candidates(1, 1, 1, cluster_evidence)
    assert len(candidates) == 1

    cluster_cand = candidates[0]
    assert cluster_cand.primitive_count == 2

    p1 = cluster_cand.primitives[0]
    assert p1.kind == "text_span"
    assert p1.font_name == "Helvetica"
    assert p1.font_size == 12.0

    p2 = cluster_cand.primitives[1]
    assert p2.kind == "rectangle"
    assert p2.font_name is None
    assert p2.font_size is None

def test_extract_x_aligned_cluster_candidates_validation_error_not_swallowed() -> None:
    extractor = PdfGeometryCandidateExtractor()
    # Create invalid evidence (e.g. font present on non-text_span)
    cluster_evidence = [
        XAlignedPrimitiveClusterEvidence(
            x0=10.0,
            x1=30.0,
            primitive_count=1,
            primitives=[
                PrimitiveGeometryEvidence(
                    x0=15.0,
                    y0=20.0,
                    x1=25.0,
                    y1=40.0,
                    kind="vertical_stroke",
                    font_name="Helvetica", # Invalid for vertical_stroke
                    font_size=None
                )
            ]
        )
    ]
    with pytest.raises(ValidationError):
        extractor.extract_x_aligned_cluster_candidates(1, 1, 1, cluster_evidence)

def test_filter_tab_barline_candidates_compact_height_bounds() -> None:
    from score2gp.pdf import filter_tab_barline_candidates, _LineSegment
    # Staff y0=100.0, y1=116.0 (staff_height = 16.0). min_barline_height = min(15.0, 14.0) = 14.0
    line_ys = [100.0, 104.0, 108.0, 112.0, 116.0]

    # Candidate 1: height = 14.0 (y0=101.0, y1=115.0), crosses staff -> ACCEPTED
    c1 = _LineSegment(x0=200.0, y0=101.0, x1=200.0, y1=115.0, primitive_kind="draw")
    # Candidate 2: height = 10.0 (y0=103.0, y1=113.0), too short -> REJECTED
    c2 = _LineSegment(x0=300.0, y0=103.0, x1=300.0, y1=113.0, primitive_kind="draw")

    res = filter_tab_barline_candidates([c1, c2], y0=100.0, y1=116.0, line_ys=line_ys, x0=100.0, x1=800.0)
    valid_xs = [d["x"] for d in res["details"] if d["final_decision"] == "accepted"]
    assert 200.0 in valid_xs
    assert 300.0 not in valid_xs

def test_filter_tab_barline_candidates_inherited_20pt_bar_width_limit() -> None:
    from score2gp.pdf import _detect_tab_systems
    from collections import namedtuple

    Point = namedtuple('Point', ['x', 'y'])
    drawings = []

    # TAB staff lines (6 lines: y = 200..230)
    for y in [200.0, 206.0, 212.0, 218.0, 224.0, 230.0]:
        drawings.append({"items": [("l", Point(100.0, y), Point(800.0, y))]})

    # Notation staff lines (5 lines: y = 100..132)
    for y in [100.0, 108.0, 116.0, 124.0, 132.0]:
        drawings.append({"items": [("l", Point(100.0, y), Point(800.0, y))]})

    # Explicit TAB barlines at x = 100.0 and x = 800.0
    for x in [100.0, 800.0]:
        drawings.append({"items": [("l", Point(x, 200.0), Point(x, 230.0))]})

    # Partner candidates crossing notation staff:
    # x = 117.0 (17.0pt from 100.0, < 20.0pt) -> REJECTED
    # x = 350.0 (250.0pt from 100.0, >= 20.0pt) -> ACCEPTED
    for x in [117.0, 350.0]:
        drawings.append({"items": [("l", Point(x, 100.0), Point(x, 132.0))]})

    class MockPage:
        def get_drawings(self):
            return drawings
        def get_text(self, kind):
            return []

    page = MockPage()
    systems = _detect_tab_systems(page, page_index=1)
    assert len(systems) == 1
    system = systems[0]

    assert 100.0 in system.barlines
    assert 800.0 in system.barlines
    assert 350.0 in system.barlines
    assert 117.0 not in system.barlines
import pytest
from pathlib import Path
from score2gp.pdf import _extract_pdf_text_candidates
import pymupdf
from unittest.mock import MagicMock
import sys

def test_300pt_heuristic_removed_regression(tmp_path: Path) -> None:
    class FakePage:
        def __init__(self):
            self.rect = MagicMock()
            self.rect.width = 1000.0
            self.rect.height = 1000.0
        
        def get_text(self, kind):
            if kind == "words":
                return [(240.0, 202.0, 260.0, 222.0, "0", 0, 0, 0)]
            if kind == "dict":
                return {"blocks": []}
            return []
            
        def get_drawings(self):
            drawings = []
            for y in [100.0, 108.0, 116.0, 124.0, 132.0]:
                drawings.append({"items": [("l", MagicMock(x=10.0, y=y), MagicMock(x=800.0, y=y))]})
            for y in [200.0, 206.0, 212.0, 218.0, 224.0, 230.0]:
                drawings.append({"items": [("l", MagicMock(x=10.0, y=y), MagicMock(x=800.0, y=y))]})
            
            drawings.append({"items": [("l", MagicMock(x=50.0, y=260.0), MagicMock(x=450.0, y=260.0))]})
            drawings.append({"items": [("l", MagicMock(x=250.0, y=230.0), MagicMock(x=250.0, y=260.0))]})
            
            return drawings

    class FakeDoc:
        def __init__(self):
            self.page_count = 1
            self.metadata = {}
        def __getitem__(self, idx):
            if idx > 0:
                raise IndexError
            return FakePage()
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with pytest.MonkeyPatch.context() as m:
        m.setattr(pymupdf, "open", lambda f: FakeDoc())
        if "fitz" in sys.modules:
            m.setattr(sys.modules["fitz"], "open", lambda f: FakeDoc())
            
        warnings = []
        meta = {"detected_systems": 0, "detected_staves": 0, "detected_bar_boxes": 0, "detected_string_lines": 0}
        cands = _extract_pdf_text_candidates(tmp_path / "dummy.pdf", warnings, meta)
        
        fret = [cand for cand in cands if cand.get("raw_text") == "0"][0]
        duration = fret["raw"]["duration_evidence"]
        
        assert duration["beam_count"] == 1, (
            f"Expected beam_count 1, got {duration['beam_count']}. "
            "This implies the 400pt line was absorbed as a staff line due to the 300pt hack!"
        )
