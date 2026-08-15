import pytest
import fitz
from score2gp.pdf_staff_notation_diagnostics import extract_structural_skeleton_diagnostics_dict

def test_quarter_note_structural_skeleton():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_structural_skeleton_diagnostics_dict(doc[0], 1)
    
    assert diag["pages"][0]["diagnostic_status"] == "pass"
    systems = diag["pages"][0]["systems"]
    assert len(systems) == 1
    
    staves = systems[0]["staves"]
    assert len(staves) == 1
    
    staff = staves[0]
    # The quarter note fixture has 1 trailing barline and 2 quarter note stems
    assert staff["confirmed_barline_count"] == 1
    assert staff["ambiguous_vertical_count"] == 2
    
    barline = next(b for b in staff["barline_candidates"] if b["classification"] == "confirmed_barline")
    assert barline["x0"] == 550.0

def test_multi_staff_structural_skeleton():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")
    diag = extract_structural_skeleton_diagnostics_dict(doc[0], 1)
    
    assert diag["pages"][0]["diagnostic_status"] == "pass"
    systems = diag["pages"][0]["systems"]
    assert len(systems) == 1
    
    staves = systems[0]["staves"]
    # The multi-staff fixture has 2 staves
    for staff in staves:
        # Each staff should have 1 confirmed barline (the internal one)
        # the system leading barline is successfully ignored
        assert staff["confirmed_barline_count"] == 1
        assert staff["ambiguous_vertical_count"] == 0
        assert staff["barline_candidates"][0]["x0"] == 250.0

def test_ledger_line_stems_not_counted_as_barlines():
    # The ledger lines fixture has tall note stems that shouldn't be counted as barlines
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    diag = extract_structural_skeleton_diagnostics_dict(doc[0], 1)

    assert diag["pages"][0]["diagnostic_status"] == "pass"
    staff = diag["pages"][0]["systems"][0]["staves"][0]

    # 1 confirmed barline, 2 ambiguous stems (including the ledger line note)
    assert staff["confirmed_barline_count"] == 1
    assert staff["ambiguous_vertical_count"] == 2

    ambiguous = next(b for b in staff["barline_candidates"] if "does not fully span" in str(b.get("ambiguity_reason", "")))
    # Verify it was flagged specifically because it didn't span the bounds
    assert "does not fully span the staff boundaries" in ambiguous["ambiguity_reason"]

def test_failure_handling_is_private_safe():
    # Pass a None instead of a page to trigger an exception
    diag = extract_structural_skeleton_diagnostics_dict(None, 1)

    assert diag["diagnostic_status"] == "fail"
    assert len(diag["failure_reasons"]) == 1
    # Ensure it's a fixed string, not a raw Exception string
    assert diag["failure_reasons"][0] == "structural_skeleton_detection_failed"
    assert "NoneType" not in diag["failure_reasons"][0]
