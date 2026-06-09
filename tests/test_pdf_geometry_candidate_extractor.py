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
