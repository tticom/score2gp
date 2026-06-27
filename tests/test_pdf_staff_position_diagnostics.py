import pytest
import fitz
from unittest.mock import patch
from score2gp.pdf_staff_position_diagnostics import extract_staff_position_diagnostics_dict

def test_quarter_note_public_fixture_maps_candidates():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) > 0
    quarter_notes = [c for c in candidates if c["candidate_type"] == "quarter_note"]
    assert len(quarter_notes) > 0
    
    for c in quarter_notes:
        assert c["position_status"] == "ambiguous_notehead_center"
        assert "unreliable_candidate_center" in c["failure_reasons"]
        assert c["center_y_source"] == "full_bbox_center"

def test_half_note_public_fixture_maps_candidates():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) > 0
    half_notes = [c for c in candidates if c["candidate_type"] == "half_note"]
    assert len(half_notes) > 0
    
    for c in half_notes:
        assert c["position_status"] == "ambiguous_notehead_center"
        assert "unreliable_candidate_center" in c["failure_reasons"]
        assert c["center_y_source"] == "full_bbox_center"

def test_whole_note_public_fixture_maps_candidates():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) > 0
    whole_notes = [c for c in candidates if c["candidate_type"] == "whole_note"]
    assert len(whole_notes) > 0
    
    for c in whole_notes:
        assert c["position_status"] in ("positioned", "ledger_positioned", "ambiguous_vertical_position")
        assert c["staff_step_index"] is not None
        assert c["center_y_source"] == "full_bbox_center"

def test_ledger_line_public_fixture_returns_ledger_positioned():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) > 0
    
    has_ledger = any(c["position_status"] == "ledger_positioned" for c in candidates)
    assert has_ledger, "Expected at least one ledger positioned candidate"
    for c in candidates:
        if c["position_status"] == "ledger_positioned":
            assert c["staff_step_index"] is not None
            assert c["staff_step_index"] < -1 or c["staff_step_index"] > 9

def test_empty_buckets_multi_staff_pass_through_safely():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    # An empty bucket yields 0 candidates from that bucket, so nothing crashes and candidates from other buckets are processed
    assert isinstance(diag["positioned_candidates"], list)

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_double_barline_empty_buckets_pass_through_safely(mock_geom, mock_bucket):
    # Simulated empty buckets from double-barline
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass", 
        "buckets": [
            {"system_index": 1, "staff_index": 1, "measure_region_index": 0, "ordered_candidates": []},
            {"system_index": 1, "staff_index": 1, "measure_region_index": 1, "ordered_candidates": []}
        ]
    }
    
    diag = extract_staff_position_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "pass"
    assert len(diag["positioned_candidates"]) == 0

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
def test_upstream_measure_bucket_diagnostics_failure(mock_bucket):
    mock_bucket.return_value = {"diagnostic_status": "fail"}
    
    diag = extract_staff_position_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "fail"
    assert "upstream_measure_bucket_failed" in diag["failure_reasons"]
    assert len(diag["positioned_candidates"]) == 0

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_unsupported_candidate_type_returns_structured_status(mock_geom, mock_bucket):
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass", 
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0, 
                "ordered_candidates": [{"candidate_type": "eighth_note", "candidate_bbox": [0,0,10,10], "center_x": 5}]
            }
        ]
    }
    
    diag = extract_staff_position_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["position_status"] == "unsupported_candidate_type"
    assert "unsupported_candidate_type" in candidates[0]["failure_reasons"]

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_missing_staff_geometry_returns_structured_status(mock_geom, mock_bucket):
    # Empty geometry but candidate exists
    mock_geom.return_value = {"status": "pass", "staves": []}
    mock_bucket.return_value = {
        "diagnostic_status": "pass", 
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0, 
                "ordered_candidates": [{"candidate_type": "whole_note", "candidate_bbox": [0,0,10,10], "center_x": 5}]
            }
        ]
    }
    
    diag = extract_staff_position_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["position_status"] == "missing_staff_geometry"
    assert "missing_staff_geometry" in candidates[0]["failure_reasons"]

