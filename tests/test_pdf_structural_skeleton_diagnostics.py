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
    assert len(staves) == 2
    
    for staff in staves:
        # Each staff should have 1 confirmed barline (the internal one)
        # the system leading barline is successfully ignored
        assert staff["confirmed_barline_count"] == 1
        assert staff["ambiguous_vertical_count"] == 0
        assert staff["barline_candidates"][0]["x0"] == 250.0

