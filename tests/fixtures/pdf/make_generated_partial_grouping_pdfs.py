from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


OUT_DIR = Path(__file__).parent


def _draw_tab_lines(page: fitz.Page, *, line_ys: list[float], x0: float = 72, x1: float = 332) -> None:
    for y in line_ys:
        page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=0.6)


def _draw_barlines(page: fitz.Page, *, line_ys: list[float], bar_xs: list[float]) -> None:
    for x in bar_xs:
        page.draw_line((x, line_ys[0]), (x, line_ys[-1]), color=(0, 0, 0), width=0.6)


def _write_fret(page: fitz.Page, text: str, x: float, y: float) -> None:
    page.insert_text((x, y + 3), text, fontsize=10, fontname="cour")


def _new_page(title: str) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    page.insert_text((72, 72), title, fontsize=12, fontname="helv")
    return doc, page


def _save(doc: fitz.Document, name: str) -> None:
    doc.save(OUT_DIR / name, garbage=4, deflate=True)
    doc.close()


def make_missing_barlines() -> None:
    doc, page = _new_page("Generated Partial Missing Barlines")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    page.insert_text((100, 102), "A", fontsize=9, fontname="helv")
    page.insert_text((250, 102), "PM", fontsize=8, fontname="helv")
    for text, x, y in [
        ("0", 118, line_ys[0]),
        ("2", 168, line_ys[1]),
        ("4", 220, line_ys[2]),
        ("7", 282, line_ys[3]),
    ]:
        _write_fret(page, text, x, y)
    _save(doc, "generated_partial_missing_barlines_tab.pdf")


def make_incomplete_staff() -> None:
    doc, page = _new_page("Generated Partial Incomplete Staff")
    line_ys = [120, 134, 148, 162, 176]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    page.insert_text((100, 102), "C", fontsize=9, fontname="helv")
    for text, x, y in [
        ("1", 118, line_ys[0]),
        ("3", 166, line_ys[1]),
        ("5", 232, line_ys[2]),
        ("8", 286, line_ys[3]),
    ]:
        _write_fret(page, text, x, y)
    _save(doc, "generated_partial_incomplete_staff_tab.pdf")


def make_ambiguous_string() -> None:
    doc, page = _new_page("Generated Partial Ambiguous String")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    page.insert_text((100, 102), "D", fontsize=9, fontname="helv")
    midpoint = (line_ys[0] + line_ys[1]) / 2
    for text, x, y in [
        ("0", 118, line_ys[0]),
        ("6", 166, midpoint),
        ("2", 232, line_ys[2]),
        ("4", 286, line_ys[3]),
    ]:
        _write_fret(page, text, x, y)
    _save(doc, "generated_partial_ambiguous_string_tab.pdf")


def make_ambiguous_bar() -> None:
    doc, page = _new_page("Generated Partial Ambiguous Bar")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    page.insert_text((100, 102), "E", fontsize=9, fontname="helv")
    for text, x, y in [
        ("0", 118, line_ys[0]),
        ("2", 201, line_ys[1]),
        ("5", 232, line_ys[2]),
        ("7", 286, line_ys[3]),
    ]:
        _write_fret(page, text, x, y)
    _save(doc, "generated_partial_ambiguous_bar_tab.pdf")


def main() -> None:
    make_missing_barlines()
    make_incomplete_staff()
    make_ambiguous_string()
    make_ambiguous_bar()


if __name__ == "__main__":
    main()
