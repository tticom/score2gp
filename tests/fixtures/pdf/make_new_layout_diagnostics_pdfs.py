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


def make_pdf_candidate_outside_system() -> None:
    doc, page = _new_page("Candidate Outside System")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    
    # Standard fret within the system
    _write_fret(page, "3", 120, line_ys[0])
    
    # Outside horizontal bounds (x1 = 332)
    _write_fret(page, "5", 350, line_ys[0])
    
    _save(doc, "generated_pdf_candidate_outside_system.pdf")


def make_pdf_candidate_outside_bar() -> None:
    doc, page = _new_page("Candidate Outside Bar")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    
    # Fret outside measure boundaries (to the left of first barline 88)
    _write_fret(page, "3", 80, line_ys[0])
    
    # Standard fret
    _write_fret(page, "5", 120, line_ys[1])
    
    _save(doc, "generated_pdf_candidate_outside_bar.pdf")


def make_pdf_multi_system_order_ambiguous() -> None:
    doc, page = _new_page("Multi-System Order Ambiguous")
    
    # System 1
    line_ys1 = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    
    # System 2 (Vertically overlapping with System 1)
    line_ys2 = [150, 164, 178, 192, 206, 220]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    
    _write_fret(page, "0", 120, line_ys1[0])
    _write_fret(page, "1", 232, line_ys2[1])
    
    _save(doc, "generated_pdf_multi_system_order_ambiguous.pdf")


def make_pdf_ascii_and_drawn_layout_conflict() -> None:
    doc, page = _new_page("ASCII and Drawn Layout Conflict")
    
    # Drawn System
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "0", 120, line_ys[0])
    
    # ASCII tab block text on the same page
    ascii_lines = [
        "e|--0--1--|",
        "B|--------|",
        "G|--------|",
        "D|--------|",
        "A|--------|",
        "E|--------|",
    ]
    for index, line in enumerate(ascii_lines):
        page.insert_text((72, 220 + index * 12), line, fontsize=10, fontname="cour")
        
    _save(doc, "generated_pdf_ascii_and_drawn_layout_conflict.pdf")


def make_pdf_prose_legend_text() -> None:
    doc, page = _new_page("Prose and Legend Text Only")
    
    # Prose and helper instructions only
    page.insert_text((72, 100), "This is a plain prose legend page designed to test non-playable text filtering.", fontsize=10, fontname="helv")
    page.insert_text((72, 120), "Legend: h = hammer-on, p = pull-off, / = slide, ~ = vibrato", fontsize=9, fontname="helv")
    page.insert_text((72, 140), "No tab staff lines should be detected, and candidates are prose-only.", fontsize=10, fontname="helv")
    
    _save(doc, "generated_pdf_prose_legend_text.pdf")


def main() -> None:
    make_pdf_candidate_outside_system()
    make_pdf_candidate_outside_bar()
    make_pdf_multi_system_order_ambiguous()
    make_pdf_ascii_and_drawn_layout_conflict()
    make_pdf_prose_legend_text()


if __name__ == "__main__":
    main()
