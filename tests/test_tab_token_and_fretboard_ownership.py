"""Unit tests for CRP-11: Biomechanical Fretboard Position Optimizer & TAB Token Ownership."""

from pathlib import Path
import pytest
from score2gp.notation_omr.position_optimizer import (
    BiomechanicalPositionOptimizer,
    FretTokenOwnership,
    STANDARD_TUNING,
    parse_pitch_to_midi,
)
from score2gp.notation_omr.pipeline import run_recognition_on_file


def test_pitch_parsing_to_midi():
    assert parse_pitch_to_midi("C4") == 60
    assert parse_pitch_to_midi("E4") == 64
    assert parse_pitch_to_midi("E2") == 40
    assert parse_pitch_to_midi("G#3") == 56
    assert parse_pitch_to_midi("Bb2") == 46
    assert parse_pitch_to_midi(60) == 60
    assert parse_pitch_to_midi(None) is None


def test_observed_vs_inferred_fret_token_ownership():
    optimizer = BiomechanicalPositionOptimizer()

    events = [
        # Explicit observed visual TAB candidate
        {
            "candidate_id": "cand_tab_01",
            "string_index": 3,
            "parsed_fret": 2,
            "resolved_pitch_midi": 57,
        },
        # Standard notation pitch without TAB info -> inferred
        {
            "candidate_id": "cand_not_02",
            "clef_resolved_staff_pitch": "E4",
        },
    ]

    ownership = optimizer.optimize_sequence(events)
    assert len(ownership) == 2

    # First event: observed
    assert ownership[0].token_id == "cand_tab_01"
    assert ownership[0].string_index == 3
    assert ownership[0].fret_number == 2
    assert ownership[0].modality == "observed_tab"
    assert ownership[0].is_observed is True
    assert ownership[0].is_inferred is False

    # Second event: inferred
    assert ownership[1].token_id == "cand_not_02"
    assert ownership[1].pitch == 64
    assert ownership[1].modality == "inferred_position"
    assert ownership[1].is_observed is False
    assert ownership[1].is_inferred is True
    assert ownership[1].string_index == 1
    assert ownership[1].fret_number == 0  # E4 on String 1 (High E) is open fret 0!


def test_biomechanical_position_optimization_sequence():
    optimizer = BiomechanicalPositionOptimizer()

    # Scale: C4(60), D4(62), E4(64), F4(65), G4(67)
    events = [
        {"candidate_id": "n1", "clef_resolved_staff_pitch": "C4"},
        {"candidate_id": "n2", "clef_resolved_staff_pitch": "D4"},
        {"candidate_id": "n3", "clef_resolved_staff_pitch": "E4"},
        {"candidate_id": "n4", "clef_resolved_staff_pitch": "F4"},
        {"candidate_id": "n5", "clef_resolved_staff_pitch": "G4"},
    ]

    ownership = optimizer.optimize_sequence(events)
    assert len(ownership) == 5

    for o in ownership:
        assert 1 <= o.string_index <= 6
        assert 0 <= o.fret_number <= 24
        assert o.pitch == STANDARD_TUNING[o.string_index - 1] + o.fret_number


def test_no_reference_gp_isolation():
    """Verifies position optimization operates strictly without reference .gp files."""
    optimizer = BiomechanicalPositionOptimizer()
    events = [
        {"candidate_id": "iso_1", "pitch": 60},
        {"candidate_id": "iso_2", "pitch": 62},
    ]

    res = optimizer.optimize_sequence(events)
    assert len(res) == 2
    assert all(isinstance(r, FretTokenOwnership) for r in res)


def test_private_fixture_lesson5_tab_token_preservation():
    lesson5 = (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else Path(__file__).resolve().parent.parent / "fixtures" / "private") / "Lesson-5.pdf"

    res = run_recognition_on_file(lesson5, assume_treble_clef=True)
    assert res is not None
    assert "fretboard_position_ownership" in res
    assert isinstance(res["fretboard_position_ownership"], list)
