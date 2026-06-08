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
