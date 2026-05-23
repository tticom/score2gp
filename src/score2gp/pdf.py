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
        for index, page in enumerate(doc, start=1):
            text_blocks = page.get_text("blocks")
            drawings = page.get_drawings()
            images = page.get_images(full=True)
            text_items_total += len(text_blocks)
            if text_blocks or drawings:
                vector_pages += 1
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_path = pages_dir / f"page-{index:03d}.png"
            pix.save(image_path)
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
            }
            summary["pages"].append(page_info)
        if vector_pages == doc.page_count and text_items_total:
            summary["kind"] = "born-digital"
        elif vector_pages:
            summary["kind"] = "mixed"
        else:
            summary["kind"] = "scanned-or-raster"

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
    }
    raw: dict[str, Any] = {
        "schema_version": TABRAW_SCHEMA_VERSION,
        "source_pdf": str(path),
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


@dataclass(frozen=True)
class _LineSegment:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def is_horizontal(self) -> bool:
        return abs(self.y0 - self.y1) <= 1.0 and abs(self.x1 - self.x0) >= 80.0

    @property
    def is_vertical(self) -> bool:
        return abs(self.x0 - self.x1) <= 1.0 and abs(self.y1 - self.y0) >= 40.0


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
        if len(self.line_ys) == 6 and len(self.barlines) >= 2:
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
        if len(self.barlines) < 2:
            warnings.append("missing_pdf_barlines")
            warnings.append("pdf_barlines_missing")
            warnings.append("pdf_bar_boxes_missing")
            if self.barline_candidates_count > 0:
                warnings.append("pdf_bar_boxes_not_constructible")
        return warnings

    @property
    def grouping_status(self) -> str:
        return "grouped" if not self.grouping_warnings else "partial"

    @property
    def bar_boxes(self) -> list[dict[str, float | int]]:
        if len(self.barlines) < 2:
            return []
        return [
            {
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
            for index, (left, right) in enumerate(zip(self.barlines, self.barlines[1:]))
        ]

    def string_for_y(self, y: float | None) -> tuple[int | None, int | None, float | None, list[str]]:
        if y is None:
            return None, None, None, []
        distances = [(abs(line_y - y), index + 1) for index, line_y in enumerate(self.line_ys)]
        distance, line_index = min(distances, key=lambda item: item[0])
        tolerance = max(4.0, self.line_spacing * 0.38)
        ambiguous_tolerance = max(tolerance, self.line_spacing * 0.58)
        if distance > tolerance:
            warnings = ["ambiguous_string_assignment", "pdf_string_assignment_ambiguous"]
            if distance <= self.line_spacing * 0.65:
                warnings.append("pdf_candidate_between_strings")
            else:
                warnings.append("pdf_string_assignment_missing")
            return None, None, distance, warnings
        return line_index, line_index, distance, []

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
        if x < self.barlines[0] - 2.0 or x > self.barlines[-1] + 2.0:
            return None, ["pdf_candidate_outside_bar", "ambiguous_bar_assignment"]
        internal_barlines = self.barlines[1:-1]
        if any(abs(x - barline) <= self.ambiguous_bar_tolerance for barline in internal_barlines):
            return None, ["ambiguous_bar_assignment", "pdf_barlines_ambiguous"]
        for index, (left, right) in enumerate(zip(self.barlines, self.barlines[1:]), start=1):
            if left - 2.0 <= x <= right + 2.0:
                return index, []
        return None, ["ambiguous_bar_assignment"]

    @property
    def line_spacing(self) -> float:
        gaps = [right - left for left, right in zip(self.line_ys, self.line_ys[1:])]
        return sum(gaps) / len(gaps) if gaps else 12.0

    @property
    def ambiguous_bar_tolerance(self) -> float:
        return max(4.0, self.line_spacing * 0.45)

    def contains_y(self, y: float | None) -> bool:
        if y is None:
            return False
        margin = max(6.0, self.line_spacing)
        return self.line_ys[0] - margin <= y <= self.line_ys[-1] + margin

    def candidate_zone_contains(self, x: float | None, y: float | None) -> bool:
        if x is None or y is None:
            return False
        horizontal_margin = 24.0
        top_margin = max(34.0, self.line_spacing * 2.5)
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


def _extract_pdf_text_candidates(pdf_path: Path, warnings: list[dict[str, Any]], meta: dict[str, int]) -> list[dict[str, Any]]:
    import fitz  # type: ignore[import-not-found]

    candidates = []
    filtered_index = 0
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            systems = _detect_tab_systems(page, page_number)
            ascii_blocks = _detect_ascii_tab_blocks(page, page_number, first_system_index=len(systems) + 1)

            # Accumulate metadata
            for system in systems:
                meta["detected_systems"] += 1
                meta["detected_staves"] += 1
                meta["detected_bar_boxes"] += len(system.bar_boxes)
                meta["detected_string_lines"] += len(system.line_ys)

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
                    if len(system.barlines) < 2:
                        warnings.append({
                            "code": "pdf_barlines_not_detected_in_system",
                            "message": f"Less than 2 valid barlines detected in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing"
                        })
                        warnings.append({
                            "code": "pdf_bar_boxes_not_constructible",
                            "message": f"Bar boxes are not constructible in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing"
                        })
                        warnings.append({
                            "code": "pdf_bar_detection_not_enough_for_build_ir",
                            "message": f"Bar detection is incomplete in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing"
                        })
                    if system.rejected_barline_count > 0 and len(system.barlines) == 0:
                        warnings.append({
                            "code": "pdf_barline_candidates_present_but_invalid",
                            "message": f"Barline candidates were present but all were rejected in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "missing"
                        })
                    reasons = system.rejection_reasons or {}
                    if reasons.get("pdf_barline_too_short", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_too_short",
                            "message": f"One or more barline candidates are too short in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_does_not_cross_staff", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_does_not_cross_staff",
                            "message": f"One or more barline candidates do not cross the tab staff in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_outside_system_bounds", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_outside_system_bounds",
                            "message": f"One or more barline candidates are outside the system bounds in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_ambiguous", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_ambiguous",
                            "message": f"One or more barline candidates are horizontally ambiguous in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "ambiguous"
                        })
                    if reasons.get("pdf_barline_too_short_absolute", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_too_short_absolute",
                            "message": f"One or more barline candidates are below absolute height threshold in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_too_short_relative_to_staff", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_too_short_relative_to_staff",
                            "message": f"One or more barline candidates are below relative staff-height threshold in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_crosses_insufficient_string_gaps", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_crosses_insufficient_string_gaps",
                            "message": f"One or more barline candidates cross too few string gaps in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_partial_staff_crossing", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_partial_staff_crossing",
                            "message": f"One or more barline candidates only partially cross the staff in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_outside_staff_region", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_outside_staff_region",
                            "message": f"One or more barline candidates are outside the staff region in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if reasons.get("pdf_barline_rejected_relative_height", 0) > 0:
                        warnings.append({
                            "code": "pdf_barline_rejected_relative_height",
                            "message": f"One or more barline candidates were rejected by relative staff-height check in system {system.system_index} on page {page_number}.",
                            "severity": "warning",
                            "grouping_status": "partial"
                        })
                    if len(system.barlines) >= 2:
                        warnings.append({
                            "code": "pdf_bar_boxes_constructed",
                            "message": f"Bar boxes successfully constructed in system {system.system_index} on page {page_number}.",
                            "severity": "info",
                            "grouping_status": "grouped"
                        })

                # Check for vertically overlapping systems on the page
                has_overlap = False
                for i, sys1 in enumerate(systems):
                    for sys2 in systems[i+1:]:
                        y_min1, y_max1 = min(sys1.line_ys), max(sys1.line_ys)
                        y_min2, y_max2 = min(sys2.line_ys), max(sys2.line_ys)
                        # Check overlap with a small tolerance of 1.0pt
                        if y_min1 <= y_max2 + 1.0 and y_min2 <= y_max1 + 1.0:
                            has_overlap = True
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
            words = sorted(
                page.get_text("words"),
                key=lambda word: (round(float(word[1]), 3), round(float(word[0]), 3), str(word[4])),
            )
            for word_index, word in enumerate(words, start=1):
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
                system = _nearest_system(systems, x, y)
                line_index = None
                string = None
                string_distance = None
                assignment_warnings: list[str] = []

                # Check for invalid geometry or candidate without geometry
                if any(v is None for v in bbox_values) or (bbox_values[0] == 0.0 and bbox_values[2] == 0.0):
                    assignment_warnings.append("pdf_text_candidate_without_geometry")

                is_fret_candidate = parse_fret_text(raw_text) is not None
                if system is not None:
                    # Check if candidate falls outside strict horizontal bounds of the system
                    if x < system.x0 or x > system.x1:
                        assignment_warnings.append("pdf_candidate_outside_system")
                    line_index, string, string_distance, string_warnings = system.string_for_y(y)
                    if string is None and is_fret_candidate:
                        assignment_warnings.append("pdf_candidates_unassigned_to_string")
                    assignment_warnings.extend(string_warnings)
                    bar_index, bar_warnings = system.bar_for_x(x)
                    if bar_index is None and is_fret_candidate:
                        assignment_warnings.append("pdf_candidates_unassigned_to_bar")
                    assignment_warnings.extend(bar_warnings)
                else:
                    bar_index = None
                    if is_fret_candidate:
                        assignment_warnings.append("pdf_candidates_unassigned_to_system")
                bar_bounds = system.bar_bounds_for_x(x) if system is not None else None
                confidence = _candidate_confidence(raw_text, system, string, bar_index, x)
                if assignment_warnings:
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
                        "pdf_word_index": word_index,
                        "pdf_block_number": int(word[5]) if len(word) > 5 else None,
                        "pdf_line_number": int(word[6]) if len(word) > 6 else None,
                        "pdf_word_number": int(word[7]) if len(word) > 7 else None,
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
                    },
                )
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
        "pdf_candidate_outside_system",
        "pdf_candidate_outside_bar",
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
    if grouping_status == "grouped":
        message = "candidate text found; tab staff/bar/string grouping inferred"
    elif grouping_status == "partial":
        message = "candidate text found; tab staff/bar/string grouping is partial"
    elif grouping_status == "ascii_grouped":
        message = "ASCII tab rows found; row/string grouping inferred, timing alignment unavailable"
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
                color=(0.8, 0.05, 0.05),
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


