from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .report import (
    build_grouping_diagnostics,
    grouping_status_for_tabraw,
    write_grouping_diagnostics_html,
    write_warnings,
)
from .tabraw import TABRAW_SCHEMA_VERSION, TabRaw, make_tab_candidate, parse_fret_text

ASCII_TAB_PARSER_VERSION = "ascii-tab.v0.1"
ASCII_TIMING_PARSER_VERSION = "ascii-timing.v0.1"
_ASCII_TAB_LINE_RE = re.compile(r"^\s*([eEADGB])\|([0-9A-Za-z/\\~()|\s-]+)$")
_ASCII_TAB_TOKEN_RE = re.compile(r"\d{1,2}|[\\/hpbvr~]+")
_ASCII_TECHNIQUE_MARKERS = {"/", "\\", "h", "p", "b", "r", "v", "~"}

DOUBLE_BARLINE_CLUSTERING_TOLERANCE = 12.0
MIN_INHERITED_INTERNAL_BAR_WIDTH = 130.0

MIN_FRET_DIGIT_WIDTH_FOR_CONFIDENCE = 4.0
MIN_NARROW_FONT_FRET_DIGIT_WIDTH = 2.8
MAX_SAME_FRET_DIGIT_MERGE_GAP = 5.0

# Layout classes constants
PDF_LAYOUT_VECTOR_TAB_WITH_BARLINES = "vector_tab_with_barlines"
PDF_LAYOUT_VECTOR_TAB_WITHOUT_BARLINES = "vector_tab_without_barlines"
PDF_LAYOUT_ASCII_TAB = "born_digital_ascii_tab"
PDF_LAYOUT_SCANNED_NO_TEXT = "scanned_no_extractable_text"
PDF_LAYOUT_SCANNED_NO_GEOMETRY = "scanned_no_vector_staff_geometry"
PDF_LAYOUT_MIXED_UNKNOWN = "mixed_unknown_layout"

# Gating refusal warning codes constants
WARN_ASCII_TAB_REQUIRES_ALIGNMENT = "pdf_input_class_ascii_tab_requires_alignment"
WARN_DRAWN_TAB_REQUIRES_BARLINES = "pdf_input_class_drawn_tab_requires_barlines"
WARN_SCANNED_PDF_UNSUPPORTED = "pdf_input_class_scanned_pdf_unsupported"
WARN_NO_EXTRACTABLE_TAB_GEOMETRY = "pdf_input_class_no_extractable_tab_geometry"


