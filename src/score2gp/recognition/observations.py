"""Canonical Vector and Text Observations Adapter.

Extracts raw physical observations (vector drawings, text glyphs/spans, and
raster regions) from document sources without assigning musical meaning.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
from typing import Any

try:
    import pymupdf as fitz  # type: ignore[import-untyped]
except ImportError:
    try:
        import fitz  # type: ignore[import-untyped,no-redef]
    except ImportError:
        fitz = None  # type: ignore[assignment]

from score2gp.recognition.schemas import (
    BoundingBox2D,
    DocumentObservations,
    ObservationProvenance,
    Point2D,
    RasterObservation,
    SourceModality,
    TextObservation,
    VectorPathObservation,
)


class ObservationAdapterError(RuntimeError):
    """Raised when document acquisition or observation extraction fails."""


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_bbox(page_index: int, x0: float, y0: float, x1: float, y1: float) -> BoundingBox2D:
    return BoundingBox2D(
        page_index=page_index,
        x0=float(min(x0, x1)),
        y0=float(min(y0, y1)),
        x1=float(max(x0, x1)),
        y1=float(max(y0, y1)),
    )


def _extract_color_channels(page: Any, xref: int, cs_field: Any) -> int:
    """Extract number of color channels (1, 3, or 4) for an image."""
    try:
        doc = getattr(page, "parent", None)
        if doc is not None and hasattr(doc, "extract_image"):
            info = doc.extract_image(xref)
            cs_val = info.get("colorspace")
            if isinstance(cs_val, int) and 1 <= cs_val <= 4:
                return cs_val
    except Exception:
        pass
    cs_name = str(cs_field).lower()
    if "gray" in cs_name or "indexed" in cs_name or "stencil" in cs_name:
        return 1
    if "cmyk" in cs_name:
        return 4
    return 3


def extract_vector_observations(
    page: Any,
    page_index: int,
    source_file: str | None = None,
    source_hash: str | None = None,
) -> list[VectorPathObservation]:
    """Extract vector path drawing primitives from a page into typed VectorPathObservations.

    Extracts individual drawing items with item-level provenance and exact
    unrounded coordinates, preserving reconstruction derivations.
    """
    vectors: list[VectorPathObservation] = []
    drawings = page.get_drawings()

    for drawing_idx, drawing in enumerate(drawings):
        items = drawing.get("items", [])
        if not items:
            continue

        seqno = drawing.get("seqno", drawing_idx)
        color = drawing.get("color")
        color_str = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}" if color and len(color) == 3 else None
        fill = drawing.get("fill")
        fill_str = f"#{int(fill[0]*255):02x}{int(fill[1]*255):02x}{int(fill[2]*255):02x}" if fill and len(fill) == 3 else None
        is_closed = bool(drawing.get("closePath", False))

        for item_idx, item in enumerate(items):
            tag = item[0]
            points: list[Point2D] = []
            path_type: str = "path"

            if tag == "l":  # Line
                path_type = "line"
                p1, p2 = item[1], item[2]
                points = [Point2D(x=float(p1.x), y=float(p1.y)), Point2D(x=float(p2.x), y=float(p2.y))]
                bbox = _normalize_bbox(page_index, p1.x, p1.y, p2.x, p2.y)
            elif tag == "re":  # Rectangle
                path_type = "rect"
                r = item[1]
                points = [
                    Point2D(x=float(r.x0), y=float(r.y0)),
                    Point2D(x=float(r.x1), y=float(r.y0)),
                    Point2D(x=float(r.x1), y=float(r.y1)),
                    Point2D(x=float(r.x0), y=float(r.y1)),
                ]
                bbox = _normalize_bbox(page_index, r.x0, r.y0, r.x1, r.y1)
            elif tag == "qu":  # Quadrilateral (Quad object)
                path_type = "polygon"
                quad = item[1]
                if hasattr(quad, "ul") and hasattr(quad, "ur") and hasattr(quad, "lr") and hasattr(quad, "ll"):
                    points = [
                        Point2D(x=float(quad.ul.x), y=float(quad.ul.y)),
                        Point2D(x=float(quad.ur.x), y=float(quad.ur.y)),
                        Point2D(x=float(quad.lr.x), y=float(quad.lr.y)),
                        Point2D(x=float(quad.ll.x), y=float(quad.ll.y)),
                    ]
                else:
                    for pt in item[1:]:
                        if hasattr(pt, "x") and hasattr(pt, "y"):
                            points.append(Point2D(x=float(pt.x), y=float(pt.y)))
                if points:
                    pts_x = [p.x for p in points]
                    pts_y = [p.y for p in points]
                    bbox = _normalize_bbox(page_index, min(pts_x), min(pts_y), max(pts_x), max(pts_y))
                else:
                    bbox = _normalize_bbox(page_index, 0.0, 0.0, 0.0, 0.0)
            elif tag == "c":  # Cubic Bezier Curve
                path_type = "curve"
                for pt in item[1:]:
                    if hasattr(pt, "x") and hasattr(pt, "y"):
                        points.append(Point2D(x=float(pt.x), y=float(pt.y)))
                if points:
                    pts_x = [p.x for p in points]
                    pts_y = [p.y for p in points]
                    bbox = _normalize_bbox(page_index, min(pts_x), min(pts_y), max(pts_x), max(pts_y))
                else:
                    bbox = _normalize_bbox(page_index, 0.0, 0.0, 0.0, 0.0)
            else:
                path_type = "path"
                for el in item[1:]:
                    if hasattr(el, "x") and hasattr(el, "y"):
                        points.append(Point2D(x=float(el.x), y=float(el.y)))
                if points:
                    pts_x = [p.x for p in points]
                    pts_y = [p.y for p in points]
                    bbox = _normalize_bbox(page_index, min(pts_x), min(pts_y), max(pts_x), max(pts_y))
                else:
                    raw_rect = drawing.get("rect")
                    if raw_rect is not None:
                        bbox = _normalize_bbox(page_index, raw_rect.x0, raw_rect.y0, raw_rect.x1, raw_rect.y1)
                    else:
                        bbox = _normalize_bbox(page_index, 0.0, 0.0, 0.0, 0.0)

            item_primitive_id = f"p{page_index}_d{drawing_idx}_i{item_idx}_s{seqno}"

            obs = VectorPathObservation(
                id=item_primitive_id,
                modality=SourceModality.VECTOR,
                provenance=ObservationProvenance(
                    modality=SourceModality.VECTOR,
                    source_file=source_file,
                    source_hash=source_hash,
                    page_index=page_index,
                    raw_primitive_id=item_primitive_id,
                    acquisition_adapter="pymupdf.drawings.item",
                    extra={
                        "drawing_index": drawing_idx,
                        "item_index": item_idx,
                        "total_items_in_drawing": len(items),
                        "seqno": seqno,
                        "item_tag": tag,
                        "stroke_opacity": drawing.get("stroke_opacity"),
                    },
                ),
                bbox=bbox,
                path_type=path_type,  # type: ignore[arg-type]
                points=points,
                stroke_width=drawing.get("width"),
                stroke_color=color_str,
                fill_color=fill_str,
                is_closed=is_closed,
                confidence=1.0,
                extra={},
            )
            vectors.append(obs)

    return vectors


def extract_text_observations(
    page: Any,
    page_index: int,
    source_file: str | None = None,
    source_hash: str | None = None,
) -> list[TextObservation]:
    """Extract text spans from a page into typed TextObservations with unrounded exact coordinates."""
    texts: list[TextObservation] = []
    text_dict = page.get_text("dict")
    span_idx = 0

    for block_idx, block in enumerate(text_dict.get("blocks", [])):
        if "lines" not in block:
            continue
        for line_idx, line in enumerate(block["lines"]):
            for span in line.get("spans", []):
                raw_text = span.get("text", "")
                if not raw_text:
                    continue

                sb = span.get("bbox", (0.0, 0.0, 0.0, 0.0))
                bbox = _normalize_bbox(page_index, sb[0], sb[1], sb[2], sb[3])
                raw_id = f"p{page_index}_t{span_idx}_{block_idx}_{line_idx}"
                span_idx += 1

                obs = TextObservation(
                    id=raw_id,
                    modality=SourceModality.TEXT,
                    provenance=ObservationProvenance(
                        modality=SourceModality.TEXT,
                        source_file=source_file,
                        source_hash=source_hash,
                        page_index=page_index,
                        raw_primitive_id=raw_id,
                        acquisition_adapter="pymupdf.dict.spans",
                        extra={
                            "block_number": block_idx,
                            "line_number": line_idx,
                            "flags": span.get("flags"),
                        },
                    ),
                    bbox=bbox,
                    raw_text=raw_text,
                    font_name=span.get("font"),
                    font_size=float(span["size"]) if span.get("size") is not None else None,
                    reading_direction="horizontal_lr",
                    confidence=1.0,
                    extra={},
                )
                texts.append(obs)

    return texts


def extract_raster_observations(
    page: Any,
    page_index: int,
    source_file: str | None = None,
    source_hash: str | None = None,
) -> list[RasterObservation]:
    """Extract embedded images from a page into typed RasterObservations."""
    rasters: list[RasterObservation] = []
    image_list = page.get_images(full=True)

    for idx, img_info in enumerate(image_list):
        xref = img_info[0]
        rects = page.get_image_rects(xref)
        bbox = _normalize_bbox(
            page_index,
            rects[0].x0 if rects else 0.0,
            rects[0].y0 if rects else 0.0,
            rects[0].x1 if rects else 0.0,
            rects[0].y1 if rects else 0.0,
        )

        raw_id = f"p{page_index}_r{idx}_xref{xref}"
        channels = _extract_color_channels(page, xref, img_info[5] if len(img_info) > 5 else None)

        obs = RasterObservation(
            id=raw_id,
            modality=SourceModality.RASTER,
            provenance=ObservationProvenance(
                modality=SourceModality.RASTER,
                source_file=source_file,
                source_hash=source_hash,
                page_index=page_index,
                raw_primitive_id=raw_id,
                acquisition_adapter="pymupdf.images",
                extra={
                    "xref": xref,
                    "smask": img_info[1],
                },
            ),
            bbox=bbox,
            resolution_dpi=float(img_info[2]) / max(bbox.x1 - bbox.x0, 1.0) * 72.0 if (bbox.x1 > bbox.x0) else 300.0,
            pixel_width=int(img_info[2]),
            pixel_height=int(img_info[3]),
            color_channels=channels,
            feature_type="region",
            raster_ref=f"xref:{xref}",
            confidence=1.0,
            extra={},
        )
        rasters.append(obs)

    return rasters


def observe_pdf(source: str | Path | bytes | Any) -> DocumentObservations:
    """Acquire and extract DocumentObservations from a PDF document."""
    if fitz is None:
        raise ObservationAdapterError("pymupdf / fitz is not installed or available.")

    doc: Any = None
    source_file: str | None = None
    source_hash: str | None = None

    try:
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.is_file():
                raise ObservationAdapterError(f"PDF source file not found: {source}")
            source_file = str(p)
            try:
                content = p.read_bytes()
                source_hash = _compute_sha256(content)
                doc = fitz.open(stream=content, filetype="pdf")
            except Exception as exc:
                raise ObservationAdapterError(f"Failed to open/parse PDF file '{source}': {exc}") from exc
        elif isinstance(source, bytes):
            source_hash = _compute_sha256(source)
            try:
                doc = fitz.open(stream=source, filetype="pdf")
            except Exception as exc:
                raise ObservationAdapterError(f"Failed to open/parse PDF bytes: {exc}") from exc
        elif hasattr(source, "page_count") and hasattr(source, "__iter__"):
            doc = source
        else:
            raise ObservationAdapterError(f"Unsupported PDF source type: {type(source)}")
    except ObservationAdapterError:
        raise
    except Exception as exc:
        raise ObservationAdapterError(f"Unexpected error acquiring PDF source: {exc}") from exc

    try:
        page_count = doc.page_count
        all_vectors: list[VectorPathObservation] = []
        all_texts: list[TextObservation] = []
        all_rasters: list[RasterObservation] = []

        for page_idx, page in enumerate(doc, start=1):
            all_vectors.extend(extract_vector_observations(page, page_idx, source_file, source_hash))
            all_texts.extend(extract_text_observations(page, page_idx, source_file, source_hash))
            all_rasters.extend(extract_raster_observations(page, page_idx, source_file, source_hash))

        doc_id = f"doc_{source_hash[:16]}" if source_hash else "doc_stream"

        # Determine overall document modality
        modalities = set()
        if all_vectors:
            modalities.add(SourceModality.VECTOR)
        if all_texts:
            modalities.add(SourceModality.TEXT)
        if all_rasters:
            modalities.add(SourceModality.RASTER)

        if len(modalities) == 1:
            overall_modality = list(modalities)[0]
        else:
            overall_modality = SourceModality.HYBRID

        return DocumentObservations(
            document_id=doc_id,
            source_file=source_file,
            page_count=page_count,
            modality=overall_modality,
            vectors=all_vectors,
            texts=all_texts,
            rasters=all_rasters,
            scale_estimates={},
            metadata={},
        )
    except Exception as exc:
        raise ObservationAdapterError(f"Failed to extract observations from PDF: {exc}") from exc
    finally:
        if isinstance(source, (str, Path, bytes)) and doc is not None:
            doc.close()


def observe(source: str | Path | bytes | Any) -> DocumentObservations:
    """Primary entrypoint for document observation extraction."""
    return observe_pdf(source)
