import pytest
from score2gp.whole_note_recogniser import build_staff_timeline_preview

def test_correctly_segmented_128():
    # 1. Correctly segmented 12/8 sequence
    # 12 eighth notes in measure 1, 12 eighth notes in measure 2, separated by an OMR barline
    outcomes = []
    # Measure 1: 12 eighth notes
    for i in range(12):
        outcomes.append({
            "candidate_id": f"note_m1_{i}",
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 10.0 + i * 15.0,
            "voice": 1,
            "clef_resolved_staff_pitch": "C4"
        })
    # Barline
    outcomes.append({
        "symbol_type": "barline_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "x0": 200.0
    })
    # Measure 2: 12 eighth notes
    for i in range(12):
        outcomes.append({
            "candidate_id": f"note_m2_{i}",
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 210.0 + i * 15.0,
            "voice": 1,
            "clef_resolved_staff_pitch": "C4"
        })

    # Expected meter: 12/8
    # Under 12/8, D_measure = 12 * 960 * 4 / 8 = 5760.
    # Total ticks per measure = 12 * 480 = 5760.
    previews = build_staff_timeline_preview(outcomes, pdf_path=None)
    assert len(previews) == 1
    measures = previews[0]["measures"]
    assert len(measures) == 2
    
    assert measures[0]["measure_index"] == 1
    assert measures[0]["valid"] is True
    assert len(measures[0]["events"]) == 12
    
    assert measures[1]["measure_index"] == 2
    assert measures[1]["valid"] is True
    assert len(measures[1]["events"]) == 12

def test_missed_barline_timing_error():
    # 2. Missed source barline must remain a detectable timing error.
    # We have 24 eighth notes in a single measure because the barline is missing/missed.
    outcomes = []
    for i in range(24):
        outcomes.append({
            "candidate_id": f"note_{i}",
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 10.0 + i * 15.0,
            "voice": 1,
            "clef_resolved_staff_pitch": "C4"
        })

    # Let's force detection of 12/8 by using 24 eighth notes (duration 11520, which is nearest to 5760 * 2)
    # Wait, if raw duration is 11520, then distance to 5760 is 5760, which is > 960.
    # So detect_time_signature might return None.
    # In that case, build_staff_timeline_preview defaults to (4, 4) in unit tests.
    # Under 4/4, D_measure = 3840. Total ticks = 11520 > 3840, so it is still invalid!
    # Let's test that it is invalid:
    previews = build_staff_timeline_preview(outcomes, pdf_path=None)
    assert len(previews) == 1
    measures = previews[0]["measures"]
    # Only 1 measure was generated (no barline to split it)
    assert len(measures) == 1
    assert measures[0]["valid"] is False

def test_split_only_on_evidence():
    # 3. Splitting only when source barline/measure-anchor evidence supports it.
    # We verify that without a barline or anchor, it is not split even if it is overfull.
    outcomes = []
    # Create 13 eighth notes (total 6240 ticks)
    for i in range(13):
        outcomes.append({
            "candidate_id": f"note_{i}",
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 10.0 + i * 15.0,
            "voice": 1,
            "clef_resolved_staff_pitch": "C4"
        })
        
    previews = build_staff_timeline_preview(outcomes, pdf_path=None)
    assert len(previews) == 1
    measures = previews[0]["measures"]
    assert len(measures) == 1
    assert measures[0]["valid"] is False


def test_iterative_barline_restoration():
    # 4. Iterative barline restoration under dense text anchors.
    # We have dense anchors, so OMR barlines are discarded.
    # But because a measure is overfull, we restore the discarded OMR barline to split it.
    outcomes = []
    # 24 eighth notes
    for i in range(24):
        outcomes.append({
            "candidate_id": f"note_{i}",
            "symbol_type": "eighth_note_candidate",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "x0": 10.0 + i * 15.0,
            "voice": 1,
            "clef_resolved_staff_pitch": "C4"
        })
    # OMR Barline at x=182.5
    outcomes.append({
        "symbol_type": "barline_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "x0": 182.5
    })

    # Page 1, System 1, Staff 1 geometries
    geometries = [{
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [10.0, 100.0, 400.0, 140.0],
        "line_y_coords": [100.0, 110.0, 120.0, 130.0, 140.0]
    }]

    # Mock measure anchors to set is_dense = True
    measure_anchors = {
        (1, 1, 1): [10.0, 400.0]
    }

    # Mock fitz.open to return "12/8" text for meter detection
    from unittest.mock import patch, MagicMock
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "12/8"
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page

    with patch("fitz.open", return_value=mock_doc):
        previews = build_staff_timeline_preview(
            outcomes,
            semantic_candidates=None,
            all_staff_geometries=geometries,
            measure_anchors=measure_anchors,
            pdf_path="dummy.pdf"
        )
    assert len(previews) == 1
    measures = previews[0]["measures"]
    # The discarded OMR barline at 190.0 should be restored, splitting it into 2 measures!
    assert len(measures) == 2
    assert measures[0]["valid"] is True
    assert measures[1]["valid"] is True