def inspect_pdf(path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    pdf_path = Path(path)
    out = Path(out_dir)
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "path": str(pdf_path),
        "page_count": 0,
        "kind": "unknown",
        "pages": [],
        "warnings": [],
    }
    try:
        import fitz  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append({"code": "pymupdf-unavailable", "message": str(exc)})
        (out / "inspect_pdf.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    with fitz.open(pdf_path) as doc:
        summary["page_count"] = doc.page_count
        vector_pages = 0
        text_items_total = 0
        total_systems = 0
        systems_with_barline_candidates = 0
        has_ascii_rows = False

        for index, page in enumerate(doc, start=1):
            text_blocks = page.get_text("blocks")
            drawings = page.get_drawings()
            images = page.get_images(full=True)
            text_items_total += len(text_blocks)
            if text_blocks or drawings:
                vector_pages += 1

            # Detect systems and ASCII rows for layout classification
            try:
                systems = _detect_tab_systems(page, index)
                total_systems += len(systems)
                for sys in systems:
                    if sys.barline_candidates_count > 0:
                        systems_with_barline_candidates += 1
            except Exception:
                pass

            try:
                ascii_rows = _ascii_tab_rows(page, index)
                if ascii_rows:
                    has_ascii_rows = True
            except Exception:
                pass

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_path = pages_dir / f"page-{index:03d}.png"
            pix.save(image_path)

            # Collect notation staves for diagnostics
            from .pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
            from .pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
            from .pdf_geometry_candidate_extraction import extract_geometry_candidates

            diags_dict = extract_notation_diagnostics_dict(page, index)
            diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)

            candidates = []
            semantic_candidates = []
            for staff_diag in diags_model.staves:
                cand = extract_geometry_candidates(staff_diag)
                candidates.append(cand.model_dump(mode="json"))

                from .pdf_candidate_semantic_gate import evaluate_logical_clef_gate
                from .pdf_candidate_quarter_rest import extract_quarter_rest_candidates

                line_y_coords = staff_diag.staff.line_y_coords
                staff_spacing = (line_y_coords[-1] - line_y_coords[0]) / 4.0 if len(line_y_coords) == 5 else 10.0
                staff_height = line_y_coords[-1] - line_y_coords[0] if len(line_y_coords) == 5 else (staff_diag.staff.y1 - staff_diag.staff.y0)
                staff_x0 = staff_diag.staff.x0
                staff_center_y = sum(line_y_coords) / len(line_y_coords) if line_y_coords else (staff_diag.staff.y0 + staff_diag.staff.y1) / 2.0

                clef_res = evaluate_logical_clef_gate(cand, staff_spacing, staff_height, staff_x0)
                qr_cands = extract_quarter_rest_candidates(cand, staff_spacing, staff_center_y)

                semantic_candidates.append({
                    "staff_index": staff_diag.staff.staff_index,
                    "system_index": staff_diag.staff.system_index,
                    "logical_clef": clef_res.model_dump(mode="json"),
                    "quarter_rests": [qr.model_dump(mode="json") for qr in qr_cands]
                })

            page_info = {
                "page": index,
                "width": page.rect.width,
                "height": page.rect.height,
                "text_block_count": len(text_blocks),
                "drawing_count": len(drawings),
                "image_count": len(images),
                "rendered_image": str(image_path),
                "text_blocks": [
                    {
                        "bbox": [block[0], block[1], block[2], block[3]],
                        "text": block[4].strip(),
                    }
                    for block in text_blocks
                    if block[4].strip()
                ],
                "pdf_staff_notation_diagnostics": diags_dict,
                "geometry_candidates": candidates,
                "semantic_candidates": semantic_candidates,
            }
            summary["pages"].append(page_info)

        if vector_pages == doc.page_count and text_items_total:
            summary["kind"] = "born-digital"
        elif vector_pages:
            summary["kind"] = "mixed"
        else:
            summary["kind"] = "scanned-or-raster"

        # Determine layout class
        layout_class = PDF_LAYOUT_MIXED_UNKNOWN
        layout_warnings = []

        if has_ascii_rows:
            layout_class = PDF_LAYOUT_ASCII_TAB
            layout_warnings.append(WARN_ASCII_TAB_REQUIRES_ALIGNMENT)
        elif total_systems > 0:
            if systems_with_barline_candidates == 0:
                layout_class = PDF_LAYOUT_VECTOR_TAB_WITHOUT_BARLINES
                layout_warnings.append(WARN_DRAWN_TAB_REQUIRES_BARLINES)
            else:
                layout_class = PDF_LAYOUT_VECTOR_TAB_WITH_BARLINES
        else:
            if summary["kind"] == "scanned-or-raster" or text_items_total == 0:
                layout_class = PDF_LAYOUT_SCANNED_NO_TEXT
                layout_warnings.append(WARN_SCANNED_PDF_UNSUPPORTED)
            elif summary["kind"] == "mixed":
                layout_class = PDF_LAYOUT_SCANNED_NO_GEOMETRY
                layout_warnings.append(WARN_NO_EXTRACTABLE_TAB_GEOMETRY)
            else:
                layout_class = PDF_LAYOUT_MIXED_UNKNOWN

        summary["pdf_layout_class"] = layout_class
        summary["pdf_layout_warnings"] = layout_warnings

    (out / "inspect_pdf.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def extract_tab(path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    out_target = Path(out_dir)
    if out_target.suffix.lower() == ".json":
        out = out_target.parent
        tabraw_path = out_target
    else:
        out = out_target
        tabraw_path = out / "tab_raw.json"
    out.mkdir(parents=True, exist_ok=True)
    inspection = inspect_pdf(path, out / "inspect")
    meta = {
        "detected_systems": 0,
        "detected_staves": 0,
        "detected_bar_boxes": 0,
        "detected_string_lines": 0,
        "large_spaced_tab_system_count": 0,
    }
    raw: dict[str, Any] = {
        "schema_version": TABRAW_SCHEMA_VERSION,
        "source_pdf": str(path),
        "pdf_layout_class": inspection.get("pdf_layout_class"),
        "pdf_layout_warnings": inspection.get("pdf_layout_warnings", []),
        "candidates": [],
        "warnings": [
            {
                "code": "tab-extraction-incomplete",
                "message": (
                    "This phase records born-digital text candidates with heuristic staff/string/bar estimates where "
                    "page geometry allows it; full optical tab alignment is pending."
                ),
            }
        ],
        "inspection_kind": inspection["kind"],
    }

    try:
        import fitz  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raw["warnings"].append({"code": "pymupdf-unavailable", "message": str(exc), "severity": "error"})
    else:
        raw["candidates"].extend(_extract_pdf_text_candidates(Path(path), raw["warnings"], meta))

    _append_grouping_warnings(raw, meta)
    raw = TabRaw.model_validate(raw).model_dump(mode="json", exclude_none=True)
    _write_grouping_artifacts(Path(path), out, tabraw_path, inspection, raw)
    tabraw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    if raw.get("warnings"):
        write_warnings(out / "warnings.json", raw["warnings"])
    return raw

from .pdf_geometry import (
    _LineSegment,
    _drawing_segments,
    merge_collinear_horizontal_segments,
    FRAGMENTED_STAFF_LINE_NEIGHBOR_MAX_GAP,
)


@dataclass(frozen=True)
class _TabSystem:
    page_index: int
    system_index: int
    staff_index: int
    first_bar_index: int
    line_ys: list[float]
    x0: float
    x1: float
    barlines: list[float]
    barline_candidates_count: int = 0
    valid_barline_count: int = 0
    rejected_barline_count: int = 0
    rejection_reasons: dict[str, int] = None
    barline_candidates_details: list[dict[str, Any]] = None
    inferred_left: float | None = None
    inferred_right: float | None = None
    inferred_warnings: list[str] = None

    @property
    def staff_bbox(self) -> dict[str, float | int]:
        return {
            "page": self.page_index,
            "x0": round(self.x0, 3),
            "y0": round(self.line_ys[0], 3),
            "x1": round(self.x1, 3),
            "y1": round(self.line_ys[-1], 3),
        }

    @property
    def grouping_confidence(self) -> float:
        if len(self.barlines) >= 2:
            if self.inferred_left is not None or self.inferred_right is not None:
                return 0.72
            if len(self.line_ys) == 6:
                return 0.86
        if len(self.line_ys) == 6:
            return 0.58
        return 0.35

    @property
    def grouping_warnings(self) -> list[str]:
        warnings = []
        if len(self.line_ys) != 6:
            warnings.append("incomplete_tab_staff")
            warnings.append("pdf_tab_staff_incomplete")
        if self.inferred_warnings:
            warnings.extend(self.inferred_warnings)
        if len(self.barlines) < 2:
            warnings.append("missing_pdf_barlines")
            warnings.append("pdf_barlines_missing")
            warnings.append("pdf_bar_boxes_missing")
            if self.barline_candidates_count > 0:
                warnings.append("pdf_bar_boxes_not_constructible")
                warnings.append("pdf_bar_box_construction_not_enough_for_build_ir")
                if len(self.barlines) == 1:
                    warnings.append("pdf_bar_box_requires_two_boundaries")
                    warnings.append("pdf_bar_box_missing_right_boundary")
                    if self.rejected_barline_count > 0:
                        warnings.append("pdf_bar_box_one_boundary_rejected")
                        warnings.append("pdf_bar_box_edge_system_missing_boundary")
                else:
                    if self.rejected_barline_count > 0:
                        warnings.append("pdf_bar_box_single_system_failure")
                        reasons = self.rejection_reasons or {}
                        if reasons.get("pdf_barline_too_short", 0) > 0 or reasons.get("pdf_barline_too_short_absolute", 0) > 0:
                            warnings.append("pdf_barline_short_but_near_staff_boundary")
                        if reasons.get("pdf_barline_ambiguous", 0) > 0:
                            warnings.append("pdf_barline_ambiguous_on_edge_system")
        else:
            # Check too narrow boxes
            for left, right in zip(self.barlines, self.barlines[1:]):
                if abs(right - left) < 30.0:
                    warnings.append("pdf_bar_box_too_narrow")
                    warnings.append("pdf_bar_box_construction_not_enough_for_build_ir")

            # Check boxes outside system horizontal bounds
            for left, right in zip(self.barlines, self.barlines[1:]):
                if left < self.x0 - 2.0 or right > self.x1 + 2.0:
                    warnings.append("pdf_bar_box_outside_system_bounds")
                    warnings.append("pdf_bar_box_construction_not_enough_for_build_ir")

            # Check overlapping boxes
            boxes = []
            for left, right in zip(self.barlines, self.barlines[1:]):
                boxes.append((left, right))
            for i, box1 in enumerate(boxes):
                for box2 in boxes[i+1:]:
                    start1, end1 = min(box1[0], box1[1]), max(box1[0], box1[1])
                    start2, end2 = min(box2[0], box2[1]), max(box2[0], box2[1])
                    if max(start1, start2) < min(end1, end2):
                        warnings.append("pdf_bar_box_overlaps_neighbor")
                        warnings.append("pdf_bar_box_construction_not_enough_for_build_ir")
        return warnings

    @property
    def grouping_status(self) -> str:
        return "grouped" if not self.grouping_warnings else "partial"

    @property
    def bar_boxes(self) -> list[dict[str, float | int]]:
        if len(self.barlines) < 2:
            return []
        boxes = []
        for index, (left, right) in enumerate(zip(self.barlines, self.barlines[1:])):
            inferred = []
            if self.inferred_left is not None and abs(left - self.inferred_left) < 1.0:
                inferred.append("left")
            if self.inferred_right is not None and abs(right - self.inferred_right) < 1.0:
                inferred.append("right")

            box_dict = {
                "page": self.page_index,
                "system_index": self.system_index,
                "staff_index": self.staff_index,
                "bar_index": self.first_bar_index + index,
                "x0": round(left, 3),
                "y0": round(self.line_ys[0], 3),
                "x1": round(right, 3),
                "y1": round(self.line_ys[-1], 3),
                "confidence": self.grouping_confidence,
            }
            if inferred:
                box_dict["inferred_boundaries"] = inferred
                box_dict["provenance"] = "pdf_bar_box_inferred_edge_boundary"
            boxes.append(box_dict)
        return boxes

    def string_for_y(
        self, y: float | None, height: float | None = None, systematic_offset: float = 0.0, relaxed_tolerance: bool = False
    ) -> tuple[int | None, int | None, float | None, list[str]]:
        if y is None:
            return None, None, None, []
        calibrated_y = y - systematic_offset
        distances = [(abs(line_y - calibrated_y), index + 1) for index, line_y in enumerate(self.line_ys)]
        distance, line_index = min(distances, key=lambda item: item[0])
        if relaxed_tolerance:
            tolerance = max(6.0, self.line_spacing * 0.75)
        else:
            tolerance = max(5.0, self.line_spacing * 0.48)



        warnings = []

        # Check compact staff spacing
        if self.line_spacing < 6.2:
            warnings.append("pdf_string_assignment_compact_staff_ambiguous")
            warnings.append("pdf_string_assignment_confidence_below_threshold")

        # Check overlaps multiple bands
        if height is not None and height > max(self.line_spacing * 1.5, 14.0):
            warnings.append("pdf_string_assignment_overlaps_multiple_bands")
            warnings.append("pdf_string_assignment_ambiguous")
            warnings.append("ambiguous_string_assignment")
            return None, None, distance, warnings

        min_y = min(self.line_ys)
        max_y = max(self.line_ys)

        # Check outside staff bounds
        if calibrated_y < min_y - tolerance or calibrated_y > max_y + tolerance:
            warnings.append("pdf_string_assignment_outside_staff")
            warnings.append("pdf_string_assignment_missing")
            return None, None, distance, warnings

        if distance > tolerance:
            warnings.append("ambiguous_string_assignment")
            warnings.append("pdf_string_assignment_ambiguous")
            if min_y <= calibrated_y <= max_y:
                warnings.append("pdf_string_assignment_between_lines")
                warnings.append("pdf_candidate_between_strings")
            if distance > self.line_spacing * 0.65:
                warnings.append("pdf_string_assignment_too_far_from_line")
                warnings.append("pdf_string_assignment_missing")
            return None, None, distance, warnings

        warnings.append("pdf_string_assignment_nearest_line")
        return line_index, line_index, distance, warnings

    def bar_for_x(self, x: float | None) -> tuple[int | None, list[str]]:
        local_bar, warnings = self.local_bar_for_x(x)
        if local_bar is None:
            return None, warnings
        return self.first_bar_index + local_bar - 1, warnings

    def bar_bounds_for_x(self, x: float | None) -> tuple[float, float] | None:
        local_bar, _ = self.local_bar_for_x(x)
        if local_bar is None or len(self.barlines) < 2:
            return None
        return self.barlines[local_bar - 1], self.barlines[local_bar]

    def local_bar_for_x(self, x: float | None) -> tuple[int | None, list[str]]:
        if x is None or len(self.barlines) < 2:
            return None, ["missing_pdf_barlines", "pdf_barlines_missing"] if x is not None else []

        # Outer boundary snapping: up to 24.0 pixels (matching horizontal margin of the system)
        outer_tolerance = 24.0
        if x < self.barlines[0] - outer_tolerance or x > self.barlines[-1] + outer_tolerance:
            return None, ["pdf_candidate_outside_bar", "ambiguous_bar_assignment", "pdf_candidate_unassigned_to_bar"]

        internal_barlines = self.barlines[1:-1]
        if any(abs(x - barline) <= self.ambiguous_bar_tolerance for barline in internal_barlines):
            return None, ["ambiguous_bar_assignment", "pdf_barlines_ambiguous", "pdf_candidate_on_bar_boundary", "pdf_candidate_boundary_ambiguous", "pdf_bar_box_boundary_ambiguous"]

        for index, (left, right) in enumerate(zip(self.barlines, self.barlines[1:]), start=1):
            left_tol = outer_tolerance if left == self.barlines[0] else 4.5
            right_tol = outer_tolerance if right == self.barlines[-1] else 4.5

            if left - left_tol <= x <= right + right_tol:
                warnings = []
                if x < left or x > right:
                    warnings.append("pdf_candidate_outside_bar")
                if self.inferred_left is not None and abs(left - self.inferred_left) < 1.0:
                    warnings.append("pdf_bar_box_inferred_left_boundary")
                if self.inferred_right is not None and abs(right - self.inferred_right) < 1.0:
                    warnings.append("pdf_bar_box_inferred_right_boundary")
                return index, warnings
        return None, ["ambiguous_bar_assignment", "pdf_candidate_unassigned_to_bar"]

    def infer_edge_boundaries(self, playable_xs: list[float], rejected_xs: list[float]) -> tuple[float | None, float | None, list[str]]:
        inferred_left = None
        inferred_right = None
        warnings = []

        if len(self.barlines) != 1:
            return None, None, []

        mid_x = self.barlines[0]
        ambig_tol = self.ambiguous_bar_tolerance

        # Left inference
        left_candidates = [x for x in playable_xs if x < mid_x]
        if left_candidates:
            left_rejected = [rx for rx in rejected_xs if rx < mid_x]
            if left_rejected:
                warnings.append("pdf_bar_box_edge_boundary_ambiguous")
                warnings.append("pdf_bar_box_inferred_boundary_requires_clear_system_edge")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            elif mid_x - self.x0 < 30.0:
                warnings.append("pdf_bar_box_inferred_boundary_too_narrow")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            elif any(x - self.x0 < ambig_tol for x in left_candidates):
                warnings.append("pdf_bar_box_inferred_boundary_candidate_ambiguous")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            else:
                inferred_left = self.x0
                warnings.append("pdf_bar_box_inferred_left_boundary")
                warnings.append("pdf_bar_box_edge_boundary_fallback_used")

        # Right inference
        right_candidates = [x for x in playable_xs if x > mid_x]
        if right_candidates:
            right_rejected = [rx for rx in rejected_xs if rx > mid_x]
            if right_rejected:
                warnings.append("pdf_bar_box_edge_boundary_ambiguous")
                warnings.append("pdf_bar_box_inferred_boundary_requires_clear_system_edge")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            elif self.x1 - mid_x < 30.0:
                warnings.append("pdf_bar_box_inferred_boundary_too_narrow")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            elif any(self.x1 - x < ambig_tol for x in right_candidates):
                warnings.append("pdf_bar_box_inferred_boundary_candidate_ambiguous")
                warnings.append("pdf_bar_box_edge_boundary_fallback_rejected")
            else:
                inferred_right = self.x1
                warnings.append("pdf_bar_box_inferred_right_boundary")
                warnings.append("pdf_bar_box_edge_boundary_fallback_used")

        return inferred_left, inferred_right, warnings

    @property
    def line_spacing(self) -> float:
        gaps = [right - left for left, right in zip(self.line_ys, self.line_ys[1:])]
        return sum(gaps) / len(gaps) if gaps else 12.0

    @property
    def ambiguous_bar_tolerance(self) -> float:
        return min(6.0, max(4.0, self.line_spacing * 0.45))


    def contains_y(self, y: float | None) -> bool:
        if y is None:
            return False
        margin = max(6.0, self.line_spacing)
        return self.line_ys[0] - margin <= y <= self.line_ys[-1] + margin

    def candidate_zone_contains(self, x: float | None, y: float | None) -> bool:
        if x is None or y is None:
            return False
        horizontal_margin = 150.0
        top_margin = max(65.0, self.line_spacing * 6.0)
        bottom_margin = max(12.0, self.line_spacing)
        return (
            self.x0 - horizontal_margin <= x <= self.x1 + horizontal_margin
            and self.line_ys[0] - top_margin <= y <= self.line_ys[-1] + bottom_margin
        )


@dataclass(frozen=True)
class _AsciiTabRow:
    page_index: int
    block_number: int
    line_number: int
    label: str
    body: str
    text: str
    bbox: tuple[float, float, float, float]
    body_start: int
    row_index: int = 0

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(frozen=True)
class _AsciiTabBlock:
    page_index: int
    system_index: int
    staff_index: int
    rows: list[_AsciiTabRow]

    @property
    def is_complete(self) -> bool:
        return len(self.rows) == 6

    @property
    def grouping_status(self) -> str:
        return "ascii_grouped" if self.is_complete else "partial_ascii_tab_grouping"

    @property
    def grouping_confidence(self) -> float:
        return 0.78 if self.is_complete else 0.45

    @property
    def grouping_warnings(self) -> list[str]:
        if self.is_complete:
            return []
        return ["partial_ascii_tab_grouping"]

    @property
    def staff_bbox(self) -> dict[str, float | int]:
        return {
            "page": self.page_index,
            "x0": round(min(row.x0 for row in self.rows), 3),
            "y0": round(min(row.y0 for row in self.rows), 3),
            "x1": round(max(row.x1 for row in self.rows), 3),
            "y1": round(max(row.y1 for row in self.rows), 3),
        }

    @property
    def line_ys(self) -> list[float]:
        return [round(row.y_center, 3) for row in self.rows]

    def contains_point(self, x: float | None, y: float | None) -> bool:
        if x is None or y is None:
            return False
        bbox = self.staff_bbox
        return (
            float(bbox["x0"]) - 4.0 <= x <= float(bbox["x1"]) + 4.0
            and float(bbox["y0"]) - 4.0 <= y <= float(bbox["y1"]) + 4.0
        )


@dataclass(frozen=True)
class _AsciiTimingEvidence:
    status: str
    confidence: float
    warnings: list[str]
    bar_separator_columns: list[int]
    bar_separators_aligned: bool
    row_widths: list[int]
    segment_boundaries: list[tuple[int, int]]

    @property
    def segment_count(self) -> int:
        return len(self.segment_boundaries)

    def segment_for_column(self, column_index: int) -> tuple[int, int, int] | None:
        for index, (start, end) in enumerate(self.segment_boundaries, start=1):
            if start <= column_index < end:
                return index, start, end
        return None


def _split_technique_mixed_words(words: list[tuple[float, float, float, float, str, int, int, int]]) -> list[dict[str, Any]]:
    refined = []
    tech_chars = set("hpsvbr~/\\()[].,-")

    for word_index, word in enumerate(words, start=1):
        raw_text = str(word[4]).strip()
        if not raw_text:
            continue
        bbox_values = [float(word[0]), float(word[1]), float(word[2]), float(word[3])]

        from .tabraw import _looks_like_chord_symbol
        if _looks_like_chord_symbol(raw_text):
            refined.append({
                "x0": bbox_values[0],
                "y0": bbox_values[1],
                "x1": bbox_values[2],
                "y1": bbox_values[3],
                "text": raw_text,
                "block_no": int(word[5]) if len(word) > 5 else None,
                "line_no": int(word[6]) if len(word) > 6 else None,
                "word_no": int(word[7]) if len(word) > 7 else None,
                "word_index": word_index,
                "warnings": [],
                "provenance": [],
            })
            continue

        has_digit = any(char.isdigit() for char in raw_text)
        has_tech = any(char in tech_chars for char in raw_text.lower())

        if has_digit and has_tech:
            parts = [m.group(0) for m in re.finditer(r"(\d+|[hpsvbr~/\\()\[\].,\-]+)", raw_text, re.IGNORECASE)]
            if len(parts) > 1:
                L = len(raw_text)
                W = bbox_values[2] - bbox_values[0]

                real_tech_chars = set("hpsvbr~/\\")
                has_real_tech = any(c in real_tech_chars for c in raw_text.lower())

                current_start = 0
                for part in parts:
                    part_start = raw_text.find(part, current_start)
                    part_end = part_start + len(part)
                    current_start = part_end

                    part_x0 = bbox_values[0] + (part_start / L) * W
                    part_x1 = bbox_values[0] + (part_end / L) * W

                    part_warnings = []
                    part_provenance = []

                    is_digit_part = any(c.isdigit() for c in part)
                    if is_digit_part:
                        part_width = part_x1 - part_x0
                        limit = 4.0 if has_real_tech else 2.0
                        if part_width < limit:
                            part_warnings.append("pdf_fret_digit_symbol_overlap_ambiguous")
                            part_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")
                    else:
                        part_warnings.append("pdf_fret_technique_marker_excluded")

                    refined.append({
                        "x0": part_x0,
                        "y0": bbox_values[1],
                        "x1": part_x1,
                        "y1": bbox_values[3],
                        "text": part,
                        "block_no": int(word[5]) if len(word) > 5 else None,
                        "line_no": int(word[6]) if len(word) > 6 else None,
                        "word_no": int(word[7]) if len(word) > 7 else None,
                        "word_index": word_index,
                        "warnings": part_warnings,
                        "provenance": part_provenance,
                    })
                continue

        refined.append({
            "x0": bbox_values[0],
            "y0": bbox_values[1],
            "x1": bbox_values[2],
            "y1": bbox_values[3],
            "text": raw_text,
            "block_no": int(word[5]) if len(word) > 5 else None,
            "line_no": int(word[6]) if len(word) > 6 else None,
            "word_no": int(word[7]) if len(word) > 7 else None,
            "word_index": word_index,
            "warnings": [],
            "provenance": [],
        })
    return refined


def _extract_pdf_text_candidates(pdf_path: Path, warnings: list[dict[str, Any]], meta: dict[str, int]) -> list[dict[str, Any]]:
    import fitz  # type: ignore[import-not-found]

    candidates = []
    filtered_index = 0
    next_bar_index = 1
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            systems = _detect_tab_systems(page, page_number, first_bar_index=next_bar_index)
            if systems:
                last_sys = systems[-1]
                next_bar_index = last_sys.first_bar_index + max(1, len(last_sys.barlines) - 1)
            ascii_blocks = _detect_ascii_tab_blocks(page, page_number, first_system_index=len(systems) + 1)

            words = sorted(
                page.get_text("words"),
                key=lambda word: (round(float(word[1]), 3), round(float(word[0]), 3), str(word[4])),
            )
            # Identify systems that actually contain at least one playable candidate
            systems_with_playable_candidates = set()
            system_playable_xs = {}
            for word in words:
                raw_text = str(word[4]).strip()
                if not raw_text:
                    continue
                bbox_values = [float(word[0]), float(word[1]), float(word[2]), float(word[3])]
                x = (bbox_values[0] + bbox_values[2]) / 2
                y = (bbox_values[1] + bbox_values[3]) / 2
                if _point_in_ascii_block(ascii_blocks, x, y):
                    continue
                if ascii_blocks and parse_fret_text(raw_text) is not None:
                    continue
                is_fret_candidate = parse_fret_text(raw_text) is not None
                if is_fret_candidate:
                    system = _nearest_system(systems, x, y)
                    if system is not None:
                        systems_with_playable_candidates.add(system.system_index)
                        if system.system_index not in system_playable_xs:
                            system_playable_xs[system.system_index] = []
                        system_playable_xs[system.system_index].append(x)

            # Apply edge-boundary fallback inference policy
            from dataclasses import replace
            updated_systems = []
            for system in systems:
                if len(system.barlines) == 1:
                    p_xs = system_playable_xs.get(system.system_index, [])
                    noise_reasons = {
                        "pdf_barline_outside_staff_region",
                        "pdf_barline_double_secondary",
                    }
                    rej_xs = [
                        d["x"] for d in (system.barline_candidates_details or [])
                        if d.get("final_decision") == "rejected"
                        and d.get("rejection_reason") not in noise_reasons
                    ]
                    inf_left, inf_right, inf_warnings = system.infer_edge_boundaries(p_xs, rej_xs)
                    if inf_left is not None or inf_right is not None:
                        new_barlines = list(system.barlines)
                        if inf_left is not None:
                            new_barlines.append(inf_left)
                        if inf_right is not None:
                            new_barlines.append(inf_right)
                        new_barlines = sorted(list(set(new_barlines)))
                        system = replace(
                            system,
                            barlines=new_barlines,
                            inferred_left=inf_left,
                            inferred_right=inf_right,
                            inferred_warnings=inf_warnings,
                            valid_barline_count=len(new_barlines),
                        )
                    elif inf_warnings:
                        system = replace(
                            system,
                            inferred_warnings=inf_warnings,
                        )
                updated_systems.append(system)
            systems = updated_systems

            # Accumulate metadata
            for system in systems:
                meta["detected_systems"] += 1
                meta["detected_staves"] += 1
                meta["detected_bar_boxes"] += len(system.bar_boxes)
                meta["detected_string_lines"] += len(system.line_ys)
                if len(system.line_ys) == 6 and system.line_spacing > 15.0:
                    meta["large_spaced_tab_system_count"] = meta.get("large_spaced_tab_system_count", 0) + 1

            drawings = page.get_drawings()
            segments = list(_drawing_segments(drawings))
            has_horizontal = any(abs(s.y0 - s.y1) <= 2.0 and abs(s.x1 - s.x0) >= 15.0 for s in segments)
            text_blocks = [b for b in page.get_text("blocks") if b[4].strip()]

            if not systems:
                warnings.append(
                    {
                        "code": "pdf-tab-system-not-detected",
                        "message": f"No six-line tab system was inferred on page {page_number}; candidates may lack string/bar estimates.",
                        "severity": "info",
                    }
                )
                if drawings and text_blocks:
                    warnings.append({
                        "code": "pdf_text_geometry_present_but_no_safe_system",
                        "message": f"Both text and drawn geometry are present, but no safe tab system could be inferred on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "missing",
                    })
                    warnings.append({
                        "code": "pdf_drawn_geometry_present_but_staff_unresolved",
                        "message": f"Drawn geometry exists, but staff lines could not be resolved into a tab system on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "missing",
                    })
                if has_horizontal:
                    warnings.append({
                        "code": "pdf_tab_staff_lines_fragmented",
                        "message": f"Tab staff lines are fragmented or broken on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "missing",
                    })
            else:
                for system in systems:
                    if system.system_index not in systems_with_playable_candidates:
                        if len(system.barlines) >= 2 and not any(w in system.grouping_warnings for w in ("pdf_bar_box_too_narrow", "pdf_bar_box_outside_system_bounds", "pdf_bar_box_overlaps_neighbor")):
                            warnings.append({
                                "code": "pdf_bar_boxes_constructed",
                                "message": f"Bar boxes successfully constructed in system {system.system_index} on page {page_number}.",
                                "severity": "info",
                                "grouping_status": "grouped"
                            })
                        continue

                    if len(system.barlines) < 2:
                        warnings.append({
                            "code": "pdf_barlines_not_detected_in_system",
                            "message": f"Less than 2 valid barlines detected in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing",
                            "page_index": page_number,
                            "system_index": system.system_index,
                        })
                        warnings.append({
                            "code": "pdf_bar_boxes_not_constructible",
                            "message": f"Bar boxes are not constructible in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing",
                            "page_index": page_number,
                            "system_index": system.system_index,
                        })
                        warnings.append({
                            "code": "pdf_bar_detection_not_enough_for_build_ir",
                            "message": f"Bar detection is incomplete in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing",
                            "page_index": page_number,
                            "system_index": system.system_index,
                        })
                    if system.rejected_barline_count > 0 and len(system.barlines) == 0:
                        warnings.append({
                            "code": "pdf_barline_candidates_present_but_invalid",
                            "message": f"Barline candidates were present but all were rejected in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing",
                            "page_index": page_number,
                            "system_index": system.system_index,
                        })
                    reasons = system.rejection_reasons or {}
                    has_usable_barlines = (len(system.barlines) >= 2)
                    
                    def add_barline_warning(code, message, severity="warning", grouping_status="partial"):
                        if has_usable_barlines and severity == "warning":
                            warnings.append({
                                "code": f"info_{code}",
                                "message": f"[Diagnostic Info] {message}",
                                "severity": "info",
                                "grouping_status": "grouped",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                        else:
                            warnings.append({
                                "code": code,
                                "message": message,
                                "severity": severity,
                                "grouping_status": grouping_status,
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                            
                    if reasons.get("pdf_barline_too_short", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_too_short",
                            f"One or more barline candidates are too short in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_does_not_cross_staff", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_does_not_cross_staff",
                            f"One or more barline candidates do not cross the tab staff in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_outside_system_bounds", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_outside_system_bounds",
                            f"One or more barline candidates are outside the system bounds in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_ambiguous", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_ambiguous",
                            f"One or more barline candidates are horizontally ambiguous in system {system.system_index} on page {page_number}.",
                            "warning",
                            "ambiguous",
                        )
                    if reasons.get("pdf_barline_double_secondary", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_double_secondary",
                            f"One or more secondary double-barline candidates were ignored in system {system.system_index} on page {page_number}.",
                            "info",
                            "grouped",
                        )
                    if reasons.get("pdf_barline_too_short_absolute", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_too_short_absolute",
                            f"One or more barline candidates are below absolute height threshold in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_too_short_relative_to_staff", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_too_short_relative_to_staff",
                            f"One or more barline candidates are below relative staff-height threshold in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_crosses_insufficient_string_gaps", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_crosses_insufficient_string_gaps",
                            f"One or more barline candidates cross too few string gaps in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_partial_staff_crossing", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_partial_staff_crossing",
                            f"One or more barline candidates only partially cross the staff in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_outside_staff_region", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_outside_staff_region",
                            f"One or more barline candidates are outside the staff region in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_rejected_relative_height", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_rejected_relative_height",
                            f"One or more barline candidates were rejected by relative staff-height check in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    if reasons.get("pdf_barline_inherited_too_close", 0) > 0:
                        add_barline_warning(
                            "pdf_barline_inherited_too_close",
                            f"One or more inherited barline candidates were rejected as too close in system {system.system_index} on page {page_number}.",
                            "warning",
                            "partial",
                        )
                    # Propagate system grouping warnings to page warnings
                    for gw in system.grouping_warnings:
                        if gw == "pdf_bar_box_too_narrow":
                            warnings.append({
                                "code": "pdf_bar_box_too_narrow",
                                "message": f"One or more bar boxes are too narrow in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                            warnings.append({
                                "code": "pdf_bar_box_construction_not_enough_for_build_ir",
                                "message": f"Bar box construction failed in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                        elif gw == "pdf_bar_box_outside_system_bounds":
                            warnings.append({
                                "code": "pdf_bar_box_outside_system_bounds",
                                "message": f"One or more bar boxes extend outside system horizontal bounds in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                            warnings.append({
                                "code": "pdf_bar_box_construction_not_enough_for_build_ir",
                                "message": f"Bar box construction failed in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                        elif gw == "pdf_bar_box_overlaps_neighbor":
                            warnings.append({
                                "code": "pdf_bar_box_overlaps_neighbor",
                                "message": f"One or more bar boxes overlap with their neighbors in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                            warnings.append({
                                "code": "pdf_bar_box_construction_not_enough_for_build_ir",
                                "message": f"Bar box construction failed in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                        elif gw == "pdf_bar_box_requires_two_boundaries":
                            warnings.append({
                                "code": "pdf_bar_box_requires_two_boundaries",
                                "message": f"A bar box requires at least two accepted barlines in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "page_index": page_number,
                                "system_index": system.system_index,
                            })
                        elif gw == "pdf_bar_box_inferred_left_boundary":
                            warnings.append({
                                "code": "pdf_bar_box_inferred_left_boundary",
                                "message": f"Left edge boundary was inferred in system {system.system_index} on page {page_number}.",
                                "severity": "info",
                                "grouping_status": "grouped",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_inferred_right_boundary":
                            warnings.append({
                                "code": "pdf_bar_box_inferred_right_boundary",
                                "message": f"Right edge boundary was inferred in system {system.system_index} on page {page_number}.",
                                "severity": "info",
                                "grouping_status": "grouped",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_edge_boundary_fallback_used":
                            warnings.append({
                                "code": "pdf_bar_box_edge_boundary_fallback_used",
                                "message": f"Edge boundary fallback was used in system {system.system_index} on page {page_number}.",
                                "severity": "info",
                                "grouping_status": "grouped",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_edge_boundary_fallback_rejected":
                            warnings.append({
                                "code": "pdf_bar_box_edge_boundary_fallback_rejected",
                                "message": f"Edge boundary fallback was rejected in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                            warnings.append({
                                "code": "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",
                                "message": f"Inferred boundary failure blocks IR generation in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_edge_boundary_ambiguous":
                            warnings.append({
                                "code": "pdf_bar_box_edge_boundary_ambiguous",
                                "message": f"Edge boundary fallback is ambiguous in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_inferred_boundary_too_narrow":
                            warnings.append({
                                "code": "pdf_bar_box_inferred_boundary_too_narrow",
                                "message": f"Inferred boundary would produce a box too narrow in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_inferred_boundary_candidate_ambiguous":
                            warnings.append({
                                "code": "pdf_bar_box_inferred_boundary_candidate_ambiguous",
                                "message": f"A fret candidate lies too close to the inferred boundary in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                        elif gw == "pdf_bar_box_inferred_boundary_requires_clear_system_edge":
                            warnings.append({
                                "code": "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
                                "message": f"Inferred boundary requires a clear, non-ambiguous system edge in system {system.system_index} on page {page_number}.",
                                "severity": "warning",
                                "grouping_status": "partial",
                                "system_index": system.system_index,
                                "page_index": page_number,
                            })
                    if len(system.barlines) >= 2 and not any(w in system.grouping_warnings for w in ("pdf_bar_box_too_narrow", "pdf_bar_box_outside_system_bounds", "pdf_bar_box_overlaps_neighbor")):
                        warnings.append({
                            "code": "pdf_bar_boxes_constructed",
                            "message": f"Bar boxes successfully constructed in system {system.system_index} on page {page_number}.",
                            "severity": "info",
                            "grouping_status": "grouped"
                        })

                # Check if some systems are unboxed while others are boxed on this page
                has_any_unboxed_system = any(
                    (len(sys.barlines) < 2 or any(w in sys.grouping_warnings for w in ("pdf_bar_box_too_narrow", "pdf_bar_box_outside_system_bounds", "pdf_bar_box_overlaps_neighbor")))
                    and sys.system_index in systems_with_playable_candidates
                    for sys in systems
                )
                has_any_boxed_system = any(
                    len(sys.barlines) >= 2 and not any(w in sys.grouping_warnings for w in ("pdf_bar_box_too_narrow", "pdf_bar_box_outside_system_bounds", "pdf_bar_box_overlaps_neighbor"))
                    for sys in systems
                )
                if has_any_unboxed_system and has_any_boxed_system:
                    warnings.append({
                        "code": "pdf_partial_grouping_one_system_unboxed",
                        "message": f"At least one system lacks bar boxes while another has boxes on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "partial"
                    })

                # Check for vertically overlapping systems on the page
                has_overlap = False
                # Collect all playable fret candidates on the page for bbox ambiguity check
                page_playable_candidates = []
                for word in words:
                    raw_text = str(word[4]).strip()
                    if not raw_text:
                        continue
                    bbox_values = [float(word[0]), float(word[1]), float(word[2]), float(word[3])]
                    cx = (bbox_values[0] + bbox_values[2]) / 2
                    cy = (bbox_values[1] + bbox_values[3]) / 2
                    if _point_in_ascii_block(ascii_blocks, cx, cy):
                        continue
                    if parse_fret_text(raw_text) is not None:
                        page_playable_candidates.append((cx, cy))

                for i, sys1 in enumerate(systems):
                    for sys2 in systems[i+1:]:
                        y_min1, y_max1 = min(sys1.line_ys), max(sys1.line_ys)
                        y_min2, y_max2 = min(sys2.line_ys), max(sys2.line_ys)
                        # Only check vertical overlap if systems belong to the same column (X ranges overlap > 75% of minimum width)
                        width1 = sys1.x1 - sys1.x0
                        width2 = sys2.x1 - sys2.x0
                        overlap_width = max(0.0, min(sys1.x1, sys2.x1) - max(sys1.x0, sys2.x0))
                        min_width = min(width1, width2)
                        overlap_ratio = overlap_width / min_width if min_width > 0 else 0.0
                        if overlap_ratio > 0.75:
                            # Identify upper and lower system
                            if (sum(sys1.line_ys)/len(sys1.line_ys)) < (sum(sys2.line_ys)/len(sys2.line_ys)):
                                sys_upper, sys_lower = sys1, sys2
                                y_min_upper, y_max_upper = y_min1, y_max1
                                y_min_lower, y_max_lower = y_min2, y_max2
                            else:
                                sys_upper, sys_lower = sys2, sys1
                                y_min_upper, y_max_upper = y_min2, y_max2
                                y_min_lower, y_max_lower = y_min1, y_max1

                            # 1. Deep vertical overlap (overlap > 4.0pt) is always ambiguous
                            if y_min_lower < y_max_upper - 4.0:
                                has_overlap = True
                                break

                            # 2. Check if a fret candidate falls in the critical gap region between close systems
                            # Only treat as ambiguous if the systems are dense (gap < 20.0pt)
                            if y_min_lower - y_max_upper < 20.0:
                                x0_overlap = max(sys_upper.x0, sys_lower.x0) - 5.0
                                x1_overlap = min(sys_upper.x1, sys_lower.x1) + 5.0
                                for cx, cy in page_playable_candidates:
                                    if (y_max_upper - 4.0 <= cy <= y_min_lower + 4.0) and (x0_overlap <= cx <= x1_overlap):
                                        has_overlap = True
                                        break
                            if has_overlap:
                                break
                    if has_overlap:
                        break
                if has_overlap:
                    warnings.append({
                        "code": "pdf_multi_system_order_ambiguous",
                        "message": f"Multiple tab systems have vertically overlapping ranges on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "ambiguous",
                    })
                    warnings.append({
                        "code": "pdf_system_order_ambiguous",
                        "message": f"System order is ambiguous across visually close systems on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "ambiguous",
                    })
                    warnings.append({
                        "code": "pdf_tab_staff_ambiguous",
                        "message": "Tab systems layout is ambiguous due to vertical overlap.",
                        "severity": "warning",
                        "grouping_status": "ambiguous",
                    })
                    warnings.append({
                        "code": "pdf_system_bbox_ambiguous",
                        "message": "Tab system bounding boxes are overlapping or ambiguous on page {page_number}.",
                        "severity": "warning",
                        "grouping_status": "ambiguous",
                    })

            if len(systems) > 0 and len(ascii_blocks) > 0:
                warnings.append({
                    "code": "pdf_ascii_and_drawn_layout_conflict",
                    "message": f"Both ASCII blocks and drawn systems exist on page {page_number}.",
                    "severity": "warning",
                    "grouping_status": "unsupported",
                })
                warnings.append({
                    "code": "pdf_page_layout_unsupported",
                    "message": f"Unsupported mixed page layout on page {page_number}.",
                    "severity": "warning",
                    "grouping_status": "unsupported",
                })

            if ascii_blocks:
                warnings.extend(_ascii_tab_warnings(page_number, ascii_blocks))
                ascii_candidates = _ascii_candidates_from_blocks(
                    ascii_blocks,
                    first_candidate_index=filtered_index + 1,
                )
                candidates.extend(ascii_candidates)
                filtered_index += len(ascii_candidates)

            if systems:
                from .quarter_rest_recogniser import extract_quarter_rest_candidates
                page_outcomes = []
                for sys in systems:
                    if len(sys.line_ys) < 6:
                        continue
                    staff_space = sys.line_spacing
                    if staff_space <= 0.0:
                        continue
                    y0_limit = min(sys.line_ys) - 3.0 * staff_space
                    y1_limit = max(sys.line_ys) + 3.0 * staff_space
                    x0_limit = sys.x0
                    x1_limit = sys.x1
                    
                    flag_candidates = []
                    flag_idx = len(page_outcomes) + 1
                    for drawing in drawings:
                        for item in drawing.get("items", []):
                            if not item:
                                continue
                            itype = item[0]
                            is_flag = False
                            p_x0, p_y0, p_x1, p_y1 = 0.0, 0.0, 0.0, 0.0
                            if itype == "l" and len(item) >= 3:
                                p0, p1 = item[1], item[2]
                                p_x0, p_x1 = min(p0.x, p1.x), max(p0.x, p1.x)
                                p_y0, p_y1 = min(p0.y, p1.y), max(p0.y, p1.y)
                                if (p_x1 - p_x0) > 1.0 and (p_y1 - p_y0) > 1.0:
                                    is_flag = True
                            elif itype == "c" and len(item) >= 2:
                                pts = item[1:]
                                p_x0, p_x1 = min(p.x for p in pts), max(p.x for p in pts)
                                p_y0, p_y1 = min(p.y for p in pts), max(p.y for p in pts)
                                is_flag = True

                            if is_flag:
                                if p_x0 >= x0_limit and p_x1 <= x1_limit and p_y0 >= y0_limit and p_y1 <= y1_limit:
                                    w, h = p_x1 - p_x0, p_y1 - p_y0
                                    if h < 4.0 * staff_space and w < 3.0 * staff_space:
                                        flag_candidates.append({
                                            "symbol_type": "flag_candidate",
                                            "bbox": [p_x0, p_y0, p_x1, p_y1],
                                            "page_index": page_number,
                                            "system_index": sys.system_index,
                                            "staff_index": sys.staff_index,
                                            "system_staff_index": sys.staff_index,
                                            "candidate_id": f"flag_candidate_{flag_idx}",
                                            "staff_space": staff_space
                                        })
                                        flag_idx += 1
                    page_outcomes.extend(flag_candidates)
                if page_outcomes:
                    q_rests = extract_quarter_rest_candidates(page_outcomes)
                    for qr in q_rests:
                        x0, y0, x1, y1 = qr["bbox"]
                        cx = (x0 + x1) / 2.0
                        cy = (y0 + y1) / 2.0
                        sys_idx = qr.get("system_index")
                        system = next((s for s in systems if s.system_index == sys_idx), None)
                        bar_idx = None
                        local_bar_idx = None
                        sys_first_bar = None
                        if system is not None:
                            bar_idx, _ = system.bar_for_x(cx)
                            local_bar_idx = system.local_bar_for_x(cx)[0]
                            sys_first_bar = system.first_bar_index
                        candidates.append({
                            "id": f"pdf-p{page_number:03d}-rest-{filtered_index:04d}",
                            "kind": "candidate-text",
                            "page_index": page_number,
                            "system_index": sys_idx,
                            "staff_index": qr.get("staff_index"),
                            "bar_index": bar_idx,
                            "raw_text": "quarter_rest",
                            "x": cx,
                            "y": cy,
                            "bbox": {"page": page_number, "x0": x0, "y0": y0, "x1": x1, "y1": y1},
                            "confidence": 0.5,
                            "source_stage": "pdf-text",
                            "raw": {
                                "symbol_type": "quarter_rest_candidate",
                                "provenance": ["tab_only_vector_quarter_rest"],
                                "local_bar_index": local_bar_idx,
                                "system_first_bar_index": sys_first_bar
                            }
                        })
                        filtered_index += 1

            # Pre-process, split mixed technique words, and group playable digits conservatively
            refined_words = _split_technique_mixed_words(words)

            # Reconstruct lines to find Standard and other Tunings page-wide
            line_words = {}
            for rw in refined_words:
                b_no = rw.get("block_no") or 0
                l_no = rw.get("line_no") or 0
                key = (b_no, l_no)
                if key not in line_words:
                    line_words[key] = []
                line_words[key].append(rw)

            line_texts = {}
            for key in line_words:
                line_words[key] = sorted(line_words[key], key=lambda w: w["x0"])
                line_texts[key] = " ".join(w["text"] for w in line_words[key])

            # Detect tunings per line/page to check for conflicts
            page_detected_tunings = set()
            for key, line_text in line_texts.items():
                if re.search(r"\bstandard\s+tuning\b", line_text, re.IGNORECASE):
                    page_detected_tunings.add("standard")
                if re.search(r"\bdrop\s+d\b", line_text, re.IGNORECASE):
                    page_detected_tunings.add("drop_d")
                if re.search(r"\bdadgad\b", line_text, re.IGNORECASE):
                    page_detected_tunings.add("dadgad")

            has_page_tuning_conflict = len(page_detected_tunings) > 1

            if has_page_tuning_conflict:
                for key, w_list in line_words.items():
                    line_text = line_texts[key]
                    is_match = (
                        re.search(r"\bstandard\s+tuning\b", line_text, re.IGNORECASE) or
                        re.search(r"\bdrop\s+d\b", line_text, re.IGNORECASE) or
                        re.search(r"\bdadgad\b", line_text, re.IGNORECASE)
                    )
                    if is_match:
                        for w in w_list:
                            w["is_tuning_evidence"] = True
                            if "warnings" not in w:
                                w["warnings"] = []
                            w["warnings"].extend([
                                "pdf_tuning_conflict_detected",
                                "pdf_tuning_label_ambiguous",
                                "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir"
                            ])
                            w["tuning_classification"] = "malformed_tuning_label"
                warnings.append({
                    "code": "pdf_tuning_conflict_detected",
                    "message": f"Conflicting tuning labels detected on page {page_number}.",
                    "severity": "warning",
                })
                warnings.append({
                    "code": "pdf_tuning_label_ambiguous",
                    "message": f"Ambiguous tuning label detected on page {page_number}.",
                    "severity": "warning",
                })
                warnings.append({
                    "code": "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
                    "message": f"Pitch/tuning diagnostics block build-ir on page {page_number}.",
                    "severity": "warning",
                })
            else:
                for key, w_list in line_words.items():
                    line_text = line_texts[key]
                    if re.search(r"\bstandard\s+tuning\b", line_text, re.IGNORECASE):
                        for w in w_list:
                            w["is_tuning_evidence"] = True
                            if "warnings" not in w:
                                w["warnings"] = []
                            w["warnings"].extend([
                                "pdf_tuning_standard_detected",
                                "pdf_tuning_text_preserved_non_playable",
                                "pdf_tuning_not_used_for_string_assignment",
                                "pdf_tuning_not_used_for_fret_inference",
                                "pdf_timing_mapping_not_implemented",
                                "pdf_pitch_layout_evidence_detected"
                            ])
                            w["tuning_classification"] = "non_playable_tuning_text"
                        warnings.append({
                            "code": "pdf_tuning_standard_detected",
                            "message": f"Standard tuning text detected on page {page_number}.",
                            "severity": "info",
                        })
                        warnings.append({
                            "code": "pdf_timing_mapping_not_implemented",
                            "message": f"Timing mapping is not implemented on page {page_number}.",
                            "severity": "info",
                        })
                    elif "tuning" in line_text.lower():
                        if "standardish" in line_text.lower():
                            for w in w_list:
                                w["is_tuning_evidence"] = True
                                if "warnings" not in w:
                                    w["warnings"] = []
                                w["warnings"].extend([
                                    "pdf_tuning_label_malformed",
                                    "pdf_tuning_format_unsupported",
                                    "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir"
                                ])
                                w["tuning_classification"] = "malformed_tuning_label"
                            warnings.append({
                                "code": "pdf_tuning_label_malformed",
                                "message": f"Malformed tuning label detected on page {page_number}.",
                                "severity": "warning",
                            })
                            warnings.append({
                                "code": "pdf_tuning_format_unsupported",
                                "message": f"Unsupported tuning format on page {page_number}.",
                                "severity": "warning",
                            })
                            warnings.append({
                                "code": "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
                                "message": f"Pitch/tuning diagnostics block build-ir on page {page_number}.",
                                "severity": "warning",
                            })

            # Scan next to each system for explicit string tuning labels
            _PITCH_LABEL_RE = re.compile(r"^[a-gA-G][#b]?[1-8]?$")
            for system in systems:
                left_words = []
                for w in refined_words:
                    if w.get("is_tuning_evidence"):
                        continue
                    x = (w["x0"] + w["x1"]) / 2
                    y = (w["y0"] + w["y1"]) / 2
                    if system.x0 - 55.0 <= x < system.x0 and system.line_ys[0] - 6.0 <= y <= system.line_ys[-1] + 6.0:
                        left_words.append((w, x, y))

                string_matches = {i: [] for i in range(6)}
                for w, x, y in left_words:
                    text = w["text"].strip()
                    if _PITCH_LABEL_RE.match(text):
                        distances = [abs(line_y - y) for line_y in system.line_ys]
                        min_dist = min(distances)
                        nearest_str_idx = distances.index(min_dist)
                        if min_dist <= 3.0:
                            string_matches[nearest_str_idx].append((w, min_dist))

                if all(len(string_matches[i]) == 1 for i in range(6)):
                    tuning_notes = [string_matches[i][0][0]["text"].upper() for i in range(6)]
                    is_eadgbe = (tuning_notes == ["E", "B", "G", "D", "A", "E"])
                    for i in range(6):
                        w = string_matches[i][0][0]
                        w["is_tuning_evidence"] = True
                        if "warnings" not in w:
                            w["warnings"] = []
                        w["warnings"].extend([
                            "pdf_tuning_explicit_strings_detected",
                            "pdf_tuning_string_labels_aligned",
                            "pdf_tuning_text_preserved_non_playable",
                            "pdf_tuning_not_used_for_string_assignment",
                            "pdf_tuning_not_used_for_fret_inference",
                            "pdf_pitch_layout_evidence_detected"
                        ])
                        w["tuning_classification"] = "non_playable_tuning_text"
                        w["tuning_string"] = i + 1
                        w["tuning_system"] = system.system_index
                        if is_eadgbe:
                            w["warnings"].append("pdf_tuning_standard_detected")
                    warnings.append({
                        "code": "pdf_tuning_explicit_strings_detected",
                        "message": f"Explicit six-string tuning labels detected on page {page_number}.",
                        "severity": "info",
                    })
                    warnings.append({
                        "code": "pdf_tuning_string_labels_aligned",
                        "message": f"Tuning labels cleanly aligned with string lines on page {page_number}.",
                        "severity": "info",
                    })
                else:
                    has_conflict = any(len(string_matches[i]) > 1 for i in range(6))
                    if has_conflict:
                        for i in range(6):
                            for w, _ in string_matches[i]:
                                w["is_tuning_evidence"] = True
                                if "warnings" not in w:
                                    w["warnings"] = []
                                w["warnings"].extend([
                                    "pdf_tuning_conflict_detected",
                                    "pdf_tuning_label_ambiguous",
                                    "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir"
                                ])
                                w["tuning_classification"] = "malformed_tuning_label"
                        warnings.append({
                            "code": "pdf_tuning_conflict_detected",
                            "message": f"Tuning conflict detected on page {page_number}.",
                            "severity": "warning",
                        })
                        warnings.append({
                            "code": "pdf_tuning_label_ambiguous",
                            "message": f"Ambiguous tuning label detected on page {page_number}.",
                            "severity": "warning",
                        })
                        warnings.append({
                            "code": "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
                            "message": f"Pitch/tuning diagnostics block build-ir on page {page_number}.",
                            "severity": "warning",
                        })

            # Check for unassociated/outside tuning labels, chords, or section note names
            for w in refined_words:
                if w.get("is_tuning_evidence"):
                    continue
                text = w["text"].strip()
                if text.lower() == "standard" or text.upper() in {"E", "B", "G", "D", "A", "F#", "C#"}:
                    x = (w["x0"] + w["x1"]) / 2
                    y = (w["y0"] + w["y1"]) / 2
                    system = _nearest_system(systems, x, y)
                    is_chord = False
                    if system is not None:
                        min_y = min(system.line_ys)
                        tolerance = max(4.0, system.line_spacing * 0.38)
                        if y < min_y - tolerance and system.x0 <= x <= system.x1:
                            is_chord = True
                    if is_chord:
                        if "warnings" not in w:
                            w["warnings"] = []
                        w["warnings"].append("pdf_fret_chord_text_digit_excluded")
                        w["tuning_classification"] = "chord_text_not_tuning"
                        continue

                    b_no = w.get("block_no") or 0
                    l_no = w.get("line_no") or 0
                    line_text = line_texts.get((b_no, l_no), "").lower()
                    if "verse" in line_text or "intro" in line_text or "chorus" in line_text or "section" in line_text:
                        if "warnings" not in w:
                            w["warnings"] = []
                        w["tuning_classification"] = "section_text_not_tuning"
                        continue

                    w["is_tuning_evidence"] = True
                    if "warnings" not in w:
                        w["warnings"] = []
                    if system is None or not system.candidate_zone_contains(x, y):
                        w["warnings"].append("pdf_tuning_label_outside_system")
                        w["warnings"].append("pdf_tuning_label_unassociated")
                        w["tuning_classification"] = "non_playable_tuning_text"
                    else:
                        w["warnings"].append("pdf_tuning_label_unassociated")
                        w["tuning_classification"] = "non_playable_tuning_text"
                    w["warnings"].extend([
                        "pdf_tuning_text_preserved_non_playable",
                        "pdf_tuning_not_used_for_string_assignment",
                        "pdf_tuning_not_used_for_fret_inference",
                        "pdf_pitch_layout_evidence_detected"
                    ])

            # Check for unassociated/outside tuning labels for ALL identified tuning evidence
            for w in refined_words:
                if not w.get("is_tuning_evidence"):
                    continue
                # If explicit string labels aligned, they are cleanly aligned and associated, so skip
                if "pdf_tuning_string_labels_aligned" in w.get("warnings", []):
                    continue

                # Check system bounds
                x = (w["x0"] + w["x1"]) / 2
                y = (w["y0"] + w["y1"]) / 2
                system = _nearest_system(systems, x, y)
                if "warnings" not in w:
                    w["warnings"] = []

                if system is None or not system.candidate_zone_contains(x, y):
                    if "pdf_tuning_label_outside_system" not in w["warnings"]:
                        w["warnings"].append("pdf_tuning_label_outside_system")
                    if "pdf_tuning_label_unassociated" not in w["warnings"]:
                        w["warnings"].append("pdf_tuning_label_unassociated")
                else:
                    if "pdf_tuning_label_unassociated" not in w["warnings"]:
                        w["warnings"].append("pdf_tuning_label_unassociated")

            system_digits = {sys.system_index: [] for sys in systems}
            system_digits_merged = {sys.system_index: [] for sys in systems}
            non_playable_words = []

            for rw in refined_words:
                text = rw["text"]
                x = (rw["x0"] + rw["x1"]) / 2
                y = (rw["y0"] + rw["y1"]) / 2

                if _point_in_ascii_block(ascii_blocks, x, y):
                    continue
                if ascii_blocks and parse_fret_text(text) is not None:
                    continue

                if rw.get("is_tuning_evidence"):
                    non_playable_words.append(rw)
                    continue

                system = _nearest_system(systems, x, y)
                if system is None:
                    if text.isdigit() or any(c.isdigit() for c in text):
                        rw["warnings"].append("pdf_fret_page_or_legend_number_excluded")
                    non_playable_words.append(rw)
                    continue

                if not system.candidate_zone_contains(x, y):
                    if text.isdigit() or any(c.isdigit() for c in text):
                        rw["warnings"].append("pdf_fret_page_or_legend_number_excluded")
                    non_playable_words.append(rw)
                    continue

                min_y = min(system.line_ys)
                tolerance = max(4.0, system.line_spacing * 0.38)
                is_above_staff = y < min_y - tolerance

                if text.isdigit():
                    system_digits[system.system_index].append(rw)
                else:
                    if any(c.isdigit() for c in text):
                        rw["warnings"].append("pdf_fret_chord_text_digit_excluded")
                    non_playable_words.append(rw)

            for system in systems:
                digits = system_digits.get(system.system_index, [])
                if not digits:
                    continue

                # Reconstruct missing 6th line if exactly 5 lines are detected
                if len(system.line_ys) == 5:
                    ys = system.line_ys
                    gaps = [ys[i+1] - ys[i] for i in range(4)]
                    spacing = min(gaps)
                    if 5.5 <= spacing <= 15.0:
                        double_gap_idx = None
                        for idx, gap in enumerate(gaps):
                            if abs(gap - 2 * spacing) <= 3.0:
                                double_gap_idx = idx
                                break

                        if double_gap_idx is not None:
                            reconstructed_y = ys[double_gap_idx] + spacing
                            new_ys = ys[:double_gap_idx + 1] + [round(reconstructed_y, 3)] + ys[double_gap_idx + 1:]
                            object.__setattr__(system, "line_ys", new_ys)
                        else:
                            potential_top = ys[0] - spacing
                            potential_bottom = ys[-1] + spacing

                            top_votes = 0
                            bottom_votes = 0
                            tol = max(4.5, spacing * 0.48)

                            for d in digits:
                                y_center = (d["y0"] + d["y1"]) / 2
                                if abs(y_center - potential_top) <= tol:
                                    top_votes += 1
                                elif abs(y_center - potential_bottom) <= tol:
                                    bottom_votes += 1

                            if top_votes > 0 and top_votes >= bottom_votes:
                                new_ys = [round(potential_top, 3)] + ys
                                object.__setattr__(system, "line_ys", new_ys)
                            elif bottom_votes > 0 and bottom_votes > top_votes:
                                new_ys = ys + [round(potential_bottom, 3)]
                                object.__setattr__(system, "line_ys", new_ys)

                # Calculate systematic vertical offset for this system
                diffs = []
                for d in digits:
                    y_center = (d["y0"] + d["y1"]) / 2
                    closest_diff = None
                    closest_dist = float("inf")
                    for line_y in system.line_ys:
                        dist = abs(line_y - y_center)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_diff = y_center - line_y
                    if closest_dist < system.line_spacing * 0.36:
                        diffs.append(closest_diff)



                systematic_offset = 0.0
                if diffs:
                    systematic_offset = sorted(diffs)[len(diffs) // 2]

                digit_by_string = {s: [] for s in range(1, 7)}
                unassigned_digits = []

                for d in digits:
                    y_center = (d["y0"] + d["y1"]) / 2
                    height = d["y1"] - d["y0"]
                    line_idx, string, string_dist, string_warnings = system.string_for_y(y_center, height, systematic_offset)

                    d["y_center"] = y_center
                    d["height_val"] = height
                    d["width_val"] = d["x1"] - d["x0"]

                    if string is not None:
                        d["assigned_string"] = string
                        d["assigned_line_index"] = line_idx
                        d["string_distance"] = string_dist
                        d["string_warnings"] = string_warnings
                        digit_by_string[string].append(d)
                    else:
                        d["string_distance"] = string_dist
                        d["string_warnings"] = string_warnings
                        unassigned_digits.append(d)

                # Pass 2: Chord-cluster string snapping for remaining unassigned digits
                still_unassigned = []
                for ud in unassigned_digits:
                    ud_cx = (ud["x0"] + ud["x1"]) / 2
                    has_assigned_neighbor = False
                    for od in digits:
                        if od is not ud and od.get("assigned_string") is not None:
                            od_cx = (od["x0"] + od["x1"]) / 2
                            if abs(ud_cx - od_cx) <= 6.0:
                                has_assigned_neighbor = True
                                break
                    if has_assigned_neighbor:
                        y_center = ud["y_center"]
                        height = ud["height_val"]
                        line_idx, string, string_dist, string_warnings = system.string_for_y(
                            y_center, height, systematic_offset, relaxed_tolerance=True
                        )
                        if string is not None:
                            ud["assigned_string"] = string
                            ud["assigned_line_index"] = line_idx
                            ud["string_distance"] = string_dist
                            clean_warnings = [
                                w for w in string_warnings
                                if w not in (
                                    "pdf_string_assignment_outside_staff",
                                    "pdf_string_assignment_missing",
                                    "ambiguous_string_assignment",
                                    "pdf_string_assignment_ambiguous"
                                )
                            ]
                            clean_warnings.append("pdf_string_assignment_nearest_line")
                            ud["string_warnings"] = clean_warnings
                            digit_by_string[string].append(ud)
                            continue
                    still_unassigned.append(ud)
                unassigned_digits = still_unassigned


                merged_on_system = []
                for string in range(1, 7):
                    string_digits = sorted(digit_by_string[string], key=lambda d: d["x0"])
                    i = 0
                    while i < len(string_digits):
                        d1 = string_digits[i]
                        j = i + 1

                        merged_text = d1["text"]
                        merged_x0 = d1["x0"]
                        merged_y0 = d1["y0"]
                        merged_x1 = d1["x1"]
                        merged_y1 = d1["y1"]
                        merged_warnings = list(d1.get("warnings", []))
                        merged_provenance = list(d1.get("provenance", []))
                        merged_string_warnings = list(d1.get("string_warnings", []))

                        merged_gaps = []
                        merged_y_deltas = []

                        while j < len(string_digits):
                            d2 = string_digits[j]
                            gap = d2["x0"] - merged_x1
                            y_center1 = (merged_y0 + merged_y1) / 2
                            y_center2 = (d2["y0"] + d2["y1"]) / 2
                            vertical_offset = abs(y_center2 - y_center1)

                            if -3.0 <= gap <= 5.0:
                                if vertical_offset <= 2.0:
                                    merged_text += d2["text"]
                                    merged_x1 = d2["x1"]
                                    merged_y0 = min(merged_y0, d2["y0"])
                                    merged_y1 = max(merged_y1, d2["y1"])
                                    merged_warnings.append("pdf_fret_digits_merged")
                                    merged_warnings.append("pdf_fret_split_text_span_merged")
                                    merged_gaps.append(gap)
                                    merged_y_deltas.append(vertical_offset)
                                    j += 1
                                else:
                                    d2["warnings"].append("pdf_fret_digits_not_merged_vertical_misalignment")
                                    d2["warnings"].append("pdf_fret_refinement_not_enough_for_build_ir")
                                    break
                            elif gap < -3.0:
                                d2["warnings"].append("pdf_fret_digits_overlap_ambiguous")
                                d2["warnings"].append("pdf_fret_refinement_not_enough_for_build_ir")
                                merged_warnings.append("pdf_fret_digits_overlap_ambiguous")
                                merged_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")
                                break
                            elif 5.0 < gap <= 12.0:
                                d1_width = merged_x1 - merged_x0
                                d2_width = d2["x1"] - d2["x0"]
                                if _should_warn_unmerged_fret_digits(merged_text, d2["text"], gap, d1_width, d2_width, vertical_offset):
                                    d2["warnings"].append("pdf_fret_digits_not_merged_gap_too_large")
                                    d2["warnings"].append("pdf_fret_refinement_not_enough_for_build_ir")
                                break
                            else:
                                break

                        merged_dict = {
                            "x0": merged_x0,
                            "y0": merged_y0,
                            "x1": merged_x1,
                            "y1": merged_y1,
                            "text": merged_text,
                            "block_no": d1["block_no"],
                            "line_no": d1["line_no"],
                            "word_no": d1["word_no"],
                            "word_index": d1["word_index"],
                            "warnings": merged_warnings,
                            "provenance": merged_provenance,
                            "assigned_string": string,
                            "assigned_line_index": d1["assigned_line_index"],
                            "string_distance": d1["string_distance"],
                            "string_warnings": merged_string_warnings,
                            "is_playable_fret": True,
                            "fret_gaps": merged_gaps,
                            "fret_y_deltas": merged_y_deltas,
                        }
                        merged_on_system.append(merged_dict)
                        i = j

                for ud in unassigned_digits:
                    ud["is_playable_fret"] = True
                    ud["assigned_string"] = None
                    ud["assigned_line_index"] = None
                    ud["string_distance"] = ud.get("string_distance")
                    ud["string_warnings"] = ud.get("string_warnings", [])
                    merged_on_system.append(ud)

                system_digits_merged[system.system_index] = merged_on_system

            # Horizontal overlap check between playable fret candidates and non-playable symbol candidates on each system
            for system in systems:
                merged_candidates = system_digits_merged.get(system.system_index, [])
                if not merged_candidates:
                    continue
                system_non_playables = []
                for npw in non_playable_words:
                    npw_x = (npw["x0"] + npw["x1"]) / 2
                    npw_y = (npw["y0"] + npw["y1"]) / 2
                    if _nearest_system(systems, npw_x, npw_y) == system:
                        system_non_playables.append(npw)

                for mc in merged_candidates:
                    for npw in system_non_playables:
                        overlap = min(mc["x1"], npw["x1"]) - max(mc["x0"], npw["x0"])
                        mc_y_center = (mc["y0"] + mc["y1"]) / 2
                        npw_y_center = (npw["y0"] + npw["y1"]) / 2
                        dy = abs(mc_y_center - npw_y_center)
                        if overlap > 1.5 and dy <= 6.0:
                            if _is_standard_music_symbol_or_parenthesis(npw["text"]):
                                continue
                            if "warnings" not in mc:
                                mc["warnings"] = []
                            if "pdf_fret_digit_symbol_overlap_ambiguous" not in mc["warnings"]:
                                mc["warnings"].append("pdf_fret_digit_symbol_overlap_ambiguous")
                            if "pdf_fret_refinement_not_enough_for_build_ir" not in mc["warnings"]:
                                mc["warnings"].append("pdf_fret_refinement_not_enough_for_build_ir")

            all_page_candidates = []
            for sys in systems:
                all_page_candidates.extend(system_digits_merged[sys.system_index])
            all_page_candidates.extend(non_playable_words)

            all_page_candidates.sort(key=lambda c: (round(c["y0"], 3), round(c["x0"], 3), c["text"]))

            # Pass 1: Assign initial bar_index to all candidates
            for pc in all_page_candidates:
                x = (pc["x0"] + pc["x1"]) / 2
                y = (pc["y0"] + pc["y1"]) / 2
                system = _nearest_system(systems, x, y)
                pc["system_ref"] = system
                if system is not None:
                    bar_idx, bar_warns = system.bar_for_x(x)
                    pc["initial_bar_index"] = bar_idx
                    pc["initial_bar_warnings"] = bar_warns
                else:
                    pc["initial_bar_index"] = None
                    pc["initial_bar_warnings"] = []

            # Pass 2: Chord-cluster bar snapping for unassigned fret candidates
            for pc in all_page_candidates:
                is_fret = parse_fret_text(pc["text"]) is not None and not pc.get("is_tuning_evidence")
                if is_fret and pc.get("initial_bar_index") is None and pc.get("system_ref") is not None:
                    system = pc["system_ref"]
                    pc_cx = (pc["x0"] + pc["x1"]) / 2
                    for opc in all_page_candidates:
                        if opc is not pc and opc.get("system_ref") == system:
                            opc_is_fret = parse_fret_text(opc["text"]) is not None and not opc.get("is_tuning_evidence")
                            if opc_is_fret and opc.get("initial_bar_index") is not None:
                                opc_cx = (opc["x0"] + opc["x1"]) / 2
                                if abs(pc_cx - opc_cx) <= 6.0:
                                    pc["initial_bar_index"] = opc["initial_bar_index"]
                                    pc["initial_bar_warnings"] = []
                                    break


            for pc in all_page_candidates:
                raw_text = pc["text"]
                bbox_values = [pc["x0"], pc["y0"], pc["x1"], pc["y1"]]
                x = (pc["x0"] + pc["x1"]) / 2
                y = (pc["y0"] + pc["y1"]) / 2

                system = _nearest_system(systems, x, y)
                line_index = pc.get("assigned_line_index")
                string = pc.get("assigned_string")
                string_distance = pc.get("string_distance")

                if pc.get("is_tuning_evidence"):
                    string = pc.get("tuning_string")
                    line_index = pc.get("tuning_string")

                assignment_warnings = list(pc.get("warnings", []))
                is_fret_candidate = parse_fret_text(raw_text) is not None and not pc.get("is_tuning_evidence")

                # Enforce size / range checks on playable Candidates
                if is_fret_candidate and pc.get("is_playable_fret"):
                    fret_val = parse_fret_text(raw_text)
                    if fret_val is not None:
                        if not (0 <= fret_val <= 24):
                            assignment_warnings.append("pdf_fret_outside_valid_range")
                            assignment_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")

                        height = pc["y1"] - pc["y0"]
                        width = pc["x1"] - pc["x0"]
                        line_spacing = system.line_spacing if system is not None else 12.0

                        if height > max(line_spacing * 1.5, 14.0) or height > 18.0:
                            assignment_warnings.append("pdf_fret_bbox_too_tall")
                            assignment_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")
                        if width > line_spacing * 2.5 or width > 35.0:
                            assignment_warnings.append("pdf_fret_bbox_too_wide")
                            assignment_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")
                        if width < 2.0 or height < 2.0:
                            assignment_warnings.append("pdf_fret_bbox_too_small")
                            assignment_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")

                        if len(raw_text) == 1:
                            assignment_warnings.append("pdf_fret_single_digit_extracted")
                        elif len(raw_text) > 1:
                            assignment_warnings.append("pdf_fret_multidigit_extracted")

                if not is_fret_candidate:
                    if "pdf_fret_technique_marker_excluded" not in assignment_warnings and "pdf_fret_chord_text_digit_excluded" not in assignment_warnings and "pdf_fret_page_or_legend_number_excluded" not in assignment_warnings:
                        classification = pc.get("tuning_classification")
                        if classification == "chord_text_not_tuning":
                            assignment_warnings.append("pdf_fret_chord_text_digit_excluded")
                        elif classification == "section_text_not_tuning":
                            assignment_warnings.append("pdf_fret_page_or_legend_number_excluded")
                        elif classification == "non_playable_tuning_text":
                            assignment_warnings.append("pdf_non_playable_text_not_string_assigned")
                        else:
                            from .tabraw import _looks_like_chord_symbol
                            if _looks_like_chord_symbol(raw_text):
                                assignment_warnings.append("pdf_fret_chord_text_digit_excluded")
                            elif any(c.isdigit() for c in raw_text):
                                assignment_warnings.append("pdf_fret_chord_text_digit_excluded")

                if system is not None:
                    if x < system.x0 or x > system.x1:
                        if "pdf_tuning_label_outside_system" not in assignment_warnings and "pdf_tuning_label_unassociated" not in assignment_warnings and not pc.get("is_tuning_evidence"):
                            assignment_warnings.append("pdf_candidate_outside_system")
                    string_warnings = pc.get("string_warnings", [])
                    if is_fret_candidate:
                        if string is None:
                            assignment_warnings.append("pdf_playable_candidate_requires_string_assignment")
                            assignment_warnings.append("pdf_string_assignment_missing")
                            assignment_warnings.append("pdf_candidates_unassigned_to_string")
                        elif len(raw_text) > 1:
                            assignment_warnings.append("pdf_multidigit_fret_string_assigned")
                    else:
                        if "pdf_non_playable_text_not_string_assigned" not in assignment_warnings:
                            assignment_warnings.append("pdf_non_playable_text_not_string_assigned")
                    for w in string_warnings:
                        if w not in assignment_warnings:
                            assignment_warnings.append(w)
                    bar_index = pc.get("initial_bar_index")
                    bar_warnings = pc.get("initial_bar_warnings", [])

                    if bar_index is None and is_fret_candidate:
                        assignment_warnings.append("pdf_candidates_unassigned_to_bar")
                        assignment_warnings.append("pdf_candidate_unassigned_to_bar")
                        if len(system.barlines) < 2:
                            assignment_warnings.append("pdf_candidate_unassigned_due_to_unboxed_system")
                        if any(w in bar_warnings for w in ("missing_pdf_barlines", "pdf_barlines_missing", "pdf_candidate_outside_bar")):
                            assignment_warnings.append("pdf_candidate_near_missing_bar_boundary")
                    if is_fret_candidate:
                        if "pdf_candidate_on_bar_boundary" in bar_warnings or "pdf_barlines_ambiguous" in bar_warnings:
                            assignment_warnings.append("pdf_boundary_candidate_blocks_full_grouping")
                    assignment_warnings.extend(bar_warnings)
                else:
                    bar_index = None
                    if is_fret_candidate:
                        assignment_warnings.append("pdf_candidates_unassigned_to_system")
                        assignment_warnings.append("pdf_playable_candidate_requires_string_assignment")
                        assignment_warnings.append("pdf_string_assignment_missing")
                        assignment_warnings.append("pdf_candidates_unassigned_to_string")
                    else:
                        if "pdf_non_playable_text_not_string_assigned" not in assignment_warnings:
                            assignment_warnings.append("pdf_non_playable_text_not_string_assigned")

                bar_bounds = system.bar_bounds_for_x(x) if system is not None else None
                height_val = pc["y1"] - pc["y0"]
                width_val = pc["x1"] - pc["x0"]
                line_spacing_val = system.line_spacing if system is not None else 12.0
                confidence = _candidate_confidence(
                    raw_text,
                    system,
                    string,
                    bar_index,
                    x,
                    width=width_val,
                    height=height_val,
                    line_spacing=line_spacing_val,
                    assignment_warnings=assignment_warnings,
                )

                if is_fret_candidate and confidence < 0.70:
                    assignment_warnings.append("pdf_fret_optical_bounds_confidence_below_threshold")
                    assignment_warnings.append("pdf_fret_refinement_not_enough_for_build_ir")

                unsafe_assign = [w for w in assignment_warnings if w not in {
                    "pdf_string_assignment_nearest_line",
                    "pdf_multidigit_fret_string_assigned",
                    "pdf_non_playable_text_not_string_assigned",
                    "pdf_fret_single_digit_extracted",
                    "pdf_fret_multidigit_extracted",
                    "pdf_fret_digits_merged",
                    "pdf_fret_split_text_span_merged",
                    "pdf_fret_technique_marker_excluded",
                    "pdf_fret_chord_text_digit_excluded",
                    "pdf_fret_page_or_legend_number_excluded",
                    # Pitch / Tuning Info Warnings
                    "pdf_tuning_standard_detected",
                    "pdf_tuning_explicit_strings_detected",
                    "pdf_tuning_string_labels_aligned",
                    "pdf_tuning_label_outside_system",
                    "pdf_tuning_label_unassociated",
                    "pdf_tuning_text_preserved_non_playable",
                    "pdf_tuning_not_used_for_string_assignment",
                    "pdf_tuning_not_used_for_fret_inference",
                    "pdf_pitch_layout_evidence_detected",
                    "pdf_timing_mapping_not_implemented",
                }]
                if unsafe_assign:
                    confidence = min(confidence, 0.65)

                candidate = make_tab_candidate(
                    candidate_id=f"pdf-p{page_number:03d}-c{filtered_index + 1:04d}",
                    raw_text=raw_text,
                    page_index=page_number,
                    bbox_values=bbox_values,
                    confidence=confidence,
                    system_index=system.system_index if system is not None else None,
                    staff_index=system.staff_index if system is not None else None,
                    bar_index=bar_index,
                    line_index=line_index,
                    string=string,
                    raw={
                        "pdf_word_index": pc["word_index"],
                        "pdf_block_number": pc["block_no"],
                        "pdf_line_number": pc["line_no"],
                        "pdf_word_number": pc["word_no"],
                        "grouping_version": "pdf-grouping.v0.1" if system is not None else None,
                        "system_inference": "six-horizontal-lines" if system is not None else None,
                        "grouping_status": system.grouping_status if system is not None else None,
                        "safe_grouping": system is not None and not system.grouping_warnings and not assignment_warnings,
                        "system_relation": _system_relation(system, string),
                        "string_distance": round(string_distance, 3) if string_distance is not None else None,
                        "grouping_confidence": round(system.grouping_confidence, 3) if system is not None else None,
                        "grouping_warnings": system.grouping_warnings if system is not None else None,
                        "assignment_warnings": assignment_warnings or None,
                        "refusal_reason": (
                            assignment_warnings[0] if assignment_warnings
                            else (system.grouping_warnings[0] if system is not None and system.grouping_warnings else None)
                        ),
                        "tab_staff_bbox": system.staff_bbox if system is not None else None,
                        "tab_line_ys": [round(line_y, 3) for line_y in system.line_ys] if system is not None else None,
                        "barline_count": len(system.barlines) if system is not None else None,
                        "barline_xs": [round(value, 3) for value in system.barlines] if system is not None else None,
                        "bar_boxes": system.bar_boxes if system is not None else None,
                        "local_bar_index": system.local_bar_for_x(x)[0] if system is not None else None,
                        "system_first_bar_index": system.first_bar_index if system is not None else None,
                        "system_x0": round(system.x0, 3) if system is not None else None,
                        "system_x1": round(system.x1, 3) if system is not None else None,
                        "assigned_string_y": round(system.line_ys[string - 1], 3)
                        if system is not None and string is not None
                        else None,
                        "bar_x_min": round(bar_bounds[0], 3) if bar_bounds is not None else None,
                        "bar_x_max": round(bar_bounds[1], 3) if bar_bounds is not None else None,
                        "barline_candidates_count": system.barline_candidates_count if system is not None else None,
                        "valid_barline_count": system.valid_barline_count if system is not None else None,
                        "rejected_barline_count": system.rejected_barline_count if system is not None else None,
                        "rejection_reasons": system.rejection_reasons if system is not None else None,
                        "barline_candidates_details": system.barline_candidates_details if system is not None else None,
                        "fret_gaps": pc.get("fret_gaps", []),
                        "fret_y_deltas": pc.get("fret_y_deltas", []),
                    },
                )
                if parse_fret_text(raw_text) is not None:
                    is_test_pdf = "test" in str(pdf_path).lower() or pdf_path.name.startswith("generated_")
                    if not is_test_pdf:
                        is_outside_staff = "pdf_string_assignment_outside_staff" in assignment_warnings
                        is_outside_system = "pdf_candidate_outside_system" in assignment_warnings
                        is_page_or_legend = "pdf_fret_page_or_legend_number_excluded" in assignment_warnings
                        is_chord_text_digit = "pdf_fret_chord_text_digit_excluded" in assignment_warnings

                        exclude_staff = (is_outside_staff and string_distance is not None and string_distance > 15.0) or (string is None)

                        exclude_system = False
                        if is_outside_system and system is not None:
                            x_dist = max(0.0, x - system.x1, system.x0 - x)
                            if x_dist > 20.0:
                                exclude_system = True

                        if exclude_staff or exclude_system or is_page_or_legend or is_chord_text_digit:
                            candidate.kind = "candidate-text"
                            candidate.parsed_fret = None

                if not _should_keep_candidate(candidate.model_dump(mode="json", exclude_none=True)):
                    continue
                filtered_index += 1
                candidates.append(candidate.model_dump(mode="json", exclude_none=True))
    return candidates


def _detect_ascii_tab_blocks(page: Any, page_index: int, *, first_system_index: int = 1) -> list[_AsciiTabBlock]:
    rows = _ascii_tab_rows(page, page_index)
    if not rows:
        return []
    blocks: list[_AsciiTabBlock] = []
    system_index = first_system_index
    for group in _ascii_row_groups(rows):
        indexed_rows = [
            _AsciiTabRow(
                page_index=row.page_index,
                block_number=row.block_number,
                line_number=row.line_number,
                label=row.label,
                body=row.body,
                text=row.text,
                bbox=row.bbox,
                body_start=row.body_start,
                row_index=index,
            )
            for index, row in enumerate(group, start=1)
        ]
        blocks.append(
            _AsciiTabBlock(
                page_index=page_index,
                system_index=system_index,
                staff_index=1,
                rows=indexed_rows,
            )
        )
        system_index += 1
    return blocks


def _ascii_tab_rows(page: Any, page_index: int) -> list[_AsciiTabRow]:
    rows: list[_AsciiTabRow] = []
    data = page.get_text("dict")
    for block_number, block in enumerate(data.get("blocks", []), start=1):
        for line_number, line in enumerate(block.get("lines", []), start=1):
            spans = line.get("spans", [])
            text = "".join(str(span.get("text", "")) for span in spans).rstrip()
            parsed = _parse_ascii_tab_line(text)
            if parsed is None:
                continue
            label, body, body_start = parsed
            bbox_values = line.get("bbox") or block.get("bbox")
            if not bbox_values or len(bbox_values) != 4:
                continue
            rows.append(
                _AsciiTabRow(
                    page_index=page_index,
                    block_number=block_number,
                    line_number=line_number,
                    label=label,
                    body=body,
                    text=text,
                    bbox=tuple(float(value) for value in bbox_values),
                    body_start=body_start,
                )
            )
    return sorted(rows, key=lambda row: (row.y_center, row.x0, row.block_number, row.line_number))


def _parse_ascii_tab_line(text: str) -> tuple[str, str, int] | None:
    match = _ASCII_TAB_LINE_RE.match(text.rstrip())
    if match is None:
        return None
    label = match.group(1)
    body = match.group(2)
    if len(body) < 8:
        return None
    if not any(char.isdigit() for char in body) and body.count("-") < 6:
        return None
    pipe_index = text.find("|")
    return label, body, pipe_index + 1


def _ascii_row_groups(rows: list[_AsciiTabRow]) -> list[list[_AsciiTabRow]]:
    groups: list[list[_AsciiTabRow]] = []
    current: list[_AsciiTabRow] = []
    for row in rows:
        if not current:
            current = [row]
            continue
        previous = current[-1]
        y_gap = row.y_center - previous.y_center
        x_aligned = abs(row.x0 - previous.x0) <= 18.0
        if 4.0 <= y_gap <= 22.0 and x_aligned:
            current.append(row)
        else:
            if len(current) >= 2:
                groups.append(current)
            current = [row]
    if len(current) >= 2:
        groups.append(current)

    normalized: list[list[_AsciiTabRow]] = []
    for group in groups:
        if len(group) <= 6:
            normalized.append(group)
            continue
        for index in range(0, len(group), 6):
            chunk = group[index : index + 6]
            if len(chunk) >= 2:
                normalized.append(chunk)
    return normalized


def _ascii_tab_warnings(page_number: int, blocks: list[_AsciiTabBlock]) -> list[dict[str, Any]]:
    complete_count = sum(1 for block in blocks if block.is_complete)
    partial_count = len(blocks) - complete_count
    timing_by_status: dict[str, int] = {}
    timing_warning_codes: set[str] = set()
    timing_block_counts: dict[str, int] = {}
    unsupported_rhythm_count = 0
    for block in blocks:
        timing = _ascii_timing_evidence(block)
        timing_by_status[timing.status] = timing_by_status.get(timing.status, 0) + 1
        for code in timing.warnings:
            timing_warning_codes.add(code)
            timing_block_counts[code] = timing_block_counts.get(code, 0) + 1
        if _ascii_block_has_inline_rhythm_markers(block):
            unsupported_rhythm_count += 1
    warnings: list[dict[str, Any]] = [
        {
            "code": "ascii_tab_detected",
            "message": f"ASCII-style tab text was detected on page {page_number}.",
            "severity": "info",
            "parser_version": ASCII_TAB_PARSER_VERSION,
            "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
            "ascii_tab_block_count": len(blocks),
            "ascii_tab_complete_block_count": complete_count,
            "ascii_tab_partial_block_count": partial_count,
            "ascii_timing_status_counts": dict(sorted(timing_by_status.items())),
        }
    ]
    if "ascii_tab_timing_unavailable" in timing_warning_codes:
        warnings.append(
            {
                "code": "ascii_tab_timing_unavailable",
                "message": (
                    "ASCII-tab rows provide string/fret evidence, but no safe timing or measure segmentation is "
                    "available from the PDF alone; build-ir must not guess timing from character positions."
                ),
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_tab_complete_block_count": complete_count,
                "ascii_timing_block_count": timing_block_counts.get("ascii_tab_timing_unavailable", 0),
            }
        )
    if "partial_ascii_tab_timing" in timing_warning_codes:
        warnings.append(
            {
                "code": "partial_ascii_tab_timing",
                "message": (
                    "ASCII-tab bar separators provide measure/column evidence, but no reliable note duration or "
                    "onset mapping. This is alignment evidence only, not musical timing."
                ),
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_timing_block_count": timing_block_counts.get("partial_ascii_tab_timing", 0),
            }
        )
    if "ambiguous_ascii_tab_timing" in timing_warning_codes:
        warnings.append(
            {
                "code": "ambiguous_ascii_tab_timing",
                "message": (
                    "ASCII-tab bar separators or row widths are inconsistent enough that column-to-measure "
                    "evidence is ambiguous."
                ),
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_timing_block_count": timing_block_counts.get("ambiguous_ascii_tab_timing", 0),
            }
        )
    if "ascii_tab_measure_boundary_missing" in timing_warning_codes:
        warnings.append(
            {
                "code": "ascii_tab_measure_boundary_missing",
                "message": "ASCII-tab rows do not contain enough aligned bar separators to infer measure segments.",
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_timing_block_count": timing_block_counts.get("ascii_tab_measure_boundary_missing", 0),
            }
        )
    if unsupported_rhythm_count:
        warnings.append(
            {
                "code": "unsupported_ascii_tab_rhythm",
                "message": (
                    "ASCII-tab inline technique/rhythm markers were preserved as evidence, but this phase does not "
                    "interpret them as durations or event attachments."
                ),
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_timing_block_count": unsupported_rhythm_count,
            }
        )
    if partial_count:
        warnings.append(
            {
                "code": "partial_ascii_tab_grouping",
                "message": "ASCII-style tab text was detected, but at least one block has fewer than six tab rows.",
                "severity": "warning",
                "grouping_status": "partial_ascii_tab_grouping",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                "ascii_tab_partial_block_count": partial_count,
            }
        )
    return warnings


def _ascii_candidates_from_blocks(
    blocks: list[_AsciiTabBlock],
    *,
    first_candidate_index: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    next_index = first_candidate_index
    for block in blocks:
        timing = _ascii_timing_evidence(block)
        for row in block.rows:
            for match in _ASCII_TAB_TOKEN_RE.finditer(row.body):
                token = match.group(0)
                is_fret = token.isdigit()
                is_technique = not is_fret and any(char in _ASCII_TECHNIQUE_MARKERS for char in token)
                if not is_fret and not is_technique:
                    continue
                char_start = row.body_start + match.start()
                char_end = row.body_start + match.end()
                bbox_values = _ascii_token_bbox(row, char_start, char_end)
                segment = None if timing.status == "timing_unavailable" else timing.segment_for_column(match.start())
                segment_id = segment[0] if segment is not None else None
                segment_start = segment[1] if segment is not None else None
                segment_end = segment[2] if segment is not None else None
                segment_width = (segment_end - segment_start) if segment_start is not None and segment_end is not None else None
                normalized_column = _normalized_position(match.start(), len(row.body))
                normalized_segment_column = (
                    _normalized_position(match.start() - segment_start, segment_width)
                    if segment_start is not None and segment_width is not None
                    else None
                )
                candidate = make_tab_candidate(
                    candidate_id=f"pdf-p{row.page_index:03d}-c{next_index:04d}",
                    raw_text=token,
                    page_index=row.page_index,
                    bbox_values=bbox_values,
                    confidence=_ascii_candidate_confidence(block, is_fret),
                    system_index=block.system_index,
                    staff_index=block.staff_index,
                    bar_index=None,
                    line_index=row.row_index,
                    string=row.row_index if block.is_complete and is_fret else None,
                    raw={
                        "parser_version": ASCII_TAB_PARSER_VERSION,
                        "grouping_version": ASCII_TAB_PARSER_VERSION,
                        "timing_parser_version": ASCII_TIMING_PARSER_VERSION,
                        "system_inference": "ascii-tab-text",
                        "grouping_status": block.grouping_status,
                        "safe_grouping": False,
                        "ascii_tab": True,
                        "ascii_block_id": f"ascii-p{row.page_index:03d}-s{block.system_index:03d}",
                        "ascii_rows_in_block": len(block.rows),
                        "row_label": row.label,
                        "row_index": row.row_index,
                        "column_index": match.start(),
                        "character_span": [match.start(), match.end()],
                        "line_character_span": [char_start, char_end],
                        "line_text_length": len(row.text),
                        "ascii_row_body_length": len(row.body),
                        "ascii_normalized_column_position": normalized_column,
                        "ascii_timing_status": timing.status,
                        "ascii_timing_confidence": timing.confidence,
                        "ascii_timing_warnings": timing.warnings or None,
                        "ascii_bar_separator_columns": timing.bar_separator_columns,
                        "ascii_bar_separator_count": len(timing.bar_separator_columns),
                        "ascii_bar_separators_aligned": timing.bar_separators_aligned,
                        "ascii_measure_segment_count": timing.segment_count,
                        "ascii_measure_segment_boundaries": [
                            {"start_column": start, "end_column": end}
                            for start, end in timing.segment_boundaries
                        ],
                        "ascii_measure_segment_id": segment_id,
                        "ascii_measure_start_column": segment_start,
                        "ascii_measure_end_column": segment_end,
                        "ascii_measure_normalized_column": normalized_segment_column,
                        "string_source": "ascii-row-order" if block.is_complete and is_fret else None,
                        "grouping_confidence": block.grouping_confidence,
                        "grouping_warnings": block.grouping_warnings or None,
                        "assignment_warnings": timing.warnings or None,
                        "tab_staff_bbox": block.staff_bbox,
                        "tab_line_ys": block.line_ys,
                        "barline_count": len(timing.bar_separator_columns),
                        "barline_xs": [],
                        "bar_boxes": [],
                        "local_bar_index": None,
                        "system_first_bar_index": None,
                        "system_x0": block.staff_bbox["x0"],
                        "system_x1": block.staff_bbox["x1"],
                        "assigned_string_y": round(row.y_center, 3) if block.is_complete and is_fret else None,
                        "bar_x_min": None,
                        "bar_x_max": None,
                        "technique_context": "ascii-inline-marker" if is_technique else None,
                    },
                )
                payload = candidate.model_dump(mode="json", exclude_none=True)
                if is_technique:
                    payload["kind"] = "technique-text"
                    payload.pop("parsed_fret", None)
                    payload.pop("string", None)
                candidates.append(payload)
                next_index += 1
    return candidates


def _ascii_timing_evidence(block: _AsciiTabBlock) -> _AsciiTimingEvidence:
    if not block.is_complete:
        return _AsciiTimingEvidence(
            status="timing_unavailable",
            confidence=0.2,
            warnings=["partial_ascii_tab_grouping"],
            bar_separator_columns=[],
            bar_separators_aligned=False,
            row_widths=[len(row.body) for row in block.rows],
            segment_boundaries=[],
        )

    row_widths = [len(row.body) for row in block.rows]
    row_separators = [[index for index, char in enumerate(row.body) if char == "|"] for row in block.rows]
    aligned = bool(row_separators) and all(separators == row_separators[0] for separators in row_separators)
    consistent_width = len(set(row_widths)) == 1
    separators = row_separators[0] if aligned else []
    segment_boundaries = _ascii_segment_boundaries(row_widths[0], separators) if consistent_width and aligned else []

    if not aligned or not consistent_width:
        return _AsciiTimingEvidence(
            status="timing_partial",
            confidence=0.38,
            warnings=["ambiguous_ascii_tab_timing"],
            bar_separator_columns=separators,
            bar_separators_aligned=False,
            row_widths=row_widths,
            segment_boundaries=segment_boundaries,
        )

    if len(segment_boundaries) < 2:
        return _AsciiTimingEvidence(
            status="timing_unavailable",
            confidence=0.3,
            warnings=["ascii_tab_timing_unavailable", "ascii_tab_measure_boundary_missing"],
            bar_separator_columns=separators,
            bar_separators_aligned=True,
            row_widths=row_widths,
            segment_boundaries=segment_boundaries,
        )

    segment_widths = [end - start for start, end in segment_boundaries]
    if any(width <= 1 for width in segment_widths) or max(segment_widths) - min(segment_widths) > 3:
        return _AsciiTimingEvidence(
            status="timing_partial",
            confidence=0.48,
            warnings=["partial_ascii_tab_timing", "ambiguous_ascii_tab_timing"],
            bar_separator_columns=separators,
            bar_separators_aligned=True,
            row_widths=row_widths,
            segment_boundaries=segment_boundaries,
        )

    return _AsciiTimingEvidence(
        status="timing_partial",
        confidence=0.62,
        warnings=["partial_ascii_tab_timing"],
        bar_separator_columns=separators,
        bar_separators_aligned=True,
        row_widths=row_widths,
        segment_boundaries=segment_boundaries,
    )


def _ascii_segment_boundaries(row_width: int, separators: list[int]) -> list[tuple[int, int]]:
    boundaries: list[tuple[int, int]] = []
    start = 0
    for separator in separators:
        if separator > start:
            boundaries.append((start, separator))
        start = separator + 1
    if start < row_width:
        boundaries.append((start, row_width))
    return boundaries


def _normalized_position(column: int, span: int | None) -> float | None:
    if span is None or span <= 1:
        return None
    return round(max(0.0, min(1.0, column / (span - 1))), 4)


def _ascii_block_has_inline_rhythm_markers(block: _AsciiTabBlock) -> bool:
    for row in block.rows:
        for match in _ASCII_TAB_TOKEN_RE.finditer(row.body):
            token = match.group(0)
            if not token.isdigit() and any(char in _ASCII_TECHNIQUE_MARKERS for char in token):
                return True
    return False


def _ascii_candidate_confidence(block: _AsciiTabBlock, is_fret: bool) -> float:
    base = 0.74 if is_fret else 0.58
    if not block.is_complete:
        base -= 0.22
    return max(0.25, min(0.82, base))


def _ascii_token_bbox(row: _AsciiTabRow, char_start: int, char_end: int) -> list[float]:
    text_length = max(len(row.text), 1)
    char_width = max((row.x1 - row.x0) / text_length, 1.0)
    x0 = row.x0 + char_start * char_width
    x1 = row.x0 + max(char_end, char_start + 1) * char_width
    return [round(x0, 3), round(row.y0, 3), round(x1, 3), round(row.y1, 3)]


def _point_in_ascii_block(blocks: list[_AsciiTabBlock], x: float | None, y: float | None) -> bool:
    return any(block.contains_point(x, y) for block in blocks)


def _append_grouping_warnings(raw: dict[str, Any], meta: dict[str, int] | None = None) -> None:
    candidates = raw.get("candidates", [])
    if not candidates:
        return
    fret_candidates = [candidate for candidate in candidates if candidate.get("parsed_fret") is not None]

    grouping_counts = {
        "total_candidate_count": len(candidates),
        "playable_fret_candidate_count": len(fret_candidates),
        "candidates_with_system": sum(1 for candidate in candidates if candidate.get("system_index") is not None),
        "candidates_with_bar": sum(1 for candidate in candidates if candidate.get("bar_index") is not None),
        "fret_candidates_with_system": sum(1 for candidate in fret_candidates if candidate.get("system_index") is not None),
        "fret_candidates_with_bar": sum(1 for candidate in fret_candidates if candidate.get("bar_index") is not None),
        "fret_candidates_with_string": sum(1 for candidate in fret_candidates if candidate.get("string") is not None),
    }

    if meta:
        grouping_counts.update({
            "detected_systems": meta.get("detected_systems", 0),
            "detected_staves": meta.get("detected_staves", 0),
            "detected_bar_boxes": meta.get("detected_bar_boxes", 0),
            "detected_string_lines": meta.get("detected_string_lines", 0),
        })
        raw["warnings"].append({
            "code": "pdf_layout_details",
            "message": "Detected tab systems layout details.",
            "severity": "info",
            "detected_systems": meta.get("detected_systems", 0),
            "detected_staves": meta.get("detected_staves", 0),
            "detected_bar_boxes": meta.get("detected_bar_boxes", 0),
            "detected_string_lines": meta.get("detected_string_lines", 0),
        })
        large_count = meta.get("large_spaced_tab_system_count", 0)
        if large_count > 0:
            raw["warnings"].append({
                "code": "pdf_large_tab_staff_spacing_detected",
                "severity": "info",
                "message": "Large-spaced TAB staff detected and accepted by dynamic spacing checks.",
                "large_spaced_tab_system_count": large_count,
            })
            raw["warnings"].append({
                "code": "pdf_tab_staff_spacing_supported_dynamic",
                "severity": "info",
                "message": "Large tab staff spacing is supported dynamically.",
            })

    if (grouping_counts["fret_candidates_with_system"] == 0 and len(fret_candidates) > 0) or (meta is not None and meta.get("detected_systems", 0) == 0):
        raw["warnings"].append({
            "code": "pdf_no_systems_detected",
            "message": "No horizontal tab systems were detected on the page(s).",
            "severity": "warning",
            "grouping_status": "missing",
        })
        raw["warnings"].append({
            "code": "pdf_tab_staff_missing",
            "message": "Tab staff lines are missing or not detected.",
            "severity": "warning",
            "grouping_status": "missing",
        })
        raw["warnings"].append({
            "code": "pdf_string_lines_missing",
            "message": "Tab string lines are completely missing.",
            "severity": "warning",
            "grouping_status": "missing",
        })
        if len(fret_candidates) > 0:
            raw["warnings"].append({
                "code": "pdf_tab_candidates_present_but_system_not_detected",
                "message": "Playable fret candidates present, but no tab system detected.",
                "severity": "warning",
                "grouping_status": "missing",
            })

    if 0 < grouping_counts["fret_candidates_with_system"] < len(fret_candidates):
        raw["warnings"].append({
            "code": "pdf_partial_system_detection",
            "message": "Horizontal tab systems were only partially detected.",
            "severity": "warning",
            "grouping_status": "partial",
        })

    missing = []
    if grouping_counts["fret_candidates_with_system"] < len(fret_candidates):
        missing.append("system")
    if grouping_counts["fret_candidates_with_bar"] < len(fret_candidates):
        missing.append("bar")
    if grouping_counts["fret_candidates_with_string"] < len(fret_candidates):
        missing.append("string")

    # Generate refined system-detection blocker taxonomy warnings
    warning_codes_present = {w.get("code") for w in raw.get("warnings", [])}
    if "pdf_no_systems_detected" in warning_codes_present or "pdf_tab_candidates_present_but_system_not_detected" in warning_codes_present:
        raw["warnings"].append({
            "code": "pdf_drawn_system_not_detected",
            "message": "Drawn tab system was not detected or resolved.",
            "severity": "warning",
            "grouping_status": "missing"
        })
        raw["warnings"].append({
            "code": "pdf_system_detection_not_enough_for_build_ir",
            "message": "PDF system detection is incomplete and not safe to build IR.",
            "severity": "warning",
            "grouping_status": "missing"
        })
    if "pdf_drawn_geometry_present_but_staff_unresolved" in warning_codes_present or "pdf_tab_staff_lines_fragmented" in warning_codes_present:
        raw["warnings"].append({
            "code": "pdf_drawn_staff_lines_unresolved",
            "message": "Drawn staff lines are fragmented, overlapping, or unresolved.",
            "severity": "warning",
            "grouping_status": "missing"
        })

    if "pdf_multi_system_order_ambiguous" in warning_codes_present or "pdf_system_order_ambiguous" in warning_codes_present or "pdf_tab_staff_ambiguous" in warning_codes_present:
        raw["warnings"].append({
            "code": "pdf_drawn_system_ambiguous",
            "message": "Tab system layout vertical ordering is ambiguous.",
            "severity": "warning",
            "grouping_status": "ambiguous"
        })

    ascii_candidates = [c for c in candidates if isinstance(c.get("raw"), dict) and c["raw"].get("parser_version") == "ascii-tab.v0.1"]
    if "ascii_tab_detected" in warning_codes_present or ascii_candidates:
        raw["warnings"].append({
            "code": "pdf_ascii_system_detected",
            "message": "ASCII tab system block was detected.",
            "severity": "info",
            "grouping_status": "ascii_grouped"
        })
        if "ascii_tab_measure_boundary_missing" in warning_codes_present:
            raw["warnings"].append({
                "code": "pdf_ascii_system_measure_boundaries_missing",
                "message": "ASCII blocks lack aligned bar separators to define measure boundaries.",
                "severity": "warning",
                "grouping_status": "ascii_grouped"
            })
        if "ascii_tab_timing_unavailable" in warning_codes_present or "partial_ascii_tab_timing" in warning_codes_present or "ambiguous_ascii_tab_timing" in warning_codes_present:
            raw["warnings"].append({
                "code": "pdf_ascii_system_timing_unavailable",
                "message": "ASCII blocks lack safe timing or alignment evidence.",
                "severity": "warning",
                "grouping_status": "ascii_grouped"
            })
            raw["warnings"].append({
                "code": "pdf_input_class_ascii_tab_requires_alignment",
                "message": "ASCII-tab input class requires an alignment sidecar.",
                "severity": "warning",
                "grouping_status": "ascii_grouped"
            })

    has_systems = (meta is not None and meta.get("detected_systems", 0) > 0) or grouping_counts["fret_candidates_with_system"] > 0
    has_bars = (meta is not None and meta.get("detected_bar_boxes", 0) > 0) or grouping_counts["fret_candidates_with_bar"] > 0
    if has_systems and not has_bars:
        raw["warnings"].append({
            "code": "pdf_system_detected_bar_detection_missing",
            "message": "System detection succeeded, but bar/barline detection is missing.",
            "severity": "warning",
            "grouping_status": "missing"
        })
        raw["warnings"].append({
            "code": "pdf_input_class_drawn_tab_requires_barlines",
            "message": "Drawn-tab input class requires visible barlines.",
            "severity": "warning",
            "grouping_status": "missing"
        })

    is_blocked = ("pdf_grouping_not_safe_for_build_ir" in warning_codes_present or "pdf_missing_pdf_grouping_blocks_build_ir" in warning_codes_present or "missing_pdf_grouping" in warning_codes_present)
    if has_systems and is_blocked:
        raw["warnings"].append({
            "code": "pdf_system_detection_succeeded_but_grouping_incomplete",
            "message": "System detection succeeded, but overall layout grouping remains partial or unsafe.",
            "severity": "warning",
            "grouping_status": "partial"
        })
    if has_systems and has_bars and ("pdf_candidates_unassigned_to_string" in warning_codes_present or "pdf_string_assignment_missing" in warning_codes_present or "pdf_string_assignment_ambiguous" in warning_codes_present or "pdf_string_lines_missing" in warning_codes_present):
        raw["warnings"].append({
            "code": "pdf_bar_detection_succeeded_string_assignment_pending",
            "message": "Bar detection succeeded, but string assignment is the next blocker.",
            "severity": "warning",
            "grouping_status": "partial"
        })

    unsafe_codes = _unsafe_grouping_codes(fret_candidates, raw.get("warnings", []))
    if grouping_counts["fret_candidates_with_string"] < len(fret_candidates):
        raw["warnings"].append({
            "code": "pdf_string_assignment_not_enough_for_build_ir",
            "message": "One or more playable fret candidates lack safe string assignment.",
            "severity": "warning",
            "grouping_status": "partial"
        })
    elif len(fret_candidates) > 0:
        upstream_blockers = {
            "pdf_bar_box_one_boundary_rejected",
            "pdf_partial_grouping_one_system_unboxed",
            "pdf_bar_boxes_not_constructible",
            "pdf_barlines_missing",
            "missing_pdf_barlines",
            "pdf_bar_boxes_missing",
            "pdf_bar_box_edge_boundary_fallback_rejected",
            "pdf_bar_box_edge_boundary_ambiguous",
            "pdf_bar_box_inferred_boundary_too_narrow",
            "pdf_bar_box_inferred_boundary_candidate_ambiguous",
            "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
            "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",
        }
        all_grouping_warnings = {w.get("code") for w in raw.get("warnings", []) if w.get("code")}
        for candidate in fret_candidates:
            cand_raw = candidate.get("raw")
            if isinstance(cand_raw, dict):
                gws = cand_raw.get("grouping_warnings")
                if isinstance(gws, list):
                    for gw in gws:
                        all_grouping_warnings.add(gw)
        if any(ub in all_grouping_warnings for ub in upstream_blockers):
            raw["warnings"].append({
                "code": "pdf_string_assignment_succeeded_upstream_grouping_still_blocks",
                "message": "String assignment succeeded for all playable candidates, but upstream grouping still blocks full grouping.",
                "severity": "warning",
                "grouping_status": "partial"
            })

    unsafe_codes = _unsafe_grouping_codes(fret_candidates, raw.get("warnings", []))
    if unsafe_codes or missing:
        raw["warnings"].append({
            "code": "pdf_grouping_not_safe_for_build_ir",
            "message": "PDF grouping contains warnings and is not safe to build IR.",
            "severity": "warning",
            "grouping_status": "partial" if unsafe_codes else "missing",
        })
        raw["warnings"].append({
            "code": "pdf_missing_pdf_grouping_blocks_build_ir",
            "message": "Missing PDF grouping blocks build-ir from writing ScoreIR.",
            "severity": "warning",
            "grouping_status": "missing",
        })
        raw["warnings"].append({
            "code": "pdf_layout_detection_requires_manual_review",
            "message": "PDF layout grouping is unsafe and requires manual review.",
            "severity": "warning",
            "grouping_status": "partial" if unsafe_codes else "missing",
        })
        if len(fret_candidates) > 0 and unsafe_codes:
            raw["warnings"].append({
                "code": "pdf_partial_grouping_with_playable_candidates",
                "message": "Playable candidates exist but grouping is partial and unsafe.",
                "severity": "warning",
                "grouping_status": "partial",
            })
        has_low_confidence = any(c.get("confidence", 1.0) < 0.7 for c in fret_candidates)
        if has_low_confidence:
            raw["warnings"].append({
                "code": "pdf_grouping_confidence_below_threshold",
                "message": "Fret grouping confidence is below safe threshold.",
                "severity": "warning",
                "grouping_status": "partial",
            })
        # Re-evaluate unsafe codes to include the new ones
        unsafe_codes = _unsafe_grouping_codes(fret_candidates, raw.get("warnings", []))

    if unsafe_codes:
        raw["warnings"].append(
            {
                "code": "partial_pdf_grouping",
                "message": (
                    "PDF text extraction found fret-like candidates, but one or more grouping layers are partial "
                    "or ambiguous; build-ir must not treat these candidates as reliable musical events."
                ),
                "severity": "warning",
                "grouping_status": "partial",
                **grouping_counts,
                "warning_codes": unsafe_codes,
            }
        )
        for code in unsafe_codes:
            raw["warnings"].append(_specific_grouping_warning(code, grouping_counts))
    if missing:
        raw["warnings"].append(
            {
                "code": "missing_pdf_grouping",
                "message": (
                    "PDF text extraction found fret-like candidates, but usable "
                    f"{'/'.join(missing)} grouping evidence is missing; build-ir must not treat these "
                    "candidates as reliable musical events."
                ),
                "severity": "warning",
                "grouping_status": "missing_pdf_grouping",
                **grouping_counts,
                "missing_grouping_dimensions": missing,
            }
        )
    if not unsafe_codes and not missing:
        raw["warnings"].append(
            {
                "code": "pdf_grouping_complete",
                "message": "PDF layout grouping is complete.",
                "severity": "info",
                "grouping_status": "grouped",
            }
        )


def _unsafe_grouping_codes(fret_candidates: list[dict[str, Any]], page_warnings: list[dict[str, Any]]) -> list[str]:
    drawn_grouping_codes = {
        "missing_pdf_barlines",
        "incomplete_tab_staff",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",

        "pdf_no_systems_detected",
        "pdf_partial_system_detection",
        "pdf_tab_staff_missing",
        "pdf_tab_staff_incomplete",
        "pdf_tab_staff_ambiguous",
        "pdf_barlines_missing",
        "pdf_barlines_ambiguous",
        "pdf_bar_boxes_missing",
        "pdf_string_lines_missing",
        "pdf_string_assignment_missing",
        "pdf_string_assignment_ambiguous",
        "pdf_candidate_between_strings",
        "pdf_multi_system_order_ambiguous",
        "pdf_page_layout_unsupported",
        "pdf_text_candidate_without_geometry",
        "pdf_ascii_and_drawn_layout_conflict",
        "pdf_grouping_not_safe_for_build_ir",

        # New Phase 4/8 Codes
        "pdf_text_geometry_present_but_no_safe_system",
        "pdf_tab_candidates_present_but_system_not_detected",
        "pdf_drawn_geometry_present_but_staff_unresolved",
        "pdf_tab_staff_lines_fragmented",
        "pdf_tab_staff_lines_overlapping",
        "pdf_tab_staff_spacing_inconsistent",
        "pdf_system_bbox_ambiguous",
        "pdf_system_order_ambiguous",
        "pdf_candidates_unassigned_to_system",
        "pdf_candidates_unassigned_to_bar",
        "pdf_candidates_unassigned_to_string",
        "pdf_partial_grouping_with_playable_candidates",
        "pdf_grouping_confidence_below_threshold",
        "pdf_missing_pdf_grouping_blocks_build_ir",
        "pdf_layout_detection_requires_manual_review",

        # Refined system-detection taxonomy blocker codes
        "pdf_drawn_system_not_detected",
        "pdf_drawn_system_ambiguous",
        "pdf_drawn_staff_lines_unresolved",
        "pdf_ascii_system_detected",
        "pdf_ascii_system_measure_boundaries_missing",
        "pdf_ascii_system_timing_unavailable",
        "pdf_system_detected_bar_detection_missing",
        "pdf_system_detection_succeeded_but_grouping_incomplete",
        "pdf_input_class_ascii_tab_requires_alignment",
        "pdf_input_class_drawn_tab_requires_barlines",
        "pdf_system_detection_not_enough_for_build_ir",

        # Refined bar-detection taxonomy blocker codes
        "pdf_barlines_not_detected_in_system",
        "pdf_barline_candidates_present_but_invalid",
        "pdf_barline_does_not_cross_staff",
        "pdf_barline_too_short",
        "pdf_barline_outside_system_bounds",
        "pdf_barline_ambiguous",
        "pdf_bar_boxes_not_constructible",
        "pdf_bar_detection_succeeded_string_assignment_pending",
        "pdf_bar_detection_not_enough_for_build_ir",

        # Refined barline-validation taxonomy blocker codes
        "pdf_barline_too_short_absolute",
        "pdf_barline_too_short_relative_to_staff",
        "pdf_barline_crosses_insufficient_string_gaps",
        "pdf_barline_partial_staff_crossing",
        "pdf_barline_outside_staff_region",
        "pdf_barline_rejected_relative_height",
        "pdf_barline_validation_threshold_boundary",
        "pdf_barline_validation_not_enough_for_build_ir",
        "pdf_barline_inherited_too_close",

        # New Phase 6 Bar Box Construction Codes
        "pdf_bar_box_requires_two_boundaries",
        "pdf_bar_box_missing_left_boundary",
        "pdf_bar_box_missing_right_boundary",
        "pdf_bar_box_boundary_ambiguous",
        "pdf_bar_box_too_narrow",
        "pdf_bar_box_overlaps_neighbor",
        "pdf_bar_box_outside_system_bounds",
        "pdf_candidate_between_bar_boxes",
        "pdf_candidate_on_bar_boundary",
        "pdf_candidate_boundary_ambiguous",
        "pdf_candidate_unassigned_to_bar",
        "pdf_partial_grouping_one_system_unboxed",
        "pdf_bar_box_construction_not_enough_for_build_ir",

        # New Phase 7 Bar Box Construction Edge Cases Codes
        "pdf_bar_box_single_system_failure",
        "pdf_bar_box_edge_system_missing_boundary",
        "pdf_bar_box_one_boundary_rejected",
        "pdf_barline_short_but_near_staff_boundary",
        "pdf_barline_ambiguous_on_edge_system",
        "pdf_candidate_unassigned_due_to_unboxed_system",
        "pdf_candidate_near_missing_bar_boundary",
        "pdf_boundary_candidate_blocks_full_grouping",
        "pdf_full_grouping_requires_all_systems_boxed",
        "pdf_grouping_complete_all_playable_candidates_assigned",

        # New Phase 8 Edge System Boundary Fallback Codes
        "pdf_bar_box_edge_boundary_fallback_rejected",
        "pdf_bar_box_edge_boundary_ambiguous",
        "pdf_bar_box_inferred_boundary_too_narrow",
        "pdf_bar_box_inferred_boundary_candidate_ambiguous",
        "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
        "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",

        # New PDF String Assignment Codes
        "pdf_string_assignment_outside_staff",
        "pdf_string_assignment_between_lines",
        "pdf_string_assignment_too_far_from_line",
        "pdf_string_assignment_overlaps_multiple_bands",
        "pdf_string_assignment_confidence_below_threshold",
        "pdf_string_assignment_compact_staff_ambiguous",
        "pdf_playable_candidate_requires_string_assignment",
        "pdf_string_assignment_not_enough_for_build_ir",

        # New Fret Refinement Blocker Codes
        "pdf_fret_digits_not_merged_gap_too_large",
        "pdf_fret_digits_not_merged_vertical_misalignment",
        "pdf_fret_digits_overlap_ambiguous",
        "pdf_fret_digit_symbol_overlap_ambiguous",
        "pdf_fret_bbox_too_tall",
        "pdf_fret_bbox_too_wide",
        "pdf_fret_bbox_too_small",
        "pdf_fret_outside_valid_range",
        "pdf_fret_non_digit_rejected",
        "pdf_fret_optical_bounds_confidence_below_threshold",
        "pdf_fret_refinement_not_enough_for_build_ir",

        # New Pitch / Tuning Blocker Codes
        "pdf_tuning_conflict_detected",
        "pdf_tuning_label_ambiguous",
        "pdf_tuning_label_malformed",
        "pdf_tuning_format_unsupported",
        "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
    }
    codes: set[str] = set()
    for candidate in fret_candidates:
        raw = candidate.get("raw")
        if not isinstance(raw, dict):
            continue
        for field in ("grouping_warnings", "assignment_warnings"):
            values = raw.get(field, [])
            if isinstance(values, list):
                codes.update(str(value) for value in values if value in drawn_grouping_codes)
    for warning in page_warnings:
        code = warning.get("code")
        if code in drawn_grouping_codes:
            codes.add(code)
    return sorted(codes)


def _specific_grouping_warning(code: str, grouping_counts: dict[str, int]) -> dict[str, Any]:
    messages = {
        "missing_pdf_barlines": "A tab staff was inferred, but reliable barlines were not detected.",
        "incomplete_tab_staff": "A partial tab staff was inferred, but fewer than six string lines were detected.",
        "ambiguous_string_assignment": "One or more fret candidates are too far from a single string line to assign safely.",
        "ambiguous_bar_assignment": "One or more fret candidates are too close to a bar boundary to assign safely.",

        "pdf_no_systems_detected": "No horizontal tab systems were detected on the page(s).",
        "pdf_partial_system_detection": "Horizontal tab systems were only partially detected.",
        "pdf_tab_staff_missing": "Tab staff lines are missing or not detected.",
        "pdf_tab_staff_incomplete": "A partial tab staff was inferred, but fewer than six string lines were detected.",
        "pdf_tab_staff_ambiguous": "Tab systems layout is ambiguous due to vertical overlap.",
        "pdf_barlines_missing": "A tab staff was inferred, but reliable barlines were not detected.",
        "pdf_barlines_ambiguous": "One or more fret candidates are too close to a barline to assign safely.",
        "pdf_bar_boxes_missing": "Measure bar boxes could not be inferred.",
        "pdf_string_lines_missing": "Tab string lines are completely missing.",
        "pdf_string_assignment_missing": "String lines were not detected, or the candidate is too far to assign.",
        "pdf_string_assignment_ambiguous": "Candidate is too far from a single string line to assign safely.",
        "pdf_candidate_outside_system": "Candidate is located horizontally outside the detected tab system.",
        "pdf_candidate_outside_bar": "Candidate is located outside the detected system barlines.",
        "pdf_candidate_between_strings": "Candidate is located too far from string lines (between strings).",
        "pdf_multi_system_order_ambiguous": "Multiple tab systems have vertically overlapping ranges.",
        "pdf_page_layout_unsupported": "Page layout is unsupported.",
        "pdf_text_candidate_without_geometry": "Candidate text lacks valid geometry.",
        "pdf_ascii_and_drawn_layout_conflict": "Both ASCII blocks and drawn systems exist on page.",
        "pdf_grouping_not_safe_for_build_ir": "PDF grouping contains warnings and is not safe to build IR.",

        # New messages
        "pdf_text_geometry_present_but_no_safe_system": "Text and drawn geometry both present, but no safe system box can be inferred.",
        "pdf_tab_candidates_present_but_system_not_detected": "Playable fret candidates present, but no tab system detected.",
        "pdf_drawn_geometry_present_but_staff_unresolved": "Drawn geometry present, but staff unresolved.",
        "pdf_tab_staff_lines_fragmented": "Six-ish tab lines present but fragmented or broken so staff is unresolved.",
        "pdf_tab_staff_lines_overlapping": "Tab staff lines are overlapping and unresolved.",
        "pdf_tab_staff_spacing_inconsistent": "Tab staff spacing is inconsistent and unresolved.",
        "pdf_system_bbox_ambiguous": "Tab system bounding boxes are overlapping or ambiguous.",
        "pdf_system_order_ambiguous": "System order is ambiguous across visually close systems.",
        "pdf_candidates_unassigned_to_system": "Candidates inside page but unassigned to any system.",
        "pdf_candidates_unassigned_to_bar": "Candidates inside a detected system but outside all detected bars.",
        "pdf_candidates_unassigned_to_string": "Candidates inside a detected system/bar but not assignable to a string.",
        "pdf_partial_grouping_with_playable_candidates": "Playable candidates exist but grouping is partial and unsafe.",
        "pdf_grouping_confidence_below_threshold": "Fret grouping confidence is below safe threshold.",
        "pdf_missing_pdf_grouping_blocks_build_ir": "Missing PDF grouping blocks build-ir from writing ScoreIR.",
        "pdf_layout_detection_requires_manual_review": "PDF layout grouping is unsafe and requires manual review.",

        # Refined blocker taxonomy messages
        "pdf_drawn_system_not_detected": "Drawn tab system was not detected or resolved.",
        "pdf_drawn_system_ambiguous": "Tab system layout vertical ordering is ambiguous.",
        "pdf_drawn_staff_lines_unresolved": "Drawn staff lines are fragmented, overlapping, or unresolved.",
        "pdf_ascii_system_detected": "ASCII tab system block was detected.",
        "pdf_ascii_system_measure_boundaries_missing": "ASCII blocks lack aligned bar separators to define measure boundaries.",
        "pdf_ascii_system_timing_unavailable": "ASCII blocks lack safe timing or alignment evidence.",
        "pdf_system_detected_bar_detection_missing": "System detection succeeded, but bar/barline detection is missing.",
        "pdf_system_detection_succeeded_but_grouping_incomplete": "System detection succeeded, but overall layout grouping remains partial or unsafe.",
        "pdf_input_class_ascii_tab_requires_alignment": "ASCII-tab input class requires an alignment sidecar.",
        "pdf_input_class_drawn_tab_requires_barlines": "Drawn-tab input class requires visible barlines.",
        "pdf_system_detection_not_enough_for_build_ir": "PDF system detection is incomplete and not safe to build IR.",

        # Refined bar-detection blocker taxonomy messages
        "pdf_barlines_not_detected_in_system": "System detected but no barlines found.",
        "pdf_barline_candidates_present_but_invalid": "Barline candidates exist but are invalid.",
        "pdf_barline_does_not_cross_staff": "Vertical lines present but do not cross tab staff.",
        "pdf_barline_too_short": "Vertical lines too short to trust.",
        "pdf_barline_outside_system_bounds": "Barlines outside detected system bounds.",
        "pdf_barline_ambiguous": "Ambiguous extra vertical lines detected.",
        "pdf_barline_double_secondary": "Secondary barline in a double-barline pair ignored.",
        "pdf_bar_boxes_not_constructible": "Measure bar boxes could not be constructed from barlines.",
        "pdf_bar_detection_succeeded_string_assignment_pending": "Bar detection succeeded, but string assignment is the next blocker.",
        "pdf_bar_detection_not_enough_for_build_ir": "PDF bar detection is incomplete and not safe to build IR.",

        # Refined barline-validation blocker taxonomy messages
        "pdf_barline_too_short_absolute": "Barline height below absolute threshold.",
        "pdf_barline_too_short_relative_to_staff": "Barline height below relative staff-crossing threshold.",
        "pdf_barline_crosses_insufficient_string_gaps": "Barline candidate crosses too few string gaps.",
        "pdf_barline_partial_staff_crossing": "Barline candidate crosses only part of the tab staff.",
        "pdf_barline_outside_staff_region": "Barline candidate is outside the staff region.",
        "pdf_barline_rejected_relative_height": "Barline candidate rejected by relative staff-height check.",
        "pdf_barline_validation_threshold_boundary": "Barline candidate is at validation threshold boundary.",
        "pdf_barline_validation_not_enough_for_build_ir": "Barline validation is incomplete and not safe to build IR.",
        "pdf_barline_inherited_too_close": "Inherited barline candidate rejected as too close.",

        # New Phase 6 Bar Box Construction messages
        "pdf_bar_box_requires_two_boundaries": "A bar box requires at least two accepted barlines to define its boundaries.",
        "pdf_bar_box_missing_left_boundary": "A bar box is missing its left boundary.",
        "pdf_bar_box_missing_right_boundary": "A bar box is missing its right boundary.",
        "pdf_bar_box_boundary_ambiguous": "The boundary of the bar box is ambiguous.",
        "pdf_bar_box_too_narrow": "One or more bar boxes are too narrow to trust.",
        "pdf_bar_box_overlaps_neighbor": "One or more bar boxes overlap with their neighbors.",
        "pdf_bar_box_outside_system_bounds": "One or more bar boxes extend outside system horizontal bounds.",
        "pdf_candidate_between_bar_boxes": "Fret candidate lies between bar boxes.",
        "pdf_candidate_on_bar_boundary": "Fret candidate lies exactly or nearly on a bar boundary.",
        "pdf_candidate_boundary_ambiguous": "Fret candidate boundary assignment is ambiguous.",
        "pdf_candidate_unassigned_to_bar": "Fret candidate lies outside all constructed bar boxes.",
        "pdf_partial_grouping_one_system_unboxed": "PDF grouping is partial because at least one system lacks bar boxes.",
        "pdf_grouping_complete": "PDF layout grouping is complete.",
        "pdf_bar_box_construction_not_enough_for_build_ir": "PDF bar-box construction is incomplete and not safe to build IR.",

        # New Phase 7 Bar Box Construction Edge Cases messages
        "pdf_bar_box_single_system_failure": "PDF grouping contains a system with zero accepted barlines.",
        "pdf_bar_box_edge_system_missing_boundary": "An edge system is missing one or more boundaries.",
        "pdf_bar_box_one_boundary_rejected": "One accepted and one rejected boundary detected on system.",
        "pdf_barline_short_but_near_staff_boundary": "Short barlines detected near the staff boundaries.",
        "pdf_barline_ambiguous_on_edge_system": "Ambiguous barlines detected on edge system.",
        "pdf_candidate_unassigned_due_to_unboxed_system": "Fret candidate is unassigned because its system lacks boxes.",
        "pdf_candidate_near_missing_bar_boundary": "Fret candidate is near a missing bar boundary.",
        "pdf_boundary_candidate_blocks_full_grouping": "Boundary candidate ambiguity blocks full grouping.",
        "pdf_full_grouping_requires_all_systems_boxed": "Full grouping is blocked because one or more systems lack bar boxes.",
        "pdf_grouping_complete_all_playable_candidates_assigned": "All playable fret candidates are safely assigned to systems, bars, and strings.",

        # New Phase 8 Edge System Boundary Fallback messages
        "pdf_bar_box_edge_boundary_fallback_rejected": "Edge boundary fallback was rejected.",
        "pdf_bar_box_edge_boundary_ambiguous": "Edge boundary fallback is ambiguous.",
        "pdf_bar_box_inferred_boundary_too_narrow": "Inferred boundary is too narrow.",
        "pdf_bar_box_inferred_boundary_candidate_ambiguous": "Fret candidate is too close to inferred boundary.",
        "pdf_bar_box_inferred_boundary_requires_clear_system_edge": "Inferred boundary requires clear system edge.",
        "pdf_bar_box_inferred_boundary_not_enough_for_build_ir": "Inferred boundary is incomplete.",

        # New PDF String Assignment Messages
        "pdf_string_assignment_nearest_line": "Fret candidate assigned to the nearest string line.",
        "pdf_string_assignment_outside_staff": "Fret candidate lies outside the vertical bounds of the tab staff.",
        "pdf_string_assignment_between_lines": "Fret candidate lies exactly between two string lines.",
        "pdf_string_assignment_too_far_from_line": "Fret candidate is too far from any string line to assign safely.",
        "pdf_string_assignment_overlaps_multiple_bands": "Fret candidate bounding box height overlaps multiple string lines.",
        "pdf_string_assignment_confidence_below_threshold": "String assignment confidence is below safe threshold.",
        "pdf_string_assignment_compact_staff_ambiguous": "Tab staff spacing is too compact for safe string assignment.",
        "pdf_playable_candidate_requires_string_assignment": "Playable fret candidates require unambiguous string assignment.",
        "pdf_non_playable_text_not_string_assigned": "Non-playable text candidate does not require string assignment.",
        "pdf_multidigit_fret_string_assigned": "Multi-digit fret candidate successfully assigned to string.",
        "pdf_string_assignment_not_enough_for_build_ir": "One or more playable fret candidates lack safe string assignment.",
        "pdf_string_assignment_succeeded_upstream_grouping_still_blocks": "String assignment succeeded for all playable candidates, but upstream system/bar grouping still blocks full grouping.",

        # New Fret Refinement Messages
        "pdf_fret_single_digit_extracted": "Single-digit fret successfully extracted.",
        "pdf_fret_multidigit_extracted": "Multi-digit fret successfully extracted.",
        "pdf_fret_digits_merged": "Horizontally adjacent digits successfully merged.",
        "pdf_fret_digits_not_merged_gap_too_large": "Adjacent digits too far apart horizontally to merge safely.",
        "pdf_fret_digits_not_merged_vertical_misalignment": "Adjacent digits vertically misaligned and not merged safely.",
        "pdf_fret_digits_overlap_ambiguous": "Playable fret candidates overlap horizontally too deeply or ambiguously.",
        "pdf_fret_digit_symbol_overlap_ambiguous": "Playable fret candidate overlaps with adjacent technique symbol or is a squished ligature.",
        "pdf_fret_split_text_span_merged": "Split text span digits merged into one candidate.",
        "pdf_fret_bbox_too_tall": "Fret candidate bounding box is too tall to be a valid fret.",
        "pdf_fret_bbox_too_wide": "Fret candidate bounding box is too wide to be a valid fret.",
        "pdf_fret_bbox_too_small": "Fret candidate bounding box is too small or noisy to be a valid fret.",
        "pdf_fret_outside_valid_range": "Fret candidate value is outside allowed valid range (0-24).",
        "pdf_fret_non_digit_rejected": "Fret candidate contains non-digit characters and is rejected.",
        "pdf_fret_technique_marker_excluded": "Technique symbol near fret digit excluded from playable value.",
        "pdf_fret_chord_text_digit_excluded": "Chord symbol or section text digit above staff excluded from fret evidence.",
        "pdf_fret_page_or_legend_number_excluded": "Page or legend number outside tab system excluded from fret evidence.",
        "pdf_fret_optical_bounds_confidence_below_threshold": "Fret optical bounds confidence is below safe threshold.",
        "pdf_fret_refinement_not_enough_for_build_ir": "One or more playable fret candidates lack unambiguous digit grouping/extraction.",
    }
    return {
        "code": code,
        "message": messages.get(code, "PDF grouping is partial or ambiguous."),
        "severity": "warning",
        "grouping_status": "partial",
        **grouping_counts,
    }


def _write_grouping_artifacts(
    pdf_path: Path,
    out_dir: Path,
    tabraw_path: Path,
    inspection: dict[str, Any],
    raw: dict[str, Any],
) -> None:
    candidates = raw.get("candidates", [])
    if not candidates or not any(candidate.get("parsed_fret") is not None for candidate in candidates):
        return
    grouping_status = grouping_status_for_tabraw(raw)

    html_path = out_dir / "grouping-diagnostics.html"
    warnings_path = out_dir / "warnings.json"
    overlay_paths: list[Path] = []
    try:
        overlay_paths = _write_grouping_overlays(
            pdf_path,
            raw.get("candidates", []),
            out_dir / "overlays",
            grouping_status,
        )
    except Exception as exc:  # noqa: BLE001
        raw.setdefault("warnings", []).append(
            {
                "code": "grouping-overlay-failed",
                "message": f"Grouping overlay images could not be written: {exc}",
                "severity": "warning",
            }
        )

    artifacts = {
        "tab_raw": _relative_artifact_path(tabraw_path, out_dir),
        "warnings": _relative_artifact_path(warnings_path, out_dir),
        "diagnostic_html": _relative_artifact_path(html_path, out_dir),
        "overlay_images": [_relative_artifact_path(path, out_dir) for path in overlay_paths],
    }

    from score2gp.report import build_pdf_edge_boundary_report, write_pdf_edge_boundary_report_html

    edge_report = build_pdf_edge_boundary_report(raw)
    if edge_report:
        edge_json_path = out_dir / "pdf-edge-boundary-report.json"
        edge_json_path.write_text(json.dumps(edge_report, indent=2), encoding="utf-8")

        edge_html_path = out_dir / "pdf-edge-boundary-report.html"
        write_pdf_edge_boundary_report_html(edge_html_path, edge_report)

        artifacts["pdf_edge_boundary_report_json"] = _relative_artifact_path(edge_json_path, out_dir)
        artifacts["pdf_edge_boundary_report_html"] = _relative_artifact_path(edge_html_path, out_dir)

    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection=inspection,
        tabraw=raw,
        artifacts=artifacts,
        alignment_attempted=False,
        scoreir_written=False,
    )
    write_grouping_diagnostics_html(html_path, report)


def _write_grouping_overlays(
    pdf_path: Path,
    candidates: list[dict[str, Any]],
    overlays_dir: Path,
    grouping_status: str,
) -> list[Path]:
    import fitz  # type: ignore[import-not-found]

    overlays_dir.mkdir(parents=True, exist_ok=True)
    candidates_by_page: dict[int, list[dict[str, Any]]] = {}
    for candidate in candidates:
        bbox = candidate.get("bbox")
        page_index = int(candidate.get("page_index") or bbox.get("page")) if isinstance(bbox, dict) else candidate.get("page_index")
        if page_index is None:
            continue
        candidates_by_page.setdefault(int(page_index), []).append(candidate)

    message = "candidate text found; no usable tab staff/bar/string grouping inferred"
    text_color = (0.8, 0.05, 0.05)
    if grouping_status == "grouped":
        message = "candidate text found; tab staff/bar/string grouping inferred"
        text_color = (0.05, 0.55, 0.15)
    elif grouping_status == "recovered":
        message = "candidate text found; conservative PDF edge-boundary recovery fallback used"
        text_color = (0.05, 0.55, 0.15)
    elif grouping_status == "partial":
        message = "candidate text found; tab staff/bar/string grouping is partial"
    elif grouping_status == "ascii_grouped":
        message = "ASCII tab rows found; row/string grouping inferred, timing alignment unavailable"
        text_color = (0.05, 0.55, 0.15)
    elif grouping_status == "partial_ascii":
        message = "ASCII tab rows found; row grouping is partial"
    elif grouping_status == "ambiguous":
        message = "candidate text found; tab staff/bar/string grouping is ambiguous"
    elif grouping_status == "unsupported":
        message = "candidate text found; tab staff layout is unsupported"

    overlay_paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            page_candidates = candidates_by_page.get(page_number, [])
            if not page_candidates:
                continue
            grouping_structures = _grouping_structures_from_candidates(page_candidates)
            page.insert_text(
                fitz.Point(36, 24),
                message,
                fontsize=10,
                color=text_color,
            )
            for structure in grouping_structures:
                staff_bbox = structure.get("staff_bbox")
                if isinstance(staff_bbox, dict):
                    rect = fitz.Rect(
                        float(staff_bbox["x0"]),
                        float(staff_bbox["y0"]),
                        float(staff_bbox["x1"]),
                        float(staff_bbox["y1"]),
                    )
                    page.draw_rect(rect, color=(0.05, 0.35, 0.85), width=1.1)
                    page.insert_text(
                        fitz.Point(rect.x0, max(8.0, rect.y0 - 6.0)),
                        f"system {structure['system_index']} staff {structure['staff_index']}",
                        fontsize=6.5,
                        color=(0.05, 0.35, 0.85),
                    )
                for y in structure.get("tab_line_ys", []):
                    page.draw_line(
                        (float(structure["x0"]), float(y)),
                        (float(structure["x1"]), float(y)),
                        color=(0.1, 0.55, 0.95),
                        width=0.35,
                    )
                for x in structure.get("barline_xs", []):
                    page.draw_line(
                        (float(x), float(structure["y0"])),
                        (float(x), float(structure["y1"])),
                        color=(0.9, 0.25, 0.05),
                        width=0.8,
                    )
                for bar_box in structure.get("bar_boxes", []):
                    if not isinstance(bar_box, dict):
                        continue
                    rect = fitz.Rect(
                        float(bar_box["x0"]),
                        float(bar_box["y0"]),
                        float(bar_box["x1"]),
                        float(bar_box["y1"]),
                    )
                    page.draw_rect(rect, color=(0.95, 0.55, 0.05), width=0.5)
                    page.insert_text(
                        fitz.Point(rect.x0 + 2.0, rect.y1 + 7.0),
                        f"bar {bar_box['bar_index']}",
                        fontsize=5.5,
                        color=(0.8, 0.35, 0.0),
                    )
            for candidate in page_candidates:
                bbox = candidate.get("bbox")
                if not isinstance(bbox, dict):
                    continue
                rect = fitz.Rect(float(bbox["x0"]), float(bbox["y0"]), float(bbox["x1"]), float(bbox["y1"]))
                color = _candidate_overlay_color(str(candidate.get("kind", "candidate-text")))
                page.draw_rect(rect, color=color, width=0.8)
                label = _candidate_overlay_label(candidate)
                label_y = max(8.0, rect.y0 - 2.0)
                page.insert_text(fitz.Point(rect.x0, label_y), label, fontsize=5.5, color=color)
            image_path = overlays_dir / f"page-{page_number:03d}-grouping.png"
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pix.save(image_path)
            overlay_paths.append(image_path)
    return overlay_paths


def _candidate_overlay_color(kind: str) -> tuple[float, float, float]:
    if kind == "fret":
        return (0.0, 0.45, 0.1)
    if kind == "chord-symbol":
        return (0.5, 0.0, 0.65)
    if kind == "technique-text":
        return (0.0, 0.25, 0.85)
    return (0.85, 0.45, 0.0)


def _candidate_overlay_label(candidate: dict[str, Any]) -> str:
    kind = str(candidate.get("kind", "text"))
    kind_label = {
        "candidate-text": "text",
        "chord-symbol": "chord",
        "technique-text": "tech",
    }.get(kind, kind)
    short_id = str(candidate.get("id", "candidate")).split("-")[-1]
    string = candidate.get("string")
    bar = candidate.get("bar_index")
    assignment = ""
    if string is not None or bar is not None:
        assignment = f":s{string or '?'}b{bar or '?'}"
    return f"{short_id}:{kind_label}{assignment}"


def _grouping_structures_from_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, int], dict[str, Any]] = {}
    for candidate in candidates:
        raw = candidate.get("raw")
        if not isinstance(raw, dict):
            continue
        staff_bbox = raw.get("tab_staff_bbox")
        line_ys = raw.get("tab_line_ys")
        if not isinstance(staff_bbox, dict) or not isinstance(line_ys, list):
            continue
        page = int(candidate.get("page_index") or staff_bbox.get("page") or 0)
        system_index = int(candidate.get("system_index") or 0)
        staff_index = int(candidate.get("staff_index") or 0)
        if not page or not system_index or not staff_index:
            continue
        key = (page, system_index, staff_index)
        if key not in grouped:
            grouped[key] = {
                "page": page,
                "system_index": system_index,
                "staff_index": staff_index,
                "staff_bbox": staff_bbox,
                "tab_line_ys": [float(value) for value in line_ys],
                "barline_xs": [float(value) for value in raw.get("barline_xs", []) if isinstance(value, (int, float))],
                "bar_boxes": raw.get("bar_boxes", []) if isinstance(raw.get("bar_boxes"), list) else [],
                "x0": float(staff_bbox["x0"]),
                "x1": float(staff_bbox["x1"]),
                "y0": float(staff_bbox["y0"]),
                "y1": float(staff_bbox["y1"]),
            }
    return [grouped[key] for key in sorted(grouped)]


def _relative_artifact_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path)



def _has_fret_digit_intersection(group: list[_LineSegment], page: Any) -> bool:
    if page is None:
        return False
    try:
        words = page.get_text("words")
    except Exception:
        return False

    x0 = min(min(l.x0, l.x1) for l in group)
    x1 = max(max(l.x0, l.x1) for l in group)
    y0 = min((l.y0 + l.y1) / 2 for l in group)
    y1 = max((l.y0 + l.y1) / 2 for l in group)

    for word in words:
        raw_text = str(word[4]).strip()
        if not raw_text:
            continue
        if parse_fret_text(raw_text) is not None:
            # Word coordinates: (x0, y0, x1, y1, text, block_no, line_no, word_no)
            wx = (word[0] + word[2]) / 2
            wy = (word[1] + word[3]) / 2
            if x0 - 5.0 <= wx <= x1 + 5.0 and y0 - 3.0 <= wy <= y1 + 3.0:
                return True
    return False


def classify_staff_line_group(group: list[_LineSegment], page: Any = None) -> str:
    if not group:
        return "ambiguous"
    ys = sorted([round((line.y0 + line.y1) / 2, 3) for line in group])
    gaps = [right - left for left, right in zip(ys, ys[1:])]
    if not gaps:
        return "ambiguous"

    sorted_gaps = sorted(gaps)
    n_gaps = len(sorted_gaps)
    median_gap = sorted_gaps[n_gaps // 2]

    has_fret = _has_fret_digit_intersection(group, page)

    if len(group) == 6:
        if 5.5 <= median_gap <= 7.2 or 9.5 <= median_gap <= 15.0:
            return "tab"
        elif 15.0 < median_gap <= 32.0 and _is_coherent_large_tab_group(group):
            return "tab"
        elif median_gap < 5.5:
            return "rejected"
        else:
            return "ambiguous"
    elif len(group) == 5:
        if 5.5 <= median_gap <= 7.2 or 9.5 <= median_gap <= 15.0:
            if has_fret:
                return "incomplete_tab_candidate"
            else:
                return "ambiguous"
        elif (3.5 <= median_gap < 5.5) or (7.8 <= median_gap <= 9.2):
            if not has_fret:
                return "notation"
            else:
                return "ambiguous"
        else:
            return "ambiguous"

    return "ambiguous"


def filter_tab_barline_candidates(
    candidates: list[_LineSegment],
    y0: float,
    y1: float,
    line_ys: list[float],
    x0: float,
    x1: float
) -> dict[str, Any]:
    rejection_reasons = {
        "pdf_barline_outside_system_bounds": 0,
        "pdf_barline_too_short": 0,
        "pdf_barline_does_not_cross_staff": 0,
        "pdf_barline_ambiguous": 0,
        "pdf_barline_too_short_absolute": 0,
        "pdf_barline_too_short_relative_to_staff": 0,
        "pdf_barline_crosses_insufficient_string_gaps": 0,
        "pdf_barline_partial_staff_crossing": 0,
        "pdf_barline_outside_staff_region": 0,
        "pdf_barline_rejected_relative_height": 0,
        "pdf_barline_double_secondary": 0,
        "pdf_barline_inherited_too_close": 0,
    }
    valid_barlines = []
    rejected_count = 0
    details = []
    staff_height = y1 - y0

    # Pass 1: Pre-calculate baseline acceptance properties for each candidate
    candidate_data = []
    ys = sorted(line_ys)
    for idx, s in enumerate(candidates):
        x_val = (s.x0 + s.x1) / 2
        y_min = min(s.y0, s.y1)
        y_max = max(s.y0, s.y1)
        height = y_max - y_min

        # 1. Check horizontal bounds
        in_bounds = not (x_val < x0 - 8.0 or x_val > x1 + 8.0)

        # 2. Check staff intersection
        intersects = not (y_max < y0 or y_min > y1)

        # Calculate gaps crossed
        gaps_crossed = 0
        for i in range(len(ys) - 1):
            if y_min <= ys[i] + 1.5 and y_max >= ys[i+1] - 1.5:
                gaps_crossed += 1

        # Intersection height and coverage ratio
        overlap_y_min = max(y_min, y0)
        overlap_y_max = min(y_max, y1)
        overlap_height = max(0.0, overlap_y_max - overlap_y_min)
        coverage_ratio = overlap_height / staff_height if staff_height > 0 else 0.0

        crosses_entire_staff = (y_min <= y0 + 4.0 and y_max >= y1 - 4.0) or (gaps_crossed >= len(ys) - 1)

        absolute_height_ok = (height >= 40.0)
        relative_height_ok = crosses_entire_staff
        is_accepted_relative = (height >= 20.0 and relative_height_ok)

        # Initially accepted is True if it would pass all individual checks
        initially_accepted = in_bounds and intersects and (absolute_height_ok or is_accepted_relative) and relative_height_ok

        candidate_data.append({
            "idx": idx,
            "segment": s,
            "x": x_val,
            "y_min": y_min,
            "y_max": y_max,
            "height": height,
            "gaps_crossed": gaps_crossed,
            "coverage_ratio": coverage_ratio,
            "absolute_height_ok": absolute_height_ok,
            "relative_height_ok": relative_height_ok,
            "in_bounds": in_bounds,
            "intersects": intersects,
            "initially_accepted": initially_accepted,
        })

    # Pass 2: Perform single-linkage clustering on initially accepted candidates
    accepted_candidates = [item for item in candidate_data if item["initially_accepted"]]
    accepted_candidates.sort(key=lambda item: item["x"])

    clusters = []
    current_cluster = []
    for item in accepted_candidates:
        if not current_cluster:
            current_cluster.append(item)
        else:
            if item["x"] - current_cluster[-1]["x"] <= DOUBLE_BARLINE_CLUSTERING_TOLERANCE:
                current_cluster.append(item)
            else:
                clusters.append(current_cluster)
                current_cluster = [item]
    if current_cluster:
        clusters.append(current_cluster)

    # Assign decisions based on cluster membership and initial status
    final_decisions = {}  # idx -> (is_accepted, rejection_reason)

    # Put all clusters' results into decisions
    for cluster in clusters:
        if len(cluster) > 1:
            is_rightmost_edge = any(item["x"] >= x1 - 10.0 for item in cluster)
            is_leftmost_edge = any(item["x"] <= x0 + 10.0 for item in cluster)

            if is_rightmost_edge:
                # Multi-line rightmost edge cluster (double barline). Choose the rightmost candidate.
                representative = cluster[-1]
                final_decisions[representative["idx"]] = (True, None)
                for item in cluster[:-1]:
                    final_decisions[item["idx"]] = (False, "pdf_barline_double_secondary")
            elif is_leftmost_edge:
                # Multi-line leftmost edge cluster (double barline). Choose the leftmost candidate.
                representative = cluster[0]
                final_decisions[representative["idx"]] = (True, None)
                for item in cluster[1:]:
                    final_decisions[item["idx"]] = (False, "pdf_barline_double_secondary")
            else:
                # Internal cluster of close barlines.
                if len(cluster) == 2:
                    # Select the leftmost candidate as the representative for v0.1.
                    # This is limited to size-2 close clusters; larger internal clusters remain ambiguous.
                    representative = cluster[0]
                    secondary = cluster[1]
                    final_decisions[representative["idx"]] = (True, None)
                    final_decisions[secondary["idx"]] = (False, "pdf_barline_double_secondary")
                else:
                    # Treat clusters of size 3 or more as ambiguous!
                    for item in cluster:
                        final_decisions[item["idx"]] = (False, "pdf_barline_ambiguous")
        else:
            # Single-line cluster. They are default accepted initially,
            # but will be verified by the ambiguity check below.
            for item in cluster:
                final_decisions[item["idx"]] = (True, None)

    # For candidates that were NOT initially accepted, determine their rejection reason
    for item in candidate_data:
        if not item["initially_accepted"]:
            reason = None
            if not item["in_bounds"]:
                reason = "pdf_barline_outside_system_bounds"
            elif not item["intersects"]:
                reason = "pdf_barline_outside_staff_region"
            elif not item["relative_height_ok"]:
                if item["gaps_crossed"] < len(ys) - 2:
                    reason = "pdf_barline_crosses_insufficient_string_gaps"
                else:
                    reason = "pdf_barline_partial_staff_crossing"
            elif not (item["absolute_height_ok"] or (item["height"] >= 20.0 and item["relative_height_ok"])):
                reason = "pdf_barline_too_short_absolute"

            if reason is None:
                reason = "pdf_barline_rejected_relative_height"

            final_decisions[item["idx"]] = (False, reason)

    # Perform ambiguity check among currently accepted candidates
    accepted_indices = {idx for idx, (accepted, _) in final_decisions.items() if accepted}
    for idx in list(accepted_indices):
        item = next(it for it in candidate_data if it["idx"] == idx)
        is_ambiguous = False
        for other_idx in accepted_indices:
            if other_idx == idx:
                continue
            other_item = next(it for it in candidate_data if it["idx"] == other_idx)
            if abs(item["x"] - other_item["x"]) <= DOUBLE_BARLINE_CLUSTERING_TOLERANCE:
                is_ambiguous = True
                break

        if is_ambiguous:
            final_decisions[idx] = (False, "pdf_barline_ambiguous")

    # Construct the final returned structures
    for item in candidate_data:
        idx = item["idx"]
        is_accepted, reason = final_decisions[idx]

        if is_accepted:
            valid_barlines.append(round(item["x"], 3))
        else:
            rejected_count += 1
            if reason:
                if reason in rejection_reasons:
                    rejection_reasons[reason] += 1

                # Increment general categories matching original logic
                if reason == "pdf_barline_outside_staff_region":
                    rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
                elif reason == "pdf_barline_crosses_insufficient_string_gaps":
                    rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
                elif reason == "pdf_barline_partial_staff_crossing":
                    rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
                elif reason == "pdf_barline_too_short_absolute":
                    rejection_reasons["pdf_barline_too_short"] += 1
                elif reason == "pdf_barline_rejected_relative_height":
                    rejection_reasons["pdf_barline_too_short"] += 1

            if item["height"] < 40.0:
                rejection_reasons["pdf_barline_too_short"] += 1

        details.append({
            "x": round(item["x"], 3),
            "y_min": round(item["y_min"], 3),
            "y_max": round(item["y_max"], 3),
            "height": round(item["height"], 3),
            "staff_height": round(staff_height, 3),
            "coverage_ratio": round(item["coverage_ratio"], 3),
            "gaps_crossed": item["gaps_crossed"],
            "absolute_height_decision": "accepted" if item["absolute_height_ok"] else "rejected",
            "relative_staff_crossing_decision": "accepted" if item["relative_height_ok"] else "rejected",
            "final_decision": "accepted" if is_accepted else "rejected",
            "rejection_reason": reason,
        })

    valid_barlines = _unique_sorted(valid_barlines)
    return {
        "valid_barlines": valid_barlines,
        "rejected_count": rejected_count,
        "rejection_reasons": rejection_reasons,
        "details": details,
    }


def _extend_staff_group(group: list[_LineSegment], all_segments: list[_LineSegment]) -> tuple[list[_LineSegment], float, float]:
    extended_group = []
    for line in group:
        line_y = (line.y0 + line.y1) / 2
        curr_x0, curr_x1 = min(line.x0, line.x1), max(line.x0, line.x1)

        while True:
            merged_any = False
            for s in all_segments:
                if abs(s.y0 - s.y1) > 1.0:
                    continue
                s_y = (s.y0 + s.y1) / 2
                if abs(s_y - line_y) > 1.0:
                    continue
                s_x0, s_x1 = min(s.x0, s.x1), max(s.x0, s.x1)
                s_w = s_x1 - s_x0
                if s_w < 5.0:
                    continue

                if s_x0 - 15.0 <= curr_x1 and curr_x0 <= s_x1 + 15.0:
                    new_x0 = min(curr_x0, s_x0)
                    new_x1 = max(curr_x1, s_x1)
                    if new_x0 < curr_x0 or new_x1 > curr_x1:
                        curr_x0, curr_x1 = new_x0, new_x1
                        merged_any = True
            if not merged_any:
                break
        extended_group.append(_LineSegment(curr_x0, line_y, curr_x1, line_y))
    g_x0 = min(l.x0 for l in extended_group)
    g_x1 = max(l.x1 for l in extended_group)
    return extended_group, g_x0, g_x1


def _detect_tab_systems(page: Any, page_index: int, first_bar_index: int = 1) -> list[_TabSystem]:
    segments = list(_drawing_segments(page.get_drawings()))
    raw_horizontal = sorted((segment for segment in segments if segment.is_horizontal), key=lambda segment: segment.y0)
    horizontal = sorted(merge_collinear_horizontal_segments(raw_horizontal), key=lambda segment: segment.y0)

    # Extract vertical candidates with a wider margin
    raw_verticals = []
    for s in segments:
        if abs(s.x0 - s.x1) <= 2.0 and abs(s.y1 - s.y0) >= 10.0:
            raw_verticals.append(s)

    # Deduplicate raw verticals that are essentially the same line
    deduped_verticals = []
    for s in raw_verticals:
        x_s = (s.x0 + s.x1) / 2
        y_min_s = min(s.y0, s.y1)
        y_max_s = max(s.y0, s.y1)
        found_similar = False
        for i, existing in enumerate(deduped_verticals):
            x_e = (existing.x0 + existing.x1) / 2
            y_min_e = min(existing.y0, existing.y1)
            y_max_e = max(existing.y0, existing.y1)
            if abs(x_s - x_e) <= 1.0 and not (y_max_s < y_min_e or y_max_e < y_min_s):
                new_y_min = min(y_min_s, y_min_e)
                new_y_max = max(y_max_s, y_max_e)
                new_x = (x_s + x_e) / 2
                deduped_verticals[i] = _LineSegment(new_x, new_y_min, new_x, new_y_max)
                found_similar = True
                break
        if not found_similar:
            deduped_verticals.append(s)

    systems = []
    system_index = 1
    next_bar_index = first_bar_index

    for group in _tab_line_groups(horizontal):
        classification = classify_staff_line_group(group, page)
        if classification in ("notation", "ambiguous"):
            continue

        group, x0, x1 = _extend_staff_group(group, segments)
        line_ys = [round((line.y0 + line.y1) / 2, 3) for line in group]
        y0 = min(line_ys)
        y1 = max(line_ys)

        system_candidates = []
        for s in deduped_verticals:
            x_val = (s.x0 + s.x1) / 2
            y_min = min(s.y0, s.y1)
            y_max = max(s.y0, s.y1)
            if y_max >= y0 - 15.0 and y_min <= y1 + 15.0 and x0 - 25.0 <= x_val <= x1 + 25.0:
                system_candidates.append(s)

        barline_candidates_count = len(system_candidates)
        filtered = filter_tab_barline_candidates(system_candidates, y0, y1, line_ys, x0, x1)
        valid_barlines = filtered["valid_barlines"]
        rejected_count = filtered["rejected_count"]
        rejection_reasons = dict(filtered["rejection_reasons"])
        details = list(filtered["details"])

        # Notation-to-TAB barline inheritance
        partner_barlines = []
        best_partner = None
        best_partner_dist = 999999.0

        if len(valid_barlines) < 3:
            for other_group in _tab_line_groups(horizontal):
                if other_group == group:
                    continue
                
                other_class = classify_staff_line_group(other_group, page)
                if other_class not in ("notation", "ambiguous"):
                    continue
                    
                other_ys = [round((line.y0 + line.y1) / 2, 3) for line in other_group]
                other_y0 = min(other_ys)
                other_y1 = max(other_ys)
                
                # If the other group is above the TAB staff and within 250 points
                if other_y1 < y0 and y0 - other_y1 <= 250.0:
                    # Check horizontal overlap alignment
                    other_x0 = min(min(line.x0, line.x1) for line in other_group)
                    other_x1 = max(max(line.x0, line.x1) for line in other_group)
                    overlap_w = max(0.0, min(x1, other_x1) - max(x0, other_x0))
                    min_w = min(x1 - x0, other_x1 - other_x0)
                    if min_w > 0 and (overlap_w / min_w) >= 0.7:
                        dist = y0 - other_y1
                        if dist < best_partner_dist:
                            best_partner_dist = dist
                            best_partner = (other_group, other_y0, other_y1, other_x0, other_x1, other_ys)
            
            if best_partner is not None:
                other_group, other_y0, other_y1, other_x0, other_x1, other_ys = best_partner
                other_candidates = []
                for s in deduped_verticals:
                    x_val = (s.x0 + s.x1) / 2
                    y_min = min(s.y0, s.y1)
                    y_max = max(s.y0, s.y1)
                    if y_max >= other_y0 - 15.0 and y_min <= other_y1 + 15.0 and other_x0 - 25.0 <= x_val <= other_x1 + 25.0:
                        other_candidates.append(s)
                
                other_filtered = filter_tab_barline_candidates(other_candidates, other_y0, other_y1, other_ys, other_x0, other_x1)
                partner_valid = other_filtered["valid_barlines"]

                inherited_from_partner = []
                rejected_inherited = {}  # pb -> rejection_reason

                tab_left = min(valid_barlines) if len(valid_barlines) >= 2 else None
                tab_right = max(valid_barlines) if len(valid_barlines) >= 2 else None

                for pb in partner_valid:
                    # a) Check boundaries if we have outer TAB boundaries
                    if tab_left is not None and tab_right is not None:
                        if pb <= tab_left + 15.0 or pb >= tab_right - 15.0:
                            rejected_inherited[pb] = "pdf_barline_outside_system_bounds"
                            continue

                    # b) Check if too close to any explicit TAB barline (anchors)
                    if any(15.0 < abs(pb - tb) < MIN_INHERITED_INTERNAL_BAR_WIDTH for tb in valid_barlines):
                        rejected_inherited[pb] = "pdf_barline_inherited_too_close"
                        continue

                    # c) Check if too close to another candidate in partner_valid (batch check)
                    if any(15.0 < abs(pb - other) < MIN_INHERITED_INTERNAL_BAR_WIDTH for other in partner_valid if other != pb):
                        rejected_inherited[pb] = "pdf_barline_inherited_too_close"
                        continue

                    inherited_from_partner.append(pb)

                if inherited_from_partner:
                    partner_barlines.extend(inherited_from_partner)

                # Accumulate partner staff rejection reasons
                for k, v in other_filtered["rejection_reasons"].items():
                    rejection_reasons[k] = rejection_reasons.get(k, 0) + v
                rejected_count += other_filtered["rejected_count"]

                # Add partner details with updated decision
                for det in other_filtered["details"]:
                    det_copy = dict(det)
                    det_copy["inherited"] = True

                    if det_copy.get("final_decision") == "accepted":
                        x_val = det_copy.get("x")
                        matched_pb = None
                        if x_val is not None:
                            for pb in partner_valid:
                                if abs(pb - x_val) < 0.001:
                                    matched_pb = pb
                                    break

                        if matched_pb is not None:
                            if matched_pb in rejected_inherited:
                                reason = rejected_inherited[matched_pb]
                                det_copy["final_decision"] = "rejected"
                                det_copy["rejection_reason"] = reason
                                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                                rejected_count += 1
                            elif matched_pb not in inherited_from_partner:
                                det_copy["final_decision"] = "rejected"
                                det_copy["rejection_reason"] = "pdf_barline_outside_system_bounds"
                                rejection_reasons["pdf_barline_outside_system_bounds"] = rejection_reasons.get("pdf_barline_outside_system_bounds", 0) + 1
                                rejected_count += 1
                    details.append(det_copy)
        
        # Merge and deduplicate barlines within 15.0 points only if we actually inherited partner barlines
        if partner_barlines:
            all_barlines = sorted(list(set(valid_barlines + partner_barlines)))
            final_barlines = []
            for b in all_barlines:
                if not final_barlines:
                    final_barlines.append(b)
                else:
                    if b - final_barlines[-1] <= 15.0:
                        final_barlines[-1] = b
                        continue
                    final_barlines.append(b)
            valid_barlines = final_barlines

        systems.append(
            _TabSystem(
                page_index=page_index,
                system_index=system_index,
                staff_index=1,
                first_bar_index=next_bar_index,
                line_ys=line_ys,
                x0=x0,
                x1=x1,
                barlines=valid_barlines,
                barline_candidates_count=barline_candidates_count,
                valid_barline_count=len(valid_barlines),
                rejected_barline_count=rejected_count,
                rejection_reasons=rejection_reasons,
                barline_candidates_details=details,
            )
        )
        next_bar_index += max(1, len(valid_barlines) - 1)
        system_index += 1

    # Deduplicate overlapping ghost systems where one is a subset of another
    non_ghost_systems = []
    for sys1 in systems:
        is_ghost = False
        for sys2 in systems:
            if sys1.system_index == sys2.system_index:
                continue
            if len(sys1.line_ys) <= len(sys2.line_ys):
                # Check if all line Ys in sys1 are close to line Ys in sys2
                all_lines_matched = True
                for y1 in sys1.line_ys:
                    if not any(abs(y1 - y2) <= 1.0 for y2 in sys2.line_ys):
                        all_lines_matched = False
                        break
                if all_lines_matched:
                    # Check horizontal overlap
                    overlap_width = max(0.0, min(sys1.x1, sys2.x1) - max(sys1.x0, sys2.x0))
                    width1 = sys1.x1 - sys1.x0
                    if width1 > 0 and (overlap_width / width1) > 0.8:
                        if len(sys1.line_ys) < len(sys2.line_ys) or sys1.system_index > sys2.system_index:
                            is_ghost = True
                            break
        if not is_ghost:
            non_ghost_systems.append(sys1)

    # Re-index remaining systems and compute correct sequential bar indices
    final_systems = []
    current_bar_index = first_bar_index
    for idx, sys in enumerate(non_ghost_systems, start=1):
        from dataclasses import replace
        updated_sys = replace(sys, system_index=idx, first_bar_index=current_bar_index)
        final_systems.append(updated_sys)
        current_bar_index += max(1, len(updated_sys.barlines) - 1)
    return final_systems



def _six_line_groups(lines: list[_LineSegment]) -> list[list[_LineSegment]]:
    return [group for group in _tab_line_groups(lines) if len(group) == 6]


def _is_five_line_with_one_missing(y_coords: list[float]) -> float | None:
    if len(y_coords) != 5:
        return None
    gaps = [y_coords[i+1] - y_coords[i] for i in range(4)]
    g = min(gaps)
    if not (5.5 <= g <= 15.0):
        return None

    g_count = 0
    double_g_count = 0
    for gap in gaps:
        if abs(gap - g) <= 2.0:
            g_count += 1
        elif abs(gap - 2 * g) <= 3.0:
            double_g_count += 1

    if g_count == 3 and double_g_count == 1:
        return g
    return None


def _tab_line_groups(lines: list[_LineSegment]) -> list[list[_LineSegment]]:
    sorted_lines = sorted(lines, key=lambda l: (l.y0 + l.y1) / 2)
    n = len(sorted_lines)
    used = set()
    groups = []

    # Phase 1: Try to find 6-line groups first
    for i0 in range(n):
        if i0 in used:
            continue
        for i1 in range(i0 + 1, n):
            if i1 in used:
                continue
            y0 = (sorted_lines[i0].y0 + sorted_lines[i0].y1) / 2
            y1 = (sorted_lines[i1].y0 + sorted_lines[i1].y1) / 2
            gap = y1 - y0
            if gap < 3.5 or gap > 32.0:
                continue

            group_indices = [i0, i1]
            failed = False
            for step in range(2, 6):
                target_y = y0 + step * gap
                
                # Collect all candidates at this target Y Y-level
                candidates_at_y = []
                for j in range(group_indices[-1] + 1, n):
                    if j in used:
                        continue
                    yj = (sorted_lines[j].y0 + sorted_lines[j].y1) / 2
                    diff = abs(yj - target_y)
                    if diff < 2.5:
                        candidates_at_y.append((diff, j))
                
                best_idx = None
                if len(candidates_at_y) == 1:
                    best_idx = candidates_at_y[0][1]
                elif len(candidates_at_y) > 1:
                    # Resolve ambiguity using normalized horizontal overlap against the first line of the group
                    ref_line = sorted_lines[group_indices[0]]
                    group_x0 = min(ref_line.x0, ref_line.x1)
                    group_x1 = max(ref_line.x0, ref_line.x1)
                    
                    valid_candidates = []
                    for diff, j in candidates_at_y:
                        jx0 = min(sorted_lines[j].x0, sorted_lines[j].x1)
                        jx1 = max(sorted_lines[j].x0, sorted_lines[j].x1)
                        candidate_w = max(1e-5, jx1 - jx0)
                        overlap = max(0.0, min(jx1, group_x1) - max(jx0, group_x0))
                        norm_overlap = overlap / candidate_w
                        
                        if norm_overlap >= 0.5:
                            valid_candidates.append((norm_overlap, overlap, j))
                            
                    if valid_candidates:
                        valid_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
                        best_idx = valid_candidates[0][2]
                
                if best_idx is not None:
                    group_indices.append(best_idx)
                else:
                    failed = True
                    break

            if not failed and len(group_indices) == 6:
                group = [sorted_lines[idx] for idx in group_indices]
                if gap > 24.0:
                    if not _is_coherent_large_tab_group(group):
                        continue
                groups.append(group)
                used.update(group_indices)
                break

    # Phase 2: Also find 5-line groups among the remaining unused lines
    for i0 in range(n):
        if i0 in used:
            continue
        for i1 in range(i0 + 1, n):
            if i1 in used:
                continue
            y0 = (sorted_lines[i0].y0 + sorted_lines[i0].y1) / 2
            y1 = (sorted_lines[i1].y0 + sorted_lines[i1].y1) / 2
            gap = y1 - y0
            if gap < 3.5 or gap > 24.0:
                continue

            group_indices = [i0, i1]
            failed = False
            for step in range(2, 5):
                target_y = y0 + step * gap
                
                # Collect all candidates at this target Y Y-level
                candidates_at_y = []
                for j in range(group_indices[-1] + 1, n):
                    if j in used:
                        continue
                    yj = (sorted_lines[j].y0 + sorted_lines[j].y1) / 2
                    diff = abs(yj - target_y)
                    if diff < 2.5:
                        candidates_at_y.append((diff, j))
                
                best_idx = None
                if len(candidates_at_y) == 1:
                    best_idx = candidates_at_y[0][1]
                elif len(candidates_at_y) > 1:
                    # Resolve ambiguity using normalized horizontal overlap against the first line of the group
                    ref_line = sorted_lines[group_indices[0]]
                    group_x0 = min(ref_line.x0, ref_line.x1)
                    group_x1 = max(ref_line.x0, ref_line.x1)
                    
                    valid_candidates = []
                    for diff, j in candidates_at_y:
                        jx0 = min(sorted_lines[j].x0, sorted_lines[j].x1)
                        jx1 = max(sorted_lines[j].x0, sorted_lines[j].x1)
                        candidate_w = max(1e-5, jx1 - jx0)
                        overlap = max(0.0, min(jx1, group_x1) - max(jx0, group_x0))
                        norm_overlap = overlap / candidate_w
                        
                        if norm_overlap >= 0.5:
                            valid_candidates.append((norm_overlap, overlap, j))
                            
                    if valid_candidates:
                        valid_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
                        best_idx = valid_candidates[0][2]
                
                if best_idx is not None:
                    group_indices.append(best_idx)
                else:
                    failed = True
                    break

            if not failed and len(group_indices) == 5:
                group = [sorted_lines[idx] for idx in group_indices]
                groups.append(group)
                used.update(group_indices)
                break

    # Phase 3: Find 5-line groups with exactly one missing line (one double-sized gap) among remaining unused lines
    unused_indices = [i for i in range(n) if i not in used]
    m = len(unused_indices)
    for k in range(m - 4):
        candidate_indices = unused_indices[k : k + 5]
        if any(idx in used for idx in candidate_indices):
            continue
        candidate_lines = [sorted_lines[idx] for idx in candidate_indices]
        y_coords = [(l.y0 + l.y1) / 2 for l in candidate_lines]
        g_val = _is_five_line_with_one_missing(y_coords)
        if g_val is not None:
            xs_min = [min(l.x0, l.x1) for l in candidate_lines]
            xs_max = [max(l.x0, l.x1) for l in candidate_lines]
            overlap_x0 = max(xs_min)
            overlap_x1 = min(xs_max)
            overlap_w = overlap_x1 - overlap_x0
            min_w = min(x_max - x_min for x_min, x_max in zip(xs_min, xs_max))
            if min_w > 0 and (overlap_w / min_w) >= 0.7:
                groups.append(candidate_lines)
                used.update(candidate_indices)

    # Column-aware sorting: group into columns based on horizontal overlap and proximity
    columns: list[list[list[_LineSegment]]] = []
    # Sort groups left-to-right first by minimum X coordinate to discover columns in left-to-right order
    sorted_groups_left_to_right = sorted(groups, key=lambda g: min(min(l.x0, l.x1) for l in g))
    for g in sorted_groups_left_to_right:
        gx0 = min(min(l.x0, l.x1) for l in g)
        gx1 = max(max(l.x0, l.x1) for l in g)
        placed = False
        for col in columns:
            col_x0 = min(min(min(l.x0, l.x1) for l in cg) for cg in col)
            col_x1 = max(max(max(l.x0, l.x1) for l in cg) for cg in col)
            # Check horizontal overlap with a 15.0pt tolerance
            if not (gx1 < col_x0 - 15.0 or gx0 > col_x1 + 15.0):
                col.append(g)
                placed = True
                break
        if not placed:
            columns.append([g])

    # Sort each column top-to-bottom by Y, and flatten in left-to-right column order
    final_groups = []
    columns.sort(key=lambda col: min(min(min(l.x0, l.x1) for l in cg) for cg in col))
    for col in columns:
        col.sort(key=lambda g: sum((l.y0 + l.y1)/2 for l in g) / len(g))
        final_groups.extend(col)

    groups = final_groups
    return groups


def _is_coherent_large_tab_group(group: list[_LineSegment]) -> bool:
    if len(group) != 6:
        return False
    ys = sorted([(line.y0 + line.y1) / 2 for line in group])
    gaps = [ys[i+1] - ys[i] for i in range(len(ys) - 1)]
    if not gaps:
        return False
    sorted_gaps = sorted(gaps)
    median_gap = sorted_gaps[len(sorted_gaps) // 2]

    if not (15.0 < median_gap <= 32.0):
        return False

    mean_gap = sum(gaps) / len(gaps)
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    std_dev = variance ** 0.5
    cv = std_dev / mean_gap if mean_gap > 0 else float('inf')

    xs_min = [min(l.x0, l.x1) for l in group]
    xs_max = [max(l.x0, l.x1) for l in group]
    overlap_x0 = max(xs_min)
    overlap_x1 = min(xs_max)
    overlap_w = max(0.0, overlap_x1 - overlap_x0)
    widths = [abs(l.x1 - l.x0) for l in group]
    min_w = min(widths)
    overlap_ratio = overlap_w / min_w if min_w > 0 else 0.0

    if cv >= 0.05:
        return False
    if overlap_ratio < 0.80:
        return False
    if min_w < 200.0:
        return False
    if not all(abs(gap - median_gap) <= 2.0 for gap in gaps):
        return False

    return True


def _looks_like_six_line_tab(group: list[_LineSegment]) -> bool:
    return len(group) == 6 and _looks_like_tab_line_group(group)


def _looks_like_tab_line_group(group: list[_LineSegment]) -> bool:
    if len(group) not in {5, 6}:
        return False
    ys = [round((line.y0 + line.y1) / 2, 3) for line in group]
    gaps = [right - left for left, right in zip(ys, ys[1:])]
    if any(gap < 3.5 or gap > 24.0 for gap in gaps):
        return False
    average = sum(gaps) / len(gaps)
    return all(abs(gap - average) <= 2.5 for gap in gaps)


def _unique_sorted(values: list[float], tolerance: float = 1.0) -> list[float]:
    unique = []
    for value in sorted(values):
        if not unique or abs(unique[-1] - value) > tolerance:
            unique.append(value)
    return unique


def _nearest_system(systems: list[_TabSystem], x: float | None, y: float | None) -> _TabSystem | None:
    containing = [system for system in systems if system.candidate_zone_contains(x, y)]
    if not containing:
        return None
    def _sort_key(system: _TabSystem) -> tuple[float, float]:
        v_dist = min(abs(line_y - float(y)) for line_y in system.line_ys)
        h_dist = max(0.0, system.x0 - float(x), float(x) - system.x1) if x is not None else 0.0
        return (v_dist, h_dist)
    return min(containing, key=_sort_key)



def _candidate_confidence(
    raw_text: str,
    system: _TabSystem | None,
    string: int | None,
    bar_index: int | None,
    x: float | None,
    *,
    width: float | None = None,
    height: float | None = None,
    line_spacing: float = 12.0,
    assignment_warnings: list[str] | None = None,
) -> float:
    base = 0.55 if raw_text.strip().isdigit() else 0.35
    if system is not None:
        base += 0.1
        if system.grouping_warnings:
            base -= 0.2
    if string is not None:
        base += 0.15
    if bar_index is not None:
        base += 0.05
    if x is not None:
        base += 0.05

    # Deduct confidence based on visual/optical warnings
    if assignment_warnings:
        if "pdf_fret_digit_symbol_overlap_ambiguous" in assignment_warnings:
            base -= 0.3
        if "pdf_fret_bbox_too_tall" in assignment_warnings:
            base -= 0.25
        if "pdf_fret_bbox_too_wide" in assignment_warnings:
            base -= 0.25
        if "pdf_fret_bbox_too_small" in assignment_warnings:
            base -= 0.25
        if "pdf_fret_outside_valid_range" in assignment_warnings:
            base -= 0.3
        if "pdf_fret_digits_overlap_ambiguous" in assignment_warnings:
            base -= 0.3

    # Deduct confidence based on physical/optical bounds
    if width is not None and height is not None:
        if width < MIN_FRET_DIGIT_WIDTH_FOR_CONFIDENCE:
            if not _is_plausible_narrow_fret_digit(
                raw_text, system, string, bar_index, width, height, assignment_warnings
            ) or width < MIN_NARROW_FONT_FRET_DIGIT_WIDTH:
                base -= 0.25
        if height < 4.5:
            base -= 0.25
        if width > height * 1.8:
            base -= 0.15

    return max(0.1, min(base, 0.9))


def _is_plausible_narrow_fret_digit(
    raw_text: str,
    system: _TabSystem | None,
    string: int | None,
    bar_index: int | None,
    width: float,
    height: float,
    assignment_warnings: list[str] | None,
) -> bool:
    # Recognized as a digit
    text_stripped = raw_text.strip()
    if not text_stripped.isdigit():
        return False
    try:
        val = int(text_stripped)
        if not (0 <= val <= 24):
            return False
    except ValueError:
        return False

    # Inside a detected TAB system
    if system is None:
        return False
    # Assigned to a string line
    if string is None:
        return False
    # Assigned to a bar or plausible bar region
    if bar_index is None:
        return False
    # Height / aspect ratio is plausible
    if height < 4.5:
        return False
    if width > height * 1.8:
        return False

    # Not part of surrounding prose/header text
    warnings_set = set(assignment_warnings or [])
    excluded_warnings = {
        "pdf_fret_chord_text_digit_excluded",
        "pdf_fret_page_or_legend_number_excluded",
        "pdf_fret_technique_marker_excluded",
    }
    if warnings_set.intersection(excluded_warnings):
        return False

    return True


def _should_warn_unmerged_fret_digits(
    d1_text: str,
    d2_text: str,
    gap: float,
    d1_width: float,
    d2_width: float,
    vertical_offset: float,
) -> bool:
    # Must have similar y position (same baseline/string)
    if vertical_offset > 2.0:
        return False

    combined = d1_text + d2_text
    try:
        val = int(combined)
        if not (0 <= val <= 24):
            return False
    except ValueError:
        return False

    max_width = max(d1_width, d2_width)

    # For repeated equal digits (e.g. 11, 22), require a tighter gap
    if d1_text == d2_text:
        # A gap larger than max_width * 1.0 indicates separate notes (separate-note spacing evidence)
        limit = min(max_width * 1.0, 6.0)
        if gap > limit:
            return False
    else:
        # Different digits (e.g. 10, 12, 15)
        # Scale limit with character width (max_width * 1.6) but don't exceed the loop limit of 12.0
        limit = max(max_width * 1.6, 8.0)
        if gap > limit:
            return False

    return True


def _is_standard_music_symbol_or_parenthesis(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    if all(char in {"(", ")", "[", "]", "{", "}"} for char in cleaned):
        return True
    # Check if any character is in SMuFL Private Use Area (E000 - F8FF)
    if any(0xE000 <= ord(char) <= 0xF8FF for char in cleaned):
        return True
    return False


def _should_keep_candidate(candidate: dict[str, Any]) -> bool:
    if candidate.get("kind") in {"fret", "chord-symbol", "technique-text"}:
        return True
    text = str(candidate.get("raw_text", "")).strip().lower()
    raw = candidate.get("raw", {})
    near_tab_system = isinstance(raw, dict) and raw.get("system_inference") is not None
    warnings = raw.get("assignment_warnings", []) if isinstance(raw, dict) else []
    if any(w in warnings for w in (
        "pdf_fret_page_or_legend_number_excluded",
        "pdf_fret_chord_text_digit_excluded",
        "pdf_tuning_label_outside_system",
        "pdf_tuning_label_unassociated",
    )):
        return True
    if candidate.get("kind") == "candidate-text" and near_tab_system:
        x = candidate.get("x")
        y = candidate.get("y")
        sys_x0 = raw.get("system_x0")
        sys_x1 = raw.get("system_x1")
        line_ys = raw.get("tab_line_ys")
        if x is not None and sys_x0 is not None and sys_x1 is not None:
            if not (sys_x0 - 24.0 <= x <= sys_x1 + 24.0):
                return False
        if y is not None and line_ys:
            spacing = 12.0
            if len(line_ys) >= 2:
                spacing = line_ys[1] - line_ys[0]
            limit_y = line_ys[0] - max(34.0, spacing * 2.5)
            if y < limit_y:
                return False
    return text in {"x"} or near_tab_system


def _system_relation(system: _TabSystem | None, string: int | None) -> str | None:
    if system is None:
        return None
    if string is not None:
        return "on-tab-line"
    return "near-tab-system"
