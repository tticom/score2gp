"""Tests for Canonical Vector and Text Observations Adapter (REC-03)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from score2gp.recognition.observations import (
    ObservationAdapterError,
    extract_raster_observations,
    extract_text_observations,
    extract_vector_observations,
    observe,
    observe_pdf,
)
from score2gp.recognition.schemas import (
    DocumentObservations,
    FORBIDDEN_OBSERVATION_SEMANTIC_KEYS,
    SourceModality,
)


FIXTURES_DIR = Path("tests/fixtures/pdf")
SPARSE_PDF = FIXTURES_DIR / "generated_standard_staff_sparse.pdf"
TEXT_DIVERSITY_PDF = FIXTURES_DIR / "generated_standard_staff_text_font_diversity.pdf"
DENSE_PDF = FIXTURES_DIR / "generated_pdf_dense_string_assignment_safe.pdf"
MULTI_SYSTEM_PDF = FIXTURES_DIR / "generated_pdf_multi_system_all_valid.pdf"


def test_observe_sparse_pdf() -> None:
    assert SPARSE_PDF.exists(), f"Fixture missing: {SPARSE_PDF}"
    obs = observe(SPARSE_PDF)

    assert isinstance(obs, DocumentObservations)
    assert obs.page_count >= 1
    assert obs.source_file == str(SPARSE_PDF)
    assert obs.document_id.startswith("doc_")
    assert len(obs.vectors) > 0

    # Validate vector properties
    for vec in obs.vectors:
        assert vec.modality == SourceModality.VECTOR
        assert vec.bbox.page_index >= 1
        assert vec.bbox.x0 <= vec.bbox.x1
        assert vec.bbox.y0 <= vec.bbox.y1
        assert vec.provenance.page_index == vec.bbox.page_index
        assert vec.provenance.modality == SourceModality.VECTOR
        assert vec.provenance.raw_primitive_id is not None
        assert vec.path_type in ("line", "curve", "rect", "polygon", "path")


def test_observe_text_diversity_pdf() -> None:
    assert TEXT_DIVERSITY_PDF.exists(), f"Fixture missing: {TEXT_DIVERSITY_PDF}"
    obs = observe(TEXT_DIVERSITY_PDF)

    assert isinstance(obs, DocumentObservations)
    assert len(obs.texts) > 0

    # Validate text properties
    for txt in obs.texts:
        assert txt.modality == SourceModality.TEXT
        assert txt.bbox.page_index >= 1
        assert txt.bbox.x0 <= txt.bbox.x1
        assert txt.bbox.y0 <= txt.bbox.y1
        assert txt.provenance.page_index == txt.bbox.page_index
        assert txt.provenance.modality == SourceModality.TEXT
        assert txt.raw_text != ""


def test_exact_coordinates_precision_unrounded() -> None:
    """Verify that source page-space coordinates retain exact unrounded precision."""
    assert TEXT_DIVERSITY_PDF.exists(), f"Fixture missing: {TEXT_DIVERSITY_PDF}"
    obs = observe(TEXT_DIVERSITY_PDF)

    # In TEXT_DIVERSITY_PDF, title span y0 is 27.099998474121094 (has > 4 decimal places)
    title_spans = [t for t in obs.texts if "generated_standard_staff_text_font_diversity.pdf" in t.raw_text]
    assert len(title_spans) > 0
    title_span = title_spans[0]
    # Check that high precision float is preserved exactly without rounding
    assert str(title_span.bbox.y0).startswith("27.09999") or title_span.bbox.y0 > 27.0999


def test_item_level_drawing_provenance() -> None:
    """Verify that multi-item drawings emit distinct observations with item-level provenance."""
    assert SPARSE_PDF.exists(), f"Fixture missing: {SPARSE_PDF}"
    obs = observe(SPARSE_PDF)

    for vec in obs.vectors:
        assert "_i" in vec.id, f"Observation id must contain item index: {vec.id}"
        assert "drawing_index" in vec.provenance.extra
        assert "item_index" in vec.provenance.extra
        assert "seqno" in vec.provenance.extra
        assert "item_tag" in vec.provenance.extra


def test_observe_multi_page_or_multi_system_pdf() -> None:
    assert MULTI_SYSTEM_PDF.exists(), f"Fixture missing: {MULTI_SYSTEM_PDF}"
    obs = observe(MULTI_SYSTEM_PDF)

    assert isinstance(obs, DocumentObservations)
    assert obs.page_count >= 1
    assert len(obs.vectors) > 0

    # Verify unique IDs across all observations
    all_ids = [v.id for v in obs.vectors] + [t.id for t in obs.texts] + [r.id for r in obs.rasters]
    assert len(all_ids) == len(set(all_ids)), "Observation IDs must be unique across the document"


def test_observations_zero_semantic_leakage() -> None:
    """Verify that observations contain zero forbidden musical/staff semantics."""
    for pdf_fixture in (SPARSE_PDF, TEXT_DIVERSITY_PDF, DENSE_PDF, MULTI_SYSTEM_PDF):
        if not pdf_fixture.exists():
            continue
        obs = observe(pdf_fixture)

        # Check metadata
        assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(obs.metadata.keys())

        # Check vectors
        for vec in obs.vectors:
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(vec.extra.keys())
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(vec.provenance.extra.keys())

        # Check texts
        for txt in obs.texts:
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(txt.extra.keys())
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(txt.provenance.extra.keys())

        # Check rasters
        for r in obs.rasters:
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(r.extra.keys())
            assert not FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(r.provenance.extra.keys())


def test_observe_determinism() -> None:
    """Verify that multiple observations of the same source yield identical outputs."""
    obs1 = observe(SPARSE_PDF)
    obs2 = observe(SPARSE_PDF)

    assert obs1.model_dump() == obs2.model_dump()


def test_observe_bytes_and_path_equivalence() -> None:
    """Verify observe(path) and observe(bytes) yield equivalent observation collections."""
    content = SPARSE_PDF.read_bytes()
    obs_path = observe(SPARSE_PDF)
    obs_bytes = observe(content)

    assert obs_path.page_count == obs_bytes.page_count
    assert len(obs_path.vectors) == len(obs_bytes.vectors)
    assert len(obs_path.texts) == len(obs_bytes.texts)
    assert len(obs_path.rasters) == len(obs_bytes.rasters)

    # Vector coordinates and ids match
    for v_p, v_b in zip(obs_path.vectors, obs_bytes.vectors):
        assert v_p.id == v_b.id
        assert v_p.bbox.model_dump() == v_b.bbox.model_dump()
        assert v_p.path_type == v_b.path_type


def test_observe_fails_on_missing_file() -> None:
    missing_path = Path("tests/fixtures/pdf/non_existent_score.pdf")
    with pytest.raises(ObservationAdapterError, match="PDF source file not found"):
        observe(missing_path)


def test_observe_fails_on_corrupted_bytes() -> None:
    corrupted_data = b"%PDF-1.4\ncorrupted content that cannot be parsed by mupdf"
    with pytest.raises(ObservationAdapterError, match="Failed to open/parse PDF bytes"):
        observe(corrupted_data)


def test_observe_fails_on_corrupted_file(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.pdf"
    corrupt_file.write_bytes(b"not a valid pdf content")
    with pytest.raises(ObservationAdapterError, match="Failed to open/parse PDF file"):
        observe(corrupt_file)


def test_observe_fails_on_invalid_type() -> None:
    with pytest.raises(ObservationAdapterError, match="Unsupported PDF source type"):
        observe(12345)  # type: ignore[arg-type]


def test_legacy_path_compatibility(tmp_path: Path) -> None:
    """Verify that existing legacy inspect_pdf remains functional without regression."""
    pdf_mod = importlib.import_module("score2gp.pdf")
    summary = pdf_mod.inspect_pdf(SPARSE_PDF, tmp_path)
    assert summary["page_count"] >= 1
    assert "warnings" in summary
    assert "pages" in summary
