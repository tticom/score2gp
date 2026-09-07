"""Tests for Raster Observation Adapter (REC-05).

Verifies:
1. Pinned renderer, scale, color mode, and coordinate transform provenance.
2. Deterministic page rendering and pixel-byte reproducibility.
3. Fail-closed contract on missing or corrupted metadata.
4. Lossless coordinate round-trips between page and pixel spaces across multiple scales.
5. Typed line, glyph, and region observations with source pixel boxes.
6. Non-destructive peer observation integration (never mutate/overwrite vectors/texts).
7. Cross-modal disagreement preservation (observable disparities never averaged away).
8. Pluggable extractor interface keeping ML models outside the adapter.
9. Real-source probes on pinned public scores.
10. Privacy and zero-network execution.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import socket
from typing import Any

import pymupdf as fitz
import pytest

from score2gp.recognition.observations import observe
from score2gp.recognition.raster import (
    AffineMatrix2D,
    ColorMode,
    CrossModalDisagreementKind,
    RasterGlyphObservation,
    RasterLineObservation,
    RasterObservation,
    RasterPixelBox,
    RasterPrimitiveType,
    RasterProvenanceError,
    RasterTransformError,
    RasterTransformProvenance,
    attach_raster_observations,
    build_transform_provenance,
    compare_text_and_raster_glyphs,
    compare_vector_and_raster_lines,
    extract_raster_glyph_observations,
    extract_raster_line_observations,
    extract_raster_observations_for_page,
    extract_raster_region_observations,
    observe_raster,
    render_page_deterministic,
)
from score2gp.recognition.schemas import (
    BoundingBox2D,
    FORBIDDEN_OBSERVATION_SEMANTIC_KEYS,
    ObservationProvenance,
    SourceModality,
    VectorPathObservation,
)


FIXTURES_DIR = Path("tests/fixtures/pdf")
PUBLIC_FIXTURES_DIR = Path("fixtures/public")

REAL_SCORE_MUTOPIA = PUBLIC_FIXTURES_DIR / "mutopia-bwv-anh-120-minuet-a-minor-a4.pdf"
REAL_SCORE_DEREK_TRUCKS = PUBLIC_FIXTURES_DIR / "Derek Trucks BB King.pdf"
SPARSE_PDF = FIXTURES_DIR / "generated_standard_staff_sparse.pdf"
PAIRED_PDF = FIXTURES_DIR / "generated_paired_notation_tab_system.pdf"
TEXT_DIVERSITY_PDF = FIXTURES_DIR / "generated_standard_staff_text_font_diversity.pdf"

# ---------------------------------------------------------------------------
# Pinned Fixture Hashes and Authority Receipts
# ---------------------------------------------------------------------------

PINNED_FIXTURE_HASHES: dict[str, dict[str, str]] = {
    "mutopia": {
        "path": str(REAL_SCORE_MUTOPIA),
        "sha256": "86435e170268a04201966492e120371348abbc7d77712221e362b91d97832eeb",
        "authority": "LilyPond 2.12.1 engraving of Bach Minuet in A minor BWV Anh. 120",
    },
    "derek_trucks": {
        "path": str(REAL_SCORE_DEREK_TRUCKS),
        "sha256": "e2b80e6fa6ad9aac8b648d501e2606086a538aa1c040b345d340bda3f5fd4b27",
        "authority": "Cherry Lane standard guitar paired notation + tab score",
    },
    "sparse": {
        "path": str(SPARSE_PDF),
        "sha256": "47a2a3a5b641910fdf540b28dd0a9c5d3ecbfa465bd238f1d6ba0b3dd0fe01fd",
        "authority": "Synthetic 5-line notation staff generator",
    },
    "paired": {
        "path": str(PAIRED_PDF),
        "sha256": "31669e6c264ed6e48423c0901f853e7fa93564fd0aa60cdc4189c53a8796dcad",
        "authority": "Synthetic paired notation + tab score generator",
    },
    "text_diversity": {
        "path": str(TEXT_DIVERSITY_PDF),
        "sha256": "070a76a78d6b44d9139cbc8e177bc02a2823647899f9c92fa621bf95324298b0",
        "authority": "Synthetic multi-font text layout generator",
    },
}


def _verify_fixture_hash(key: str) -> Path:
    info = PINNED_FIXTURE_HASHES[key]
    path = Path(info["path"])
    assert path.is_file(), f"Fixture file does not exist: {path}"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == info["sha256"], f"Fixture {key} SHA-256 mismatch: got {digest}, expected {info['sha256']}"
    return path


# ---------------------------------------------------------------------------
# 1. Pinned Renderer, Scale, Color Mode, and Transform Provenance
# ---------------------------------------------------------------------------

def test_renderer_provenance_pinned_fields() -> None:
    """Verify renderer name, version, scale, and affine matrices are recorded explicitly."""
    page_rect = (0.0, 0.0, 595.28, 841.89)
    prov = build_transform_provenance(
        page_rect=page_rect,
        pixel_width=1241,
        pixel_height=1754,
        dpi=150.0,
        color_mode=ColorMode.GRAY,
        pixel_offset_x=0,
        pixel_offset_y=0,
        samples_sha256="abcdef1234567890",
        renderer_name="pymupdf",
        renderer_ver="1.28.2",
    )

    assert prov.renderer == "pymupdf"
    assert prov.renderer_version == "1.28.2"
    assert prov.dpi == 150.0
    assert prov.scale_x == pytest.approx(150.0 / 72.0)
    assert prov.scale_y == pytest.approx(150.0 / 72.0)
    assert prov.color_mode == ColorMode.GRAY
    assert prov.color_channels == 1
    assert prov.page_width_pt == pytest.approx(595.28)
    assert prov.page_height_pt == pytest.approx(841.89)
    assert prov.pixel_width == 1241
    assert prov.pixel_height == 1754
    assert prov.samples_sha256 == "abcdef1234567890"

    # Transform matrices must be non-null and invertible
    assert prov.transform_matrix.is_invertible()
    assert prov.inverse_matrix.is_invertible()
    assert prov.transform_matrix.a == pytest.approx(150.0 / 72.0)
    assert prov.transform_matrix.d == pytest.approx(150.0 / 72.0)
    assert prov.inverse_matrix.a == pytest.approx(72.0 / 150.0)
    assert prov.inverse_matrix.d == pytest.approx(72.0 / 150.0)


# ---------------------------------------------------------------------------
# 2. Deterministic Rendering and Byte Reproducibility
# ---------------------------------------------------------------------------

def test_deterministic_rendering_repeated_executions() -> None:
    """Repeated rendering of the same page must produce byte-for-byte identical output."""
    path = _verify_fixture_hash("mutopia")
    doc = fitz.open(path)
    page = doc[0]

    # Render 5 times independently
    digests: list[str] = []
    sample_lengths: list[int] = []

    for _ in range(5):
        raw_samples, prov = render_page_deterministic(
            page,
            dpi=150.0,
            color_mode=ColorMode.GRAY,
        )
        digests.append(hashlib.sha256(raw_samples).hexdigest())
        sample_lengths.append(len(raw_samples))
        assert prov.samples_sha256 == digests[-1]

    doc.close()

    # All SHA-256 digests must be exactly identical
    assert len(set(digests)) == 1, f"Rendering non-deterministic: got differing hashes {digests}"
    assert len(set(sample_lengths)) == 1


def test_deterministic_rendering_across_color_modes() -> None:
    """Verify determinism across GRAY, RGB, and BINARY rendering modes."""
    path = _verify_fixture_hash("sparse")
    doc = fitz.open(path)
    page = doc[0]

    for mode in (ColorMode.GRAY, ColorMode.RGB, ColorMode.BINARY):
        s1, p1 = render_page_deterministic(page, dpi=150.0, color_mode=mode)
        s2, p2 = render_page_deterministic(page, dpi=150.0, color_mode=mode)
        assert hashlib.sha256(s1).hexdigest() == hashlib.sha256(s2).hexdigest()
        assert p1.samples_sha256 == p2.samples_sha256
        if mode == ColorMode.GRAY:
            assert p1.color_channels == 1
        elif mode == ColorMode.RGB:
            assert p1.color_channels == 3
        elif mode == ColorMode.BINARY:
            assert p1.color_channels == 1
            # In binary mode, samples should only be 0 or 255
            unique_vals = set(s1)
            assert unique_vals.issubset({0, 255})

    doc.close()


# ---------------------------------------------------------------------------
# 3. Fail-Closed Contract on Missing or Corrupted Metadata
# ---------------------------------------------------------------------------

def test_fail_closed_on_missing_renderer() -> None:
    """Missing or empty renderer name must fail closed with RasterProvenanceError."""
    page_rect = (0.0, 0.0, 500.0, 700.0)
    with pytest.raises(RasterProvenanceError, match="Renderer name must not be empty"):
        build_transform_provenance(
            page_rect=page_rect,
            pixel_width=1000,
            pixel_height=1400,
            dpi=144.0,
            renderer_name="",
        )


def test_fail_closed_on_invalid_dpi() -> None:
    """Non-positive DPI must fail closed with RasterProvenanceError."""
    page_rect = (0.0, 0.0, 500.0, 700.0)
    with pytest.raises(RasterProvenanceError, match="DPI must be positive"):
        build_transform_provenance(
            page_rect=page_rect,
            pixel_width=1000,
            pixel_height=1400,
            dpi=-10.0,
        )

    with pytest.raises(RasterProvenanceError, match="DPI must be positive"):
        build_transform_provenance(
            page_rect=page_rect,
            pixel_width=1000,
            pixel_height=1400,
            dpi=0.0,
        )


def test_fail_closed_on_invalid_dimensions() -> None:
    """Non-positive pixel or page dimensions must fail closed."""
    with pytest.raises(RasterProvenanceError, match="Invalid page rectangle dimensions"):
        build_transform_provenance(
            page_rect=(100.0, 100.0, 100.0, 100.0),  # zero width and height
            pixel_width=100,
            pixel_height=100,
            dpi=72.0,
        )

    with pytest.raises(RasterProvenanceError, match="Pixel dimensions must be positive"):
        build_transform_provenance(
            page_rect=(0.0, 0.0, 100.0, 100.0),
            pixel_width=-5,
            pixel_height=100,
            dpi=72.0,
        )


def test_fail_closed_on_singular_transform_matrix() -> None:
    """Singular or non-invertible transform matrix must fail closed."""
    singular_matrix = AffineMatrix2D(a=0.0, b=0.0, c=0.0, d=0.0, e=0.0, f=0.0)
    assert not singular_matrix.is_invertible()
    with pytest.raises(RasterTransformError, match="singular"):
        singular_matrix.inverse()


def test_fail_closed_on_corrupted_inverse_matrix() -> None:
    """If supplied inverse matrix does not match analytical inverse, fail closed."""
    fwd = AffineMatrix2D(a=2.0, b=0.0, c=0.0, d=2.0, e=0.0, f=0.0)
    corrupted_inv = AffineMatrix2D(a=999.0, b=0.0, c=0.0, d=999.0, e=0.0, f=0.0)

    with pytest.raises(RasterProvenanceError, match="Supplied inverse_matrix does not match"):
        RasterTransformProvenance(
            renderer="pymupdf",
            renderer_version="1.28.2",
            dpi=144.0,
            scale_x=2.0,
            scale_y=2.0,
            color_mode=ColorMode.GRAY,
            color_channels=1,
            page_width_pt=100.0,
            page_height_pt=100.0,
            pixel_width=200,
            pixel_height=200,
            transform_matrix=fwd,
            inverse_matrix=corrupted_inv,
        )


def test_fail_closed_on_invalid_page_object() -> None:
    """Passing an invalid object missing 'rect' must fail closed."""
    with pytest.raises(RasterProvenanceError, match="missing 'rect' attribute"):
        render_page_deterministic(object(), dpi=150.0)


# ---------------------------------------------------------------------------
# 4. Lossless Coordinate Round-Trips Across Multiple Scales
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dpi", [72.0, 144.0, 150.0, 300.0, 600.0])
def test_lossless_coordinate_round_trip_points(dpi: float) -> None:
    """Point round trips (page -> pixel -> page) must be lossless to machine precision."""
    page_rect = (0.0, 0.0, 612.0, 792.0)
    scale = dpi / 72.0
    w_px = int(math.ceil(612.0 * scale))
    h_px = int(math.ceil(792.0 * scale))

    prov = build_transform_provenance(
        page_rect=page_rect,
        pixel_width=w_px,
        pixel_height=h_px,
        dpi=dpi,
        color_mode=ColorMode.GRAY,
    )

    test_points = [
        (0.0, 0.0),
        (612.0, 792.0),
        (100.25, 250.75),
        (306.12345, 396.98765),
        (1.0e-4, 5.0e-4),
    ]

    for x, y in test_points:
        rx, ry = prov.round_trip_point(x, y)
        assert abs(rx - x) < 1e-9, f"Point x ({x}) round-trip error: {rx}"
        assert abs(ry - y) < 1e-9, f"Point y ({y}) round-trip error: {ry}"


@pytest.mark.parametrize("dpi", [72.0, 150.0, 300.0])
def test_lossless_coordinate_round_trip_bboxes(dpi: float) -> None:
    """BoundingBox2D -> RasterPixelBox -> BoundingBox2D round trips must preserve coordinates."""
    page_rect = (0.0, 0.0, 595.28, 841.89)
    scale = dpi / 72.0
    prov = build_transform_provenance(
        page_rect=page_rect,
        pixel_width=int(math.ceil(595.28 * scale)),
        pixel_height=int(math.ceil(841.89 * scale)),
        dpi=dpi,
        color_mode=ColorMode.GRAY,
    )

    original_bbox = BoundingBox2D(
        page_index=1,
        x0=54.321,
        y0=120.456,
        x1=450.789,
        y1=300.654,
    )

    # Convert to continuous pixel box
    px_box = prov.page_bbox_to_pixel_box(original_bbox)
    assert px_box.px0 < px_box.px1
    assert px_box.py0 < px_box.py1

    # Convert back to canonical page bbox
    reconstructed_bbox = prov.pixel_box_to_page_bbox(px_box, page_index=1)
    assert reconstructed_bbox.x0 == pytest.approx(original_bbox.x0, abs=1e-8)
    assert reconstructed_bbox.y0 == pytest.approx(original_bbox.y0, abs=1e-8)
    assert reconstructed_bbox.x1 == pytest.approx(original_bbox.x1, abs=1e-8)
    assert reconstructed_bbox.y1 == pytest.approx(original_bbox.y1, abs=1e-8)


def test_coordinate_transform_with_nonzero_origin_and_offsets() -> None:
    """Non-zero page origin and pixel offsets must be mapped correctly and losslessly."""
    page_rect = (50.0, 100.0, 550.0, 750.0)  # non-zero origin
    prov = build_transform_provenance(
        page_rect=page_rect,
        pixel_width=1000,
        pixel_height=1300,
        dpi=144.0,
        pixel_offset_x=10,
        pixel_offset_y=20,
    )

    # Origin point (50.0, 100.0) in page coords must map to (10, 20) in pixels
    px0, py0 = prov.page_to_pixel(50.0, 100.0)
    assert px0 == pytest.approx(10.0, abs=1e-8)
    assert py0 == pytest.approx(20.0, abs=1e-8)

    # Pixel (10, 20) must map back to (50.0, 100.0)
    x0, y0 = prov.pixel_to_page(10.0, 20.0)
    assert x0 == pytest.approx(50.0, abs=1e-8)
    assert y0 == pytest.approx(100.0, abs=1e-8)


# ---------------------------------------------------------------------------
# 5. Typed Observations (Line, Glyph, Region) with Source Pixel Boxes
# ---------------------------------------------------------------------------

def test_typed_line_observations_contain_source_pixel_boxes() -> None:
    """Line observations must carry source pixel boxes and physical line coordinates."""
    path = _verify_fixture_hash("sparse")
    doc = fitz.open(path)
    page = doc[0]

    raw_samples, prov = render_page_deterministic(page, dpi=150.0, color_mode=ColorMode.GRAY)
    lines = extract_raster_line_observations(raw_samples, prov, page_index=1, min_width_ratio=0.2)
    doc.close()

    assert len(lines) >= 5, f"Expected at least 5 staff lines, got {len(lines)}"

    for line in lines:
        assert isinstance(line, RasterLineObservation)
        assert line.page_index == 1
        assert isinstance(line.pixel_box, RasterPixelBox)
        assert line.pixel_box.px0 < line.pixel_box.px1
        assert line.pixel_box.py0 < line.pixel_box.py1
        assert line.line_y_pixel > 0
        assert line.line_y_page > 0
        assert line.thickness_pixel > 0
        assert line.thickness_page > 0

        # Convert to canonical schema observation
        schema_obs = line.to_raster_observation(source_file=str(path))
        assert isinstance(schema_obs, RasterObservation)
        assert schema_obs.modality == SourceModality.RASTER
        assert schema_obs.id == line.id
        assert schema_obs.bbox == line.page_bbox

        # Source pixel box must be recorded in extra
        assert "source_pixel_box" in schema_obs.extra
        spb = schema_obs.extra["source_pixel_box"]
        assert spb["px0"] == line.pixel_box.px0
        assert spb["py0"] == line.pixel_box.py0
        assert spb["px1"] == line.pixel_box.px1
        assert spb["py1"] == line.pixel_box.py1

        # Reject any musical semantic leakage
        for forbidden in FORBIDDEN_OBSERVATION_SEMANTIC_KEYS:
            assert forbidden not in schema_obs.extra


def test_typed_glyph_observations_contain_pixel_boxes_and_areas() -> None:
    """Glyph observations must carry source pixel boxes and component pixel areas."""
    path = _verify_fixture_hash("text_diversity")
    doc = fitz.open(path)
    page = doc[0]

    raw_samples, prov = render_page_deterministic(page, dpi=150.0, color_mode=ColorMode.GRAY)
    glyphs = extract_raster_glyph_observations(raw_samples, prov, page_index=1)
    doc.close()

    assert len(glyphs) > 10, f"Expected >10 glyph components in text diversity PDF, got {len(glyphs)}"

    for glyph in glyphs:
        assert isinstance(glyph, RasterGlyphObservation)
        assert glyph.page_index == 1
        assert isinstance(glyph.pixel_box, RasterPixelBox)
        assert glyph.pixel_area >= 4
        assert glyph.page_bbox.x0 <= glyph.page_bbox.x1
        assert glyph.page_bbox.y0 <= glyph.page_bbox.y1

        schema_obs = glyph.to_raster_observation(source_file=str(path))
        assert isinstance(schema_obs, RasterObservation)
        assert schema_obs.feature_type == "glyph_crop"
        assert schema_obs.extra["raster_primitive_type"] == RasterPrimitiveType.GLYPH.value
        assert "source_pixel_box" in schema_obs.extra
        assert schema_obs.extra["pixel_area"] == glyph.pixel_area

        for forbidden in FORBIDDEN_OBSERVATION_SEMANTIC_KEYS:
            assert forbidden not in schema_obs.extra


def test_typed_region_observations_contain_page_and_content_bounds() -> None:
    """Region observations must emit page crop and content extent regions."""
    path = _verify_fixture_hash("sparse")
    doc = fitz.open(path)
    page = doc[0]

    raw_samples, prov = render_page_deterministic(page, dpi=150.0, color_mode=ColorMode.GRAY)
    regions = extract_raster_region_observations(raw_samples, prov, page_index=1)
    doc.close()

    assert len(regions) >= 2  # page_crop and content_extent
    types = {r.region_type for r in regions}
    assert "page_crop" in types
    assert "content_extent" in types

    page_reg = next(r for r in regions if r.region_type == "page_crop")
    assert page_reg.pixel_box.px0 == 0.0
    assert page_reg.pixel_box.py0 == 0.0
    assert page_reg.pixel_box.px1 == float(prov.pixel_width)
    assert page_reg.pixel_box.py1 == float(prov.pixel_height)

    content_reg = next(r for r in regions if r.region_type == "content_extent")
    assert content_reg.pixel_box.px0 >= 0.0
    assert content_reg.pixel_box.px1 <= float(prov.pixel_width)
    assert content_reg.pixel_box.py0 >= 0.0
    assert content_reg.pixel_box.py1 <= float(prov.pixel_height)


# ---------------------------------------------------------------------------
# 6. Non-Destructive Peer Observation Integration (Never Mutate/Overwrite)
# ---------------------------------------------------------------------------

def test_attach_raster_never_mutates_or_overwrites_vector_observations() -> None:
    """Attaching raster observations must leave vector and text observations completely untouched."""
    path = _verify_fixture_hash("sparse")
    base_obs = observe(path)

    # Record baseline state before attaching
    orig_vectors_dump = [v.model_dump() for v in base_obs.vectors]
    orig_texts_dump = [t.model_dump() for t in base_obs.texts]
    orig_vector_ids = [v.id for v in base_obs.vectors]
    orig_text_ids = [t.id for t in base_obs.texts]

    # Extract raster observations
    raster_obs = observe_raster(path, dpi=150.0)
    assert len(raster_obs) > 0

    # Attach raster observations
    updated_obs = attach_raster_observations(base_obs, raster_obs)

    # Invariant: Vector observations must be byte-for-byte identical to baseline
    assert len(updated_obs.vectors) == len(orig_vectors_dump)
    assert [v.id for v in updated_obs.vectors] == orig_vector_ids
    assert [v.model_dump() for v in updated_obs.vectors] == orig_vectors_dump

    # Invariant: Text observations must be byte-for-byte identical to baseline
    assert len(updated_obs.texts) == len(orig_texts_dump)
    assert [t.id for t in updated_obs.texts] == orig_text_ids
    assert [t.model_dump() for t in updated_obs.texts] == orig_texts_dump

    # Rasters must be present and IDs unique
    assert len(updated_obs.rasters) == len(raster_obs)
    assert {r.id for r in updated_obs.rasters} == {r.id for r in raster_obs}

    # Modality must transition to HYBRID when vectors and rasters co-exist
    assert updated_obs.modality == SourceModality.HYBRID


def test_attach_raster_rejects_duplicate_ids() -> None:
    """Duplicate raster IDs must be rejected fail-closed."""
    path = _verify_fixture_hash("sparse")
    base_obs = observe(path)
    raster_obs = observe_raster(path, dpi=150.0)

    # Attach once
    updated_obs = attach_raster_observations(base_obs, raster_obs)

    # Attaching the same rasters again must raise ValueError for duplicate IDs
    with pytest.raises(ValueError, match="Duplicate raster observation ID"):
        attach_raster_observations(updated_obs, raster_obs)


# ---------------------------------------------------------------------------
# 7. Cross-Modal Disagreement Preservation (Never Averaged Away)
# ---------------------------------------------------------------------------

def test_cross_modal_line_disagreements_are_observable_not_averaged() -> None:
    """Line comparison must preserve differences distinctly rather than averaging coordinates away."""
    path = _verify_fixture_hash("sparse")
    base_obs = observe(path)
    raster_obs = observe_raster(path, dpi=150.0)

    comparison = compare_vector_and_raster_lines(
        vectors=base_obs.vectors,
        rasters=raster_obs,
        tolerance_pt=3.0,
        page_index=1,
    )

    assert comparison.total_vectors > 0
    assert comparison.total_rasters > 0
    assert len(comparison.matched_pairs) >= 5

    for match in comparison.matched_pairs:
        # Vector y and raster y must remain distinct
        assert match.vector_id != ""
        assert match.raster_id != ""
        assert match.vector_y_pt > 0
        assert match.raster_y_pt > 0
        assert match.disparity_pt == abs(match.delta_y_pt)
        # Vector coordinate must NOT be overwritten or averaged with raster
        assert match.vector_bbox.y0 <= match.vector_y_pt <= match.vector_bbox.y1

    # Now intentionally inject an offset into a raster line to test that disparity is preserved
    injected_delta = 1.75  # points
    modified_rasters = []
    for r in raster_obs:
        dump = r.model_dump()
        dump["bbox"]["y0"] += injected_delta
        dump["bbox"]["y1"] += injected_delta
        if "line_y_page" in dump["extra"]:
            dump["extra"]["line_y_page"] += injected_delta
        modified_rasters.append(RasterObservation(**dump))

    disparity_comparison = compare_vector_and_raster_lines(
        vectors=base_obs.vectors,
        rasters=modified_rasters,
        tolerance_pt=3.0,
        page_index=1,
    )

    # Must find position disparities
    pos_disagreements = [
        d for d in disparity_comparison.disagreements
        if d.kind == CrossModalDisagreementKind.POSITION_DISPARITY
    ]
    assert len(pos_disagreements) > 0, "Injected disparity was not detected as an observable disagreement!"

    for d in pos_disagreements:
        assert d.disparity_pt is not None
        # Disparity must reflect the injected ~1.75 pt offset, NOT 0.0 or an averaged midpoint
        assert d.disparity_pt == pytest.approx(injected_delta, abs=0.5)


def test_cross_modal_unmatched_lines_record_distinct_modalities() -> None:
    """Lines present in only one modality must emit VECTOR_ONLY or RASTER_ONLY disagreements."""
    v_obs = VectorPathObservation(
        id="vec_isolated_1",
        provenance=ObservationProvenance(modality=SourceModality.VECTOR, page_index=1),
        bbox=BoundingBox2D(page_index=1, x0=50.0, y0=50.0, x1=200.0, y1=51.0),
        path_type="line",
    )
    r_obs = RasterObservation(
        id="ras_isolated_1",
        provenance=ObservationProvenance(modality=SourceModality.RASTER, page_index=1),
        bbox=BoundingBox2D(page_index=1, x0=50.0, y0=300.0, x1=200.0, y1=301.0),
        resolution_dpi=144.0,
        pixel_width=1000,
        pixel_height=1000,
        feature_type="region",
        extra={"raster_primitive_type": "line", "line_y_page": 300.5},
    )

    res = compare_vector_and_raster_lines([v_obs], [r_obs], tolerance_pt=3.0, page_index=1)
    assert len(res.matched_pairs) == 0
    assert "vec_isolated_1" in res.vector_only_ids
    assert "ras_isolated_1" in res.raster_only_ids

    kinds = {d.kind for d in res.disagreements}
    assert CrossModalDisagreementKind.VECTOR_ONLY in kinds
    assert CrossModalDisagreementKind.RASTER_ONLY in kinds


def test_cross_modal_text_and_raster_glyph_comparison() -> None:
    """Compare text observations with raster glyph observations preserving center distances and IoU."""
    path = _verify_fixture_hash("text_diversity")
    base_obs = observe(path)
    raster_obs = observe_raster(path, dpi=150.0)

    res = compare_text_and_raster_glyphs(
        texts=base_obs.texts,
        rasters=raster_obs,
        tolerance_pt=10.0,
        page_index=1,
    )

    assert res.total_texts > 0
    assert res.total_rasters > 0
    assert len(res.matched_pairs) > 0

    for m in res.matched_pairs:
        assert m.text_id != ""
        assert m.raster_id != ""
        assert m.disparity_center_pt >= 0.0
        assert 0.0 <= m.overlap_iou <= 1.0


# ---------------------------------------------------------------------------
# 8. Pluggable Extractor Interface (Model Loading Outside Interface)
# ---------------------------------------------------------------------------

def test_custom_extractor_protocol_pluggable() -> None:
    """An external extractor callable can be plugged in without loading ML models in the adapter."""
    path = _verify_fixture_hash("sparse")
    doc = fitz.open(path)
    page = doc[0]

    custom_called = False

    def dummy_custom_extractor(
        image_bytes: bytes,
        prov: RasterTransformProvenance,
        page_index: int,
    ) -> list[RasterObservation]:
        nonlocal custom_called
        custom_called = True
        return [
            RasterObservation(
                id="custom_extractor_obs_1",
                modality=SourceModality.RASTER,
                provenance=ObservationProvenance(
                    modality=SourceModality.RASTER,
                    page_index=page_index,
                    acquisition_adapter="external.custom_model",
                ),
                bbox=BoundingBox2D(page_index=page_index, x0=10.0, y0=20.0, x1=30.0, y1=40.0),
                resolution_dpi=prov.dpi,
                pixel_width=prov.pixel_width,
                pixel_height=prov.pixel_height,
                feature_type="region",
            )
        ]

    obs = extract_raster_observations_for_page(
        page=page,
        page_index=1,
        dpi=150.0,
        extractor=dummy_custom_extractor,
    )
    doc.close()

    assert custom_called, "Custom extractor was not called!"
    assert len(obs) == 1
    assert obs[0].id == "custom_extractor_obs_1"
    assert obs[0].provenance.acquisition_adapter == "external.custom_model"


# ---------------------------------------------------------------------------
# 9. Real-Source Probes (Mutopia & Derek Trucks)
# ---------------------------------------------------------------------------

def test_real_source_probe_mutopia_bach_minuet() -> None:
    """Probe real public score (Bach Minuet) to verify staff line detection and alignment."""
    path = _verify_fixture_hash("mutopia")
    doc = fitz.open(path)
    page = doc[0]

    raw_samples, prov = render_page_deterministic(page, dpi=150.0, color_mode=ColorMode.GRAY)
    raster_lines = extract_raster_line_observations(raw_samples, prov, page_index=1, min_width_ratio=0.3)
    doc.close()

    # Bach Minuet page 1 contains grand staff systems (5 lines each)
    assert len(raster_lines) >= 10, f"Expected at least 10 staff lines in Bach Minuet, got {len(raster_lines)}"

    # Check staff line spacing consistency (~5 pt staff space at LilyPond staff size 20)
    ys = sorted(line_item.line_y_page for line_item in raster_lines)
    gaps = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
    # Staff space in mutopia is ~5 pt
    staff_space_gaps = [g for g in gaps if 4.0 <= g <= 6.0]
    assert len(staff_space_gaps) >= 8, f"Expected consistent ~5pt staff line gaps, got {staff_space_gaps}"


def test_real_source_probe_derek_trucks() -> None:
    """Probe real paired score (Derek Trucks BB King) for lines, glyphs, and non-destructive merge."""
    path = _verify_fixture_hash("derek_trucks")
    base_obs = observe(path)
    raster_obs = observe_raster(path, dpi=150.0)

    # Must extract both lines and glyphs
    line_rasters = [r for r in raster_obs if r.extra.get("raster_primitive_type") == "line"]
    glyph_rasters = [r for r in raster_obs if r.extra.get("raster_primitive_type") == "glyph"]

    assert len(line_rasters) >= 10
    assert len(glyph_rasters) >= 20

    # Cross-modal comparison
    comparison = compare_vector_and_raster_lines(
        vectors=base_obs.vectors,
        rasters=raster_obs,
        tolerance_pt=3.0,
        page_index=1,
    )
    assert len(comparison.matched_pairs) >= 10
    assert comparison.mean_y_disparity_pt is not None
    assert comparison.mean_y_disparity_pt < 1.5  # tight alignment between vector and raster lines


# ---------------------------------------------------------------------------
# 10. Privacy and No-Network Execution Checks
# ---------------------------------------------------------------------------

def test_zero_network_execution_guarantee(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure that all raster operations execute strictly offline with zero socket network calls."""
    def forbidden_connect(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Network connection attempted during offline raster processing!")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)
    if hasattr(socket, "create_connection"):
        monkeypatch.setattr(socket, "create_connection", forbidden_connect)

    path = _verify_fixture_hash("sparse")
    # Execute full pipeline: observe, render, extract, compare
    base_obs = observe(path)
    raster_obs = observe_raster(path, dpi=150.0)
    attached = attach_raster_observations(base_obs, raster_obs)
    res = compare_vector_and_raster_lines(attached.vectors, attached.rasters, page_index=1)

    assert len(raster_obs) > 0
    assert len(res.matched_pairs) > 0
