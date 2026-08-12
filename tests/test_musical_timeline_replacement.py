from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.timeline import (
    TopologicallyLockedBarTimeline,
    build_staff_timeline_preview,
    resolve_tuplet_duration,
)
from score2gp.notation_omr.pipeline import run_recognition_on_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_bar_timeline_dataclass_capacity_invariants() -> None:
    """Verify TopologicallyLockedBarTimeline enforces metre and bar capacity invariants."""
    bar = TopologicallyLockedBarTimeline(
        measure_index=1,
        capacity_ticks=3840,
        voice_1_final_tick=3840,
        voice_2_final_tick=0,
        valid=True,
        events=[
            {"symbol_type": "quarter_note", "voice": 1, "start_tick": 0, "duration_ticks": 960},
            {"symbol_type": "quarter_note", "voice": 1, "start_tick": 960, "duration_ticks": 960},
            {"symbol_type": "quarter_note", "voice": 1, "start_tick": 1920, "duration_ticks": 960},
            {"symbol_type": "quarter_note", "voice": 1, "start_tick": 2880, "duration_ticks": 960},
        ],
    )

    assert bar.validate_capacity() is True
    bar_dict = bar.to_dict()
    assert bar_dict["measure_index"] == 1
    assert bar_dict["valid"] is True
    assert bar_dict["voice_1_final_tick"] == 3840

    # Overfull bar capacity invariant failure
    overfull_bar = TopologicallyLockedBarTimeline(
        measure_index=2,
        capacity_ticks=3840,
        voice_1_final_tick=4800,
        voice_2_final_tick=0,
        valid=True,
    )
    assert overfull_bar.validate_capacity() is False
    assert overfull_bar.to_dict()["valid"] is False


def test_tuplet_duration_resolution() -> None:
    """Verify tuplet duration resolution for 3:2 eighth-note triplets."""
    eighth_cand = {"symbol_type": "eighth_note_candidate", "tuplet_association": {"ratio": "3:2"}}
    dur = resolve_tuplet_duration(eighth_cand, 480)
    assert dur == 320

    eighth_cand_dict = {"symbol_type": "eighth_note_candidate", "tuplet_association": {"actual_notes": 3, "normal_notes": 2}}
    dur_dict = resolve_tuplet_duration(eighth_cand_dict, 480)
    assert dur_dict == 320


def test_44_triplet_timing_preservation() -> None:
    """Verify 4/4 triplet duration assignment keeps measure capacity balanced at 3840 ticks without note drops."""
    triplet_assoc = {"actual_notes": 3, "normal_notes": 2, "type": "triplet"}

    outcomes = [
        # Triplet group (3 eighth notes)
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 100.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 120.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 140.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        # 3 Quarter notes
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 200.0,
            "voice": 1,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 300.0,
            "voice": 1,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 400.0,
            "voice": 1,
        },
    ]

    semantic = [{"time_signature_num": 4, "time_signature_den": 4}]
    previews = build_staff_timeline_preview(outcomes, semantic_candidates=semantic)

    assert len(previews) == 1
    measures = previews[0]["measures"]
    assert len(measures) == 1
    m1 = measures[0]

    assert m1["valid"] is True
    assert m1["voice_1_final_tick"] == 3840

    # 3 triplet notes + 3 quarter notes = 6 events
    note_events = [e for e in m1["events"] if e.get("symbol_type") != "padding_rest"]
    assert len(note_events) == 6

    # 480 * 2 / 3 = 320 ticks each
    triplet_events = note_events[:3]
    for te in triplet_events:
        assert te["duration_ticks"] == 320


def test_timeline_reference_isolation() -> None:
    """Verify timeline reconstruction operates without receiving reference .gp files."""
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "x0": 100.0},
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "x0": 200.0},
    ]
    previews = build_staff_timeline_preview(outcomes)
    assert len(previews) == 1
    assert previews[0]["measures"][0]["valid"] is True


def test_private_fixture_lesson6_smoke_preservation() -> None:
    """Verify pipeline recognition on Lesson-6.pdf preserves 4/4 triplet timing."""
    lesson6_pdf = PROJECT_ROOT / "fixtures" / "private" / "Lesson-6.pdf"
    if not lesson6_pdf.exists():
        pytest.skip("Private fixture Lesson-6.pdf not present in test environment")

    result = run_recognition_on_file(lesson6_pdf, assume_treble_clef=True)
    assert result is not None
    assert "timeline_preview" in result
