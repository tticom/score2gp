import zipfile
import pytest
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch

from score2gp.whole_note_recogniser import run_recognition_on_file
from score2gp.notation_bridge import build_ir_from_notation_outcomes
from score2gp.gp_package import write_gp, validate_gp

def test_quarter_rest_e2e_acceptance(tmp_path):
    pdf_path = Path("fixtures/public/generated_simple/simple/QuarterRestThenNotes.pdf")
    
    # 1. Extraction boundary
    res = run_recognition_on_file(
        pdf_path,
        assume_treble_clef=True,
        include_ledger_line_candidates=True,
        include_flag_beam_candidates=True,
        include_left_margin_candidates=True,
        include_x_aligned_clusters=True
    )
    outcomes = res.get("read_only_recognition_outcomes", [])
    
    # 2. ScoreIR Sequence boundary
    score = build_ir_from_notation_outcomes(outcomes)
    events = score.bars[0].events
    
    assert len(events) == 3
    ev0 = events[0]
    assert ev0.is_rest is True
    assert ev0.timing.notated_duration.value == "quarter"
    assert ev0.notes == []
    
    # 3. Export boundary
    out = tmp_path / "test_e2e.gp"
    
    # Patch sys.modules to bypass pytest-only legacy XML path
    with patch.dict("sys.modules"):
        import sys
        if "pytest" in sys.modules:
            del sys.modules["pytest"]
        original_argv = sys.argv
        sys.argv = [arg for arg in sys.argv if "pytest" not in arg]
        try:
            warnings = write_gp(score, out)
        finally:
            sys.argv = original_argv
            
    assert warnings == []
    assert zipfile.is_zipfile(out)
    
    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        beats = root.findall(".//Beat")
        assert len(beats) == 3
        
        # The first beat is the rest
        beat = beats[0]
        assert beat.find("Notes") is None
        assert beat.find("Chord") is None
        
        rhythm_ref = beat.find("Rhythm").get("ref")
        assert rhythm_ref is not None
        
        rhythm_def = root.find(f".//Rhythm[@id='{rhythm_ref}']")
        assert rhythm_def is not None
        assert rhythm_def.find("NoteValue").text == "Quarter"
        
        notes_db = root.find("Notes")
        if notes_db is not None:
            # 2 notes from the remaining events
            assert len(list(notes_db)) == 2

    validation = validate_gp(out)
    assert validation["is_zip"] is True
    assert validation["xml_well_formed"] is True
    assert validation["errors"] == []
