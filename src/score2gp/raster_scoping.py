"""Measurement hook for scanned and hand-drawn sources (RASTER-00).

Scoping only: nothing here is wired into ``convert`` and no source output changes. It reports counts
(pages, image size and resolution, staff-like line chains located) for image-only PDF pages so that the
scoping document can say how far staff location gets on the sources that have no vector content.

Method (deterministic, pure Pillow, no model): render a page to grey at a pinned dpi, take the mean ink per
pixel row (anti-aliasing tolerant, unlike the 128-threshold unbroken-run test of
``pdf_raster_staff_diagnostics``), merge adjacent inked rows into line rows, then find evenly spaced chains
of lines. A chain of 5 lines is a notation-staff candidate, a chain of 6 a TAB-staff candidate. Spacing and
position are reported with each chain. Results are NOT independently verified: no reference file exists for
these sources, so the located counts are checked only against a viewer's count of the printed page.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image

RENDER_DPI = 150.0
INK_ROW_THRESHOLD = 0.15  # mean ink (0..1) across the page width for a row to count as part of a line
MIN_SPACING_PT = 2.0
MAX_SPACING_PT = 12.0
SPACING_TOLERANCE = 0.2
NOTATION_LINES = 5
TAB_LINES = 6


@dataclass(frozen=True)
class StaffChain:
    """One evenly spaced run of horizontal lines (pixel units at ``RENDER_DPI``)."""

    line_count: int
    y_first: float
    spacing: float

    @property
    def kind(self) -> str:
        if self.line_count == NOTATION_LINES:
            return "notation_5_line"
        if self.line_count == TAB_LINES:
            return "tab_6_line"
        return "other_line_count"


def ink_row_profile(page: Any, dpi: float = RENDER_DPI) -> list[float]:
    """Mean ink (0 white .. 1 black) of every pixel row of the page rendered at ``dpi``."""
    import pymupdf as fitz  # type: ignore[import-not-found]

    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    image = Image.frombytes("L", [pix.width, pix.height], pix.samples)
    column = image.resize((1, image.height), Image.BOX).tobytes()
    return [1.0 - value / 255.0 for value in column]


def line_rows(profile: list[float], threshold: float = INK_ROW_THRESHOLD) -> list[float]:
    """Ink-weighted centre row of every run of adjacent rows at or above ``threshold``."""
    centres: list[float] = []
    y, total = 0, len(profile)
    while y < total:
        if profile[y] < threshold:
            y += 1
            continue
        start = y
        while y < total and profile[y] >= threshold:
            y += 1
        weights = profile[start:y]
        centres.append(sum((start + i) * w for i, w in enumerate(weights)) / sum(weights))
    return centres


def staff_chains(ys: list[float], dpi: float = RENDER_DPI) -> list[StaffChain]:
    """Maximal, non-overlapping chains of >=5 evenly spaced lines, longest first then top to bottom."""
    px_per_pt = dpi / 72.0
    min_spacing, max_spacing = MIN_SPACING_PT * px_per_pt, MAX_SPACING_PT * px_per_pt
    total = len(ys)
    candidates: list[list[int]] = []
    for i in range(total):
        for j in range(i + 1, total):
            spacing = ys[j] - ys[i]
            if spacing < min_spacing:
                continue
            if spacing > max_spacing:
                break
            chain = [i, j]
            while True:
                target = ys[chain[-1]] + spacing
                nearby = [k for k in range(chain[-1] + 1, total) if abs(ys[k] - target) <= SPACING_TOLERANCE * spacing]
                if not nearby:
                    break
                chain.append(min(nearby, key=lambda k: abs(ys[k] - target)))
                spacing = (ys[chain[-1]] - ys[chain[0]]) / (len(chain) - 1)
            if len(chain) >= NOTATION_LINES:
                candidates.append(chain)
    candidates.sort(key=lambda c: (-len(c), c[0]))
    used: set[int] = set()
    chosen: list[list[int]] = []
    for chain in candidates:
        if used.intersection(chain):
            continue
        used.update(chain)
        chosen.append(chain)
    chosen.sort(key=lambda c: c[0])
    return [
        StaffChain(len(c), round(ys[c[0]], 1), round((ys[c[-1]] - ys[c[0]]) / (len(c) - 1), 2))
        for c in chosen
    ]


def page_image_facts(page: Any) -> dict[str, Any]:
    """Embedded-image and vector facts of one page: counts and pixel size only."""
    images = page.get_images(full=True)
    facts: dict[str, Any] = {
        "vector_drawings": len(page.get_drawings()),
        "images": len(images),
        "text_words": len(page.get_text("words")),
        "page_width_pt": round(page.rect.width, 1),
        "page_height_pt": round(page.rect.height, 1),
    }
    if images:
        width_px, height_px = int(images[0][2]), int(images[0][3])
        facts["image_width_px"] = width_px
        facts["image_height_px"] = height_px
        facts["image_dpi"] = round(width_px / page.rect.width * 72.0)
    return facts


def measure_staff_location(page: Any) -> dict[str, Any]:
    """The staff-location measurement for one page: chain counts by kind and the line rows behind them."""
    ys = line_rows(ink_row_profile(page))
    chains = staff_chains(ys)
    counts = {"notation_5_line": 0, "tab_6_line": 0, "other_line_count": 0}
    for chain in chains:
        counts[chain.kind] += 1
    return {
        "render_dpi": RENDER_DPI,
        "line_rows": len(ys),
        "chains": [{"lines": c.line_count, "y": c.y_first, "spacing": c.spacing, "kind": c.kind} for c in chains],
        "counts": counts,
        "staves_located": len(chains),
    }


def measure_existing_locator(page: Any, page_index: int) -> dict[str, Any]:
    """What ``build_raster_notation_diagnostics`` (5-line notation, unbroken >35%-width runs) finds today."""
    from score2gp.pdf_raster_staff_diagnostics import build_raster_notation_diagnostics

    result = build_raster_notation_diagnostics(page, page_index)
    staffs = result["staffs"]
    return {
        "staffs": len(staffs),
        "with_opening_symbol_candidate": sum(1 for s in staffs if s["raster_opening_symbol_candidate"]),
        "treble_clef_candidates": sum(
            1 for s in staffs if s["raster_opening_symbol_classification"]["label"] == "treble_clef_candidate"
        ),
    }


def measure_page(page: Any, page_index: int, *, include_existing: bool = True) -> dict[str, Any]:
    """Facts, staff-location measurement and (optionally) the existing locator's result for one page."""
    measured: dict[str, Any] = {"page": page_index, **page_image_facts(page), "location": measure_staff_location(page)}
    if include_existing:
        measured["existing_locator"] = measure_existing_locator(page, page_index)
    return measured


