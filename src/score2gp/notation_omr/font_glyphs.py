"""Expose painted music-font text to the existing staff-relative contour readers.

Font-cell boxes include ascenders and whitespace. Use the source font's actual
outlines, preserving the page transforms and paint, without substituting a
font, a reference score, or a duration inferred from character spacing.
"""
from __future__ import annotations

import copy
from typing import Any
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"


def _svg_bytes(outlined: ET.Element) -> bytes:
    """MuPDF needs unprefixed SVG elements; keep namespace changes local.

    ElementTree's default ns0/ns1 spelling leaves glyph references unresolved
    in the SVG importer. Do not rely on another module registering namespaces.
    """
    source = copy.deepcopy(outlined)
    for node in source.iter():
        if node.tag.startswith(SVG):
            node.tag = node.tag[len(SVG):]
        for key in list(node.attrib):
            if key.startswith(XLINK):
                node.set("xlink:" + key[len(XLINK):], node.attrib.pop(key))
    source.set("xmlns", SVG[1:-1])
    source.set("xmlns:xlink", XLINK[1:-1])
    return ET.tostring(source)


def is_music_font_text(text: str) -> bool:
    return any(0xE000 <= ord(char) <= 0xF8FF for char in text)


def music_font_drawings(page: Any) -> list[dict[str, Any]]:
    """Outline private-use text only; ordinary text keeps its existing route."""
    if not any(is_music_font_text(char["c"])
               for block in page.get_text("rawdict").get("blocks", [])
               for line in block.get("lines", []) for span in line.get("spans", [])
               for char in span.get("chars", [])):
        return []
    import pymupdf  # noqa: PLC0415 - PDF runtime is optional outside recognition

    source = ET.fromstring(page.get_svg_image(text_as_path=True))
    codes: list[str] = []

    def select(node: ET.Element) -> ET.Element | None:
        if node.tag == SVG + "defs":
            return copy.deepcopy(node)
        if node.tag == SVG + "use":
            text = node.get("data-text", "")
            if not is_music_font_text(text):
                return None
            codes.append(text)
            return copy.deepcopy(node)
        selected = [child for item in node if (child := select(item)) is not None]
        if not selected:
            return None
        result = ET.Element(node.tag, node.attrib)
        result.extend(selected)
        return result

    outlined = select(source)
    if outlined is None or not codes:
        raise ValueError("music_font_outline_unavailable")
    with pymupdf.open(stream=_svg_bytes(outlined), filetype="svg") as vector:
        with pymupdf.open(stream=vector.convert_to_pdf(), filetype="pdf") as document:
            drawings = document[0].get_drawings()
    if not drawings:
        raise ValueError("music_font_outline_unavailable")
    for index, drawing in enumerate(drawings):
        drawing["source_form"] = "font_glyph_outline"
        # Some fonts split a character into several painted paths. Never guess
        # a character-to-path correspondence when that happens.
        if len(drawings) == len(codes):
            drawing["font_glyph_codes"] = [f"U+{ord(c):04X}" for c in codes[index]]
    return drawings
