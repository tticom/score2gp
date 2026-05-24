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


def _write_fret(page: fitz.Page, text: str, x: float, y: float, fontsize: int = 10, fontname: str = "cour") -> None:
    page.insert_text((x, y + 3), text, fontsize=fontsize, fontname=fontname)


def _new_page(title: str) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    page.insert_text((72, 72), title, fontsize=12, fontname="helv")
    return doc, page


def _save(doc: fitz.Document, name: str) -> None:
    doc.save(OUT_DIR / name, garbage=4, deflate=True)
    doc.close()


def make_pdf_fret_clean_single_digit() -> None:
    # 1. Clean single-digit frets on staff.
    doc, page = _new_page("Clean Single Digit Frets")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 100, line_ys[0])
    _write_fret(page, "5", 130, line_ys[1])
    _write_fret(page, "0", 160, line_ys[2])
    _write_fret(page, "2", 220, line_ys[3])
    _write_fret(page, "3", 250, line_ys[4])
    _write_fret(page, "1", 280, line_ys[5])
    _save(doc, "generated_pdf_fret_clean_single_digit.pdf")


def make_pdf_fret_clean_multidigit() -> None:
    # 2. Clean multi-digit frets.
    doc, page = _new_page("Clean Multi-digit Frets")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "10", 100, line_ys[0])
    _write_fret(page, "12", 150, line_ys[2])
    _write_fret(page, "15", 250, line_ys[4])
    _save(doc, "generated_pdf_fret_clean_multidigit.pdf")


def make_pdf_fret_split_span_merged() -> None:
    # 3. Multi-digit fret split into separate text spans but tightly aligned.
    doc, page = _new_page("Split Span Multi-digit Merged")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "1" and "2" extremely close (dx = 9.0 pt)
    _write_fret(page, "1", 100, line_ys[1])
    _write_fret(page, "2", 109, line_ys[1])
    _save(doc, "generated_pdf_fret_split_span_merged.pdf")


def make_pdf_fret_gap_too_large() -> None:
    # 4. Adjacent digits too far apart horizontally.
    doc, page = _new_page("Adjacent Digits Gap Too Large")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "1" and "2" with horizontal gap > 5.0 pt (e.g. 15.0 pt)
    _write_fret(page, "1", 100, line_ys[1])
    _write_fret(page, "2", 115, line_ys[1])
    _save(doc, "generated_pdf_fret_gap_too_large.pdf")


def make_pdf_fret_vertical_misalignment() -> None:
    # 5. Adjacent digits vertically misaligned.
    doc, page = _new_page("Adjacent Digits Vertically Misaligned")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "1" and "2" vertically misaligned (dy = 3.0 pt)
    _write_fret(page, "1", 100, line_ys[1])
    _write_fret(page, "2", 109, line_ys[1] + 3.0)
    _save(doc, "generated_pdf_fret_vertical_misalignment.pdf")


def make_pdf_fret_technique_marker() -> None:
    # 6. Digit near technique marker, e.g. 7h9, 5/7, 8b.
    doc, page = _new_page("Digit near Technique Marker")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "7h9", 100, line_ys[1])
    _write_fret(page, "5/7", 180, line_ys[2])
    _write_fret(page, "8b", 240, line_ys[3])
    _save(doc, "generated_pdf_fret_technique_marker.pdf")


def make_pdf_fret_chord_text_excluded() -> None:
    # 7. Chord symbol or section text containing digits above staff, e.g. A7 or Verse 2.
    doc, page = _new_page("Chord or Section Text Excluded")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "A7", 100, 100, fontsize=10, fontname="helv")
    _write_fret(page, "Verse 2", 180, 100, fontsize=10, fontname="helv")
    _save(doc, "generated_pdf_fret_chord_text_excluded.pdf")


def make_pdf_fret_page_legend_excluded() -> None:
    # 8. Page number / legend number outside tab system.
    doc, page = _new_page("Page or Legend Number Excluded")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "1", 380, 20, fontsize=8, fontname="helv")  # page number top-right
    _write_fret(page, "Legend: 1 = Ring", 72, 280, fontsize=8, fontname="helv")  # legend bottom-left
    _save(doc, "generated_pdf_fret_page_legend_excluded.pdf")


