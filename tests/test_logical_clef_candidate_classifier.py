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

def test_classify_logical_clef_candidate_weak_evidence_too_narrow():
    cand = make_candidate("text_span", 10.0, 10.0, 15.0, 35.0) # width 5.0 (ratio 1.0 < 1.5)
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"

def test_classify_logical_clef_candidate_invalid_width():
    cand = make_candidate("text_span", 10.0, 10.0, 10.0, 35.0) # width 0
    result = classify_logical_clef_candidate([cand], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"

def test_multiple_curve_segments_grouped_forms_treble():
    # Individual curves are too short/narrow
    # Spacing=5.0, threshold=17.5 height, 7.5 width
    c1 = make_candidate("curve", 10.0, 10.0, 18.0, 20.0) # width 8.0, height 10.0 (too short)
    c2 = make_candidate("curve", 12.0, 20.0, 16.0, 35.0) # width 4.0, height 15.0 (too short)
    # The two are adjacent (y1 of c1 == y0 of c2), their distance is 0.0 <= staff_spacing (5.0)
    # Combined: x0=10.0, y0=10.0, x1=18.0, y1=35.0 -> width 8.0, height 25.0 (valid)
    result = classify_logical_clef_candidate([c1, c2], 5.0, 20.0, 10.0)
    assert result["label"] == "treble_clef_candidate"
    assert result["features"]["candidate_kind"] == "curve_group"
    assert result["features"]["height_to_spacing"] == 5.0

def test_clearly_separate_competing_candidate_groups_returning_unknown():
    # Two valid treble clefs that are far apart (distance > 5.0)
    c1 = make_candidate("curve", 10.0, 10.0, 18.0, 35.0) # valid, group 1
    c2 = make_candidate("curve", 30.0, 10.0, 38.0, 35.0) # valid, group 2, dx = 12.0 > 5.0
    result = classify_logical_clef_candidate([c1, c2], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "Ambiguous" in result["reason"]

def test_multiple_strong_incompatible_candidates_returning_unknown():
    # A valid text_span and a valid curve group. Text spans do not cluster.
    c1 = make_candidate("text_span", 10.0, 10.0, 18.0, 35.0) # valid
    c2 = make_candidate("curve", 10.0, 10.0, 18.0, 35.0) # valid
    result = classify_logical_clef_candidate([c1, c2], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
    assert "Ambiguous" in result["reason"]

def test_text_spans_do_not_cluster():
    # Two text_spans that would form a valid clef if combined, but shouldn't be
    c1 = make_candidate("text_span", 10.0, 10.0, 18.0, 20.0)
    c2 = make_candidate("text_span", 12.0, 20.0, 16.0, 35.0)
    result = classify_logical_clef_candidate([c1, c2], 5.0, 20.0, 10.0)
    assert result["label"] == "unknown"
