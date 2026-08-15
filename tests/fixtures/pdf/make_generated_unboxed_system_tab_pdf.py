from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


OUT_DIR = Path(__file__).parent


def _draw_tab_lines(page: fitz.Page, *, line_ys: list[float], x0: float = 72, x1: float = 332) -> None:
    for y in line_ys:
        page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=0.6)


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


def make_pdf_unboxed_system() -> None:
    # Simulates a system with staff lines but exactly zero barlines, containing playable candidates
    doc, page = _new_page("Unboxed System Recovery")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Write some fret candidates
    _write_fret(page, "3", 120, line_ys[0])
    _write_fret(page, "5", 240, line_ys[1])
    _save(doc, "generated_unboxed_system_tab.pdf")


def main() -> None:
    make_pdf_unboxed_system()


if __name__ == "__main__":
    main()