def make_pdf_fret_oversized_tall() -> None:
    # 9. Oversized/tall text that overlaps multiple string bands.
    doc, page = _new_page("Oversized Tall Fret Candidate")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys[2], fontsize=24)  # fontsize=24 is oversized/tall
    _save(doc, "generated_pdf_fret_oversized_tall.pdf")


def make_pdf_fret_tiny_noisy() -> None:
    # 10. Tiny/noisy digit-like text.
    doc, page = _new_page("Tiny Noisy Fret Candidate")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "5", 120, line_ys[2], fontsize=3)  # fontsize=3 is tiny
    _save(doc, "generated_pdf_fret_tiny_noisy.pdf")


def make_pdf_fret_grouped_success() -> None:
    # 11. Valid grouped counterpart where fret refinement, system, bar, and string assignment all succeed.
    doc, page = _new_page("Valid Grouped Fret Refinement")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 100, line_ys[1])
    _write_fret(page, "5", 220, line_ys[2])
    _save(doc, "generated_pdf_fret_grouped_success.pdf")


def make_pdf_fret_touching_digits_safe() -> None:
    # 12. Touching digits safe to merge
    doc, page = _new_page("Touching Digits Safe to Merge")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "1 ", 100, line_ys[1])
    _write_fret(page, "0", 104, line_ys[1])  # dx = 4.0, gap = -2.0 (safe touch/overlap)
    _save(doc, "generated_pdf_fret_touching_digits_safe.pdf")


def make_pdf_fret_overlapping_digits_ambiguous() -> None:
    # 13. Overlapping digits too deep / ambiguous
    doc, page = _new_page("Overlapping Digits Ambiguous")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "1 ", 100, line_ys[1])
    _write_fret(page, "0", 101, line_ys[1])  # dx = 1.0, gap = -5.0 (ambiguous/deep overlap)
    _save(doc, "generated_pdf_fret_overlapping_digits_ambiguous.pdf")


def make_pdf_fret_custom_width_digits() -> None:
    # 14. Custom font digits with unusual width (narrow/wide glyphs, parentheses (5), clean separations)
    doc, page = _new_page("Custom Width Digits and Parentheses")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Safe custom width/size digits
    _write_fret(page, "5", 100, line_ys[1], fontsize=7)  # small but clear
    _write_fret(page, "3", 130, line_ys[2], fontsize=13)  # large but clear
    # Digit adjacent to parentheses/brackets/punctuation (which are tech_chars)
    _write_fret(page, "(5)", 160, line_ys[3])  # parenthesized fret (e.g. ghost note)
    _write_fret(page, "[3]", 220, line_ys[4])  # bracketed fret
    _write_fret(page, "7.", 250, line_ys[5])  # digit with punctuation
    _write_fret(page, "8", 280, line_ys[0])  # clean counterpart
    _write_fret(page, "h", 289, line_ys[0])  # clearly separated technique
    _save(doc, "generated_pdf_fret_custom_width_digits.pdf")


def make_pdf_fret_ligature_overlapping_ambiguous() -> None:
    # 15. Unsafe ligatures, deeply overlapping digit/symbol text
    doc, page = _new_page("Ligature and Overlapping Ambiguous")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Overlapping digit and symbol (drawn separately but overlapping horizontally > 1.5 pt)
    _write_fret(page, "5", 100, line_ys[1])
    _write_fret(page, "h", 101.5, line_ys[1])  # deep overlap: dx = 1.5 pt
    # Unsafe highly-compressed/ligature mixed word (tiny font making the split digit width < 4.0 pt)
    _write_fret(page, "9p", 150, line_ys[2], fontsize=5)
    _save(doc, "generated_pdf_fret_ligature_overlapping_ambiguous.pdf")


def main() -> None:
    make_pdf_fret_clean_single_digit()
    make_pdf_fret_clean_multidigit()
    make_pdf_fret_split_span_merged()
    make_pdf_fret_gap_too_large()
    make_pdf_fret_vertical_misalignment()
    make_pdf_fret_technique_marker()
    make_pdf_fret_chord_text_excluded()
    make_pdf_fret_page_legend_excluded()
    make_pdf_fret_oversized_tall()
    make_pdf_fret_tiny_noisy()
    make_pdf_fret_grouped_success()
    make_pdf_fret_touching_digits_safe()
    make_pdf_fret_overlapping_digits_ambiguous()
    make_pdf_fret_custom_width_digits()
    make_pdf_fret_ligature_overlapping_ambiguous()


if __name__ == "__main__":
    main()