def _detect_tab_systems(page: Any, page_index: int) -> list[_TabSystem]:
    segments = list(_drawing_segments(page.get_drawings()))
    horizontal = sorted((segment for segment in segments if segment.is_horizontal), key=lambda segment: segment.y0)

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
    next_bar_index = 1

    for group in _tab_line_groups(horizontal):
        line_ys = [round((line.y0 + line.y1) / 2, 3) for line in group]
        x0 = min(min(line.x0, line.x1) for line in group)
        x1 = max(max(line.x0, line.x1) for line in group)
        y0 = min(line_ys)
        y1 = max(line_ys)

        system_candidates = []
        for s in deduped_verticals:
            x_val = (s.x0 + s.x1) / 2
            y_min = min(s.y0, s.y1)
            y_max = max(s.y0, s.y1)
            if y_max >= y0 - 15.0 and y_min <= y1 + 15.0 and x0 - 50.0 <= x_val <= x1 + 50.0:
                system_candidates.append(s)

        barline_candidates_count = len(system_candidates)
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
        }

        valid_barlines = []
        rejected_count = 0
        details = []
        staff_height = y1 - y0

        for s in system_candidates:
            x_val = (s.x0 + s.x1) / 2
            y_min = min(s.y0, s.y1)
            y_max = max(s.y0, s.y1)
            height = y_max - y_min

            # 1. Check horizontal bounds
            if x_val < x0 - 8.0 or x_val > x1 + 8.0:
                rejection_reasons["pdf_barline_outside_system_bounds"] += 1
                rejected_count += 1
                details.append({
                    "x": round(x_val, 3),
                    "y_min": round(y_min, 3),
                    "y_max": round(y_max, 3),
                    "height": round(height, 3),
                    "staff_height": round(staff_height, 3),
                    "coverage_ratio": 0.0,
                    "gaps_crossed": 0,
                    "absolute_height_decision": "rejected",
                    "relative_staff_crossing_decision": "rejected",
                    "final_decision": "rejected",
                    "rejection_reason": "pdf_barline_outside_system_bounds",
                })
                continue

            # 2. Check staff intersection
            if y_max < y0 or y_min > y1:
                rejection_reasons["pdf_barline_outside_staff_region"] += 1
                rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
                rejected_count += 1
                details.append({
                    "x": round(x_val, 3),
                    "y_min": round(y_min, 3),
                    "y_max": round(y_max, 3),
                    "height": round(height, 3),
                    "staff_height": round(staff_height, 3),
                    "coverage_ratio": 0.0,
                    "gaps_crossed": 0,
                    "absolute_height_decision": "rejected",
                    "relative_staff_crossing_decision": "rejected",
                    "final_decision": "rejected",
                    "rejection_reason": "pdf_barline_outside_staff_region",
                })
                continue

            # Calculate gaps crossed
            ys = sorted(line_ys)
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
            is_accepted = (absolute_height_ok or is_accepted_relative) and relative_height_ok

            rejection_reason = None
            if not relative_height_ok:
                if gaps_crossed < len(ys) - 2:
                    rejection_reason = "pdf_barline_crosses_insufficient_string_gaps"
                    rejection_reasons["pdf_barline_crosses_insufficient_string_gaps"] += 1
                    rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
                else:
                    rejection_reason = "pdf_barline_partial_staff_crossing"
                    rejection_reasons["pdf_barline_partial_staff_crossing"] += 1
                    rejection_reasons["pdf_barline_does_not_cross_staff"] += 1
            elif not is_accepted:
                # Crossed the staff region, but too short (e.g. < 20pt)
                rejection_reason = "pdf_barline_too_short_absolute"
                rejection_reasons["pdf_barline_too_short_absolute"] += 1
                rejection_reasons["pdf_barline_too_short"] += 1

            if rejection_reason is None and not is_accepted:
                rejection_reason = "pdf_barline_rejected_relative_height"
                rejection_reasons["pdf_barline_rejected_relative_height"] += 1
                rejection_reasons["pdf_barline_too_short"] += 1

            # Check ambiguity among candidates that otherwise would be valid barlines
            if is_accepted:
                is_ambiguous = False
                for other in system_candidates:
                    if other is s:
                        continue
                    other_x = (other.x0 + other.x1) / 2
                    other_y_min = min(other.y0, other.y1)
                    other_y_max = max(other.y0, other.y1)
                    other_height = other_y_max - other_y_min

                    # Estimate other gaps crossed
                    other_gaps = 0
                    for i in range(len(ys) - 1):
                        if other_y_min <= ys[i] + 1.5 and other_y_max >= ys[i+1] - 1.5:
                            other_gaps += 1
                    other_crosses = (other_y_min <= y0 + 4.0 and other_y_max >= y1 - 4.0) or (other_gaps >= len(ys) - 1)
                    other_accepted = ((other_height >= 40.0) or (other_height >= 20.0 and other_crosses)) and other_crosses

                    if other_accepted and abs(x_val - other_x) < 6.0:
                        is_ambiguous = True
                        break

                if is_ambiguous:
                    is_accepted = False
                    rejection_reason = "pdf_barline_ambiguous"
                    rejection_reasons["pdf_barline_ambiguous"] += 1

            if not is_accepted:
                if rejection_reason is None:
                    rejection_reason = "pdf_barline_too_short"
                    rejection_reasons["pdf_barline_too_short"] += 1
                elif height < 40.0:
                    rejection_reasons["pdf_barline_too_short"] += 1
                rejected_count += 1
            else:
                valid_barlines.append(round(x_val, 3))

            details.append({
                "x": round(x_val, 3),
                "y_min": round(y_min, 3),
                "y_max": round(y_max, 3),
                "height": round(height, 3),
                "staff_height": round(staff_height, 3),
                "coverage_ratio": round(coverage_ratio, 3),
                "gaps_crossed": gaps_crossed,
                "absolute_height_decision": "accepted" if absolute_height_ok else "rejected",
                "relative_staff_crossing_decision": "accepted" if relative_height_ok else "rejected",
                "final_decision": "accepted" if is_accepted else "rejected",
                "rejection_reason": rejection_reason,
            })

        valid_barlines = _unique_sorted(valid_barlines)

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
    return systems


