import pytest
from pydantic import ValidationError
from score2gp.pdf_candidate_semantic_gate import LogicalClefCandidate
from score2gp.pdf_candidate_quarter_rest import QuarterRestCandidate
from score2gp.pdf_geometry_candidates import XAlignedPrimitiveClusterCandidate

def test_logical_clef_candidate_validation() -> None:
    # 1. Valid: logical_clef_candidate with clef_kind treble
    cand = LogicalClefCandidate(
        status="logical_clef_candidate",
        reason="Treble clef matched",
        clef_kind="treble"
    )
    assert cand.status == "logical_clef_candidate"
    assert cand.clef_kind == "treble"

    # 2. Invalid: logical_clef_candidate without clef_kind
    with pytest.raises(ValidationError):
        LogicalClefCandidate(
            status="logical_clef_candidate",
            reason="Missing clef_kind",
            clef_kind=None
        )

    # 3. Valid: no_candidate with clef_kind None
    cand2 = LogicalClefCandidate(
        status="no_candidate",
        reason="Empty left margin",
        clef_kind=None
    )
    assert cand2.status == "no_candidate"
    assert cand2.clef_kind is None

    # 4. Invalid: no_candidate with clef_kind set
    with pytest.raises(ValidationError):
        LogicalClefCandidate(
            status="no_candidate",
            reason="Invalid clef_kind set",
            clef_kind="treble"
        )


def test_quarter_rest_candidate_bounds_validation() -> None:
    # Build a dummy cluster
    from score2gp.pdf_geometry_candidates import PrimitiveEvidenceCandidate
    dummy_prim = PrimitiveEvidenceCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        source="x_aligned_cluster",
        x0=10.0,
        y0=100.0,
        x1=15.0,
        y1=120.0,
        kind="curve"
    )
    dummy_cluster = XAlignedPrimitiveClusterCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=10.0,
        x1=20.0,
        primitive_count=1,
        primitives=[dummy_prim]
    )

    # 1. Valid bounds
    qr = QuarterRestCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=10.0,
        y0=100.0,
        x1=15.0,
        y1=120.0,
        cluster=dummy_cluster
    )
    assert qr.x0 == 10.0

    # 2. Invalid bounds: x0 > x1
    with pytest.raises(ValidationError):
        QuarterRestCandidate(
            page_index=1,
            system_index=1,
            staff_index=1,
            x0=20.0,
            y0=100.0,
            x1=15.0,
            y1=120.0,
            cluster=dummy_cluster
        )

    # 3. Invalid bounds: y0 > y1
    with pytest.raises(ValidationError):
        QuarterRestCandidate(
            page_index=1,
            system_index=1,
            staff_index=1,
            x0=10.0,
            y0=130.0,
            x1=15.0,
            y1=120.0,
            cluster=dummy_cluster
        )
