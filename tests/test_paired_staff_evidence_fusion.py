from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.staff_geometry import SystemTopology
from score2gp.notation_omr.evidence import (
    PairedStaffEvidenceFusion,
    PairedStaffFusionEngine,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_paired_staff_evidence_fusion_one_to_one() -> None:
    """Verify PairedStaffFusionEngine associates candidates by SystemTopology and sets one_to_one status."""
    engine = PairedStaffFusionEngine()

    systems = [
        SystemTopology(system_index=1, page_number=1),
        SystemTopology(system_index=2, page_number=1),
    ]

    notation_cands = [
        {"candidate_id": "note_1", "system_index": 1, "page_index": 1, "bbox": [10, 10, 20, 20]},
        {"candidate_id": "note_2", "system_index": 2, "page_index": 1, "bbox": [10, 100, 20, 110]},
    ]
    tab_cands = [
        {"candidate_id": "tab_1", "system_index": 1, "page_index": 1, "bbox": [10, 40, 20, 50]},
    ]

    fusions = engine.fuse(notation_cands, tab_cands, systems)

    assert len(fusions) == 2
    assert fusions[0].system_index == 1
    assert len(fusions[0].notation_candidates) == 1
    assert len(fusions[0].tab_candidates) == 1
    assert fusions[0].ownership_status == "one_to_one"

    assert fusions[1].system_index == 2
    assert len(fusions[1].notation_candidates) == 1
    assert len(fusions[1].tab_candidates) == 0


def test_prevent_cross_system_snapping() -> None:
    """Verify candidate alignment is strictly scoped within system and page boundaries."""
    engine = PairedStaffFusionEngine()

    systems = [
        SystemTopology(system_index=1, page_number=1),
        SystemTopology(system_index=2, page_number=1),
    ]

    notation_cands = [
        {"candidate_id": "note_sys1", "system_index": 1, "page_index": 1, "bbox": [10, 10, 20, 20]},
    ]
    tab_cands = [
        {"candidate_id": "tab_sys2", "system_index": 2, "page_index": 1, "bbox": [10, 100, 20, 110]},
    ]

    fusions = engine.fuse(notation_cands, tab_cands, systems)

    # Candidate from System 1 is never associated with System 2
    assert fusions[0].system_index == 1
    assert len(fusions[0].notation_candidates) == 1
    assert len(fusions[0].tab_candidates) == 0

    assert fusions[1].system_index == 2
    assert len(fusions[1].notation_candidates) == 0
    assert len(fusions[1].tab_candidates) == 1


def test_paired_staff_fusion_reference_isolation() -> None:
    """Verify paired-staff evidence fusion operates without requiring reference .gp files."""
    engine = PairedStaffFusionEngine()
    systems = [SystemTopology(system_index=1, page_number=1)]
    fusions = engine.fuse([], [], systems)
    assert len(fusions) == 1
    assert fusions[0].ownership_status == "one_to_one"
