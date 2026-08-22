from __future__ import annotations

from pathlib import Path
from score2gp.notation_omr.evidence import (
    SourceModality,
    EvidenceRecord,
    CandidateAdapter,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_source_modality_enum() -> None:
    """Verify SourceModality enum values."""
    assert SourceModality.TEXT.value == "text"
    assert SourceModality.VECTOR.value == "vector"
    assert SourceModality.RASTER.value == "raster"
    assert SourceModality.HYBRID.value == "hybrid"


def test_candidate_adapter_preservation() -> None:
    """Verify CandidateAdapter preserves coordinates, modality, confidence, absence, ambiguity, and conflict metadata."""
    adapter = CandidateAdapter()

    raw_dict = {
        "id": "cand_001",
        "page_index": 2,
        "system_index": 1,
        "staff_index": 1,
        "raw_text": "7",
        "modality": "vector",
        "bbox": [10.0, 20.0, 30.0, 40.0],
        "confidence": 0.95,
        "is_absent": False,
        "is_ambiguous": True,
        "is_conflicted": False,
        "custom_tag": "fret_candidate",
    }

    record = adapter.adapt(raw_dict)

    assert isinstance(record, EvidenceRecord)
    assert record.candidate_id == "cand_001"
    assert record.modality == SourceModality.VECTOR
    assert record.bbox == (10.0, 20.0, 30.0, 40.0)
    assert record.page_index == 2
    assert record.system_index == 1
    assert record.staff_index == 1
    assert record.raw_symbol == "7"
    assert record.confidence == 0.95
    assert record.is_absent is False
    assert record.is_ambiguous is True
    assert record.is_conflicted is False
    assert record.metadata.get("custom_tag") == "fret_candidate"


def test_recognition_adapters_reference_isolation() -> None:
    """Verify candidate evidence wrapping operates without receiving reference .gp files."""
    adapter = CandidateAdapter()
    record = adapter.adapt({"id": "cand_iso", "bbox": [0, 0, 10, 10], "page": 1})
    assert record.candidate_id == "cand_iso"
    assert not hasattr(record, "reference_gp")
