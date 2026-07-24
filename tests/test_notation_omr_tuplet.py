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
    """1. Genuine above-staff tuplet '3' associates to exactly three eighth notes in same measure."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0],
        "bbox": [50.0, 100.0, 500.0, 140.0],
        "barlines": [{"bbox": [300.0, 100.0, 301.0, 140.0], "kind": "barline"}]
    }]

    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_001",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bbox=(145.0, 80.0, 155.0, 90.0),
        geometry_facts={"kind": "text_span"}
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"symbol_type": "barline", "bbox": [300.0, 100.0, 301.0, 140.0], "page_index": 1, "system_index": 1, "staff_index": 1}
    ]

    assocs = associate_local_tuplets([marker], outcomes, staff_geom)
    assert len(assocs) == 1
    assert assocs[0].status == "associated"
    assert assocs[0].associated_candidate_ids == ("8th_001", "8th_002", "8th_003")
    assert assocs[0].ratio == (3, 2)


def test_cross_measure_notes_cannot_group():
    """Production Blocker Regression: Candidates across a barline in different measures CANNOT group into one tuplet."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0],
        "bbox": [50.0, 100.0, 500.0, 140.0],
    }]

    # Barline at x=180.0 divides staff into Measure 1 (x < 180) and Measure 2 (x > 180)
    # Note 1 is in Measure 1 (x=120). Notes 2 & 3 are in Measure 2 (x=195, x=245).
    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [115.0, 105.0, 125.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "bar_001", "symbol_type": "barline", "bbox": [179.0, 100.0, 181.0, 140.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [190.0, 105.0, 200.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [240.0, 105.0, 250.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
    ]

    # Tuplet marker at x=175 (Measure 1)
    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_001",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bbox=(170.0, 80.0, 180.0, 90.0)
    )

    assocs = associate_local_tuplets([marker], outcomes, staff_geom)
    # Must fail closed: Note 1 is in Measure 1, Notes 2 & 3 are in Measure 2 -> cannot group across barline!
    assert len(assocs) == 0


def test_unpartitioned_staff_without_barlines_fails_closed():
    """Production Blocker Regression: An unpartitioned staff without barlines or explicit span_id fails closed without manufacturing fake span IDs."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0],
        "bbox": [50.0, 100.0, 500.0, 140.0]
    }]

    # No barlines in outcomes or staff_geom, and no explicit span_id
    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1},
    ]

    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_001",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bbox=(145.0, 80.0, 155.0, 90.0)
    )

    assocs = associate_local_tuplets([marker], outcomes, staff_geom)
    assert len(assocs) == 0

    # Ensure outcomes are NOT mutated to add manufactured span_id
    for c in outcomes:
        assert "span_id" not in c


def test_tuplet_marker_extraction_derives_ownership_from_staff_geometry():
    """Finding 1 Regression: Raw text '3' words derive ownership from staves_geometry instead of defaulting."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 7,
        "staff_index": 2,
        "span_id": "span_p1_sys7_s2",
        "line_y_coords": [500.0, 510.0, 520.0, 530.0, 540.0],
        "bbox": [50.0, 500.0, 500.0, 540.0],
        "barlines": [{"bbox": [300.0, 500.0, 301.0, 540.0], "kind": "barline"}]
    }]

    raw_text = [
        {"text": "3", "bbox": [145.0, 480.0, 155.0, 490.0], "page_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 1
    assert markers[0].system_index == 7
    assert markers[0].staff_index == 2
    assert markers[0].span_id == "span_m1_p1_sys7_s2"



def test_unmapped_text_without_matching_staff_geometry_is_rejected():
    """Finding 1 Regression: Plain text '3' with no matching staff geometry is not assigned fake ownership."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0],
        "bbox": [50.0, 100.0, 500.0, 140.0]
    }]

    raw_text = [
        {"text": "3", "bbox": [145.0, 800.0, 155.0, 810.0], "page_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 0


def test_missing_staff_geometry_fails_closed():
    """Finding 2 Regression: Empty or missing 5-line staff geometry produces no association."""
    marker = TupletMarkerEvidence(
        marker_id="tuplet_marker_001",
        literal="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        span_id="span_m1",
        bbox=(145.0, 80.0, 155.0, 90.0)
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "span_id": "span_m1"},
    ]

    assocs = associate_local_tuplets([marker], outcomes, [])
    assert len(assocs) == 0


def test_adversarial_tab_fret_digit_rejection():
    """2. TAB fret '3' or '13' (inside staff or labeled tab_fret) is rejected."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    raw_text = [
        {"text": "3", "bbox": [145.0, 120.0, 155.0, 130.0], "kind": "tab_fret", "page_index": 1},
        {"text": "13", "bbox": [145.0, 120.0, 155.0, 130.0], "kind": "text_span", "page_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 0


def test_adversarial_measure_label_rejection():
    """3. Measure label '3' is rejected."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    raw_text = [
        {"text": "3", "bbox": [50.0, 85.0, 60.0, 95.0], "kind": "measure_label", "page_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, staff_geom, page_index=1)
    assert len(markers) == 0


def test_adversarial_metadata_text_rejection():
    """4. Metadata text like '[3:50]' is rejected."""
    raw_text = [
        {"text": "[3:50]", "bbox": [145.0, 85.0, 185.0, 95.0], "kind": "text_span", "page_index": 1}
    ]

    markers = extract_tuplet_marker_evidence(raw_text, page_index=1)
    assert len(markers) == 0


def test_ambiguous_geometry_marker_position_preserves_competing_ids():
    """Finding 3 Regression: Marker positioned ambiguously tracks competing candidate IDs and status='ambiguous'."""
    staff_geom = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

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
    assert len(assocs[0].competing_candidate_ids) > 0


def test_timeline_diagnostics_preserves_tuplet_association_in_events():
    """Finding 3 Regression: Timeline preview measure events preserve explicit tuplet_association dictionary."""
    assoc = TupletAssociation(
        marker_id="tuplet_marker_001",
        associated_candidate_ids=("8th_001", "8th_002", "8th_003"),
        ratio=(3, 2),
        span_id="span_m1",
        status="associated"
    )

    outcomes = [
        {"candidate_id": "8th_001", "symbol_type": "eighth_note_candidate", "bbox": [95.0, 105.0, 105.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "tuplet_association": assoc.to_dict()},
        {"candidate_id": "8th_002", "symbol_type": "eighth_note_candidate", "bbox": [145.0, 105.0, 155.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "tuplet_association": assoc.to_dict()},
        {"candidate_id": "8th_003", "symbol_type": "eighth_note_candidate", "bbox": [195.0, 105.0, 205.0, 115.0], "page_index": 1, "system_index": 1, "staff_index": 1, "tuplet_association": assoc.to_dict()},
    ]

    previews = build_staff_timeline_preview(outcomes)
    assert len(previews) == 1
    events = previews[0]["measures"][0]["events"]
    eighth_events = [e for e in events if e.get("candidate_id") in ("8th_001", "8th_002", "8th_003")]
    assert len(eighth_events) == 3
    for e in eighth_events:
        assert "tuplet_association" in e
        assert e["tuplet_association"]["status"] == "associated"
        assert e["tuplet_association"]["marker_id"] == "tuplet_marker_001"


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
