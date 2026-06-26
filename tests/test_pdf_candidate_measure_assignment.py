import pytest
import fitz
from unittest.mock import patch
from score2gp.pdf_staff_notation_diagnostics import extract_candidate_measure_assignment_diagnostics_dict

def test_candidate_assignment_quarter_note_exact_bounds():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assert diag["diagnostic_status"] == "pass"
    assignments = diag["assignments"]
    assert len(assignments) == 2

    for a in assignments:
        assert a["candidate_type"] == "quarter_note"
        assert a["assignment_status"] == "assigned"
        assert a["measure_region_index"] == 0
        assert a["page_index"] == 1
        assert a["system_index"] == 1
        assert a["staff_index"] == 1

def test_candidate_assignment_ledger_lines():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assert diag["diagnostic_status"] == "pass"
    assignments = diag["assignments"]
    assert len(assignments) == 2 # there are 2 notes

    for a in assignments:
        assert a["assignment_status"] == "assigned"
        assert a["measure_region_index"] == 0

def test_candidate_assignment_mock_injection_multi_staff():
    """
    In the multi-staff fixture there are no real notes.
    We mock extract_notation_diagnostics_dict to inject a fake note candidate.
    """
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject a fake quarter note on staff 2, region 2 (x > 250)
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [300.0, 150.0, 310.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": 1,
                "system_index": 1,
                "staff_index": 2
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assert diag["diagnostic_status"] == "pass"
    assignments = diag["assignments"]
    assert len(assignments) == 1

    a = assignments[0]
    assert a["assignment_status"] == "assigned"
    # region 0 is 50-250, region 1 is 250-545.28
    assert a["measure_region_index"] == 1
    assert a["staff_index"] == 2

def test_candidate_assignment_failure_status_out_of_bounds():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject note outside measure region (< 50)
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [10.0, 150.0, 20.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assignments = diag["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["assignment_status"] == "out_of_bounds"

def test_candidate_assignment_failure_status_boundary_ambiguous():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject note exactly on boundary 250.0
        # For boundary ambiguous, we use center_x. So center_x must be 250.0
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [245.0, 150.0, 255.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assignments = diag["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["assignment_status"] == "boundary_ambiguous"

def test_candidate_assignment_failure_status_identity_none():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject note with page_index=None
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [100.0, 150.0, 110.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": None,
                "system_index": 1,
                "staff_index": 1
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assignments = diag["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["assignment_status"] == "identity_none"
    assert assignments[0]["measure_region_index"] is None

def test_candidate_assignment_failure_status_staff_unmatched():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject note with impossible staff_index (e.g., 999)
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [100.0, 150.0, 110.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": 1,
                "system_index": 1,
                "staff_index": 999
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assignments = diag["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["assignment_status"] == "staff_unmatched"
    assert assignments[0]["measure_region_index"] is None

def test_candidate_assignment_double_barline():
    doc = fitz.open("tests/fixtures/pdf/generated_paired_notation_tab_system_double_barline.pdf")

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict as original_extract

    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject a note that falls in the first measure region.
        # Regions typically start around x=50.
        orig_dict["quarter_note_candidates"] = [
            {
                "bbox": [100.0, 150.0, 110.0, 160.0],
                "width": 10.0,
                "height": 10.0,
                "aspect_ratio": 1.0,
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1
            }
        ]
        return orig_dict

    with patch("score2gp.pdf_staff_notation_diagnostics.extract_notation_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)

    assert diag["diagnostic_status"] == "pass"
    assignments = diag["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["assignment_status"] == "assigned"
    assert assignments[0]["measure_region_index"] is not None

def test_candidate_assignment_page_level_grid_failure():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    
    from score2gp.pdf_staff_notation_diagnostics import extract_measure_grid_diagnostics_dict as original_extract
    
    def mock_extract(page, page_index):
        orig_dict = original_extract(page, page_index)
        # Inject page-level failure
        for p in orig_dict.get("pages", []):
            if p.get("page_index") == page_index:
                p["status"] = "fail"
        return orig_dict
        
    with patch("score2gp.pdf_staff_notation_diagnostics.extract_measure_grid_diagnostics_dict", side_effect=mock_extract):
        diag = extract_candidate_measure_assignment_diagnostics_dict(doc[0], 1)
        
    assert diag["diagnostic_status"] == "fail"
    assert "measure_grid_diagnostics_failed" in diag["failure_reasons"]
