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


def make_pdf_mixed_prose_tab_numbers() -> None:
    doc, page = _new_page("Mixed Prose and Tab Numbers")
    # Write normal prose text that contains tab-like numbers but has no staff lines
    page.insert_text((72, 100), "Mixed normal prose legend page designed to test non-playable text filtering.", fontsize=10, fontname="helv")
    page.insert_text((72, 120), "Parts 1 and 2 should be repeated 3 to 5 times.", fontsize=10, fontname="helv")
    _save(doc, "generated_pdf_mixed_prose_tab_numbers.pdf")


def make_pdf_text_geometry_present_but_no_safe_system() -> None:
    doc, page = _new_page("Text & Geometry Present but No Safe System")
    # Draw two arbitrary horizontal lines (fewer than 5)
    page.draw_line((72, 120), (332, 120), color=(0, 0, 0), width=0.6)
    page.draw_line((72, 140), (332, 140), color=(0, 0, 0), width=0.6)
    # Draw some text
    page.insert_text((72, 160), "Some text next to some geometry lines.", fontsize=10, fontname="helv")
    _write_fret(page, "3", 120, 120)
    _save(doc, "generated_pdf_text_geometry_present_but_no_safe_system.pdf")


def make_pdf_tab_candidates_present_but_system_not_detected() -> None:
    doc, page = _new_page("Tab Candidates Present but System Not Detected")
    # No lines drawn
    # Insert playable fret candidates
    _write_fret(page, "3", 120, 150)
    _write_fret(page, "5", 150, 150)
    _save(doc, "generated_pdf_tab_candidates_present_but_system_not_detected.pdf")


def make_pdf_tab_staff_lines_fragmented() -> None:
    doc, page = _new_page("Tab Staff Lines Fragmented")
    # Draw 6 short lines (length 40 < 80)
    line_ys = [120, 134, 148, 162, 176, 190]
    for y in line_ys:
        page.draw_line((72, y), (112, y), color=(0, 0, 0), width=0.6)
    # Place fret candidate
    _write_fret(page, "3", 90, line_ys[0])
    _save(doc, "generated_pdf_tab_staff_lines_fragmented.pdf")


def make_pdf_candidates_between_systems() -> None:
    doc, page = _new_page("Candidates Between Systems")
    # System 1
    line_ys1 = [100, 114, 128, 142, 156, 170]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    # System 2
    line_ys2 = [220, 234, 248, 262, 276, 290]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])

    # Place a fret in System 1
    _write_fret(page, "3", 120, line_ys1[0])
    # Place a fret between System 1 and System 2 (Y=195)
    _write_fret(page, "5", 120, 195)
    _save(doc, "generated_pdf_candidates_between_systems.pdf")


def make_pdf_candidates_unassigned_to_string() -> None:
    doc, page = _new_page("Candidates Unassigned to String")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Standard fret
    _write_fret(page, "3", 120, line_ys[0])
    # Fret far from any string line (Y=90, spacing=14, so distance=30)
    _write_fret(page, "4", 150, 90)
    _save(doc, "generated_pdf_candidates_unassigned_to_string.pdf")


def make_pdf_system_order_ambiguous_close() -> None:
    doc, page = _new_page("System Order Ambiguous Close")
    # System 1
    line_ys1 = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys1, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys1, bar_xs=[88, 205, 322])
    # System 2 (Very close to System 1, overlapping vertically)
    line_ys2 = [140, 154, 168, 182, 196, 210]
    _draw_tab_lines(page, line_ys=line_ys2, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys2, bar_xs=[88, 205, 322])

    _write_fret(page, "3", 120, line_ys1[0])
    _write_fret(page, "5", 150, line_ys2[1])
    _save(doc, "generated_pdf_system_order_ambiguous_close.pdf")


