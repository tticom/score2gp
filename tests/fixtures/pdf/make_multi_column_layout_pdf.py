from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]

OUT_DIR = Path(__file__).parent


def _draw_tab_lines(page: fitz.Page, *, line_ys: list[float], x0: float, x1: float) -> None:
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


def make_pdf_multi_column_layout() -> None:
    doc, page = _new_page("Multi-Column Layout (Safe)")
    
    # Left Column: x0 = 50, x1 = 190
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=50, x1=190)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[60, 120, 180])
    _write_fret(page, "3", 100, line_ys1[1])
    
    line_ys2 = [190, 204, 218, 232, 246, 260]
    _draw_tab_lines(page, line_ys=line_ys2, x0=50, x1=190)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[60, 120, 180])
    _write_fret(page, "5", 100, line_ys2[1])
    
    # Right Column: x0 = 210, x1 = 350
    # Note: line_ys3 [110, 180] overlaps vertically with line_ys1 [100, 170]
    line_ys3 = [110, 124, 138, 152, 166, 180]
    _draw_tab_lines(page, line_ys=line_ys3, x0=210, x1=350)
    _draw_barlines(page, line_ys=line_ys3, bar_xs=[220, 280, 340])
    _write_fret(page, "2", 260, line_ys3[1])
    
    line_ys4 = [200, 214, 228, 242, 256, 270]
    _draw_tab_lines(page, line_ys=line_ys4, x0=210, x1=350)
    _draw_barlines(page, line_ys=line_ys4, bar_xs=[220, 280, 340])
    _write_fret(page, "7", 260, line_ys4[1])
    
    _save(doc, "generated_pdf_multi_column_layout.pdf")


def main() -> None:
    make_pdf_multi_column_layout()


if __name__ == "__main__":
    main()
