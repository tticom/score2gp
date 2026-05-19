from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .tabraw import TABRAW_SCHEMA_VERSION, TabRaw, make_tab_candidate


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

    raw = TabRaw.model_validate(raw).model_dump(mode="json", exclude_none=True)
    tabraw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
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
    line_ys: list[float]
    x0: float
    x1: float
    barlines: list[float]

    def string_for_y(self, y: float | None) -> tuple[int | None, int | None, float | None]:
        if y is None:
            return None, None, None
        distances = [(abs(line_y - y), index + 1) for index, line_y in enumerate(self.line_ys)]
        distance, line_index = min(distances, key=lambda item: item[0])
        tolerance = max(4.0, self.line_spacing * 0.45)
        if distance > tolerance:
            return None, None, distance
        return line_index, line_index, distance

    def bar_for_x(self, x: float | None) -> int | None:
        if x is None or len(self.barlines) < 2:
            return None
        for index, (left, right) in enumerate(zip(self.barlines, self.barlines[1:]), start=1):
            if left - 2.0 <= x <= right + 2.0:
                return index
        return None

    @property
    def line_spacing(self) -> float:
        gaps = [right - left for left, right in zip(self.line_ys, self.line_ys[1:])]
        return sum(gaps) / len(gaps) if gaps else 12.0

    def contains_y(self, y: float | None) -> bool:
        if y is None:
            return False
        margin = max(6.0, self.line_spacing)
        return self.line_ys[0] - margin <= y <= self.line_ys[-1] + margin


def _extract_pdf_text_candidates(pdf_path: Path, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import fitz  # type: ignore[import-not-found]

    candidates = []
    filtered_index = 0
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            systems = _detect_tab_systems(page, page_number)
            if not systems:
                warnings.append(
                    {
                        "code": "pdf-tab-system-not-detected",
                        "message": f"No six-line tab system was inferred on page {page_number}; candidates may lack string/bar estimates.",
                        "severity": "info",
                    }
                )
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
                system = _nearest_system(systems, y)
                line_index = None
                string = None
                string_distance = None
                if system is not None:
                    line_index, string, string_distance = system.string_for_y(y)
                candidate = make_tab_candidate(
                    candidate_id=f"pdf-p{page_number:03d}-c{filtered_index + 1:04d}",
                    raw_text=raw_text,
                    page_index=page_number,
                    bbox_values=bbox_values,
                    confidence=_candidate_confidence(raw_text, system, string, x),
                    system_index=system.system_index if system is not None else None,
                    staff_index=system.staff_index if system is not None else None,
                    bar_index=system.bar_for_x(x) if system is not None else None,
                    line_index=line_index,
                    string=string,
                    raw={
                        "pdf_word_index": word_index,
                        "pdf_block_number": int(word[5]) if len(word) > 5 else None,
                        "pdf_line_number": int(word[6]) if len(word) > 6 else None,
                        "pdf_word_number": int(word[7]) if len(word) > 7 else None,
                        "system_inference": "six-horizontal-lines" if system is not None else None,
                        "string_distance": round(string_distance, 3) if string_distance is not None else None,
                        "barline_count": len(system.barlines) if system is not None else None,
                    },
                )
                if not _should_keep_candidate(candidate.model_dump(mode="json", exclude_none=True)):
                    continue
                filtered_index += 1
                candidates.append(candidate.model_dump(mode="json", exclude_none=True))
    return candidates


def _detect_tab_systems(page: Any, page_index: int) -> list[_TabSystem]:
    segments = list(_drawing_segments(page.get_drawings()))
    horizontal = sorted((segment for segment in segments if segment.is_horizontal), key=lambda segment: segment.y0)
    vertical = sorted((segment for segment in segments if segment.is_vertical), key=lambda segment: segment.x0)
    systems = []
    system_index = 1

    for group in _six_line_groups(horizontal):
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
                line_ys=line_ys,
                x0=x0,
                x1=x1,
                barlines=barlines,
            )
        )
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
    groups = []
    index = 0
    while index + 5 < len(lines):
        group = lines[index : index + 6]
        if _looks_like_six_line_tab(group):
            groups.append(group)
            index += 6
        else:
            index += 1
    return groups


def _looks_like_six_line_tab(group: list[_LineSegment]) -> bool:
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


def _nearest_system(systems: list[_TabSystem], y: float | None) -> _TabSystem | None:
    containing = [system for system in systems if system.contains_y(y)]
    if not containing:
        return None
    return min(containing, key=lambda system: min(abs(line_y - float(y)) for line_y in system.line_ys))


def _candidate_confidence(raw_text: str, system: _TabSystem | None, string: int | None, x: float | None) -> float:
    base = 0.65 if raw_text.strip().isdigit() else 0.45
    if system is not None:
        base += 0.1
    if string is not None:
        base += 0.15
    if x is not None:
        base += 0.05
    return min(base, 0.9)


def _should_keep_candidate(candidate: dict[str, Any]) -> bool:
    if candidate.get("kind") in {"fret", "chord-symbol", "technique-text"}:
        return True
    text = str(candidate.get("raw_text", "")).strip().lower()
    return text in {"x"}
