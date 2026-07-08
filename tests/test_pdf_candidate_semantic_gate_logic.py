from score2gp.pdf_geometry_candidates import (
    GeometryCandidateSet,
    LeftMarginPrimitiveCandidate
)
from score2gp.pdf_candidate_semantic_gate import evaluate_logical_clef_gate

def test_semantic_gate_no_candidate():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry)
    assert result.status == "no_candidate"

def test_semantic_gate_ambiguous_candidate():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[
            LeftMarginPrimitiveCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                x0=10, y0=10, x1=20, y1=100,
                kind="vertical_stroke",
                source="left_margin"
            )
        ],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry)
    assert result.status == "ambiguous_candidate"

def test_semantic_gate_logical_clef_unknown_from_text():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[
            LeftMarginPrimitiveCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                x0=10, y0=10, x1=20, y1=100,
                kind="text_span",
                source="left_margin",
                font_name="Sonata"
            )
        ],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry)
    assert result.status == "logical_clef_candidate"
    assert result.clef_kind == "unknown"

def test_semantic_gate_logical_clef_unknown_from_curve():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[
            LeftMarginPrimitiveCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                x0=10, y0=10, x1=20, y1=100,
                kind="curve",
                source="left_margin"
            )
        ],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry)
    assert result.status == "logical_clef_candidate"
    assert result.clef_kind == "unknown"
