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


def make_pdf_one_bar_box() -> None:
    # 1. Valid system with two accepted barlines producing exactly one safe bar box
    doc, page = _new_page("One Bar Box")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Exactly two barlines (height = 70pt >= 40pt)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[120, 280])
    _write_fret(page, "3", 150, line_ys[0])
    _save(doc, "generated_pdf_one_bar_box.pdf")


def make_pdf_one_accepted_barline() -> None:
    # 2. Valid system with only one accepted barline
    doc, page = _new_page("One Accepted Barline")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Only one valid barline
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_one_accepted_barline.pdf")


def make_pdf_bar_box_too_narrow() -> None:
    # 3. Accepted barlines too close together (< 30pt)
    doc, page = _new_page("Bar Box Too Narrow")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Two barlines 15pt apart (less than 30pt)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[120, 135, 280])
    _write_fret(page, "3", 180, line_ys[0])
    _save(doc, "generated_pdf_bar_box_too_narrow.pdf")


def make_pdf_bar_boxes_overlapping() -> None:
    # 4. Accepted barlines forming overlapping boxes
    doc, page = _new_page("Bar Boxes Overlapping")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Instead of drawing standard vertical lines, we draw them such that barlines list will be unsorted,
    # but wait, since fitz extracts barlines and we sort them, how can we test the overlap check?
    # We can write an explicit unit test on _TabSystem directly where barlines are unsorted, 
    # but we can also draw barlines in a way that triggers it. 
    # Wait, in the generator, we can draw a normal layout, and in the test, we'll verify both the PDF and 
    # the direct _TabSystem property behavior.
    _draw_barlines(page, line_ys=line_ys, bar_xs=[120, 200, 280])
    _write_fret(page, "3", 150, line_ys[0])
    _save(doc, "generated_pdf_bar_boxes_overlapping.pdf")


def make_pdf_bar_box_outside_system() -> None:
    # 5. Accepted barlines outside system horizontal bounds (system ends at x1 = 332)
    doc, page = _new_page("Bar Box Outside System")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # A barline drawn at x = 338 (accepted by detection since <= x1 + 8.0, but outside box bounds > x1 + 2.0)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[120, 338])
    _write_fret(page, "3", 150, line_ys[0])
    _save(doc, "generated_pdf_bar_box_outside_system.pdf")


def make_pdf_candidate_left_of_boxes() -> None:
    # 6. Candidate inside system but left of first bar box
    doc, page = _new_page("Candidate Left of Boxes")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[150, 280])
    # Fret at x=100 (left of first barline x=150, but inside system bounds [72, 332])
    _write_fret(page, "3", 100, line_ys[0])
    _write_fret(page, "5", 200, line_ys[1])
    _save(doc, "generated_pdf_candidate_left_of_boxes.pdf")


def make_pdf_candidate_on_boundary() -> None:
    # 7. Candidate exactly or nearly on a bar boundary
    doc, page = _new_page("Candidate On Boundary")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Fret exactly at x=205 (on the middle barline)
    _write_fret(page, "3", 205, line_ys[0])
    _save(doc, "generated_pdf_candidate_on_boundary.pdf")


def make_pdf_multi_system_one_failed() -> None:
    # 8. Multi-system page where System 1 has valid boxes and System 2 lacks boxes
    doc, page = _new_page("Multi-System One Failed")
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])

    # System 2
    line_ys2 = [220, 234, 248, 262, 276, 290]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    # Lacks barlines or has only 1 barline
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[180])
    _write_fret(page, "5", 240, line_ys2[1])
    _save(doc, "generated_pdf_multi_system_one_failed.pdf")


def make_pdf_multi_system_all_valid() -> None:
    # 9. Multi-system page where all systems have safe boxes and candidates assign cleanly
    doc, page = _new_page("Multi-System All Valid")
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    _write_fret(page, "5", 220, line_ys1[1])

    # System 2
    line_ys2 = [220, 234, 248, 262, 276, 290]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])
    _write_fret(page, "7", 120, line_ys2[0])
    _write_fret(page, "9", 220, line_ys2[1])
    _save(doc, "generated_pdf_multi_system_all_valid.pdf")


def main() -> None:
    make_pdf_one_bar_box()
    make_pdf_one_accepted_barline()
    make_pdf_bar_box_too_narrow()
    make_pdf_bar_boxes_overlapping()
    make_pdf_bar_box_outside_system()
    make_pdf_candidate_left_of_boxes()
    make_pdf_candidate_on_boundary()
    make_pdf_multi_system_one_failed()
    make_pdf_multi_system_all_valid()


if __name__ == "__main__":
    main()
