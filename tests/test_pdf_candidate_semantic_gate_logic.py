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

def test_semantic_gate_logical_clef_unknown_when_heuristics_fail():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[
            LeftMarginPrimitiveCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                # Tiny text span, fails treble clef heuristics
                x0=10, y0=10, x1=12, y1=12,
                kind="text_span",
                source="left_margin",
                font_name="Sonata"
            )
        ],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry, staff_spacing=10.0, staff_height=40.0, staff_x0=0.0)
    assert result.status == "logical_clef_candidate"
    assert result.clef_kind == "unknown"

def test_semantic_gate_logical_clef_treble():
    geometry = GeometryCandidateSet(
        left_margin_primitives=[
            LeftMarginPrimitiveCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                # Large text span that matches treble clef heuristics
                # width = 20 (width_to_spacing = 2.0 >= 1.5)
                # height = 50 (height_to_spacing = 5.0 >= 3.5, height_to_staff_height = 1.25 > 1.2)
                x0=10, y0=10, x1=30, y1=60,
                kind="text_span",
                source="left_margin",
                font_name="Sonata"
            )
        ],
        x_aligned_clusters=[]
    )
    result = evaluate_logical_clef_gate(geometry, staff_spacing=10.0, staff_height=40.0, staff_x0=0.0)
    assert result.status == "logical_clef_candidate"
    assert result.clef_kind == "treble"
