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
        raw["candidates"].extend(_extract_pdf_text_candidates(Path(path), raw["warnings"]))

    _append_grouping_warnings(raw)
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
        if len(self.barlines) < 2:
            warnings.append("missing_pdf_barlines")
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
            warnings = ["ambiguous_string_assignment"] if distance <= ambiguous_tolerance else []
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
            return None, ["missing_pdf_barlines"] if x is not None else []
        internal_barlines = self.barlines[1:-1]
        if any(abs(x - barline) <= self.ambiguous_bar_tolerance for barline in internal_barlines):
            return None, ["ambiguous_bar_assignment"]
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


def _extract_pdf_text_candidates(pdf_path: Path, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import fitz  # type: ignore[import-not-found]

    candidates = []
    filtered_index = 0
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            systems = _detect_tab_systems(page, page_number)
            ascii_blocks = _detect_ascii_tab_blocks(page, page_number, first_system_index=len(systems) + 1)
            if not systems:
                warnings.append(
                    {
                        "code": "pdf-tab-system-not-detected",
                        "message": f"No six-line tab system was inferred on page {page_number}; candidates may lack string/bar estimates.",
                        "severity": "info",
                    }
                )
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
                if system is not None:
                    line_index, string, string_distance, string_warnings = system.string_for_y(y)
                    assignment_warnings.extend(string_warnings)
                if system is not None:
                    bar_index, bar_warnings = system.bar_for_x(x)
                    assignment_warnings.extend(bar_warnings)
                else:
                    bar_index = None
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
    warnings: list[dict[str, Any]] = [
        {
            "code": "ascii_tab_detected",
            "message": f"ASCII-style tab text was detected on page {page_number}.",
            "severity": "info",
            "parser_version": ASCII_TAB_PARSER_VERSION,
            "ascii_tab_block_count": len(blocks),
            "ascii_tab_complete_block_count": complete_count,
            "ascii_tab_partial_block_count": partial_count,
        }
    ]
    if complete_count:
        warnings.append(
            {
                "code": "ascii_tab_timing_unavailable",
                "message": (
                    "ASCII-tab rows provide string/fret evidence, but no safe MusicXML timing or bar alignment is "
                    "available from the PDF alone; build-ir must not guess timing from character positions."
                ),
                "severity": "warning",
                "grouping_status": "ascii_grouped",
                "parser_version": ASCII_TAB_PARSER_VERSION,
                "ascii_tab_complete_block_count": complete_count,
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
                        "system_inference": "ascii-tab-text",
                        "grouping_status": block.grouping_status,
                        "safe_grouping": False,
                        "ascii_tab": True,
                        "ascii_block_id": f"ascii-p{row.page_index:03d}-s{block.system_index:03d}",
                        "row_label": row.label,
                        "row_index": row.row_index,
                        "character_span": [match.start(), match.end()],
                        "line_character_span": [char_start, char_end],
                        "line_text_length": len(row.text),
                        "string_source": "ascii-row-order" if block.is_complete and is_fret else None,
                        "grouping_confidence": block.grouping_confidence,
                        "grouping_warnings": block.grouping_warnings or None,
                        "assignment_warnings": ["ascii_tab_timing_unavailable"],
                        "tab_staff_bbox": block.staff_bbox,
                        "tab_line_ys": block.line_ys,
                        "barline_count": 0,
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


def _append_grouping_warnings(raw: dict[str, Any]) -> None:
    candidates = raw.get("candidates", [])
    fret_candidates = [candidate for candidate in candidates if candidate.get("parsed_fret") is not None]
    if not candidates or not fret_candidates:
        return

    grouping_counts = {
        "total_candidate_count": len(candidates),
        "playable_fret_candidate_count": len(fret_candidates),
        "candidates_with_system": sum(1 for candidate in candidates if candidate.get("system_index") is not None),
        "candidates_with_bar": sum(1 for candidate in candidates if candidate.get("bar_index") is not None),
        "fret_candidates_with_system": sum(1 for candidate in fret_candidates if candidate.get("system_index") is not None),
        "fret_candidates_with_bar": sum(1 for candidate in fret_candidates if candidate.get("bar_index") is not None),
        "fret_candidates_with_string": sum(1 for candidate in fret_candidates if candidate.get("string") is not None),
    }
    missing = []
    if grouping_counts["fret_candidates_with_system"] < len(fret_candidates):
        missing.append("system")
    if grouping_counts["fret_candidates_with_bar"] < len(fret_candidates):
        missing.append("bar")
    if grouping_counts["fret_candidates_with_string"] < len(fret_candidates):
        missing.append("string")
    unsafe_codes = _unsafe_grouping_codes(fret_candidates)
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


def _unsafe_grouping_codes(fret_candidates: list[dict[str, Any]]) -> list[str]:
    drawn_grouping_codes = {
        "missing_pdf_barlines",
        "incomplete_tab_staff",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
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
    return sorted(codes)


def _specific_grouping_warning(code: str, grouping_counts: dict[str, int]) -> dict[str, Any]:
    messages = {
        "missing_pdf_barlines": "A tab staff was inferred, but reliable barlines were not detected.",
        "incomplete_tab_staff": "A partial tab staff was inferred, but fewer than six string lines were detected.",
        "ambiguous_string_assignment": "One or more fret candidates are too far from a single string line to assign safely.",
        "ambiguous_bar_assignment": "One or more fret candidates are too close to a bar boundary to assign safely.",
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
    vertical = sorted((segment for segment in segments if segment.is_vertical), key=lambda segment: segment.x0)
    systems = []
    system_index = 1
    next_bar_index = 1

    for group in _tab_line_groups(horizontal):
        line_ys = [round((line.y0 + line.y1) / 2, 3) for line in group]
        x0 = min(min(line.x0, line.x1) for line in group)
        x1 = max(max(line.x0, line.x1) for line in group)
        y0 = min(line_ys)
        y1 = max(line_ys)
        barlines = [
            round((line.x0 + line.x1) / 2, 3)
            for line in vertical
            if x0 - 8.0 <= (line.x0 + line.x1) / 2 <= x1 + 8.0
            and min(line.y0, line.y1) <= y0 + 4.0
            and max(line.y0, line.y1) >= y1 - 4.0
        ]
        barlines = _unique_sorted(barlines)
        systems.append(
            _TabSystem(
                page_index=page_index,
                system_index=system_index,
                staff_index=1,
                first_bar_index=next_bar_index,
                line_ys=line_ys,
                x0=x0,
                x1=x1,
                barlines=barlines,
            )
        )
        next_bar_index += max(1, len(barlines) - 1)
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
    groups = []
    index = 0
    while index < len(lines):
        group = lines[index : index + 6]
        if len(group) == 6 and _looks_like_tab_line_group(group):
            groups.append(group)
            index += 6
            continue
        group = lines[index : index + 5]
        if len(group) == 5 and _looks_like_tab_line_group(group):
            groups.append(group)
            index += 5
        else:
            index += 1
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
