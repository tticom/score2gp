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


def make_pdf_dense_string_assignment_safe() -> None:
    # Dense string assignment safe counterpart (resolved/safe)
    # Line spacing is 14.0pt, and all fret candidates are shifted vertically by +4.0pt
    doc, page = _new_page("Dense String Assignment Safe (Resolved)")
    
    line_ys = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    
    # Write frets with +4.0pt vertical shift (Y position in insert_text is line_y + 4.0)
    # Note: _write_fret has y + 3 internally, so we pass line_y + 1.0 to get exactly line_y + 4.0
    _write_fret(page, "3", 120, line_ys[0] + 1.0)
    _write_fret(page, "5", 150, line_ys[1] + 1.0)
    _write_fret(page, "7", 180, line_ys[2] + 1.0)
    
    _save(doc, "generated_pdf_dense_string_assignment_safe.pdf")


def make_pdf_dense_string_assignment_ambiguous() -> None:
    # Genuinely ambiguous/equidistant string assignment (refused)
    doc, page = _new_page("Dense String Assignment Ambiguous (Refused)")
    
    line_ys = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    
    # Standard fret on String 1
    _write_fret(page, "3", 120, line_ys[0] - 3.0)
    
    # Fret exactly in the middle between String 1 (100) and String 2 (114)
    # Y = 107.0 (distance 7.0pt from both strings). Since _write_fret adds 3, we pass 104.0.
    _write_fret(page, "5", 150, 104.0)
    
    # Standard fret on String 3
    _write_fret(page, "7", 180, line_ys[2] - 3.0)
    
    _save(doc, "generated_pdf_dense_string_assignment_ambiguous.pdf")


def main() -> None:
    make_pdf_dense_string_assignment_safe()
    make_pdf_dense_string_assignment_ambiguous()


if __name__ == "__main__":
    main()
