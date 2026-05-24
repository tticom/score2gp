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

def make_pdf_edge_candidate_snapping() -> None:
    # Create a PDF with:
    # 1. A chord at x=150 where:
    #    - Fret "5" is at y=148 (String 3, perfectly centered)
    #    - Fret "7" is at y=120 - 7.5 (Marginally outside top string 1, normally outside 6.72 tolerance but inside chord relaxed tolerance)
    # 2. A pickup measure/chord at x=85.0 where:
    #    - Left barline is at x=88.0.
    #    - Fret "3" is at x=85.0 (3.0pt to the left of the left barline, but inside outer snap tolerance)
    doc, page = _new_page("Edge Candidate Snapping")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    
    # 1. Chord cluster snapping
    _write_fret(page, "5", 150, line_ys[2])  # perfectly on string 3
    _write_fret(page, "7", 150, line_ys[0] - 7.5)  # marginally outside top string 1
    
    # 2. Outer barline boundary snapping
    _write_fret(page, "3", 85, line_ys[1])  # 3.0pt to the left of left barline x=88
    
    _save(doc, "generated_pdf_edge_candidate_snapping.pdf")

def main() -> None:
    make_pdf_edge_candidate_snapping()

if __name__ == "__main__":
    main()