def test_bbox_center_uncertainty_is_represented():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_staff_position_diagnostics_dict(doc[0], 1)
    
    candidates = diag["positioned_candidates"]
    assert len(candidates) > 0
    for c in candidates:
        if c["candidate_type"] in ("quarter_note", "half_note"):
            assert c["center_y_source"] == "full_bbox_center"
            assert c["position_status"] == "ambiguous_notehead_center"

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_malformed_evidence_handled_safely(mock_geom, mock_bucket):
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass",
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0,
                "ordered_candidates": [
                    {"candidate_type": "quarter_note", "candidate_bbox": [10], "center_x": 5}, # Short bbox
                    {"candidate_type": "quarter_note", "candidate_bbox": [0, "bad", 10, 20], "center_x": 15}, # Non-numeric bbox
                    "not_a_dict", # Non-dict candidate
                    {"candidate_type": "quarter_note"}, # Missing bbox and center_x
                    {"candidate_type": "quarter_note", "candidate_bbox": [10, 15, 20, 25], "center_x": 15} # Valid candidate
                ]
            }
        ]
    }

    diag = extract_staff_position_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "pass"
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 5

    assert candidates[0]["position_status"] == "malformed_candidate_data"
    assert "malformed_candidate_bbox" in candidates[0]["failure_reasons"]

    assert candidates[1]["position_status"] == "malformed_candidate_data"
    assert "non_numeric_candidate_bbox" in candidates[1]["failure_reasons"]

    assert candidates[2]["position_status"] == "malformed_candidate_data"
    assert "non_dict_candidate" in candidates[2]["failure_reasons"]

    assert candidates[3]["position_status"] == "malformed_candidate_data"
    assert "malformed_candidate_bbox" in candidates[3]["failure_reasons"]

    # Valid candidate is still returned normally
    assert candidates[4]["position_status"] in ("positioned", "ambiguous_notehead_center", "ledger_positioned")

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_partial_staff_geometry_rejected(mock_geom, mock_bucket):
    # Only 4 lines instead of 5
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass",
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0,
                "ordered_candidates": [{"candidate_type": "whole_note", "candidate_bbox": [0,0,10,10], "center_x": 5}]
            }
        ]
    }
    diag = extract_staff_position_diagnostics_dict(None, 1)
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["position_status"] == "ambiguous_vertical_position"
    assert "missing_staff_lines" in candidates[0]["failure_reasons"]

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_off_grid_center_is_ambiguous(mock_geom, mock_bucket):
    # staff spacing is 10, line[0] is 10. (spacing/2.0) = 5.
    # cy = 12.5 -> staff_step_index = 2.5 / 5 = 0.5. (Off-grid)
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass",
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0,
                "ordered_candidates": [{"candidate_type": "whole_note", "candidate_bbox": [10, 10, 20, 15], "center_x": 15}] # cy = 12.5
            }
        ]
    }
    diag = extract_staff_position_diagnostics_dict(None, 1)
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["position_status"] == "ambiguous_vertical_position"
    assert "off_grid_candidate_center" in candidates[0]["failure_reasons"]

@patch("score2gp.pdf_staff_position_diagnostics.extract_measure_bucket_diagnostics_dict")
@patch("score2gp.pdf_staff_position_diagnostics.extract_notation_diagnostics_dict")
def test_on_grid_center_is_positioned(mock_geom, mock_bucket):
    # cy = 10 -> staff_step_index = 0
    mock_geom.return_value = {"status": "pass", "staves": [{"staff": {"system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]}}]}
    mock_bucket.return_value = {
        "diagnostic_status": "pass",
        "buckets": [
            {
                "system_index": 1, "staff_index": 1, "measure_region_index": 0,
                "ordered_candidates": [{"candidate_type": "whole_note", "candidate_bbox": [5, 5, 15, 15], "center_x": 10}] # cy = 10
            }
        ]
    }
    diag = extract_staff_position_diagnostics_dict(None, 1)
    candidates = diag["positioned_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["position_status"] == "positioned"
