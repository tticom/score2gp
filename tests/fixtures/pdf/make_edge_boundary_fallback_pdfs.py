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


def make_pdf_edge_left_fallback() -> None:
    # 1. Edge system with one accepted right boundary and clear left system edge (safe left fallback)
    doc, page = _new_page("Edge Left Fallback")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Exactly one accepted barline at x=180
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    # Playable candidate to the left of 180 (needs left fallback at 72)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_edge_left_fallback.pdf")


def make_pdf_edge_right_fallback() -> None:
    # 2. Edge system with one accepted left boundary and clear right system edge (safe right fallback)
    doc, page = _new_page("Edge Right Fallback")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Exactly one accepted barline at x=180
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    # Playable candidate to the right of 180 (needs right fallback at 332)
    _write_fret(page, "5", 240, line_ys[1])
    _save(doc, "generated_pdf_edge_right_fallback.pdf")


def make_pdf_edge_ambiguous_fallback() -> None:
    # 3. Edge system with one accepted boundary but ambiguous system edge (rejected boundary)
    doc, page = _new_page("Edge Ambiguous Fallback")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Exactly one accepted barline at x=180
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    # One short/rejected barline to the right at x=220
    page.draw_line((220, 120), (220, 138), color=(0, 0, 0), width=0.6)
    # Playable candidate to the right of 180
    _write_fret(page, "5", 240, line_ys[1])
    _save(doc, "generated_pdf_edge_ambiguous_fallback.pdf")


def make_pdf_edge_too_narrow_fallback() -> None:
    # 4. Edge system with inferred boundary producing too-narrow box (< 30pt)
    doc, page = _new_page("Edge Too Narrow Fallback")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Accepted barline at x=90 (left edge is 72, so distance 18 < 30)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[90])
    # Playable candidate to the left of 90
    _write_fret(page, "3", 80, line_ys[0])
    _save(doc, "generated_pdf_edge_too_narrow_fallback.pdf")


def make_pdf_edge_candidate_near_inferred() -> None:
    # 5. Edge system with candidate near inferred boundary (distance < ambiguous_bar_tolerance)
    doc, page = _new_page("Edge Candidate Near Inferred")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Accepted barline at x=180
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    # Playable candidate at x=75 (left edge is 72, so distance is 3 < ~6.3)
    _write_fret(page, "3", 75, line_ys[0])
    _save(doc, "generated_pdf_edge_candidate_near_inferred.pdf")


def make_pdf_non_edge_internal_missing() -> None:
    # 6. Non-edge internal missing boundary (does not use fallback since len(barlines) == 2, but has candidate inside single wide box)
    doc, page = _new_page("Non-Edge Internal Missing")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Two valid barlines at 88 and 322 (the outer ones)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 322])
    # Fret candidate in the middle
    _write_fret(page, "3", 200, line_ys[0])
    _save(doc, "generated_pdf_non_edge_internal_missing.pdf")


def make_pdf_multi_system_safe_fallback() -> None:
    # 7. Multi-system page where one edge system uses safe inferred boundary and all playable candidates assign
    doc, page = _new_page("Multi-System Safe Fallback")
    
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])
    _write_fret(page, "5", 220, line_ys1[1])

    # System 2
    line_ys2 = [220, 234, 248, 262, 276, 290]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    # 1 valid barline at 180
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[180])
    _write_fret(page, "7", 120, line_ys2[0])
    
    _save(doc, "generated_pdf_multi_system_safe_fallback.pdf")


def make_pdf_multi_system_partial_fallback() -> None:
    # 8. Multi-system page where inferred boundary still leaves candidates unassigned (partial grouping)
    doc, page = _new_page("Multi-System Partial Fallback")
    
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])

    # System 2
    line_ys2 = [220, 234, 248, 262, 276, 290]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    # 1 valid barline at 180
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[180])
    # Candidate near inferred boundary
    _write_fret(page, "7", 75, line_ys2[0])
    
    _save(doc, "generated_pdf_multi_system_partial_fallback.pdf")


def make_pdf_next_blocker_string_assignment() -> None:
    # 9. Fixture that moves next blocker to string assignment
    doc, page = _new_page("Next Blocker String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Fret candidate with y value far from any string line but inside candidate zone (y=90)
    _write_fret(page, "3", 120, 90)
    _save(doc, "generated_pdf_next_blocker_string_assignment.pdf")


def make_pdf_empty_system_policy_fallback() -> None:
    # 10. Empty system / decorative system handling with safe edge fallback
    doc, page = _new_page("Empty System Policy Fallback")
    
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys1[0])

    # System 2 - Empty
    line_ys2 = [180, 194, 208, 222, 236, 250]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)

    # System 3 - 1 valid barline
    line_ys3 = [260, 274, 288, 302, 316, 330]
    _draw_tab_lines(page, line_ys=line_ys3, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys3, bar_xs=[180])
    _write_fret(page, "5", 240, line_ys3[1])

    _save(doc, "generated_pdf_empty_system_policy_fallback.pdf")


def main() -> None:
    make_pdf_edge_left_fallback()
    make_pdf_edge_right_fallback()
    make_pdf_edge_ambiguous_fallback()
    make_pdf_edge_too_narrow_fallback()
    make_pdf_edge_candidate_near_inferred()
    make_pdf_non_edge_internal_missing()
    make_pdf_multi_system_safe_fallback()
    make_pdf_multi_system_partial_fallback()
    make_pdf_next_blocker_string_assignment()
    make_pdf_empty_system_policy_fallback()


if __name__ == "__main__":
    main()
