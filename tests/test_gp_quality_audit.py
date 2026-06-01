import sys
from pathlib import Path

# Add scripts directory to sys.path to allow importing from private_gp_quality_audit
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from private_gp_quality_audit import classify_gp_quality


def test_classify_gp_quality_basic_pass() -> None:
    # Test 1: Non-empty ScoreIR/GPIF is classified as Basic Pass when no technique candidates exist
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 50,
        "scoreir_note_count": 50,
        "playable_fret_candidate_count": 50,
        "matched_fret_candidate_count": 50,
        "gpif_measure_count": 10,
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 0,
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_quality_pass_basic"


def test_classify_gp_quality_empty_or_near_empty() -> None:
    # Test 2: Empty GPIF is classified as Empty/Near-Empty
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 0,
        "scoreir_note_count": 0,
        "playable_fret_candidate_count": 50,
        "matched_fret_candidate_count": 0,
        "gpif_measure_count": 10,
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 0,
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_empty_or_near_empty"


def test_classify_gp_quality_fret_matching_suspect() -> None:
    # Test 3: Low matched candidate count is classified as fret matching suspect
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 50,
        "scoreir_note_count": 50,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 20,  # 20% match rate (< 40%)
        "gpif_measure_count": 10,
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 0,
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_fret_matching_suspect"


def test_classify_gp_quality_technique_loss_expected() -> None:
    # Test 4: Technique markers without serialization are classified separately
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 50,
        "scoreir_note_count": 50,
        "playable_fret_candidate_count": 50,
        "matched_fret_candidate_count": 50,
        "gpif_measure_count": 10,
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 5,  # Technique text candidates exist
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_technique_loss_expected"


def test_classify_gp_quality_serialized_coverage_low() -> None:
    # Test 5: High ScoreIR notes but low GPIF notes => gp_output_note_coverage_low
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 15,  # Much lower than ScoreIR notes (15 < 50 * 0.70)
        "scoreir_note_count": 50,
        "playable_fret_candidate_count": 50,
        "matched_fret_candidate_count": 50,
        "gpif_measure_count": 10,
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 0,
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_note_coverage_low"


def test_classify_gp_quality_measure_mismatch() -> None:
    # Test 6: GPIF/ScoreIR measure mismatch => bar alignment suspect
    metrics = {
        "whether_gp_package_produced": True,
        "gpif_note_count": 50,
        "scoreir_note_count": 50,
        "playable_fret_candidate_count": 50,
        "matched_fret_candidate_count": 50,
        "gpif_measure_count": 12,  # 12 != 10
        "scoreir_bar_count": 10,
        "non_playable_technique_text_candidate_count": 0,
        "warning_code_counts": {},
    }
    assert classify_gp_quality(metrics) == "gp_output_bar_alignment_suspect"