def make_ascii_tab_three_blocks_no_bars() -> None:
    doc, page = _new_page("ASCII Tab Three Blocks No Bars")
    ascii_lines_block1 = [
        "e|--0--1--",
        "B|--------",
        "G|--------",
        "D|--------",
        "A|--------",
        "E|--------",
    ]
    ascii_lines_block2 = [
        "e|--2--3--",
        "B|--------",
        "G|--------",
        "D|--------",
        "A|--------",
        "E|--------",
    ]
    ascii_lines_block3 = [
        "e|--4--5--",
        "B|--------",
        "G|--------",
        "D|--------",
        "A|--------",
        "E|--------",
    ]
    for index, line in enumerate(ascii_lines_block1):
        page.insert_text((72, 80 + index * 12), line, fontsize=10, fontname="cour")
    for index, line in enumerate(ascii_lines_block2):
        page.insert_text((72, 160 + index * 12), line, fontsize=10, fontname="cour")
    for index, line in enumerate(ascii_lines_block3):
        page.insert_text((72, 240 + index * 12), line, fontsize=10, fontname="cour")
    _save(doc, "generated_ascii_tab_three_blocks_no_bars.pdf")


def make_pdf_system_detected_no_barlines() -> None:
    doc, page = _new_page("System Detected No Barlines")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _write_fret(page, "3", 120, line_ys[0])
    _write_fret(page, "5", 150, line_ys[1])
    _save(doc, "generated_pdf_system_detected_no_barlines.pdf")


def make_pdf_barlines_do_not_cross_staff() -> None:
    doc, page = _new_page("Barlines Do Not Cross Staff")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Draw vertical lines that are not crossing (height = 50, but starting at 150 to 200, so y_min = 150 > y0 + 4 = 124)
    page.draw_line((88, 150), (88, 200), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 150), (205, 200), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 150), (322, 200), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_do_not_cross_staff.pdf")


def make_pdf_barlines_too_short() -> None:
    doc, page = _new_page("Barlines Too Short")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Draw short vertical lines (height = 20 < 40)
    page.draw_line((88, 130), (88, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 130), (205, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 130), (322, 150), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_too_short.pdf")


def make_pdf_barlines_outside_bounds() -> None:
    doc, page = _new_page("Barlines Outside Bounds")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Draw vertical lines outside bounds (x = 50, x = 350)
    page.draw_line((50, line_ys[0] - 5), (50, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((350, line_ys[0] - 5), (350, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_outside_bounds.pdf")


def make_pdf_barlines_ambiguous() -> None:
    doc, page = _new_page("Barlines Ambiguous")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Draw ambiguous barlines (close together, cluster of 3)
    page.draw_line((88, line_ys[0] - 5), (88, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((90, line_ys[0] - 5), (90, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((92, line_ys[0] - 5), (92, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((205, line_ys[0] - 5), (205, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((207, line_ys[0] - 5), (207, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    page.draw_line((209, line_ys[0] - 5), (209, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_ambiguous.pdf")


def make_pdf_bar_boxes_not_constructible() -> None:
    doc, page = _new_page("Bar Boxes Not Constructible")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Only 1 valid barline
    page.draw_line((88, line_ys[0] - 5), (88, line_ys[-1] + 5), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_bar_boxes_not_constructible.pdf")


def make_pdf_valid_grouped_counterpart() -> None:
    doc, page = _new_page("Valid Grouped Counterpart")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys[0])
    _write_fret(page, "5", 220, line_ys[1])
    _save(doc, "generated_pdf_valid_grouped_counterpart.pdf")


def make_pdf_barlines_below_threshold_crossing_staff() -> None:
    doc, page = _new_page("Barlines Below Threshold Crossing Staff")
    line_ys = [120, 126, 132, 138, 144, 150]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 150), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_below_threshold_crossing_staff.pdf")


def make_pdf_barlines_below_threshold_crossing_partial_staff() -> None:
    doc, page = _new_page("Barlines Below Threshold Crossing Partial Staff")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 145), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 145), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 145), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_below_threshold_crossing_partial_staff.pdf")


def make_pdf_barlines_above_threshold_outside_staff_region() -> None:
    doc, page = _new_page("Barlines Above Threshold Outside Staff Region")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 60), (88, 105), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 60), (205, 105), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 60), (322, 105), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_above_threshold_outside_staff_region.pdf")


def make_pdf_barlines_crossing_top_bottom_missing_middle() -> None:
    doc, page = _new_page("Barlines Crossing Top Bottom Missing Middle")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 130), color=(0, 0, 0), width=0.6)
    page.draw_line((88, 180), (88, 190), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 130), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 180), (205, 190), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 130), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 180), (322, 190), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_crossing_top_bottom_missing_middle.pdf")


def make_pdf_barlines_crossing_all_gaps_short_absolute() -> None:
    doc, page = _new_page("Barlines Crossing All Gaps Short Absolute")
    line_ys = [120, 126, 132, 138, 144, 150]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 150), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_crossing_all_gaps_short_absolute.pdf")


def make_pdf_barlines_crossing_only_some_gaps() -> None:
    doc, page = _new_page("Barlines Crossing Only Some Gaps")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 134), (88, 162), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 134), (205, 162), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 134), (322, 162), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _save(doc, "generated_pdf_barlines_crossing_only_some_gaps.pdf")


def make_pdf_compact_barlines_safe_boxes() -> None:
    doc, page = _new_page("Compact Barlines Safe Boxes")
    line_ys = [120, 126, 132, 138, 144, 150]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 150), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 120, line_ys[0])
    _write_fret(page, "5", 220, line_ys[1])
    _save(doc, "generated_pdf_compact_barlines_safe_boxes.pdf")


