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

from score2gp.quarter_rest_recogniser import extract_quarter_rest_candidates

def test_quarter_rest_candidate_staff_partitioning():
    # Two staves. On each staff, there are 30 orphan flag fragments forming a valid rest candidate.
    # The x-coordinates overlap. If they weren't partitioned, they would form a cluster with width 30 and height 50,
    # which might fail the height threshold or misattribute fragments.
    outcomes = []
    
    # Staff 1 fragments (valid width 15, height 30)
    for i in range(30):
        outcomes.append({
            "symbol_type": "flag_candidate",
            "bbox": [10.0 + (i * 0.5), 10.0, 10.0 + (i * 0.5) + 1.0, 40.0],
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "primitive_source_ids": [f"s1_f{i}"]
        })
        
    # Staff 2 fragments (valid width 15, height 30), overlapping x with Staff 1
    for i in range(30):
        outcomes.append({
            "symbol_type": "flag_candidate",
            "bbox": [10.0 + (i * 0.5), 100.0, 10.0 + (i * 0.5) + 1.0, 130.0],
            "page_index": 0,
            "system_index": 0,
            "staff_index": 1,
            "primitive_source_ids": [f"s2_f{i}"]
        })

    results = extract_quarter_rest_candidates(outcomes)
    
    # We should get exactly 2 separate rest candidates
    assert len(results) == 2
    
    # Check that they preserved the staff indices
    staff_indices = sorted([r.get("staff_index") for r in results])
    assert staff_indices == [0, 1]

def test_quarter_rest_candidate_staff_index_preservation():
    outcomes = []
    # 30 fragments that will form a cluster
    for i in range(30):
        outcomes.append({
            "symbol_type": "flag_candidate",
            "bbox": [50.0 + (i * 0.5), 50.0, 50.0 + (i * 0.5) + 1.0, 80.0],
            "page_index": 2,
            "system_index": 1,
            "staff_index": 3,
            "system_staff_index": 4,
            "primitive_source_ids": [f"f{i}"]
        })
        
    results = extract_quarter_rest_candidates(outcomes)
    assert len(results) == 1
    
    qr = results[0]
    assert qr.get("page_index") == 2
    assert qr.get("system_index") == 1
    assert qr.get("staff_index") == 3
    assert qr.get("system_staff_index") == 4
