from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
from score2gp.pdf_geometry_candidates import GeometryCandidateSet

def test_extract_geometry_candidates_skeleton() -> None:
    diagnostics_dummy = {
        "x0": 0.0,
        "y_start": 100.0,
        "line_gap": 10.0
    }
    
    candidates = extract_geometry_candidates(diagnostics_dummy)
    
    assert isinstance(candidates, GeometryCandidateSet)
    assert len(candidates.circular_markers) == 0
    assert len(candidates.clusters) == 0

from score2gp.pdf_geometry_candidate_extraction import extract_left_margin_geometry_candidates

def test_extract_left_margin_geometry_candidates() -> None:
    diagnostics_dummy = {
        "left_margin": {
            "text_span_count": 2,
            "curve_candidate_count": 1,
            "vertical_stroke_candidate_count": 0,
            "rectangle_candidate_count": 3
        }
    }
    
    candidates = extract_left_margin_geometry_candidates(diagnostics_dummy)
    
    assert isinstance(candidates, GeometryCandidateSet)
    assert len(candidates.text_markers) == 2
    assert len(candidates.curve_markers) == 1
    assert len(candidates.vertical_strokes) == 0
    assert len(candidates.rectangle_markers) == 3

def test_extract_left_margin_geometry_candidates_empty() -> None:
    diagnostics_dummy = {}
    
    candidates = extract_left_margin_geometry_candidates(diagnostics_dummy)
    
    assert isinstance(candidates, GeometryCandidateSet)
    assert len(candidates.text_markers) == 0
    assert len(candidates.curve_markers) == 0
    assert len(candidates.vertical_strokes) == 0
    assert len(candidates.rectangle_markers) == 0

from score2gp.pdf_geometry_candidate_extraction import extract_x_aligned_cluster_candidates

def test_extract_x_aligned_cluster_candidates() -> None:
    diagnostics_dummy = {
        "clustering": {
            "x_aligned_cluster_count": 5
        }
    }
    
    candidates = extract_x_aligned_cluster_candidates(diagnostics_dummy)
    
    assert isinstance(candidates, GeometryCandidateSet)
    assert len(candidates.clusters) == 5

def test_extract_x_aligned_cluster_candidates_empty() -> None:
    diagnostics_dummy = {}
    
    candidates = extract_x_aligned_cluster_candidates(diagnostics_dummy)
    
    assert isinstance(candidates, GeometryCandidateSet)
    assert len(candidates.clusters) == 0
