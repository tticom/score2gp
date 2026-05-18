from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    inspection = inspect_pdf(path, out / "inspect")
    raw = {
        "source_pdf": str(path),
        "items": [],
        "warnings": [
            {
                "code": "tab-extraction-incomplete",
                "message": "First milestone only records PDF text diagnostics; full tab extraction is pending.",
            }
        ],
        "inspection_kind": inspection["kind"],
    }
    for page in inspection["pages"]:
        for block in page.get("text_blocks", []):
            text = block["text"]
            if any(char.isdigit() for char in text) or any(token in text.lower() for token in ("slide", "bend", "vib", "let")):
                raw["items"].append(
                    {
                        "page": page["page"],
                        "text": text,
                        "bbox": block["bbox"],
                        "confidence": 0.4,
                        "kind": "candidate-text",
                    }
                )
    (out / "tab_raw.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return raw
