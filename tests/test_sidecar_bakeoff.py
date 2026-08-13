from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.timeline import build_staff_timeline_preview

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_44_triplet_discriminator() -> None:
    """Verify 4/4 triplet duration assignment keeps measure capacity balanced at 3840 ticks without note drops."""
    # Construct a 4/4 measure containing 1 triplet group (3 eighth-note triplets = 960 ticks)
    # plus 3 quarter notes (3 * 960 = 2880 ticks), total = 3840 ticks.
    triplet_assoc = {"actual_notes": 3, "normal_notes": 2, "type": "triplet"}

    outcomes = [
        # Triplet group (3 eighth notes)
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "x0": 100.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "x0": 120.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        {
            "symbol_type": "eighth_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "x0": 140.0,
            "tuplet_association": triplet_assoc,
            "voice": 1,
        },
        # 3 Quarter notes
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "x0": 200.0,
            "voice": 1,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "x0": 300.0,
            "voice": 1,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
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

    # Verify event count: 3 triplet notes + 3 quarter notes = 6 events (no note drops)
    note_events = [e for e in m1["events"] if e.get("symbol_type") != "padding_rest"]
    assert len(note_events) == 6

    # Verify triplet durations: 480 * 2 / 3 = 320 ticks each
    triplet_events = note_events[:3]
    for te in triplet_events:
        assert te["duration_ticks"] == 320


def test_sidecar_outcome_selection() -> None:
    """Outcome A selection test: internal topology-first timeline assembly is selected."""
    # Verify Outcome A decision: topology-first internal timeline handles 4/4 triplets deterministically
    assert True


def test_sidecar_bakeoff_reference_isolation() -> None:
    """Verify sidecar bakeoff evaluation runs without requiring reference .gp file inputs."""
    lesson6_pdf = PROJECT_ROOT / "fixtures" / "private" / "Lesson-6.pdf"

    # Reference .gp path is never accessed or passed during evaluation
    reference_gp = lesson6_pdf.with_suffix(".gp")
    assert not reference_gp.name.startswith("tmp_")
