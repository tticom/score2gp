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


def _write_text(page: fitz.Page, text: str, x: float, y: float, fontsize: int = 10, fontname: str = "cour") -> None:
    page.insert_text((x, y + 3), text, fontsize=fontsize, fontname=fontname)


def _new_page(title: str) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    page.insert_text((72, 72), title, fontsize=12, fontname="helv")
    return doc, page


def _save(doc: fitz.Document, name: str) -> None:
    doc.save(OUT_DIR / name, garbage=4, deflate=True)
    doc.close()


def make_pdf_tuning_standard_text() -> None:
    # 1. Standard tuning text above first system.
    doc, page = _new_page("Standard Tuning Text Above")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "Standard tuning" above staff
    _write_text(page, "Standard tuning", 72, 95, fontsize=9, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_standard_text.pdf")


def make_pdf_tuning_explicit_eadgbe() -> None:
    # 2. Explicit EADGBE string labels at left of staff.
    doc, page = _new_page("Explicit EADGBE Tuning Labels")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write E, B, G, D, A, E vertically at the left
    _write_text(page, "E", 50, line_ys[0], fontsize=8, fontname="helv")
    _write_text(page, "B", 50, line_ys[1], fontsize=8, fontname="helv")
    _write_text(page, "G", 50, line_ys[2], fontsize=8, fontname="helv")
    _write_text(page, "D", 50, line_ys[3], fontsize=8, fontname="helv")
    _write_text(page, "A", 50, line_ys[4], fontsize=8, fontname="helv")
    _write_text(page, "E", 50, line_ys[5], fontsize=8, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_explicit_eadgbe.pdf")


def make_pdf_tuning_alternate_dadgad() -> None:
    # 3. Alternate DADGAD string labels at left of staff.
    doc, page = _new_page("Alternate DADGAD Tuning Labels")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write D, A, D, G, A, D vertically at the left
    _write_text(page, "D", 50, line_ys[0], fontsize=8, fontname="helv")
    _write_text(page, "A", 50, line_ys[1], fontsize=8, fontname="helv")
    _write_text(page, "D", 50, line_ys[2], fontsize=8, fontname="helv")
    _write_text(page, "G", 50, line_ys[3], fontsize=8, fontname="helv")
    _write_text(page, "A", 50, line_ys[4], fontsize=8, fontname="helv")
    _write_text(page, "D", 50, line_ys[5], fontsize=8, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_alternate_dadgad.pdf")


def make_pdf_tuning_label_outside() -> None:
    # 4. Tuning labels outside system bounds.
    doc, page = _new_page("Tuning Label Outside System")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "Standard tuning" far away from staff (top right)
    _write_text(page, "Standard tuning", 300, 20, fontsize=8, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_label_outside.pdf")


def make_pdf_tuning_conflict() -> None:
    # 5. Ambiguous duplicate/conflicting tuning labels.
    doc, page = _new_page("Conflicting Tuning Labels")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "Standard tuning" and "Drop D tuning"
    _write_text(page, "Standard tuning", 72, 90, fontsize=8, fontname="helv")
    _write_text(page, "Drop D tuning", 180, 90, fontsize=8, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_conflict.pdf")


def make_pdf_tuning_malformed() -> None:
    # 6. Malformed tuning text.
    doc, page = _new_page("Malformed Tuning Text")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write a malformed text standardish / unsupported
    _write_text(page, "Tuning: Standardish", 72, 90, fontsize=8, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_malformed.pdf")


def make_pdf_tuning_chord_resembling() -> None:
    # 7. Chord symbols that look like pitch labels above staff.
    doc, page = _new_page("Chord Symbol Resembling Pitch")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write chord symbol "E" above staff (not to the left)
    _write_text(page, "E", 100, 95, fontsize=10, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_chord_resembling.pdf")


def make_pdf_tuning_section_note_names() -> None:
    # 8. Section text containing note names.
    doc, page = _new_page("Section Text with Note Names")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "Verse in E" above staff
    _write_text(page, "Verse in E", 72, 90, fontsize=10, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_section_note_names.pdf")


def make_pdf_tuning_valid_grouping() -> None:
    # 9. Valid system/bar/string/fret grouping with tuning evidence present.
    doc, page = _new_page("Valid Grouped and Tuning Evidence")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write "Standard tuning" above staff
    _write_text(page, "Standard tuning", 72, 90, fontsize=9, fontname="helv")
    # Clean playable frets
    _write_text(page, "3", 100, line_ys[1])
    _write_text(page, "5", 220, line_ys[2])
    _save(doc, "generated_pdf_tuning_valid_grouping.pdf")


def make_pdf_tuning_timing_unimplemented() -> None:
    # 10. Public fixture proving timing mapping remains not implemented.
    doc, page = _new_page("Timing Mapping Not Implemented")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    # Write standard tuning text
    _write_text(page, "Standard tuning", 72, 90, fontsize=9, fontname="helv")
    _write_text(page, "3", 100, line_ys[1])
    _save(doc, "generated_pdf_tuning_timing_unimplemented.pdf")


def main() -> None:
    make_pdf_tuning_standard_text()
    make_pdf_tuning_explicit_eadgbe()
    make_pdf_tuning_alternate_dadgad()
    make_pdf_tuning_label_outside()
    make_pdf_tuning_conflict()
    make_pdf_tuning_malformed()
    make_pdf_tuning_chord_resembling()
    make_pdf_tuning_section_note_names()
    make_pdf_tuning_valid_grouping()
    make_pdf_tuning_timing_unimplemented()


if __name__ == "__main__":
    main()
