import pytest
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate
from score2gp.logical_clef_candidate_classifier import classify_logical_clef_candidate

def make_candidate(kind: str, x0: float, y0: float, x1: float, y1: float) -> LeftMarginPrimitiveCandidate:
    # A helper to easily construct test candidates
    font_kwargs = {}
    if kind == "text_span":
        font_kwargs = {"font_name": "Opus", "font_size": 24.0}
        
    return LeftMarginPrimitiveCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        kind=kind,  # type: ignore
        source="left_margin",
        **font_kwargs
    )

def test_classify_logical_clef_candidate_missing_evidence():
    result = classify_logical_clef_candidate(None, 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert result["reason"] == "Missing candidate evidence"

    result_empty = classify_logical_clef_candidate([], 5.0, 20.0, 10.0)
    assert result_empty["label"] == "unknown"

def test_classify_logical_clef_candidate_invalid_staff_geometry():
    cand = make_candidate("text_span", 10.0, 10.0, 20.0, 30.0)
    result = classify_logical_clef_candidate([cand], 0.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "Invalid staff geometry" in result["reason"]

    result2 = classify_logical_clef_candidate([cand], 5.0, 0.0, 10.0)
    assert result2["label"] == "unknown"

def test_classify_logical_clef_candidate_no_valid_kind():
    cand = make_candidate("rectangle", 10.0, 10.0, 20.0, 30.0)
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "No valid text_span or curve" in result["reason"]

def test_classify_logical_clef_candidate_valid_treble():
    # Spacing 5.0, height 20.0 (4 spaces)
    # Treble clef needs height_to_spacing >= 3.5 (i.e. >= 17.5) and width_to_spacing >= 1.5 (i.e. >= 7.5)
    cand = make_candidate("text_span", 10.0, 10.0, 18.0, 35.0) # height 25.0, width 8.0
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "treble_clef_candidate"
    assert result["features"]["height_to_spacing"] == 5.0
    assert result["features"]["width_to_spacing"] == 1.6
    assert result["features"]["height_to_staff_height"] == 1.25

def test_classify_logical_clef_candidate_valid_treble_curve():
    cand = make_candidate("curve", 10.0, 10.0, 18.0, 35.0) # height 25.0, width 8.0
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "treble_clef_candidate"

def test_classify_logical_clef_candidate_weak_evidence_too_short():
    cand = make_candidate("text_span", 10.0, 10.0, 18.0, 25.0) # height 15.0 (ratio 3.0 < 3.5)
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "Evidence is ambiguous" in result["reason"]

def test_classify_logical_clef_candidate_weak_evidence_too_narrow():
    cand = make_candidate("text_span", 10.0, 10.0, 15.0, 35.0) # width 5.0 (ratio 1.0 < 1.5)
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"

def test_classify_logical_clef_candidate_invalid_width():
    cand = make_candidate("text_span", 10.0, 10.0, 10.0, 35.0) # width 0
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "Candidate width is invalid" in result["reason"]

def test_classify_logical_clef_candidate_chooses_largest_valid_candidate():
    small_cand = make_candidate("text_span", 10.0, 10.0, 15.0, 15.0) # height 5
    large_cand = make_candidate("curve", 10.0, 10.0, 18.0, 35.0) # height 25
    result = classify_logical_clef_candidate([small_cand, large_cand], 5.0, 20.0, 10.0)
    assert result["label"] == "treble_clef_candidate"
    assert result["features"]["candidate_kind"] == "curve"
