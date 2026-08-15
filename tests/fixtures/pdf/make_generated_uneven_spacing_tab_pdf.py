from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


def _draw_tab_system(page: fitz.Page, *, line_ys: list[float], x0: float, x1: float, bar_xs: list[float]) -> None:
    for y in line_ys:
        page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs:
        page.draw_line((x, line_ys[0]), (x, line_ys[-1]), color=(0, 0, 0), width=0.6)


def _write_fret(page: fitz.Page, text: str, x: float, y: float) -> None:
    page.insert_text((x, y + 3), text, fontsize=10, fontname="cour")


def main() -> None:
    out = Path(__file__).with_name("generated_uneven_spacing_tab.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=360)

    x0 = 72
    x1 = 540
    line_ys = [150, 164, 178, 192, 206, 220]
    bar_xs = [88, 306, 526]

    page.insert_text((72, 72), "Generated Uneven Spacing Tab", fontsize=13, fontname="helv")
    _draw_tab_system(page, line_ys=line_ys, x0=x0, x1=x1, bar_xs=bar_xs)

    page.insert_text((108, 126), "C", fontsize=9, fontname="helv")
    page.insert_text((336, 126), "F", fontsize=9, fontname="helv")
    page.insert_text((172, 138), "PM", fontsize=8, fontname="helv")
    page.insert_text((452, 138), "slide", fontsize=8, fontname="helv")

    # Bar 1 is intentionally regular enough to produce good diagnostics.
    for text, x, y in [
        ("0", 124, line_ys[0]),
        ("1", 124, line_ys[1]),
        ("2", 198, line_ys[2]),
        ("3", 272, line_ys[0]),
    ]:
        _write_fret(page, text, x, y)

    # Bar 2 keeps musical onsets evenly spaced, but two visual groups are
    # deliberately too close for the diagnostic layer to trust.
    for text, x, y in [
        ("5", 338, line_ys[0]),
        ("7", 342, line_ys[1]),
        ("10", 438, line_ys[2]),
        ("12", 504, line_ys[0]),
    ]:
        _write_fret(page, text, x, y)

    doc.save(out, garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    main()
