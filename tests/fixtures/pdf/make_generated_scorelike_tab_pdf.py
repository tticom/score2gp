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
    out = Path(__file__).with_name("generated_scorelike_tab.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    x0 = 72
    x1 = 540
    bar_xs = [88, 306, 526]
    system_1 = [170, 184, 198, 212, 226, 240]
    system_2 = [390, 404, 418, 432, 446, 460]

    page.insert_text((72, 72), "Generated Scorelike Tab", fontsize=13, fontname="helv")

    _draw_tab_system(page, line_ys=system_1, x0=x0, x1=x1, bar_xs=bar_xs)
    page.insert_text((104, 146), "Am", fontsize=9, fontname="helv")
    page.insert_text((335, 146), "G", fontsize=9, fontname="helv")
    page.insert_text((184, 158), "h", fontsize=8, fontname="helv")
    page.insert_text((250, 160), "cue", fontsize=8, fontname="helv")
    page.insert_text((455, 158), "slide", fontsize=8, fontname="helv")
    for text, x, y in [
        ("0", 124, system_1[0]),
        ("1", 124, system_1[1]),
        ("2", 188, system_1[2]),
        ("3", 344, system_1[0]),
        ("5", 405, system_1[1]),
        ("10", 472, system_1[0]),
    ]:
        _write_fret(page, text, x, y)

    _draw_tab_system(page, line_ys=system_2, x0=x0, x1=x1, bar_xs=bar_xs)
    page.insert_text((104, 366), "D7", fontsize=9, fontname="helv")
    page.insert_text((335, 366), "Am", fontsize=9, fontname="helv")
    page.insert_text((217, 378), "PM", fontsize=8, fontname="helv")
    page.insert_text((250, 380), "note", fontsize=8, fontname="helv")
    page.insert_text((430, 378), "let ring", fontsize=8, fontname="helv")
    for text, x, y in [
        ("2", 134, system_2[3]),
        ("0", 220, system_2[2]),
        ("3", 360, system_2[1]),
        ("4", 360, system_2[2]),
        ("12", 440, system_2[0]),
    ]:
        _write_fret(page, text, x, y)

    doc.save(out, garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    main()
