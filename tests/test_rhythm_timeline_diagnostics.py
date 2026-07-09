import pytest
from score2gp.whole_note_recogniser import build_staff_timeline_preview

def test_rhythm_timeline_rests_and_voices():
    # Test cases mapping note types, voice assignments, rest positions and barline resets.
    # 1. Staff geometries (middle line at 220)
    geometries = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [50.0, 200.0, 500.0, 240.0],
            "line_y_coords": [200.0, 210.0, 220.0, 230.0, 240.0]
        }
    ]

    outcomes = [
        # Note 0: Voice 1 (stems up) at x=100.0
        {
            "candidate_id": "note_v1",
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 100.0,
            "y0": 210.0,
            "stem_direction": "up"
        },
        # Note 1: Voice 2 (stems down) at x=100.0 (vertically aligned)
        {
            "candidate_id": "note_v2",
            "symbol_type": "half_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 102.0,
            "y0": 230.0,
            "stem_direction": "down"
        },
        # Note 2: Voice 1 (stems up) at x=200.0
        {
            "candidate_id": "note_v1_next",
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 200.0,
            "y0": 210.0,
            "stem_direction": "up"
        },
        # Barline at x=250.0 -> Reset cursors to 0
        {
            "symbol_type": "barline_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 250.0
        },
        # Note 3: After barline, Voice 1 note at x=300.0
        {
            "candidate_id": "note_m2",
            "symbol_type": "quarter_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 300.0,
            "y0": 210.0,
            "stem_direction": "up"
        }
    ]

    semantic_candidates = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            # Rests:
            # 1. Whole rest centered at x=150.0 (will map to voice 1, y0 is above middle_y)
            "whole_rests": [
                {"x0": 150.0, "y0": 210.0, "bbox": [145.0, 205.0, 155.0, 215.0]}
            ],
            # 2. Half rest in measure 2 below middle line (y0=230 -> voice 2) at x=350.0
            "half_rests": [
                {"x0": 350.0, "y0": 230.0, "bbox": [345.0, 225.0, 355.0, 235.0]}
            ]
        }
    ]

    previews = build_staff_timeline_preview(outcomes, semantic_candidates, geometries)

    assert len(previews) == 1
    preview = previews[0]
    assert preview["page_index"] == 1
    assert preview["system_index"] == 1
    assert preview["staff_index"] == 1

    measures = preview["measures"]
    assert len(measures) == 2

    # --- Measure 1 ---
    # Expected layout:
    # Beat 1 (x=100/102): Voice 1 quarter (dur=960), Voice 2 half (dur=1920). Cursors: V1=960, V2=1920.
    # Beat 2 (x=150): Whole rest in Voice 1 (dur=3840). Start tick is max(cursor_1, cursor_2) = 1920. Voice 1 cursor goes to 1920 + 3840 = 5760.
    # Beat 3 (x=200): Voice 1 quarter (dur=960). Start tick is cursor_1 = 5760. Voice 1 cursor goes to 6720.
    # Total V1 duration = 6720 > 3840 -> marked invalid!
    m1 = measures[0]
    assert m1["measure_index"] == 1
    assert m1["valid"] is False

    events_m1 = m1["events"]
    # Check that events have timeline parameters populated
    n_v1 = next(e for e in outcomes if e.get("candidate_id") == "note_v1")
    assert n_v1["timeline_start_tick"] == 0
    assert n_v1["timeline_duration_ticks"] == 960

    n_v2 = next(e for e in outcomes if e.get("candidate_id") == "note_v2")
    assert n_v2["timeline_start_tick"] == 0
    assert n_v2["timeline_duration_ticks"] == 1920

    # --- Measure 2 ---
    # Beat 1 (x=300): Voice 1 quarter note (dur=960). Cursor V1=960, V2=0.
    # Beat 2 (x=350): Voice 2 half rest (dur=1920). Start tick = cursor_2 = 0. Cursor V1=960, V2=1920.
    # End of measure: padded to 3840 ticks.
    # Voice 1 padding: dur = 3840 - 960 = 2880 ticks.
    # Voice 2 padding: dur = 3840 - 1920 = 1920 ticks.
    m2 = measures[1]
    assert m2["measure_index"] == 2
    assert m2["valid"] is True
    assert m2["voice_1_final_tick"] == 3840
    assert m2["voice_2_final_tick"] == 3840

    events_m2 = m2["events"]
    # 4 events: Note (V1, 0, 960), Half Rest (V2, 0, 1920), Padding Rest (V1, 960, 2880), Padding Rest (V2, 1920, 1920)
    assert len(events_m2) == 4
