import pytest
import sys
from pathlib import Path

# Need to ensure scripts/ is importable
repo_root = Path(__file__).resolve().parent.parent
scripts_dir = repo_root / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import run_coverage_analysis_task170

def test_determine_dominant_blocker_ambiguous_clef():
    aggregate = {
        "skipped_clef_ambiguous": 100,
        "skipped_clef_missing": 50,
        "skipped_missing_required_ledger_support": 10,
        "skipped_staff_association_malformed": 5,
        "skipped_staff_position_malformed": 2
    }
    
    dominant_blocker, recommendation = run_coverage_analysis_task170.determine_dominant_blocker(aggregate)
    
    assert dominant_blocker == "ambiguous clef evidence"
    assert "disambiguation" in recommendation.lower()

def test_determine_dominant_blocker_missing_clef():
    aggregate = {
        "skipped_clef_ambiguous": 10,
        "skipped_clef_missing": 100,
        "skipped_missing_required_ledger_support": 50,
        "skipped_staff_association_malformed": 5,
        "skipped_staff_position_malformed": 2
    }
    
    dominant_blocker, recommendation = run_coverage_analysis_task170.determine_dominant_blocker(aggregate)
    
    assert dominant_blocker == "missing clef evidence"
    assert "bridge logical clef" in recommendation.lower()

def test_determine_dominant_blocker_ledger_lines():
    aggregate = {
        "skipped_clef_ambiguous": 10,
        "skipped_clef_missing": 10,
        "skipped_missing_required_ledger_support": 100,
        "skipped_staff_association_malformed": 5,
        "skipped_staff_position_malformed": 2
    }
    
    dominant_blocker, recommendation = run_coverage_analysis_task170.determine_dominant_blocker(aggregate)
    
    assert dominant_blocker == "missing ledger support"
    assert "ledger line" in recommendation.lower()

def test_determine_dominant_blocker_malformed_staff_association():
    aggregate = {
        "skipped_clef_ambiguous": 10,
        "skipped_clef_missing": 10,
        "skipped_missing_required_ledger_support": 5,
        "skipped_staff_association_malformed": 100,
        "skipped_staff_position_malformed": 2
    }

    dominant_blocker, recommendation = run_coverage_analysis_task170.determine_dominant_blocker(aggregate)

    assert dominant_blocker == "malformed staff association"
    assert "staff association" in recommendation.lower()

def test_determine_dominant_blocker_malformed_staff_position():
    aggregate = {
        "skipped_clef_ambiguous": 10,
        "skipped_clef_missing": 10,
        "skipped_missing_required_ledger_support": 5,
        "skipped_staff_association_malformed": 2,
        "skipped_staff_position_malformed": 100
    }

    dominant_blocker, recommendation = run_coverage_analysis_task170.determine_dominant_blocker(aggregate)

    assert dominant_blocker == "malformed staff position"
    assert "staff position" in recommendation.lower()
