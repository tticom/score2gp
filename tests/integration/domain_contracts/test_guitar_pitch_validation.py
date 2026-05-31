import pytest
from pathlib import Path
from score2gp.ir import validate_score_ir_file

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "public" / "invalid"

def test_guitar_pitch_bounds_validation():
    # 1. Test standard guitar lower pitch limit E2 (MIDI 40)
    # Pitch 39 must be rejected as impossible sounding pitch
    low_path = FIXTURES_DIR / "impossible_guitar_pitch_low.ir.json"
    assert low_path.exists()
    
    score, errors = validate_score_ir_file(low_path)
    assert score is None
    assert len(errors) > 0, "Lower pitch boundary violation went uncaught"
    assert any("physically playable pitch range of a standard guitar" in err for err in errors)

    # 2. Test standard guitar upper pitch limit E6 (MIDI 88)
    # Pitch 89 must be rejected as impossible sounding pitch
    high_path = FIXTURES_DIR / "impossible_guitar_pitch_high.ir.json"
    assert high_path.exists()
    
    score_high, errors_high = validate_score_ir_file(high_path)
    assert score_high is None
    assert len(errors_high) > 0, "Upper pitch boundary violation went uncaught"
    assert any("physically playable pitch range of a standard guitar" in err for err in errors_high)

def test_valid_guitar_pitch_agreement():
    # Load a synthetic valid ScoreIR fixture to verify standard guitar pitches pass validation cleanly
    valid_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "public" / "tiny_score.ir.json"
    assert valid_path.exists()
    
    score, errors = validate_score_ir_file(valid_path)
    assert score is not None
    assert len(errors) == 0, f"Valid guitar pitch/tuning structure produced unexpected errors: {errors}"
