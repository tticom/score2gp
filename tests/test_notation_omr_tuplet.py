"""Unit and regression tests for local tuplet evidence and association."""

import pytest
from score2gp.notation_omr.tuplet import (
    TupletAssociation,
    TupletMarkerEvidence,
    associate_local_tuplets,
    extract_tuplet_marker_evidence,
)
from score2gp.notation_omr.timeline import build_staff_timeline_preview


def test_genuine_above_staff_tuplet_association():
    """1. Genuine above-staff tuplet '3' associates to exactly three eighth notes."""
    # Staff line 1 is at y=100.0, spacing=10.0. Above-staff lane is y in [80.0, 100.0].
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0],
        "bbox": [50.0, 100.0, 500.0, 140.0]
    }]

    # Marker x=150 (between note1 x=100 and note3 x=200), y=85 (above staff lane)
    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_001",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        span_id="span_m1",
        bbox=(145.0, 80.0, 155.0, 90.0),  # y_center = 85.0
        geometry_facts={"kind": "text_span"}
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
    ]

    assocs = associate_local_tuplets([marker], outcomes, staff_geom)
    assert len(assocs) == 1
    assert assocs[0].status == "associated"
    assert assocs[0].associated_candidate_ids == ("8th_001", "8th_002", "8th_003")
    assert assocs[0].ratio == (3, 2)


def test_adversarial_tab_fret_digit_rejection():
    """2. TAB fret '3' or '13' (below/inside staff or labeled tab_fret) is rejected."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    # TAB fret digit inside staff y=125 (inside staff lines)
    raw_text = [
        {"text": "3", "bbox": [145.0, 120.0, 155.0, 130.0], "kind": "tab_fret", "system_index": 1, "staff_index": 1},
        {"text": "13", "bbox": [145.0, 120.0, 155.0, 130.0], "kind": "text_span", "system_index": 1, "staff_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 0  # Rejects tab_fret and "13"


def test_adversarial_measure_label_rejection():
    """3. Measure label '3' is rejected."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    raw_text = [
        {"text": "3", "bbox": [50.0, 75.0, 60.0, 85.0], "kind": "measure_label", "system_index": 1, "staff_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 0


def test_adversarial_metadata_text_rejection():
    """4. Metadata text like '[3:50]' is rejected."""
    raw_text = [
        {"text": "[3:50]", "bbox": [145.0, 80.0, 185.0, 90.0], "kind": "text_span", "system_index": 1, "staff_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, page_index=1)
    assert len(markers) == 0


def test_ambiguous_geometry_marker_position():
    """5. Marker positioned ambiguously between competing three-event groups produces status='ambiguous'."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    # Marker x=175 (between 8th_001 & 8th_003 AND between 8th_002 & 8th_004)
    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_amb",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        span_id="span_m1",
        bbox=(170.0, 85.0, 180.0, 95.0)
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [100.0, 105.0, 110.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [150.0, 105.0, 160.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [200.0, 105.0, 210.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_004", "symbol_type": "eighth_note_candidate", "bbox": [250.0, 105.0, 260.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
    ]

    assocs = associate_local_tuplets([marker], outcomes, staff_geom)
    assert len(assocs) == 1
    assert assocs[0].status == "ambiguous"


def test_unmarked_compound_meter_remains_unscaled():
    """6. Ordinary unmarked eighth-note groups in 6/8 and 12/8 remain unscaled."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    outcomes = [
        {"candidate_id": f"8th_{i:03d}", "symbol_type": "eighth_note_candidate", "bbox": [100.0 + i*30, 105.0, 110.0 + i*30, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"}
        for i in range(6)
    ]

    assocs = associate_local_tuplets([], outcomes, staff_geom)
    assert len(assocs) == 0

    for cand in outcomes:
        assert "duration_ticks" not in cand or cand["duration_ticks"] == 480


def test_malformed_ownership_missing_span_and_invalid_geometry():
    """7. Malformed ownership, missing span, or out-of-lane geometry produces no association."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    marker_mismatched_span = TupletMarkerEvidence(
        marker_id="tuplet_marker_span_err",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        span_id="span_A",
        bbox=(145.0, 85.0, 155.0, 95.0)
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_B"},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_B"},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_B"},
    ]

    assocs = associate_local_tuplets([marker_mismatched_span], outcomes, staff_geom)
    assert len(assocs) == 0


def test_timeline_diagnostics_preserves_association_status():
    """8. Prove association status is not discarded before timeline diagnostics."""
    assoc = TupletAssociation(
        marker_id="tuplet_marker_001",
        associated_candidate_ids=("8th_001", "8th_002", "8th_003"),
        ratio=(3, 2),
        span_id="span_m1",
        status="associated"
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "duration_ticks": 320, "tuplet_association": assoc.to_dict()},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "duration_ticks": 320, "tuplet_association": assoc.to_dict()},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "duration_ticks": 320, "tuplet_association": assoc.to_dict()},
    ]

    previews = build_staff_timeline_preview(outcomes)
    assert len(previews) == 1
    events = previews[0]["measures"][0]["events"]
    eighth_events = [e for e in events if e.get("candidate_id") in ("8th_001", "8th_002", "8th_003")]
    assert len(eighth_events) == 3
    for e in eighth_events:
        assert e["duration_ticks"] == 320