def _drawing_segments(drawings: list[dict[str, Any]]) -> list[_LineSegment]:
    segments = []
    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item:
                continue
            if item[0] == "l" and len(item) >= 3:
                p0 = item[1]
                p1 = item[2]
                segments.append(_LineSegment(float(p0.x), float(p0.y), float(p1.x), float(p1.y)))
            elif item[0] == "re" and len(item) >= 2:
                rect = item[1]
                segments.extend(
                    [
                        _LineSegment(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y0)),
                        _LineSegment(float(rect.x1), float(rect.y0), float(rect.x1), float(rect.y1)),
                        _LineSegment(float(rect.x1), float(rect.y1), float(rect.x0), float(rect.y1)),
                        _LineSegment(float(rect.x0), float(rect.y1), float(rect.x0), float(rect.y0)),
                    ]
                )
    return segments


def _six_line_groups(lines: list[_LineSegment]) -> list[list[_LineSegment]]:
    return [group for group in _tab_line_groups(lines) if len(group) == 6]


def _tab_line_groups(lines: list[_LineSegment]) -> list[list[_LineSegment]]:
    sorted_lines = sorted(lines, key=lambda l: (l.y0 + l.y1) / 2)
    n = len(sorted_lines)
    used = set()
    groups = []

    # Try to find 6-line groups first
    for i0 in range(n):
        if i0 in used:
            continue
        for i1 in range(i0 + 1, n):
            if i1 in used:
                continue
            y0 = (sorted_lines[i0].y0 + sorted_lines[i0].y1) / 2
            y1 = (sorted_lines[i1].y0 + sorted_lines[i1].y1) / 2
            gap = y1 - y0
            if gap < 6.0 or gap > 24.0:
                continue

            group_indices = [i0, i1]
            for step in range(2, 6):
                target_y = y0 + step * gap
                best_idx = None
                best_diff = 2.5
                for j in range(group_indices[-1] + 1, n):
                    if j in used:
                        continue
                    yj = (sorted_lines[j].y0 + sorted_lines[j].y1) / 2
                    diff = abs(yj - target_y)
                    if diff < best_diff:
                        best_diff = diff
                        best_idx = j
                if best_idx is not None:
                    group_indices.append(best_idx)
                else:
                    break

            if len(group_indices) == 6:
                group = [sorted_lines[idx] for idx in group_indices]
                groups.append(group)
                used.update(group_indices)
                break

    # Also find 5-line groups among the remaining unused lines
    for i0 in range(n):
        if i0 in used:
            continue
        for i1 in range(i0 + 1, n):
            if i1 in used:
                continue
            y0 = (sorted_lines[i0].y0 + sorted_lines[i0].y1) / 2
            y1 = (sorted_lines[i1].y0 + sorted_lines[i1].y1) / 2
            gap = y1 - y0
            if gap < 6.0 or gap > 24.0:
                continue

            group_indices = [i0, i1]
            for step in range(2, 5):
                target_y = y0 + step * gap
                best_idx = None
                best_diff = 2.5
                for j in range(group_indices[-1] + 1, n):
                    if j in used:
                        continue
                    yj = (sorted_lines[j].y0 + sorted_lines[j].y1) / 2
                    diff = abs(yj - target_y)
                    if diff < best_diff:
                        best_diff = diff
                        best_idx = j
                if best_idx is not None:
                    group_indices.append(best_idx)
                else:
                    break

            if len(group_indices) == 5:
                group = [sorted_lines[idx] for idx in group_indices]
                groups.append(group)
                used.update(group_indices)
                break

    groups.sort(key=lambda g: sum((l.y0 + l.y1)/2 for l in g) / len(g))
    return groups


