"""Tests for Local Scale Model (REC-04).

Verifies independent estimation of notation staff space and TAB string space,
support observations, uncertainty quantification, raw/normalized diagnostics,
dimensionless detector policies, scale transformation stability, real public
score provenance, and negative/unsupported controls.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import statistics
from typing import Any
import pymupdf
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
# Pinned Authoritative Source Specifications and Extraction Provenance
# ---------------------------------------------------------------------------

MUTOPIA_SOURCE_ORACLE: dict[str, Any] = {
    "sha256": "86435e170268a04201966492e120371348abbc7d77712221e362b91d97832eeb",
    "authority": "LilyPond 2.12.1 engraving specification (#(set-global-staff-size 20))",
    "receipt": (
        "LilyPond Emmentaler-20 font design specification defines staff design height = 19.9253 pt "
        "across 4 staff spaces; standard notehead height = 1.0 staff space = 4.9813 pt. "
        "Measured dynamically at test time from PDF primitives via _extract_independent_pdf_glyph_oracle."
    ),
}

DEREK_TRUCKS_SOURCE_ORACLE: dict[str, Any] = {
    "sha256": "e2b80e6fa6ad9aac8b648d501e2606086a538aa1c040b345d340bda3f5fd4b27",
    "authority": (
        "Cherry Lane standard guitar paired score engraving specification "
        "(1.50mm notation staff space / 2.25mm tab string space)"
    ),
    "receipt": (
        "Notation staff space = 1.50 mm (4.2520 pt); TAB string space = 2.25 mm (6.3779 pt); "
        "rendered fret digits in ArialRegular = 7.00 pt; standard notehead height = 4.2520 pt. "
        "Measured dynamically at test time from PDF primitives via _extract_independent_pdf_glyph_oracle."
    ),
}

PAIRED_SOURCE_ORACLE: dict[str, Any] = {
    "sha256": "31669e6c264ed6e48423c0901f853e7fa93564fd0aa60cdc4189c53a8796dcad",
    "authority": "fixtures/public/generated_paired_notation_tab_system.json",
    "receipt": (
        "JSON specification line_gap=8.5 for notation, 6.4 for tab; "
        "Courier fret digit span bounding box height measured directly from PyMuPDF dict = 6.8695 pt."
    ),
}

TINY_TAB_SOURCE_ORACLE: dict[str, Any] = {
    "sha256": "7917b8cae7e3da9c7888a28204743e882b6d4fe4a703225e33c90b8d85274fed",
    "authority": "tests/fixtures/pdf/make_generated_tiny_tab_pdf.py",
    "receipt": (
        "line_ys = [120, 134, 148, 162, 176, 190] (string gap = 14.0 pt); "
        "Courier fret digit span bounding box height measured directly from PyMuPDF dict = 12.4900 pt."
    ),
}

SPARSE_NOTATION_SOURCE_ORACLE: dict[str, Any] = {
    "sha256": "47a2a3a5b641910fdf540b28dd0a9c5d3ecbfa465bd238f1d6ba0b3dd0fe01fd",
    "authority": "tests/fixtures/pdf/generated_standard_staff_sparse.pdf",
    "receipt": "Synthetic 5-line notation staff with line_gap = 8.5 pt and no text/font glyphs.",
}


# ---------------------------------------------------------------------------
# Independent Reproducible PyMuPDF Primitives Geometry Oracles
# ---------------------------------------------------------------------------


def _extract_independent_pdf_line_geometry(
    pdf_path: Path, expected_sha256: str, page_index: int = 1
) -> dict[str, Any]:
    """Reproducible independent oracle measuring staff line geometry directly from PyMuPDF drawings.

    Bypasses score2gp.recognition.scale entirely and directly inspects raw PDF vector
    drawings to measure:
      - notation staff space (median gap among 5-line staff line groups)
      - TAB string space (median gap among 6-line staff line groups)
      - stroke thickness (median stroke width of staff lines)

    Verifies the pinned SHA-256 byte provenance before extraction.
    """
    assert pdf_path.exists(), f"Missing PDF fixture: {pdf_path}"
    actual_sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert actual_sha == expected_sha256, (
        f"PDF fixture SHA-256 mismatch for {pdf_path.name}: "
        f"expected {expected_sha256}, got {actual_sha}"
    )

    doc = pymupdf.open(pdf_path)
    page = doc[page_index - 1]
    drawings = page.get_drawings()

    raw_lines: list[tuple[float, float, float, float]] = []
    for d in drawings:
        w = d.get("width")
        if w is None:
            w = 0.5
        for item in d["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) <= 0.2 and abs(p1.x - p2.x) >= 20.0:
                    raw_lines.append(
                        (
                            (p1.y + p2.y) / 2.0,
                            min(p1.x, p2.x),
                            max(p1.x, p2.x),
                            float(w),
                        )
                    )
            elif item[0] == "re":
                r = item[1]
                dx = abs(r.x1 - r.x0)
                dy = abs(r.y1 - r.y0)
                if dx >= 20.0 and dy <= 2.5:
                    raw_lines.append(
                        (
                            (r.y0 + r.y1) / 2.0,
                            min(r.x0, r.x1),
                            max(r.x0, r.x1),
                            float(dy),
                        )
                    )

    raw_lines.sort(key=lambda item: item[0])
    y_levels: list[list[tuple[float, float, float, float]]] = []
    for line in raw_lines:
        matched = False
        for grp in y_levels:
            if abs(line[0] - grp[0][0]) <= 0.5:
                grp.append(line)
                matched = True
                break
        if not matched:
            y_levels.append([line])

    level_data: list[tuple[float, float, float]] = []
    for grp in y_levels:
        min_x = min(seg[1] for seg in grp)
        max_x = max(seg[2] for seg in grp)
        span = max_x - min_x
        if span >= 50.0:
            med_y = statistics.median(seg[0] for seg in grp)
            sw_vals = [seg[3] for seg in grp if seg[3] is not None]
            med_sw = statistics.median(sw_vals) if sw_vals else 0.5
            level_data.append((med_y, span, med_sw))

    level_data.sort(key=lambda x: x[0])
    notation_gaps: list[float] = []
    tab_gaps: list[float] = []
    stroke_widths = [x[2] for x in level_data if x[2] is not None]

    cur_group = [level_data[0]] if level_data else []
    for item in level_data[1:]:
        gap = item[0] - cur_group[-1][0]
        if len(cur_group) == 1:
            if 2.0 <= gap <= 25.0:
                cur_group.append(item)
            else:
                cur_group = [item]
        else:
            prev_gaps = [
                cur_group[i + 1][0] - cur_group[i][0] for i in range(len(cur_group) - 1)
            ]
            med_g = statistics.median(prev_gaps)
            if abs(gap - med_g) <= 0.8:
                cur_group.append(item)
            else:
                if len(cur_group) == 5:
                    notation_gaps.extend(prev_gaps)
                elif len(cur_group) == 6:
                    tab_gaps.extend(prev_gaps)
                cur_group = [item]
    if len(cur_group) == 5:
        notation_gaps.extend(
            [cur_group[i + 1][0] - cur_group[i][0] for i in range(len(cur_group) - 1)]
        )
    elif len(cur_group) == 6:
        tab_gaps.extend(
            [cur_group[i + 1][0] - cur_group[i][0] for i in range(len(cur_group) - 1)]
        )

    return {
        "notation_staff_space": (
            round(statistics.median(notation_gaps), 4) if notation_gaps else None
        ),
        "tab_string_space": (
            round(statistics.median(tab_gaps), 4) if tab_gaps else None
        ),
        "stroke_thickness": (
            round(statistics.median(stroke_widths), 4) if stroke_widths else None
        ),
    }


def _extract_independent_pdf_glyph_oracle(
    pdf_path: Path, expected_sha256: str, page_index: int = 1
) -> dict[str, float | None]:
    """Independent oracle extracting rendered glyph and digit metrics directly from PDF primitives.

    Bypasses score2gp.recognition.scale entirely and inspects raw PyMuPDF page text
    and font descriptors to measure:
      - rendered_digit_height: physical bounding box height of on-staff fret digits or
        time-signature numerals, applying explicit selection rules that isolate relevant
        musical staff digits from unrelated header/footer text and measure numbers.
      - music_font_scale: physical scale of standard 4-space music font glyphs (e.g.
        Emmentaler, Bravura) derived from the font design size / 4.0 in the PDF font descriptor.
      - glyph_scale: primary characteristic glyph scale (music font notehead scale if present,
        otherwise rendered fret digit height).

    Verifies the pinned SHA-256 byte provenance before extraction.
    """
    assert pdf_path.exists(), f"Missing PDF fixture: {pdf_path}"
    actual_sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert actual_sha == expected_sha256, (
        f"PDF fixture SHA-256 mismatch for {pdf_path.name}: "
        f"expected {expected_sha256}, got {actual_sha}"
    )

    doc = pymupdf.open(pdf_path)
    page = doc[page_index - 1]

    # Explicit selection rule 1: Staff Locality.
    # Identify the vertical span of musical staves from drawings to reject
    # header metadata (title, composer, tuning) and footer metadata (credits, license).
    drawings = page.get_drawings()
    line_ys: list[float] = []
    for d in drawings:
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) <= 0.2 and abs(p1.x - p2.x) >= 20.0:
                    line_ys.append((p1.y + p2.y) / 2.0)
            elif item[0] == "re":
                r = item[1]
                if abs(r.x1 - r.x0) >= 20.0 and abs(r.y1 - r.y0) <= 2.5:
                    line_ys.append((r.y0 + r.y1) / 2.0)

    min_staff_y = min(line_ys) - 15.0 if line_ys else 0.0
    max_staff_y = max(line_ys) + 15.0 if line_ys else 9999.0

    text_dict = page.get_text("dict")
    digit_heights: list[float] = []
    music_font_scales: list[float] = []

    for b in text_dict.get("blocks", []):
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox", (0, 0, 0, 0))
                y0, y1 = bbox[1], bbox[3]

                # Selection rule 1: must be within the active vertical staff region
                if not (min_staff_y <= y0 and y1 <= max_staff_y):
                    continue

                font = span.get("font", "")
                font_lower = font.lower()
                text = span.get("text", "").strip()
                if not text:
                    continue

                # Selection rule 2: Role separation.
                # Exclude non-musical annotations (measure numbers, tempo, technique text)
                # which use standard body/serif fonts (Century Schoolbook, Times New Roman).
                is_annotation_font = any(
                    af in font_lower for af in ["centuryschl", "timesnewroman"]
                )

                # Fret digits on TAB staves:
                if text.isdigit() and not is_annotation_font:
                    h = y1 - y0
                    digit_heights.append(float(h))

                # Music fonts (e.g. Emmentaler, Bravura):
                if any(mf in font_lower for mf in ["emmentaler", "bravura"]):
                    sz = span.get("size", 0.0)
                    if sz > 0:
                        # In standard music engraving fonts, font size represents the 4-space staff height
                        music_font_scales.append(float(sz) / 4.0)

    med_digit = round(statistics.median(digit_heights), 4) if digit_heights else None
    med_music = (
        round(statistics.median(music_font_scales), 4) if music_font_scales else None
    )
    primary_glyph_scale = med_music if med_music is not None else med_digit

    return {
        "rendered_digit_height": med_digit,
        "music_font_scale": med_music,
        "glyph_scale": primary_glyph_scale,
    }


def _extract_independent_rendered_digit_height(
    pdf_path: Path, expected_sha256: str, page_index: int = 1
) -> float | None:
    """Independent oracle measuring raw rendered text bounding box heights for fret digits."""
    return _extract_independent_pdf_glyph_oracle(
        pdf_path, expected_sha256, page_index=page_index
    )["rendered_digit_height"]


# ---------------------------------------------------------------------------
# Real Scores Validation (At least two real scores with different scales)
# ---------------------------------------------------------------------------


def test_real_score_mutopia_notation_scale() -> None:
    """Verify real classical notation score produces clean notation scale matching independent oracle."""
    line_oracle = _extract_independent_pdf_line_geometry(
        REAL_SCORE_MUTOPIA, MUTOPIA_SOURCE_ORACLE["sha256"], page_index=1
    )
    glyph_oracle = _extract_independent_pdf_glyph_oracle(
        REAL_SCORE_MUTOPIA, MUTOPIA_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert line_oracle["notation_staff_space"] is not None
    assert line_oracle["tab_string_space"] is None
    assert line_oracle["stroke_thickness"] is not None
    assert glyph_oracle["glyph_scale"] is not None

    obs = observe(REAL_SCORE_MUTOPIA)
    page_scale = estimate_page_scale(obs, page_index=1)

    assert page_scale.status == ScaleStatus.ESTIMATED
    # Compare directly against independent PyMuPDF oracle measurement (~4.9812 pt)
    assert page_scale.notation_staff_space is not None
    assert (
        abs(page_scale.notation_staff_space - line_oracle["notation_staff_space"])
        < 1e-3
    )
    assert page_scale.tab_string_space is None
    assert page_scale.stroke_thickness is not None
    assert abs(page_scale.stroke_thickness - line_oracle["stroke_thickness"]) < 0.10

    # Glyph scale must match independent PyMuPDF glyph oracle (~4.9813 pt from Emmentaler-20)
    assert page_scale.glyph_scale is not None
    assert abs(page_scale.glyph_scale - glyph_oracle["glyph_scale"]) < 1e-3
    assert abs(page_scale.glyph_scale - page_scale.notation_staff_space) < 0.20
    assert glyph_oracle["music_font_scale"] == 4.9813

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
        assert abs(staff.notation_staff_space - line_oracle["notation_staff_space"]) < 0.10


def test_real_score_derek_trucks_paired_notation_and_tab() -> None:
    """Verify real paired notation+TAB score estimates both scales matching independent oracle."""
    line_oracle = _extract_independent_pdf_line_geometry(
        REAL_SCORE_DEREK_TRUCKS, DEREK_TRUCKS_SOURCE_ORACLE["sha256"], page_index=1
    )
    glyph_oracle = _extract_independent_pdf_glyph_oracle(
        REAL_SCORE_DEREK_TRUCKS, DEREK_TRUCKS_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert line_oracle["notation_staff_space"] is not None
    assert line_oracle["tab_string_space"] is not None
    assert (
        abs(line_oracle["tab_string_space"] - line_oracle["notation_staff_space"])
        > 1.8
    )

    obs = observe(REAL_SCORE_DEREK_TRUCKS)
    page_scale = estimate_page_scale(obs, page_index=1)

    assert page_scale.status == ScaleStatus.ESTIMATED
    # Compare directly against independent PyMuPDF oracle measurements (notation ~4.252 pt, tab ~6.378 pt)
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is not None
    assert (
        abs(page_scale.notation_staff_space - line_oracle["notation_staff_space"])
        < 1e-3
    )
    assert (
        abs(page_scale.tab_string_space - line_oracle["tab_string_space"]) < 1e-3
    )
    assert page_scale.notation_staff_space != page_scale.tab_string_space
    diff = abs(page_scale.tab_string_space - page_scale.notation_staff_space)
    assert diff > 1.8, "Notation and TAB spaces must be distinct, not collapsed"

    # Glyph scale matches independent PyMuPDF glyph oracle (~4.2520 pt)
    assert page_scale.glyph_scale is not None
    assert abs(page_scale.glyph_scale - glyph_oracle["glyph_scale"]) < 1e-3
    # Rendered fret digit height on TAB staves matches independent PyMuPDF text-bbox oracle (7.0 pt)
    assert glyph_oracle["rendered_digit_height"] == 7.0
    assert glyph_oracle["music_font_scale"] == 4.252

    # Local systems must identify both notation and TAB staves
    local_staves = estimate_local_scales(obs, page_index=1)
    notation_staves = [
        s for s in local_staves if s.support.staff_kind == StaffKind.NOTATION
    ]
    tab_staves = [s for s in local_staves if s.support.staff_kind == StaffKind.TAB]

    assert len(notation_staves) >= 4
    assert len(tab_staves) >= 4

    for s in notation_staves:
        assert s.notation_staff_space is not None
        assert s.tab_string_space is None
        assert abs(s.notation_staff_space - line_oracle["notation_staff_space"]) < 0.10

    for s in tab_staves:
        assert s.tab_string_space is not None
        assert s.notation_staff_space is None
        assert abs(s.tab_string_space - line_oracle["tab_string_space"]) < 0.10


# ---------------------------------------------------------------------------
# Multi-modality and Mixed-Scale Fixtures
# ---------------------------------------------------------------------------


def test_paired_notation_tab_fixture_independent_estimation() -> None:
    """Verify synthetic paired notation+tab fixture estimates independent scales matching oracle."""
    line_oracle = _extract_independent_pdf_line_geometry(
        PAIRED_PDF, PAIRED_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert line_oracle["notation_staff_space"] == 8.5
    assert line_oracle["tab_string_space"] == 6.4

    glyph_oracle = _extract_independent_pdf_glyph_oracle(
        PAIRED_PDF, PAIRED_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert glyph_oracle["rendered_digit_height"] == 6.8695

    obs = observe(PAIRED_PDF)
    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED

    # Compare directly against independent PyMuPDF oracle measurements
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is not None
    assert (
        abs(page_scale.notation_staff_space - line_oracle["notation_staff_space"])
        < 1e-3
    )
    assert (
        abs(page_scale.tab_string_space - line_oracle["tab_string_space"]) < 1e-3
    )

    # Glyph scale from music/tab text glyphs matches independent PyMuPDF rendered digit height (~6.8695 pt)
    assert page_scale.glyph_scale is not None
    assert abs(page_scale.glyph_scale - glyph_oracle["glyph_scale"]) < 1e-3

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

    assert abs(not_staff.notation_staff_space - line_oracle["notation_staff_space"]) < 1e-3
    assert not_staff.tab_string_space is None
    assert abs(tab_staff.tab_string_space - line_oracle["tab_string_space"]) < 1e-3
    assert tab_staff.notation_staff_space is None


def test_tiny_tab_only_fixture() -> None:
    """Verify pure TAB fixture yields tab_string_space matching independent oracle."""
    line_oracle = _extract_independent_pdf_line_geometry(
        TINY_TAB_PDF, TINY_TAB_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert line_oracle["tab_string_space"] == 14.0
    assert line_oracle["notation_staff_space"] is None

    glyph_oracle = _extract_independent_pdf_glyph_oracle(
        TINY_TAB_PDF, TINY_TAB_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert glyph_oracle["rendered_digit_height"] == 12.4900

    obs = observe(TINY_TAB_PDF)
    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is None
    assert page_scale.tab_string_space is not None
    assert abs(page_scale.tab_string_space - line_oracle["tab_string_space"]) < 1e-3
    assert page_scale.stroke_thickness == 0.6
    assert page_scale.glyph_scale is not None
    assert abs(page_scale.glyph_scale - glyph_oracle["glyph_scale"]) < 1e-3


def test_sparse_notation_only_fixture() -> None:
    """Verify pure notation fixture yields notation_staff_space matching independent oracle."""
    line_oracle = _extract_independent_pdf_line_geometry(
        SPARSE_NOTATION_PDF, SPARSE_NOTATION_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert line_oracle["notation_staff_space"] == 8.5
    assert line_oracle["tab_string_space"] is None

    glyph_oracle = _extract_independent_pdf_glyph_oracle(
        SPARSE_NOTATION_PDF, SPARSE_NOTATION_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert glyph_oracle["glyph_scale"] is None

    obs = observe(SPARSE_NOTATION_PDF)
    page_scale = estimate_page_scale(obs, page_index=1)
    assert page_scale.status == ScaleStatus.ESTIMATED
    assert page_scale.notation_staff_space is not None
    assert page_scale.tab_string_space is None
    assert (
        abs(page_scale.notation_staff_space - line_oracle["notation_staff_space"])
        < 1e-3
    )
    assert page_scale.stroke_thickness == 0.5
    assert page_scale.glyph_scale is None


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
                points=[
                    Point2D(x=50.0 * scale_factor, y=y),
                    Point2D(x=(50.0 + scaled_w), y=y),
                ],
                bbox=BoundingBox2D(
                    page_index=1,
                    x0=50.0 * scale_factor,
                    y0=y,
                    x1=(50.0 + scaled_w),
                    y1=y,
                ),
                stroke_width=scaled_sw,
                provenance=ObservationProvenance(
                    page_index=1, raw_primitive_id=f"raw_s_{i}"
                ),
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
    obs = _build_synthetic_staff_obs(
        line_count=5, gap=base_gap, stroke_width=base_sw, scale_factor=scale_factor
    )

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
                    provenance=ObservationProvenance(
                        page_index=1, raw_primitive_id="raw_f1"
                    ),
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
                    provenance=ObservationProvenance(
                        page_index=1, raw_primitive_id="raw_f2"
                    ),
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
                    provenance=ObservationProvenance(
                        page_index=1, raw_primitive_id=f"raw_{i}"
                    ),
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
                provenance=ObservationProvenance(
                    page_index=1, raw_primitive_id=f"raw_n_{i}"
                ),
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
    assert DimensionlessDetectorPolicy.is_notehead(
        width=12.0, height=10.0, staff_space=sp
    )

    # Height just inside vs just outside
    assert DimensionlessDetectorPolicy.is_notehead(
        width=12.0, height=7.1, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_notehead(
        width=12.0, height=6.9, staff_space=sp
    )
    assert DimensionlessDetectorPolicy.is_notehead(
        width=12.0, height=14.4, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_notehead(
        width=12.0, height=14.6, staff_space=sp
    )

    # Width just inside vs just outside
    assert DimensionlessDetectorPolicy.is_notehead(
        width=7.6, height=10.0, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_notehead(
        width=7.4, height=10.0, staff_space=sp
    )
    assert DimensionlessDetectorPolicy.is_notehead(
        width=18.4, height=10.0, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_notehead(
        width=18.6, height=10.0, staff_space=sp
    )


def test_detector_policy_beam_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_beam."""
    sp = 10.0
    # Beam: width >= 0.50 sp, height <= 0.85 sp, aspect >= 1.80
    assert DimensionlessDetectorPolicy.is_beam(width=20.0, height=4.0, staff_space=sp)

    # Height boundary
    assert DimensionlessDetectorPolicy.is_beam(width=20.0, height=8.4, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_beam(
        width=20.0, height=8.6, staff_space=sp
    )

    # Width boundary
    assert DimensionlessDetectorPolicy.is_beam(width=5.1, height=2.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_beam(
        width=4.9, height=2.0, staff_space=sp
    )

    # Aspect ratio boundary
    assert DimensionlessDetectorPolicy.is_beam(
        width=10.0, height=5.0, staff_space=sp
    )  # aspect 2.0 >= 1.8
    assert not DimensionlessDetectorPolicy.is_beam(
        width=10.0, height=6.0, staff_space=sp
    )  # aspect 1.66 < 1.8


def test_detector_policy_barline_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_barline."""
    sp = 10.0
    # 5-line staff: expected height 4.0 sp (40.0 pt). Tol: 0.55 sp (5.5 pt). Max width: 0.35 sp (3.5 pt)
    assert DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=40.0, staff_space=sp, line_count=5
    )

    # Just inside tolerance (40.0 ± 5.4 pt)
    assert DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=45.4, staff_space=sp, line_count=5
    )
    assert DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=34.6, staff_space=sp, line_count=5
    )
    # Just outside tolerance (40.0 ± 5.6 pt)
    assert not DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=45.6, staff_space=sp, line_count=5
    )
    assert not DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=34.4, staff_space=sp, line_count=5
    )

    # Width boundary
    assert DimensionlessDetectorPolicy.is_barline(
        width=3.4, height=40.0, staff_space=sp, line_count=5
    )
    assert not DimensionlessDetectorPolicy.is_barline(
        width=3.6, height=40.0, staff_space=sp, line_count=5
    )

    # 6-line staff: expected height 5.0 sp (50.0 pt)
    assert DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=50.0, staff_space=sp, line_count=6
    )
    assert not DimensionlessDetectorPolicy.is_barline(
        width=1.0, height=40.0, staff_space=sp, line_count=6
    )


def test_detector_policy_fret_digit_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_fret_digit."""
    string_sp = 8.0
    # Fret digit: height [0.40, 1.30] sp, width [0.20, 1.60] sp
    assert DimensionlessDetectorPolicy.is_fret_digit(
        width=5.0, height=6.0, string_space=string_sp
    )
    assert not DimensionlessDetectorPolicy.is_fret_digit(
        width=5.0, height=3.0, string_space=string_sp
    )
    assert not DimensionlessDetectorPolicy.is_fret_digit(
        width=5.0, height=11.0, string_space=string_sp
    )


def test_detector_policy_stem_boundaries() -> None:
    """Discriminating boundary tests for DimensionlessDetectorPolicy.is_stem."""
    sp = 10.0
    # Stem: height [1.80, 5.00] sp, width <= 0.30 sp
    assert DimensionlessDetectorPolicy.is_stem(width=1.0, height=30.0, staff_space=sp)
    assert not DimensionlessDetectorPolicy.is_stem(
        width=1.0, height=15.0, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_stem(
        width=1.0, height=55.0, staff_space=sp
    )
    assert not DimensionlessDetectorPolicy.is_stem(
        width=3.5, height=30.0, staff_space=sp
    )


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


# ---------------------------------------------------------------------------
# Reviewer Findings Regression Probes (Findings 1 through 6)
# ---------------------------------------------------------------------------


def test_probe_1_isolated_divider_rule_does_not_truncate_staff() -> None:
    """Reviewer Probe 1: Preceding isolated divider rule does not truncate staff into unknown.

    When an isolated divider line precedes a standard 5-line staff, the gap mismatch
    between the divider and the first staff line must not drop the first staff line,
    preserving the complete 5-line notation staff.
    """
    vectors: list[VectorPathObservation] = []
    # Isolated divider line at y=50.0
    vectors.append(
        VectorPathObservation(
            id="divider_rule",
            modality=SourceModality.VECTOR,
            path_type="line",
            points=[Point2D(x=50.0, y=50.0), Point2D(x=350.0, y=50.0)],
            bbox=BoundingBox2D(page_index=1, x0=50.0, y0=50.0, x1=350.0, y1=50.0),
            stroke_width=0.5,
            provenance=ObservationProvenance(page_index=1, raw_primitive_id="raw_div"),
        )
    )
    # Standard 5-line staff starting at y=80.0 with 10.0 pt gap
    for i in range(5):
        y = 80.0 + i * 10.0
        vectors.append(
            VectorPathObservation(
                id=f"staff_line_{i}",
                modality=SourceModality.VECTOR,
                path_type="line",
                points=[Point2D(x=50.0, y=y), Point2D(x=350.0, y=y)],
                bbox=BoundingBox2D(page_index=1, x0=50.0, y0=y, x1=350.0, y1=y),
                stroke_width=0.5,
                provenance=ObservationProvenance(
                    page_index=1, raw_primitive_id=f"raw_s_{i}"
                ),
            )
        )
    obs = DocumentObservations(
        document_id="doc_probe_1",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )
    est = estimate_page_scale(obs, page_index=1)
    assert est.status == ScaleStatus.ESTIMATED
    assert est.notation_staff_space == 10.0

    local_staves = estimate_local_scales(obs, page_index=1)
    assert len(local_staves) == 1
    assert local_staves[0].support.staff_kind == StaffKind.NOTATION
    assert local_staves[0].support.line_count == 5
    assert local_staves[0].notation_staff_space == 10.0


def test_probe_2_unsupported_status_and_strict_error_boundary() -> None:
    """Reviewer Probe 2: Unclassifiable staves return UNSUPPORTED and enforce error boundary.

    When staves cannot be classified into notation or tab (e.g. 4-line unknown staves),
    page estimation must return ScaleStatus.UNSUPPORTED with confidence=0.0 and None scales,
    and raise UnsupportedScaleError under raise_on_unsupported=True.
    """
    # 4-line unknown staff with gap=10.0 pt (4 lines is neither notation=5 nor tab=6)
    vectors: list[VectorPathObservation] = []
    for i in range(4):
        y = 100.0 + i * 10.0
        vectors.append(
            VectorPathObservation(
                id=f"unk_line_{i}",
                modality=SourceModality.VECTOR,
                path_type="line",
                points=[Point2D(x=50.0, y=y), Point2D(x=350.0, y=y)],
                bbox=BoundingBox2D(page_index=1, x0=50.0, y0=y, x1=350.0, y1=y),
                stroke_width=0.5,
                provenance=ObservationProvenance(
                    page_index=1, raw_primitive_id=f"raw_u_{i}"
                ),
            )
        )
    obs = DocumentObservations(
        document_id="doc_probe_2",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )
    # Diagnostic mode: returns typed estimate with UNSUPPORTED status and None scales
    est = estimate_page_scale(obs, page_index=1, raise_on_unsupported=False)
    assert est.status == ScaleStatus.UNSUPPORTED
    assert est.notation_staff_space is None
    assert est.tab_string_space is None
    assert est.uncertainty is None
    assert est.error_message is not None

    # Strict mode: must raise UnsupportedScaleError
    with pytest.raises(UnsupportedScaleError):
        estimate_page_scale(obs, page_index=1, raise_on_unsupported=True)


def test_probe_3_dense_fret_cutouts_merged_and_tab_preserved() -> None:
    """Reviewer Probe 3: Dense fret cutouts broken into <20pt fragments are merged and preserved.

    A 6-line TAB staff where string 2 is cut by multiple fret digits into fragments
    shorter than 20 pt must not be dropped, preserving the 6-line TAB classification.
    """
    vectors: list[VectorPathObservation] = []
    string_space = 8.0
    y_start = 100.0
    for line_idx in range(6):
        y = y_start + line_idx * string_space
        if line_idx == 2:
            # Dense fret cutouts: fragments of length 14 pt separated by 6 pt gaps across 200 pt
            cur_x = 50.0
            seg_idx = 0
            while cur_x < 240.0:
                seg_x1 = cur_x + 14.0
                vectors.append(
                    VectorPathObservation(
                        id=f"dense_frag_{seg_idx}",
                        modality=SourceModality.VECTOR,
                        path_type="line",
                        points=[Point2D(x=cur_x, y=y), Point2D(x=seg_x1, y=y)],
                        bbox=BoundingBox2D(
                            page_index=1, x0=cur_x, y0=y, x1=seg_x1, y1=y
                        ),
                        stroke_width=0.5,
                        provenance=ObservationProvenance(
                            page_index=1, raw_primitive_id=f"raw_df_{seg_idx}"
                        ),
                    )
                )
                cur_x = seg_x1 + 6.0  # 6 pt fret cutout gap
                seg_idx += 1
        else:
            vectors.append(
                VectorPathObservation(
                    id=f"tab_line_{line_idx}",
                    modality=SourceModality.VECTOR,
                    path_type="line",
                    points=[Point2D(x=50.0, y=y), Point2D(x=250.0, y=y)],
                    bbox=BoundingBox2D(page_index=1, x0=50.0, y0=y, x1=250.0, y1=y),
                    stroke_width=0.5,
                    provenance=ObservationProvenance(
                        page_index=1, raw_primitive_id=f"raw_tl_{line_idx}"
                    ),
                )
            )

    obs = DocumentObservations(
        document_id="doc_probe_3",
        page_count=1,
        vectors=vectors,
        texts=[],
        rasters=[],
    )
    est = estimate_page_scale(obs, page_index=1)
    assert est.status == ScaleStatus.ESTIMATED
    assert est.tab_string_space == 8.0
    assert est.notation_staff_space is None

    local_staves = estimate_local_scales(obs, page_index=1)
    assert len(local_staves) == 1
    assert local_staves[0].support.staff_kind == StaffKind.TAB
    assert local_staves[0].support.line_count == 6
    assert local_staves[0].tab_string_space == 8.0


def test_probe_4_beam_detector_rejects_thin_staff_lines_and_hairlines() -> None:
    """Reviewer Probe 4: Beam detector enforces BEAM_MIN_HEIGHT_SP rejecting staff lines.

    DimensionlessDetectorPolicy.is_beam requires normalized height >= 0.20 staff space,
    rejecting thin horizontal staff lines (e.g. h=0.5 pt, 0.05 sp) and hairline strokes.
    """
    sp = 10.0
    # Thin staff line: width=200.0, height=0.5 pt (0.05 sp) -> must be rejected
    assert not DimensionlessDetectorPolicy.is_beam(
        width=200.0, height=0.5, staff_space=sp
    )
    # Hairline stroke: width=50.0, height=0.1 pt (0.01 sp) -> must be rejected
    assert not DimensionlessDetectorPolicy.is_beam(
        width=50.0, height=0.1, staff_space=sp
    )

    # Boundary discrimination at BEAM_MIN_HEIGHT_SP = 0.20:
    # Just below minimum height (h = 1.9 pt, 0.19 sp < 0.20 sp) -> rejected
    assert not DimensionlessDetectorPolicy.is_beam(
        width=20.0, height=1.9, staff_space=sp
    )
    # Just at/above minimum height (h = 2.1 pt, 0.21 sp >= 0.20 sp, aspect 9.5 >= 1.8) -> accepted
    assert DimensionlessDetectorPolicy.is_beam(width=20.0, height=2.1, staff_space=sp)


def test_probe_5_glyph_scale_assertions_on_real_and_synthetic_fixtures() -> None:
    """Reviewer Probe 5: Assert glyph_scale across real and synthetic scores against independent oracles.

    Verifies music font interpretation (font_size / 4.0 for 4-space staff height)
    and bounds candidate glyph dimensions relative to local staff space against independent PyMuPDF oracles.
    """
    # 1. Mutopia real classical score: Emmentaler-20 font -> glyph_scale ~ 4.9813 pt
    oracle_mutopia = _extract_independent_pdf_glyph_oracle(
        REAL_SCORE_MUTOPIA, MUTOPIA_SOURCE_ORACLE["sha256"], page_index=1
    )
    obs_mutopia = observe(REAL_SCORE_MUTOPIA)
    scale_mutopia = estimate_page_scale(obs_mutopia, page_index=1)
    assert scale_mutopia.glyph_scale is not None
    assert abs(scale_mutopia.glyph_scale - oracle_mutopia["glyph_scale"]) < 1e-3
    assert abs(scale_mutopia.glyph_scale - scale_mutopia.notation_staff_space) < 0.20
    assert oracle_mutopia["music_font_scale"] == 4.9813

    # 2. Derek Trucks real paired notation+TAB score -> glyph_scale ~ 4.2520 pt
    oracle_dt = _extract_independent_pdf_glyph_oracle(
        REAL_SCORE_DEREK_TRUCKS, DEREK_TRUCKS_SOURCE_ORACLE["sha256"], page_index=1
    )
    obs_dt = observe(REAL_SCORE_DEREK_TRUCKS)
    scale_dt = estimate_page_scale(obs_dt, page_index=1)
    assert scale_dt.glyph_scale is not None
    assert abs(scale_dt.glyph_scale - oracle_dt["glyph_scale"]) < 1e-3
    assert abs(scale_dt.glyph_scale - scale_dt.notation_staff_space) < 0.20
    # Independent PyMuPDF text-bbox oracle confirms rendered fret digits on TAB staves
    assert oracle_dt["rendered_digit_height"] == 7.0
    assert oracle_dt["music_font_scale"] == 4.252

    # 3. Generated paired score with text/fret digits -> digit bbox height = 6.8695 pt
    oracle_paired = _extract_independent_pdf_glyph_oracle(
        PAIRED_PDF, PAIRED_SOURCE_ORACLE["sha256"], page_index=1
    )
    obs_paired = observe(PAIRED_PDF)
    scale_paired = estimate_page_scale(obs_paired, page_index=1)
    assert scale_paired.glyph_scale is not None
    assert abs(scale_paired.glyph_scale - oracle_paired["glyph_scale"]) < 1e-3
    assert oracle_paired["rendered_digit_height"] == 6.8695

    # 4. Tiny TAB fixture with fret digits -> digit bbox height = 12.4900 pt
    oracle_tiny = _extract_independent_pdf_glyph_oracle(
        TINY_TAB_PDF, TINY_TAB_SOURCE_ORACLE["sha256"], page_index=1
    )
    obs_tiny = observe(TINY_TAB_PDF)
    scale_tiny = estimate_page_scale(obs_tiny, page_index=1)
    assert scale_tiny.glyph_scale is not None
    assert abs(scale_tiny.glyph_scale - oracle_tiny["glyph_scale"]) < 1e-3
    assert oracle_tiny["rendered_digit_height"] == 12.4900

    # 5. Sparse vector-only fixture has no text/font observations -> glyph_scale is None
    oracle_sparse = _extract_independent_pdf_glyph_oracle(
        SPARSE_NOTATION_PDF, SPARSE_NOTATION_SOURCE_ORACLE["sha256"], page_index=1
    )
    assert oracle_sparse["glyph_scale"] is None
    obs_sparse = observe(SPARSE_NOTATION_PDF)
    scale_sparse = estimate_page_scale(obs_sparse, page_index=1)
    assert scale_sparse.glyph_scale is None


def test_probe_6_staff_kind_enum_identity() -> None:
    """Verify StaffKind in scale.py is imported directly from schemas.py without duplication."""
    from score2gp.recognition.scale import StaffKind as ScaleStaffKind
    from score2gp.recognition.schemas import StaffKind as SchemaStaffKind

    assert ScaleStaffKind is SchemaStaffKind
    assert ScaleStaffKind.NOTATION.value == "notation"
    assert ScaleStaffKind.TAB.value == "tab"
    assert ScaleStaffKind.UNKNOWN.value == "unknown"
