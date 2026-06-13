from pathlib import Path
from score2gp.whole_note_recogniser import map_whole_note_candidates_to_read_only_outcomes

def test_whole_note_read_only_recognition_outcome():
    # We want to test that given some candidate evidence (like the ones generated from generated_standard_staff_whole_note.pdf)
    # the recognizer maps them correctly.
    # To keep the test fast and avoid running the whole PDF pipeline if possible, or just mock the locations.
    # But the prompt says "proving the safe public whole-note fixture maps to the expected recognition outcome for its validated candidates."
    # So we should probably run the diagnostics on the fixture.
    
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from raster_diagnostics_gate_report import run_diagnostics_on_file
    
    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_whole_note.pdf"
    res = run_diagnostics_on_file(pdf_path)
    
    assert res is not None
    locations = res.get("whole_note_candidate_locations", [])
    
    assert len(locations) == 2
    
    outcomes = map_whole_note_candidates_to_read_only_outcomes(locations)
    
    assert len(outcomes) == 2
    assert outcomes[0]["symbol_type"] == "whole_note_candidate"
    assert outcomes[0]["candidate_id"] == "whole_note_candidate_001"
    assert "bbox" in outcomes[0]
    assert outcomes[0]["page_index"] == 1
    assert outcomes[0]["source"] == "diagnostic_candidate_evidence"

    assert outcomes[1]["symbol_type"] == "whole_note_candidate"
    assert outcomes[1]["candidate_id"] == "whole_note_candidate_002"
    assert "bbox" in outcomes[1]
    assert outcomes[1]["page_index"] == 1
    assert outcomes[1]["source"] == "diagnostic_candidate_evidence"