def _looks_like_six_line_tab(group: list[_LineSegment]) -> bool:
    return len(group) == 6 and _looks_like_tab_line_group(group)


def _looks_like_tab_line_group(group: list[_LineSegment]) -> bool:
    if len(group) not in {5, 6}:
        return False
    ys = [round((line.y0 + line.y1) / 2, 3) for line in group]
    gaps = [right - left for left, right in zip(ys, ys[1:])]
    if any(gap < 6.0 or gap > 24.0 for gap in gaps):
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
    return min(containing, key=lambda system: min(abs(line_y - float(y)) for line_y in system.line_ys))


def _candidate_confidence(
    raw_text: str,
    system: _TabSystem | None,
    string: int | None,
    bar_index: int | None,
    x: float | None,
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
    return min(base, 0.9)


def _should_keep_candidate(candidate: dict[str, Any]) -> bool:
    if candidate.get("kind") in {"fret", "chord-symbol", "technique-text"}:
        return True
    text = str(candidate.get("raw_text", "")).strip().lower()
    raw = candidate.get("raw", {})
    near_tab_system = isinstance(raw, dict) and raw.get("system_inference") is not None
    return text in {"x"} or near_tab_system


def _system_relation(system: _TabSystem | None, string: int | None) -> str | None:
    if system is None:
        return None
    if string is not None:
        return "on-tab-line"
    return "near-tab-system"