DIGIT_HEIGHT_MIN_SPACINGS = 0.5
DIGIT_HEIGHT_MAX_SPACINGS = 2.0
LINE_ERASE_HALF_WIDTH_PX = 1


def tab_digit_candidates(page: Any, page_index: int, chain: dict[str, Any]) -> dict[str, Any]:
    """Count digit-sized ink components inside one located 6-line chain. Digits are NOT identified.

    Staff-line rows are blanked, then the in-repo connected-component extractor
    (``recognition.raster.extract_raster_glyph_observations``) runs on the band. A component whose height is
    between 0.5 and 2.0 line spacings is a digit-sized candidate; nothing here says which digit it is, whether
    a pair of components is one two-digit fret, or whether a mark is a digit at all.
    """
    from score2gp.recognition.raster import ColorMode, extract_raster_glyph_observations, render_page_deterministic

    px_per_pt = RENDER_DPI / 72.0
    spacing = float(chain["spacing"])
    top_px = float(chain["y"]) - spacing
    bottom_px = float(chain["y"]) + (int(chain["lines"]) - 1) * spacing + spacing
    page_width, page_height = page.rect.width, page.rect.height
    clip = (0.0, max(0.0, top_px / px_per_pt), page_width, min(page_height, bottom_px / px_per_pt))
    samples, provenance = render_page_deterministic(page, dpi=RENDER_DPI, color_mode=ColorMode.GRAY, clip=clip)
    width, height = provenance.pixel_width, provenance.pixel_height
    band = bytearray(samples)
    origin_px = clip[1] * px_per_pt
    for k in range(int(chain["lines"])):
        row = round(float(chain["y"]) + k * spacing - origin_px)
        for r in range(row - LINE_ERASE_HALF_WIDTH_PX, row + LINE_ERASE_HALF_WIDTH_PX + 1):
            if 0 <= r < height:
                band[r * width:(r + 1) * width] = b"\xff" * width
    glyphs = extract_raster_glyph_observations(bytes(band), provenance, page_index)
    digit_sized = [
        g for g in glyphs
        if DIGIT_HEIGHT_MIN_SPACINGS * spacing <= g.pixel_box.height <= DIGIT_HEIGHT_MAX_SPACINGS * spacing
    ]
    return {"components": len(glyphs), "digit_sized_components": len(digit_sized), "digits_identified": 0}
