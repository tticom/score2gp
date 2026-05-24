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
    page.insert_text((72, 40), title, fontsize=12, fontname="helv")
    return doc, page


def _save(doc: fitz.Document, name: str) -> None:
    doc.save(OUT_DIR / name, garbage=4, deflate=True)
    doc.close()


def make_pdf_system_overlap_same_column() -> None:
    # Truly ambiguous same-column vertical overlap (refused)
    doc, page = _new_page("Same-Column Vertical Overlap (Refused)")
    
    # System 1: Y range [120, 190] (spacing=14)
    line_ys1 = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    
    # System 2: Y range [162, 232] (28pt vertical overlap / interleaved lines)
    line_ys2 = [162, 176, 190, 204, 218, 232]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    _write_fret(page, "5", 150, line_ys2[3])
    
    _save(doc, "generated_pdf_system_overlap_same_column.pdf")


def make_pdf_system_overlap_ambiguous_bbox() -> None:
    # Ambiguous staff bbox overlap (refused)
    doc, page = _new_page("Ambiguous Staff BBox Overlap (Refused)")
    
    # System 1: Y range [100, 170] (spacing=14)
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    
    # System 2: Y range [186, 256] (16pt gap, but with ambiguous candidate in gap)
    line_ys2 = [186, 200, 214, 228, 242, 256]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    _write_fret(page, "5", 150, line_ys2[1])
    
    # Write a fret candidate right in the middle (Y=178), which is extremely ambiguous
    _write_fret(page, "4", 180, 178)
    
    _save(doc, "generated_pdf_system_overlap_ambiguous_bbox.pdf")


def make_pdf_system_overlap_dense_adjacent() -> None:
    # Dense adjacent systems in the same column (resolved/safe)
    doc, page = _new_page("Dense Adjacent Systems (Safe)")
    
    # System 1: Y range [100, 170] (spacing=14)
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    
    # System 2: Y range [186, 256] (16pt gap, clearly separate lines, no candidate in gap)
    line_ys2 = [186, 200, 214, 228, 242, 256]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    _write_fret(page, "5", 150, line_ys2[1])
    
    _save(doc, "generated_pdf_system_overlap_dense_adjacent.pdf")


def make_pdf_system_overlap_safe_counterpart() -> None:
    # Safe counterpart layout with standard clear spacing
    doc, page = _new_page("Safe Counterpart Layout (Safe)")
    
    # System 1: Y range [100, 170] (spacing=14)
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    
    # System 2: Y range [240, 310] (70pt gap, spacing=14)
    line_ys2 = [240, 254, 268, 282, 296, 310]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    _write_fret(page, "5", 150, line_ys2[1])
    
    _save(doc, "generated_pdf_system_overlap_safe_counterpart.pdf")


def main() -> None:
    make_pdf_system_overlap_same_column()
    make_pdf_system_overlap_ambiguous_bbox()
    make_pdf_system_overlap_dense_adjacent()
    make_pdf_system_overlap_safe_counterpart()


if __name__ == "__main__":
    main()
