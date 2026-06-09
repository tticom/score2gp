import pytest
import re
from score2gp.pdf_geometry_candidates import (
    PrimitiveEvidenceCandidate,
    LeftMarginPrimitiveCandidate,
    XAlignedPrimitiveClusterCandidate
)

def test_primitive_evidence_candidate_construction() -> None:
    for kind in ["text_span", "curve", "vertical_stroke", "horizontal_stroke", "diagonal_stroke", "rectangle"]:
        if kind == "text_span":
            p = PrimitiveEvidenceCandidate(
                page_index=1, system_index=1, staff_index=1,
                x0=10.0, y0=20.0, x1=30.0, y1=40.0,
                kind=kind, source="left_margin", # type: ignore
                font_name="Arial", font_size=12.0
            )
            assert p.font_name == "Arial"
            assert p.font_size == 12.0
        else:
            p = PrimitiveEvidenceCandidate(
                page_index=1, system_index=1, staff_index=1,
                x0=10.0, y0=20.0, x1=30.0, y1=40.0,
                kind=kind, source="x_aligned_cluster" # type: ignore
            )
        assert p.kind == kind

def test_reject_font_metadata_on_non_text() -> None:
    with pytest.raises(ValueError, match="font metadata must be absent"):
        PrimitiveEvidenceCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=10.0, y0=20.0, x1=30.0, y1=40.0,
            kind="rectangle", source="left_margin",
            font_name="Arial"
        )

def test_reject_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="x0 must be <= x1"):
        PrimitiveEvidenceCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=30.0, y0=20.0, x1=10.0, y1=40.0,
            kind="rectangle", source="left_margin"
        )
    with pytest.raises(ValueError, match="y0 must be <= y1"):
        PrimitiveEvidenceCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=10.0, y0=40.0, x1=30.0, y1=20.0,
            kind="rectangle", source="left_margin"
        )

def test_reject_invalid_indexes() -> None:
    with pytest.raises(ValueError):
        PrimitiveEvidenceCandidate(
            page_index=0, system_index=1, staff_index=1,
            x0=10.0, y0=20.0, x1=30.0, y1=40.0,
            kind="rectangle", source="left_margin"
        )

def test_left_margin_primitive_candidate() -> None:
    p = LeftMarginPrimitiveCandidate(
        page_index=1, system_index=2, staff_index=3,
        x0=10.0, y0=20.0, x1=30.0, y1=40.0,
        kind="curve", source="left_margin"
    )
    assert p.kind == "curve"

    with pytest.raises(ValueError, match="must have source"):
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=2, staff_index=3,
            x0=10.0, y0=20.0, x1=30.0, y1=40.0,
            kind="curve", source="x_aligned_cluster" # type: ignore
        )

def test_models_are_frozen() -> None:
    from pydantic import ValidationError
    p = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=30.0, y1=40.0,
        kind="rectangle", source="left_margin"
    )
    with pytest.raises(ValidationError):
        p.x0 = 50.0 # type: ignore

    p_cluster = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=30.0, y1=40.0,
        kind="rectangle", source="x_aligned_cluster"
    )
    c = XAlignedPrimitiveClusterCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, x1=30.0, primitive_count=1,
        primitives=[p_cluster]
    )
    with pytest.raises(ValidationError):
        c.x0 = 50.0 # type: ignore

def test_x_aligned_cluster_candidate() -> None:
    p1 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=20.0, y1=40.0,
        kind="rectangle", source="x_aligned_cluster"
    )
    p2 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=15.0, y0=20.0, x1=30.0, y1=40.0,
        kind="vertical_stroke", source="x_aligned_cluster"
    )
    c = XAlignedPrimitiveClusterCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, x1=30.0, primitive_count=2,
        primitives=[p1, p2]
    )
    assert c.primitive_count == 2

def test_reject_cluster_mismatched_count() -> None:
    p1 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=20.0, y1=40.0,
        kind="rectangle", source="x_aligned_cluster"
    )
    with pytest.raises(ValueError, match="primitive_count must equal length"):
        XAlignedPrimitiveClusterCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=10.0, x1=20.0, primitive_count=2,
            primitives=[p1]
        )

def test_reject_cluster_mixed_identity() -> None:
    p1 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=20.0, y1=40.0,
        kind="rectangle", source="x_aligned_cluster"
    )
    p2 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=2, staff_index=1,
        x0=15.0, y0=20.0, x1=30.0, y1=40.0,
        kind="vertical_stroke", source="x_aligned_cluster"
    )
    with pytest.raises(ValueError, match="mixed staff identity"):
        XAlignedPrimitiveClusterCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=10.0, x1=30.0, primitive_count=2,
            primitives=[p1, p2]
        )

def test_reject_cluster_invalid_source() -> None:
    p1 = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=10.0, y0=20.0, x1=20.0, y1=40.0,
        kind="rectangle", source="left_margin"
    )
    with pytest.raises(ValueError, match="cluster primitives must have source"):
        XAlignedPrimitiveClusterCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=10.0, x1=20.0, primitive_count=1,
            primitives=[p1]
        )
