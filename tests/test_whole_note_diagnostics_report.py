import pytest
from pathlib import Path

from scripts.whole_note_diagnostics_report import run_diagnostics_on_file

def test_whole_note_candidate_detection_positive():
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    # If the test suite is run from a different directory, handle the path safely
    assert fixture_path.exists(), f"Fixture {fixture_path} missing"

    res = run_diagnostics_on_file(fixture_path)
    assert res is not None
    assert res["status"] == "success"
    assert res["total_whole_note_candidates"] == 2

    page1 = res["pages"][0]
    assert page1["whole_note_candidate_count"] == 2

    candidates = page1["candidates"]
    assert len(candidates) == 2

    cand1 = candidates[0]
    assert cand1["kind"] == "whole_note_candidate"
    assert 1.2 <= cand1["aspect_ratio"] <= 2.0
    # ensure it outputs bounding boxes
    assert "bbox" in cand1
    assert "width" in cand1
    assert "height" in cand1

def test_whole_note_candidate_detection_negative():
    # This fixture has rectangles for notes but no whole notes
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf")
    assert fixture_path.exists(), f"Fixture {fixture_path} missing"

    res = run_diagnostics_on_file(fixture_path)
    assert res is not None
    assert res["status"] == "success"
    # Should find 0 whole note candidates
    assert res["total_whole_note_candidates"] == 0

def test_whole_note_candidate_detection_half_note():
    # This fixture has hollow notes with stems (half notes)
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")
    assert fixture_path.exists(), f"Fixture {fixture_path} missing"

    res = run_diagnostics_on_file(fixture_path)
    assert res is not None
    assert res["status"] == "success"
    # Should find 0 whole note candidates because of stem exclusion
    assert res["total_whole_note_candidates"] == 0