def make_pdf_compact_barlines_candidate_outside() -> None:
    doc, page = _new_page("Compact Barlines Candidate Outside")
    line_ys = [120, 126, 132, 138, 144, 150]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    page.draw_line((88, 120), (88, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((205, 120), (205, 150), color=(0, 0, 0), width=0.6)
    page.draw_line((322, 120), (322, 150), color=(0, 0, 0), width=0.6)
    _write_fret(page, "3", 80, line_ys[0])
    _save(doc, "generated_pdf_compact_barlines_candidate_outside.pdf")


def main() -> None:
    make_pdf_candidate_outside_system()
    make_pdf_candidate_outside_bar()
    make_pdf_multi_system_order_ambiguous()
    make_pdf_ascii_and_drawn_layout_conflict()
    make_pdf_prose_legend_text()
    make_pdf_mixed_prose_tab_numbers()
    make_pdf_text_geometry_present_but_no_safe_system()
    make_pdf_tab_candidates_present_but_system_not_detected()
    make_pdf_tab_staff_lines_fragmented()
    make_pdf_candidates_between_systems()
    make_pdf_candidates_unassigned_to_string()
    make_pdf_system_order_ambiguous_close()
    make_ascii_tab_three_blocks_no_bars()
    make_pdf_system_detected_no_barlines()
    make_pdf_barlines_do_not_cross_staff()
    make_pdf_barlines_too_short()
    make_pdf_barlines_outside_bounds()
    make_pdf_barlines_ambiguous()
    make_pdf_bar_boxes_not_constructible()
    make_pdf_valid_grouped_counterpart()
    make_pdf_barlines_below_threshold_crossing_staff()
    make_pdf_barlines_below_threshold_crossing_partial_staff()
    make_pdf_barlines_above_threshold_outside_staff_region()
    make_pdf_barlines_crossing_top_bottom_missing_middle()
    make_pdf_barlines_crossing_all_gaps_short_absolute()
    make_pdf_barlines_crossing_only_some_gaps()
    make_pdf_compact_barlines_safe_boxes()
    make_pdf_compact_barlines_candidate_outside()


if __name__ == "__main__":
    main()
