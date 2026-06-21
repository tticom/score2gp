import json
import pytest
from pathlib import Path
from score2gp.whole_note_recogniser import run_recognition_on_file

FIXTURES_DIR = Path("fixtures/public/generated_simple/simple")
TARGET_PDF = FIXTURES_DIR / "QuarterRestThenNotes.pdf"
CONTROL_PDFS = [
    FIXTURES_DIR / "4QuarterNotes.pdf",
    FIXTURES_DIR / "2EighthNotes.pdf",
    FIXTURES_DIR / "4SixteenthNotes.pdf"
]

def test_quarter_rest_candidate_extraction_target():
    result = run_recognition_on_file(
        TARGET_PDF,
        assume_treble_clef=True,
        include_ledger_line_candidates=True,
        include_flag_beam_candidates=True
    )
    
    outcomes = result.get("read_only_recognition_outcomes", [])
    quarter_rests = [c for c in outcomes if c.get("symbol_type") == "quarter_rest_candidate"]
    
    assert len(quarter_rests) == 1, f"Expected exactly 1 quarter rest, found {len(quarter_rests)}"
    
    qr = quarter_rests[0]
    assert qr.get("duration") == "quarter"
    assert "bbox" in qr
    assert "primitive_source_ids" in qr
    assert "evidence" in qr

@pytest.mark.parametrize("control_pdf", CONTROL_PDFS)
def test_quarter_rest_candidate_extraction_controls(control_pdf):
    result = run_recognition_on_file(
        control_pdf,
        assume_treble_clef=True,
        include_ledger_line_candidates=True,
        include_flag_beam_candidates=True
    )
    
    outcomes = result.get("read_only_recognition_outcomes", [])
    quarter_rests = [c for c in outcomes if c.get("symbol_type") == "quarter_rest_candidate"]
    
    assert len(quarter_rests) == 0, f"Expected 0 quarter rests in {control_pdf.name}, found {len(quarter_rests)}"
