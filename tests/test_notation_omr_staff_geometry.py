"""Direct tests for score2gp.notation_omr.evidence and score2gp.notation_omr.staff_geometry."""

import pytest
from score2gp.notation_omr import (
    _associate_staves,
    map_ledger_line_candidates_to_read_only_outcomes,
    map_ledger_lines_to_note_candidates,
    map_staff_geometry_to_read_only_report,
    shape_candidate_evidence,
    shape_ledger_line_candidate_evidence,
)
from score2gp.notation_omr.evidence import shape_candidate_evidence as direct_shape_evidence
from score2gp.notation_omr.staff_geometry import (
    _associate_staves as direct_associate_staves,
)
from score2gp.whole_note_recogniser import (
    _associate_staves as shim_associate_staves,
    shape_candidate_evidence as shim_shape_evidence,
)


class DummyCandidate:
    def __init__(self, bbox, origin_x=None, origin_y=None):
        self.bbox = bbox
        self.origin_x = origin_x
        self.origin_y = origin_y


def test_notation_omr_evidence_shaping():
    """Test representative behavior path for evidence.py shape_candidate_evidence."""
    raw = [
        DummyCandidate(bbox=[10.0, 20.0, 25.0, 30.0], origin_x=10.0, origin_y=20.0)
    ]

    shaped = direct_shape_evidence(raw, page_index=1, candidate_prefix="test_cand", start_index=1)
    assert len(shaped) == 1
    cand = shaped[0]
    assert cand["candidate_id"] == "test_cand_001"
    assert cand["page_index"] == 1
    assert cand["bbox"] == [10.0, 20.0, 25.0, 30.0]
    assert cand["origin_x"] == 10.0
    assert cand["origin_y"] == 20.0

    # Verify shim re-export equality
    shim_shaped = shim_shape_evidence(raw, page_index=1, candidate_prefix="test_cand", start_index=1)
    assert shaped == shim_shaped


def test_notation_omr_staff_association():
    """Test representative behavior path for staff_geometry.py _associate_staves."""
    shaped_candidates = [
        {"bbox": [10.0, 95.0, 30.0, 105.0]}
    ]
    staves = [
        {
            "staff": {
                "page_index": 0,
                "system_index": 0,
                "staff_index": 0,
                "x0": 0.0,
                "y0": 80.0,
                "x1": 100.0,
                "y1": 120.0,
            }
        }
    ]

    direct_associate_staves(shaped_candidates, staves)
    cand = shaped_candidates[0]
    assert cand["association_status"] == "success"
    assert cand["system_index"] == 0
    assert cand["staff_index"] == 0

    # Test shim re-export equivalence
    shim_candidates = [{"bbox": [10.0, 95.0, 30.0, 105.0]}]
    shim_associate_staves(shim_candidates, staves)
    assert shaped_candidates == shim_candidates


def test_notation_omr_ledger_line_shaping_and_outcomes():
    """Test representative behavior path for ledger line shaping and outcome mapping."""
    raw_clusters = [
        {
            "system_index": 0,
            "staff_index": 0,
            "primitives": [
                {"kind": "horizontal_stroke", "x0": 12.0, "y0": 70.0, "x1": 32.0, "y1": 72.0},
                {"kind": "rectangle", "x0": 15.0, "y0": 68.0, "x1": 25.0, "y1": 74.0},
            ],
        }
    ]

    ledger_cands = shape_ledger_line_candidate_evidence(raw_clusters, page_index=0, start_index=1)
    assert len(ledger_cands) == 1
    cand = ledger_cands[0]
    assert cand["candidate_id"] == "ledger_line_candidate_001"
    assert cand["bbox"] == [12.0, 70.0, 32.0, 72.0]

    outcomes = map_ledger_line_candidates_to_read_only_outcomes(ledger_cands)
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["symbol_type"] == "ledger_line_candidate"
    assert outcome["candidate_id"] == "ledger_line_candidate_001"
    assert outcome["source"] == "diagnostic_candidate_evidence"


def test_notation_omr_staff_geometry_report():
    """Test staff geometry report generation."""
    staves_diags = [
        {
            "staff": {
                "page_index": 0,
                "system_index": 0,
                "staff_index": 0,
                "x0": 10.0,
                "y0": 50.0,
                "x1": 200.0,
                "y1": 90.0,
                "line_y_coords": [50.0, 60.0, 70.0, 80.0, 90.0],
            }
        }
    ]

    reports = map_staff_geometry_to_read_only_report(staves_diags)
    assert len(reports) == 1
    rep = reports[0]
    assert rep["page_index"] == 0
    assert rep["system_index"] == 0
    assert rep["staff_index"] == 0
    assert rep["bbox"] == [10.0, 50.0, 200.0, 90.0]
    assert rep["line_y_coords"] == [50.0, 60.0, 70.0, 80.0, 90.0]


def test_notation_omr_map_ledger_lines_to_note_candidates():
    """Test ledger line attachment to note candidates."""
    outcomes = [
        {
            "symbol_type": "ledger_line_candidate",
            "candidate_id": "ll_001",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "staff_position_index": -1,
            "bbox": [10.0, 45.0, 30.0, 47.0],
        },
        {
            "symbol_type": "quarter_note_candidate",
            "candidate_id": "note_001",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "staff_position_index": -1,
            "bbox": [12.0, 44.0, 28.0, 52.0],
        },
    ]

    map_ledger_lines_to_note_candidates(outcomes)
    note = outcomes[1]
    assert note.get("attached_ledger_line_candidate_ids") == ["ll_001"]
