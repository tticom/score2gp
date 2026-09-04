"""Tests for Local Scale Model (REC-04).

Verifies independent estimation of notation staff space and TAB string space,
support observations, uncertainty quantification, raw/normalized diagnostics,
dimensionless detector policies, scale transformation stability, real public
score provenance, and negative/unsupported controls.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from score2gp.recognition.observations import observe
from score2gp.recognition.scale import (
    DimensionlessDetectorPolicy,
    ScaleStatus,
    StaffKind,
    UnsupportedScaleError,
    denormalize_dimension,
    estimate_local_scales,
    estimate_page_scale,
    estimate_scales_for_document,
    normalize_dimension,
)
from score2gp.recognition.schemas import (
    BoundingBox2D,
    DocumentObservations,
    ObservationProvenance,
    Point2D,
    ScaleEstimate,
    SourceModality,
    VectorPathObservation,
)

FIXTURES_DIR = Path("tests/fixtures/pdf")
PUBLIC_FIXTURES_DIR = Path("fixtures/public")

PAIRED_PDF = FIXTURES_DIR / "generated_paired_notation_tab_system.pdf"
SPARSE_NOTATION_PDF = FIXTURES_DIR / "generated_standard_staff_sparse.pdf"
TINY_TAB_PDF = FIXTURES_DIR / "generated_tiny_tab.pdf"
REAL_SCORE_MUTOPIA = PUBLIC_FIXTURES_DIR / "mutopia-bwv-anh-120-minuet-a-minor-a4.pdf"
REAL_SCORE_DEREK_TRUCKS = PUBLIC_FIXTURES_DIR / "Derek Trucks BB King.pdf"


# ---------------------------------------------------------------------------
# Real Scores Validation (At least two real scores with different scales)
# ---------------------------------------------------------------------------

def test_real_score_mutopia_notation_scale() -> None:
    """Verify real classical notation score produces clean notation scale without TAB."""
    assert REAL_SCORE_MUTOPIA.exists(), f"Missing real fixture: {REAL_SCORE_MUTOPIA}"
    obs = observe(REAL_SCORE_MUTOPIA)
    page_scale = estimate_page_scale(obs, page_index=1)

    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is not None
    # Real Mutopia Bach Minuet has staff space around 4.98 pt
    assert 4.80 <= page_scale.notation_staff_space <= 5.15
    # Classical score has no tablature staves
    assert page_scale.tab_string_space is None
    assert page_scale.stroke_thickness is not None
    assert 0.35 <= page_scale.stroke_thickness <= 0.65

    # Uncertainty must be low for clean engraved score
    assert page_scale.uncertainty is not None
    assert page_scale.uncertainty.sample_count >= 20
    assert page_scale.uncertainty.standard_deviation < 0.10
    assert page_scale.uncertainty.confidence > 0.90

    # Local estimates must all be notation staves
    local_staves = estimate_local_scales(obs, page_index=1)
    assert len(local_staves) >= 6
    for staff in local_staves:
        assert staff.support.staff_kind == StaffKind.NOTATION
        assert staff.notation_staff_space is not None
        assert staff.tab_string_space is None
        assert 4.80 <= staff.notation_staff_space <= 5.15


def test_real_score_derek_trucks_paired_notation_and_tab() -> None:
    """Verify real paired notation+TAB score estimates both scales independently."""
    assert REAL_SCORE_DEREK_TRUCKS.exists(), f"Missing real fixture: {REAL_SCORE_DEREK_TRUCKS}"
    obs = observe(REAL_SCORE_DEREK_TRUCKS)
    page_scale = estimate_page_scale(obs, page_index=1)

    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is not None

    # Verify that notation space (~4.25 pt) and TAB space (~6.38 pt) do NOT collapse
    assert 4.10 <= page_scale.notation_staff_space <= 4.40
    assert 6.20 <= page_scale.tab_string_space <= 6.55
    assert page_scale.notation_staff_space != page_scale.tab_string_space
    diff = abs(page_scale.tab_string_space - page_scale.notation_staff_space)
    assert diff > 1.8, "Notation and TAB spaces must be distinct, not collapsed"

    # Local systems must identify both notation and TAB staves
    local_staves = estimate_local_scales(obs, page_index=1)
    notation_staves = [s for s in local_staves if s.support.staff_kind == StaffKind.NOTATION]
    tab_staves = [s for s in local_staves if s.support.staff_kind == StaffKind.TAB]

    assert len(notation_staves) >= 4
    assert len(tab_staves) >= 4

    for s in notation_staves:
        assert s.notation_staff_space is not None
        assert s.tab_string_space is None
        assert 4.10 <= s.notation_staff_space <= 4.40

    for s in tab_staves:
        assert s.tab_string_space is not None
        assert s.notation_staff_space is None
        assert 6.20 <= s.tab_string_space <= 6.55


# ---------------------------------------------------------------------------
# Multi-modality and Mixed-Scale Fixtures
# ---------------------------------------------------------------------------

def test_paired_notation_tab_fixture_independent_estimation() -> None:
    """Verify synthetic paired notation+tab fixture estimates independent scales."""
    assert PAIRED_PDF.exists(), f"Missing fixture: {PAIRED_PDF}"
    obs = observe(PAIRED_PDF)

    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED

    # Ground truth from JSON specification: notation=8.5, tab=6.4
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is not None
    assert abs(page_scale.notation_staff_space - 8.5) < 0.05
    assert abs(page_scale.tab_string_space - 6.4) < 0.05

    # Stroke thickness: 0.5 for notation, 0.6 for tab -> median 0.55
    assert page_scale.stroke_thickness is not None
    assert abs(page_scale.stroke_thickness - 0.55) < 0.05

    # Diagnostics check
    diag = page_scale.diagnostics
    assert len(diag.raw_gaps) == 9  # 4 notation gaps + 5 tab gaps
    assert len(diag.normalized_gaps) == 9
    for norm_g in diag.normalized_gaps:
        assert abs(norm_g - 1.0) < 0.05, f"Normalized gap must be ~1.0, got {norm_g}"

    # Local estimates
    locals_ = estimate_local_scales(obs, page_index=1)
    assert len(locals_) == 2
    not_staff = next(s for s in locals_ if s.support.staff_kind == StaffKind.NOTATION)
    tab_staff = next(s for s in locals_ if s.support.staff_kind == StaffKind.TAB)

    assert abs(not_staff.notation_staff_space - 8.5) < 0.05
    assert not_staff.tab_string_space is None
    assert abs(tab_staff.tab_string_space - 6.4) < 0.05
    assert tab_staff.notation_staff_space is None


def test_tiny_tab_only_fixture() -> None:
    """Verify pure TAB fixture yields tab_string_space and no notation_staff_space."""
    assert TINY_TAB_PDF.exists(), f"Missing fixture: {TINY_TAB_PDF}"
    obs = observe(TINY_TAB_PDF)

    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is None
    assert page_scale.tab_string_space is not None
    assert abs(page_scale.tab_string_space - 14.0) < 0.10
    assert page_scale.stroke_thickness == 0.6


def test_sparse_notation_only_fixture() -> None:
    """Verify pure notation fixture yields notation_staff_space and no tab_string_space."""
    assert SPARSE_NOTATION_PDF.exists(), f"Missing fixture: {SPARSE_NOTATION_PDF}"
    obs = observe(SPARSE_NOTATION_PDF)

    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is None
    assert abs(page_scale.notation_staff_space - 8.5) < 0.05
    assert page_scale.stroke_thickness == 0.5


# ---------------------------------------------------------------------------
# Synthetic Transformation and Scale Invariance Tests
# ---------------------------------------------------------------------------

def _build_synthetic_staff_obs(
    line_count: int = 5,
    base_y: float = 100.0,
    gap: float = 10.0,
    width: float = 300.0,
    stroke_width: float = 0.5,
    scale_factor: float = 1.0,
    y_offset: float = 0.0,
) -> DocumentObservations:
    vectors: list[VectorPathObservation] = []
    scaled_gap = gap * scale_factor
    scaled_w = width * scale_factor
    scaled_sw = stroke_width * scale_factor
    start_y = (base_y + y_offset) * scale_factor

    for i in range(line_count):
        y = start_y + i * scaled_gap
        vectors.append(
            VectorPathObservation(
                id=f"synth_line_{i}",
                modality=SourceModality.VECTOR,
                path_type="line",
                points=[Point2D(x=50.0 * scale_factor, y=y), Point2D(x=(50.0 + scaled_w), y=y)],
                bbox=BoundingBox2D(page_index=1, x0=50.0 * scale_factor, y0=y, x1=(50.0 + scaled_w), y1=y),
                stroke_width=scaled_sw,
                provenance=ObservationProvenance(page_index=1, raw_primitive_id=f"raw_s_{i}"),
            )
        )
    return DocumentObservations(
        document_id=f"synth_doc_scale_{scale_factor}",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )


@pytest.mark.parametrize("scale_factor", [0.75, 1.0, 1.5, 2.0, 3.25])
def test_scale_invariance_normalized_data_stability(scale_factor: float) -> None:
    """Acceptance: Equivalent layouts at different sizes produce materially stable normalized data."""
    base_gap = 12.0
    base_sw = 0.6
    obs = _build_synthetic_staff_obs(line_count=5, gap=base_gap, stroke_width=base_sw, scale_factor=scale_factor)

    est = estimate_page_scale(obs, page_index=1)
    assert est.status == ScaleStatus.ESTIMATED
    assert est.notation_staff_space is not None
    expected_space = base_gap * scale_factor
    assert abs(est.notation_staff_space - expected_space) < 1e-4

    # Normalized gaps must be identically 1.0
    assert len(est.diagnostics.normalized_gaps) == 4
    for norm_g in est.diagnostics.normalized_gaps:
        assert abs(norm_g - 1.0) < 1e-4

    # Normalized stroke width must be constant regardless of scale_factor
    expected_norm_sw = base_sw / base_gap  # 0.6 / 12.0 = 0.05
    for norm_sw in est.diagnostics.normalized_stroke_widths:
        assert abs(norm_sw - expected_norm_sw) < 1e-4


@pytest.mark.parametrize("y_offset", [0.0, 45.0, 120.0, 500.0])
def test_translation_invariance(y_offset: float) -> None:
    """Verify scale estimation is strictly invariant to vertical translation."""
    obs = _build_synthetic_staff_obs(line_count=5, gap=10.0, y_offset=y_offset)
    est = estimate_page_scale(obs, page_index=1)
    assert est.status == ScaleStatus.ESTIMATED
    assert est.notation_staff_space == 10.0


def test_collinear_fragmented_lines_reconstruction() -> None:
    """Verify split line fragments (e.g. fret cutouts) do not create duplicate line levels."""
    # Create a 6-line staff where line index 2 is split into 2 horizontal fragments
    vectors: list[VectorPathObservation] = []
    y_start = 100.0
    gap = 8.0
    for i in range(6):
        y = y_start + i * gap
        if i == 2:
            # Fragment 1: x 20..120
            vectors.append(
                VectorPathObservation(
                    id="frag_1",
                    modality=SourceModality.VECTOR,
                    path_type="line",
                    points=[Point2D(x=20.0, y=y), Point2D(x=120.0, y=y)],
                    bbox=BoundingBox2D(page_index=1, x0=20.0, y0=y, x1=120.0, y1=y),
                    stroke_width=0.5,
                    provenance=ObservationProvenance(page_index=1, raw_primitive_id="raw_f1"),
                )
            )
            # Fragment 2: x 140..250 (gap for fret digit)
            vectors.append(
                VectorPathObservation(
                    id="frag_2",
                    modality=SourceModality.VECTOR,
                    path_type="line",
                    points=[Point2D(x=140.0, y=y), Point2D(x=250.0, y=y)],
                    bbox=BoundingBox2D(page_index=1, x0=140.0, y0=y, x1=250.0, y1=y),
                    stroke_width=0.5,
                    provenance=ObservationProvenance(page_index=1, raw_primitive_id="raw_f2"),
                )
            )
        else:
            vectors.append(
                VectorPathObservation(
                    id=f"line_{i}",
                    modality=SourceModality.VECTOR,
                    path_type="line",
                    points=[Point2D(x=20.0, y=y), Point2D(x=250.0, y=y)],
                    bbox=BoundingBox2D(page_index=1, x0=20.0, y0=y, x1=250.0, y1=y),
                    stroke_width=0.5,
                    provenance=ObservationProvenance(page_index=1, raw_primitive_id=f"raw_{i}"),
                )
            )

    obs = DocumentObservations(
        document_id="doc_frag",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )
    est = estimate_page_scale(obs, page_index=1)
    assert est.status == ScaleStatus.ESTIMATED
    assert est.tab_string_space == 8.0
    # Both fragment observation IDs must be retained in support
    assert "frag_1" in est.support.vector_observation_ids
    assert "frag_2" in est.support.vector_observation_ids


# ---------------------------------------------------------------------------
# State Distinctions and Negative Controls
# ---------------------------------------------------------------------------

def test_empty_document_returns_unsupported() -> None:
    """Requirement 5: Return Unsupported rather than a default scale when evidence is inadequate."""
    obs = DocumentObservations(
        document_id="doc_empty",
        page_count=1,
        vectors=[],
        texts=[],
        rasters=[],
    )

    # Diagnostic mode: returns typed estimate with UNSUPPORTED status
    est = estimate_page_scale(obs, page_index=1, raise_on_unsupported=False)
    assert est.status == ScaleStatus.UNSUPPORTED
    assert est.notation_staff_space is None
    assert est.tab_string_space is None
    assert est.error_message is not None

    # Strict mode: raises UnsupportedScaleError
    with pytest.raises(UnsupportedScaleError):
        estimate_page_scale(obs, page_index=1, raise_on_unsupported=True)


def test_insufficient_lines_under_minimum_count() -> None:
    """Verify 3 lines (less than minimum 4) returns UNSUPPORTED."""
    obs = _build_synthetic_staff_obs(line_count=3, gap=10.0)
    est = estimate_page_scale(obs, page_index=1, raise_on_unsupported=False)
    assert est.status == ScaleStatus.UNSUPPORTED
    assert est.notation_staff_space is None
    assert est.tab_string_space is None


def test_random_irregular_lines_rejected() -> None:
    """Verify irregular non-periodic lines do not result in a false scale."""
    vectors: list[VectorPathObservation] = []
    # Gaps: 5.0, 22.0, 7.0, 31.0 (random, non-periodic)
    for i, y in enumerate([10.0, 15.0, 37.0, 44.0, 75.0]):
        vectors.append(
            VectorPathObservation(
                id=f"v_noise_{i}",
                modality=SourceModality.VECTOR,
                path_type="line",
                points=[Point2D(x=10.0, y=y), Point2D(x=200.0, y=y)],
                bbox=BoundingBox2D(page_index=1, x0=10.0, y0=y, x1=200.0, y1=y),
                stroke_width=0.5,
                provenance=ObservationProvenance(page_index=1, raw_primitive_id=f"raw_n_{i}"),
            )
        )
    obs = DocumentObservations(
        document_id="doc_noise",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )
    est = estimate_page_scale(obs, page_index=1, raise_on_unsupported=False)
    assert est.status == ScaleStatus.UNSUPPORTED
    assert est.notation_staff_space is None
    assert est.tab_string_space is None


def test_invalid_page_index_error() -> None:
    """Verify out-of-bounds page index handling."""
    obs = _build_synthetic_staff_obs(line_count=5, gap=10.0)
    est = estimate_page_scale(obs, page_index=2, raise_on_unsupported=False)
    assert est.status == ScaleStatus.UNSUPPORTED
    assert "out of bounds" in est.error_message

    with pytest.raises(UnsupportedScaleError):
        estimate_page_scale(obs, page_index=2, raise_on_unsupported=True)


# ---------------------------------------------------------------------------
# Dimensionless Detector Policies and Boundary Discrimination Tests
# ---------------------------------------------------------------------------

def test_dimensionless_normalization_helpers() -> None:
    """Verify normalize_dimension and denormalize_dimension roundtrip."""
    scale = 10.0
    val = 15.0
    norm = normalize_dimension(val, scale)
    assert norm == 1.5
    denorm = denormalize_dimension(norm, scale)
    assert denorm == 15.0

    with pytest.raises(ValueError):
        normalize_dimension(10.0, 0.0)
    with pytest.raises(ValueError):
        denormalize_dimension(1.0, -2.0)


def test_detector_policy_notehead_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_notehead."""
    sp = 10.0
    # Notehead: height [0.70, 1.45] sp, width [0.75, 1.85] sp
    # Exactly inside
    assert DimensionlessDetectorPolicy.is_notehead(width=12.0, height=10.0, staff_space=sp)

    # Height just inside vs just outside
    assert DimensionlessDetectorPolicy.is_notehead(width=12.0, height=7.1, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_notehead(width=12.0, height=6.9, staff_space=sp)
    assert DimensionlessDetectorPolicy.is_notehead(width=12.0, height=14.4, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_notehead(width=12.0, height=14.6, staff_space=sp)

    # Width just inside vs just outside
    assert DimensionlessDetectorPolicy.is_notehead(width=7.6, height=10.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_notehead(width=7.4, height=10.0, staff_space=sp)
    assert DimensionlessDetectorPolicy.is_notehead(width=18.4, height=10.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_notehead(width=18.6, height=10.0, staff_space=sp)


def test_detector_policy_beam_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_beam."""
    sp = 10.0
    # Beam: width >= 0.50 sp, height <= 0.85 sp, aspect >= 1.80
    assert DimensionlessDetectorPolicy.is_beam(width=20.0, height=4.0, staff_space=sp)

    # Height boundary
    assert DimensionlessDetectorPolicy.is_beam(width=20.0, height=8.4, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_beam(width=20.0, height=8.6, staff_space=sp)

    # Width boundary
    assert DimensionlessDetectorPolicy.is_beam(width=5.1, height=2.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_beam(width=4.9, height=2.0, staff_space=sp)

    # Aspect ratio boundary
    assert DimensionlessDetectorPolicy.is_beam(width=10.0, height=5.0, staff_space=sp)  # aspect 2.0 >= 1.8
    assert not DimensionlessDetectorPolicy.is_beam(width=10.0, height=6.0, staff_space=sp)  # aspect 1.66 < 1.8


def test_detector_policy_barline_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_barline."""
    sp = 10.0
    # 5-line staff: expected height 4.0 sp (40.0 pt). Tol: 0.55 sp (5.5 pt). Max width: 0.35 sp (3.5 pt)
    assert DimensionlessDetectorPolicy.is_barline(width=1.0, height=40.0, staff_space=sp, line_count=5)

    # Just inside tolerance (40.0 ± 5.4 pt)
    assert DimensionlessDetectorPolicy.is_barline(width=1.0, height=45.4, staff_space=sp, line_count=5)
    assert DimensionlessDetectorPolicy.is_barline(width=1.0, height=34.6, staff_space=sp, line_count=5)
    # Just outside tolerance (40.0 ± 5.6 pt)
    assert not DimensionlessDetectorPolicy.is_barline(width=1.0, height=45.6, staff_space=sp, line_count=5)
    assert not DimensionlessDetectorPolicy.is_barline(width=1.0, height=34.4, staff_space=sp, line_count=5)

    # Width boundary
    assert DimensionlessDetectorPolicy.is_barline(width=3.4, height=40.0, staff_space=sp, line_count=5)
    assert not DimensionlessDetectorPolicy.is_barline(width=3.6, height=40.0, staff_space=sp, line_count=5)

    # 6-line staff: expected height 5.0 sp (50.0 pt)
    assert DimensionlessDetectorPolicy.is_barline(width=1.0, height=50.0, staff_space=sp, line_count=6)
    assert not DimensionlessDetectorPolicy.is_barline(width=1.0, height=40.0, staff_space=sp, line_count=6)


def test_detector_policy_fret_digit_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_fret_digit."""
    string_sp = 8.0
    # Fret digit: height [0.40, 1.30] sp, width [0.20, 1.60] sp
    assert DimensionlessDetectorPolicy.is_fret_digit(width=5.0, height=6.0, string_space=string_sp)
    assert not DimensionlessDetectorPolicy.is_fret_digit(width=5.0, height=3.0, string_space=string_sp)
    assert not DimensionlessDetectorPolicy.is_fret_digit(width=5.0, height=11.0, string_space=string_sp)


def test_detector_policy_stem_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_stem."""
    sp = 10.0
    # Stem: height [1.80, 5.00] sp, width <= 0.30 sp
    assert DimensionlessDetectorPolicy.is_stem(width=1.0, height=30.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_stem(width=1.0, height=15.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_stem(width=1.0, height=55.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_stem(width=3.5, height=30.0, staff_space=sp)


# ---------------------------------------------------------------------------
# Integration with DocumentObservations
# ---------------------------------------------------------------------------

def test_estimate_scales_for_document_populates_scale_estimates() -> None:
    """Verify estimate_scales_for_document populates DocumentObservations.scale_estimates."""
    assert PAIRED_PDF.exists()
    obs = observe(PAIRED_PDF)
    assert len(obs.scale_estimates) == 0

    enriched = estimate_scales_for_document(obs)
    assert len(enriched.scale_estimates) == obs.page_count
    assert "page-1" in enriched.scale_estimates

    p1_scale = enriched.scale_estimates["page-1"]
    assert isinstance(p1_scale, ScaleEstimate)
    assert p1_scale.notation_staff_space is not None
    assert p1_scale.tab_string_space is not None
    assert abs(p1_scale.notation_staff_space - 8.5) < 0.05
    assert abs(p1_scale.tab_string_space - 6.4) < 0.05
