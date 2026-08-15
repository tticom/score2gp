"""Unit tests for CRP-11: Biomechanical Fretboard Position Optimizer & TAB Token Ownership."""

from pathlib import Path
import pytest
import pytest
from score2gp.notation_omr.position_optimizer import (
    BiomechanicalPositionOptimizer,
    FretTokenOwnership,
    STANDARD_TUNING,
    parse_pitch_to_midi,
)
from score2gp.notation_omr.pipeline import run_recognition_on_file





def test_private_fixture_lesson5_tab_token_preservation():
    lesson5 = Path("fixtures/private/Lesson-5.pdf")
    if not lesson5.exists():
        import pytest; pytest.skip("Missing fixture")

    res = run_recognition_on_file(lesson5, assume_treble_clef=True)
    assert res is not None
    assert "fretboard_position_ownership" in res
    ownership_list = res["fretboard_position_ownership"]
    assert isinstance(ownership_list, list)

    # Re-test the core FretTokenOwnership properties on real-world evidence
    if ownership_list:
        for ownership in ownership_list:
            # We expect these to be either FretTokenOwnership objects or dicts depending on pipeline stage
            if isinstance(ownership, dict):
                assert ownership.get("modality") == "observed_tab"
                assert 1 <= ownership.get("string_index", 0) <= 6
                assert 0 <= ownership.get("fret_number", -1) <= 24
            else:
                assert ownership.modality == "observed_tab"
                assert ownership.is_observed is True
                assert ownership.is_inferred is False
                assert 1 <= ownership.string_index <= 6
                assert 0 <= ownership.fret_number <= 24
