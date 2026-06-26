import pytest
import fitz
from unittest.mock import patch
from score2gp.pdf_staff_notation_diagnostics import extract_measure_bucket_diagnostics_dict

def test_single_staff_quarter_note_fixture():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_measure_bucket_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    buckets = diag["buckets"]
    
    ordered_buckets = [b for b in buckets if b["bucket_status"] == "ordered"]
    assert len(ordered_buckets) > 0
    bucket = ordered_buckets[0]
    
    assert bucket["page_index"] == 1
    assert bucket["system_index"] == 1
    assert bucket["staff_index"] == 1
    assert bucket["candidate_count"] > 0
    assert bucket["measure_region_index"] is not None

def test_ledger_line_fixture():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    diag = extract_measure_bucket_diagnostics_dict(doc[0], 1)
    
    assert diag["diagnostic_status"] == "pass"
    buckets = diag["buckets"]
    
    ordered_buckets = [b for b in buckets if b["bucket_status"] == "ordered"]
    assert len(ordered_buckets) > 0
    bucket = ordered_buckets[0]
    
    assert bucket["staff_index"] == 1
    assert bucket["candidate_count"] > 0

@patch("score2gp.pdf_staff_notation_diagnostics.extract_candidate_measure_assignment_diagnostics_dict")
@patch("score2gp.pdf_staff_notation_diagnostics.extract_measure_grid_diagnostics_dict")
def test_multi_staff_mock_injection(mock_grid, mock_assignment):
    mock_grid.return_value = {
        "diagnostic_status": "pass",
        "pages": [{
            "page_index": 1,
            "systems": [{
                "system_index": 1,
                "staves": [
                    {"staff_index": 1, "measure_regions": [{"region_index": 0}]},
                    {"staff_index": 2, "measure_regions": [{"region_index": 0}]}
                ]
            }]
        }]
    }
    mock_assignment.return_value = {
        "diagnostic_status": "pass",
        "assignments": [
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 1, "measure_region_index": 0, "center_x": 10.0, "candidate_type": "quarter_note", "candidate_bbox": [0,0,0,0]},
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 2, "measure_region_index": 0, "center_x": 10.0, "candidate_type": "quarter_note", "candidate_bbox": [0,0,0,0]}
        ]
    }
    
    diag = extract_measure_bucket_diagnostics_dict(None, 1)
    buckets = diag["buckets"]
    assert len(buckets) == 2
    
    b1 = [b for b in buckets if b["staff_index"] == 1][0]
    b2 = [b for b in buckets if b["staff_index"] == 2][0]
    
    assert b1["candidate_count"] == 1
    assert b2["candidate_count"] == 1

@patch("score2gp.pdf_staff_notation_diagnostics.extract_candidate_measure_assignment_diagnostics_dict")
@patch("score2gp.pdf_staff_notation_diagnostics.extract_measure_grid_diagnostics_dict")
def test_center_x_ambiguity_mock_injection(mock_grid, mock_assignment):
    mock_grid.return_value = {
        "diagnostic_status": "pass",
        "pages": [{
            "page_index": 1,
            "systems": [{
                "system_index": 1,
                "staves": [{"staff_index": 1, "measure_regions": [{"region_index": 0}]}]
            }]
        }]
    }
    mock_assignment.return_value = {
        "diagnostic_status": "pass",
        "assignments": [
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 1, "measure_region_index": 0, "center_x": 10.0, "candidate_type": "quarter_note", "candidate_bbox": [0,0,0,0]},
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 1, "measure_region_index": 0, "center_x": 10.4, "candidate_type": "half_note", "candidate_bbox": [0,0,0,0]}
        ]
    }
    
    diag = extract_measure_bucket_diagnostics_dict(None, 1)
    buckets = diag["buckets"]
    assert len(buckets) == 1
    assert buckets[0]["bucket_status"] == "center_x_ambiguous"

@patch("score2gp.pdf_staff_notation_diagnostics.extract_candidate_measure_assignment_diagnostics_dict")
@patch("score2gp.pdf_staff_notation_diagnostics.extract_measure_grid_diagnostics_dict")
def test_chord_like_overlapping_ambiguity_mock_injection(mock_grid, mock_assignment):
    mock_grid.return_value = {
        "diagnostic_status": "pass",
        "pages": [{
            "page_index": 1,
            "systems": [{
                "system_index": 1,
                "staves": [{"staff_index": 1, "measure_regions": [{"region_index": 0}]}]
            }]
        }]
    }
    mock_assignment.return_value = {
        "diagnostic_status": "pass",
        "assignments": [
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 1, "measure_region_index": 0, "center_x": 10.0, "candidate_type": "quarter_note", "candidate_bbox": [0,0,0,0]},
            {"assignment_status": "assigned", "page_index": 1, "system_index": 1, "staff_index": 1, "measure_region_index": 0, "center_x": 10.0, "candidate_type": "quarter_note", "candidate_bbox": [0,10,0,10]}
        ]
    }
    
    diag = extract_measure_bucket_diagnostics_dict(None, 1)
    buckets = diag["buckets"]
    assert len(buckets) == 1
    assert buckets[0]["bucket_status"] == "center_x_ambiguous"

@patch("score2gp.pdf_staff_notation_diagnostics.extract_candidate_measure_assignment_diagnostics_dict")
def test_upstream_failure_mock(mock_assignment):
    mock_assignment.return_value = {
        "diagnostic_status": "fail",
        "failure_reasons": ["some_upstream_error"]
    }
    
    diag = extract_measure_bucket_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "fail"
    assert "some_upstream_error" in diag["failure_reasons"]
    assert diag["buckets"] == []

@patch("score2gp.pdf_staff_notation_diagnostics.extract_candidate_measure_assignment_diagnostics_dict")
@patch("score2gp.pdf_staff_notation_diagnostics.extract_measure_grid_diagnostics_dict")
def test_empty_bucket_behaviour_mock(mock_grid, mock_assignment):
    mock_grid.return_value = {
        "diagnostic_status": "pass",
        "pages": [{
            "page_index": 1,
            "systems": [{
                "system_index": 1,
                "staves": [{"staff_index": 1, "measure_regions": [{"region_index": 0}]}]
            }]
        }]
    }
    mock_assignment.return_value = {
        "diagnostic_status": "pass",
        "assignments": []
    }
    
    diag = extract_measure_bucket_diagnostics_dict(None, 1)
    assert diag["diagnostic_status"] == "pass"
    buckets = diag["buckets"]
    assert len(buckets) == 1
    assert buckets[0]["bucket_status"] == "empty"
    assert buckets[0]["candidate_count"] == 0
    assert buckets[0]["ordered_candidates"] == []
