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


def make_pdf_string_assignment_valid() -> None:
    # 1. Valid six-line tab staff with single-digit fret numbers centered on each string.
    doc, page = _new_page("Valid String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 100, line_ys[0])
    _write_fret(page, "5", 130, line_ys[1])
    _write_fret(page, "0", 160, line_ys[2])
    _write_fret(page, "2", 220, line_ys[3])
    _write_fret(page, "3", 250, line_ys[4])
    _write_fret(page, "1", 280, line_ys[5])
    _save(doc, "generated_pdf_string_assignment_valid.pdf")


def make_pdf_string_assignment_multidigit() -> None:
    # 2. Valid staff with multi-digit fret numbers.
    doc, page = _new_page("Multi-digit String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "10", 100, line_ys[0])
    _write_fret(page, "12", 150, line_ys[2])
    _write_fret(page, "15", 250, line_ys[4])
    _save(doc, "generated_pdf_string_assignment_multidigit.pdf")


def make_pdf_string_assignment_offset_tolerant() -> None:
    # 3. Candidate slightly above/below a string line but inside tolerance.
    doc, page = _new_page("Offset Tolerant String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys[1] + 3.0)  # +3.0 is within 5.32 tolerance
    _save(doc, "generated_pdf_string_assignment_offset_tolerant.pdf")


def make_pdf_string_assignment_between_lines() -> None:
    # 4. Candidate exactly between two string lines.
    doc, page = _new_page("Between Lines String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, (line_ys[0] + line_ys[1]) / 2)  # exactly between
    _save(doc, "generated_pdf_string_assignment_between_lines.pdf")


def make_pdf_string_assignment_outside_staff() -> None:
    # 5. Candidate outside the top/bottom staff region.
    doc, page = _new_page("Outside Staff String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys[0] - 10.0)  # above top
    _write_fret(page, "5", 240, line_ys[5] + 10.0)  # below bottom
    _save(doc, "generated_pdf_string_assignment_outside_staff.pdf")


def make_pdf_string_assignment_compact_staff() -> None:
    # 6. Compact staff where vertical bands overlap.
    doc, page = _new_page("Compact Staff String Assignment")
    line_ys = [120, 126, 132, 138, 144, 150]  # line spacing = 6.0 < 8.0
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 120, line_ys[1])
    _save(doc, "generated_pdf_string_assignment_compact_staff.pdf")


def make_pdf_string_assignment_techniques() -> None:
    # 7. Technique markers near strings such as h, p, /, \, b, r, ~.
    doc, page = _new_page("Technique Markers near Strings")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 100, line_ys[1])
    _write_fret(page, "h", 115, line_ys[1])  # 'h' technique marker
    _write_fret(page, "5", 140, line_ys[1])
    _write_fret(page, "p", 155, line_ys[1])  # 'p' technique marker
    _write_fret(page, "/", 195, line_ys[2])  # '/' technique marker
    _save(doc, "generated_pdf_string_assignment_techniques.pdf")


def make_pdf_string_assignment_chords() -> None:
    # 8. Chord symbols or text above the staff.
    doc, page = _new_page("Chords above Staff")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    page.insert_text((100, 80), "C", fontsize=10, fontname="helv")  # C chord symbol well above
    page.insert_text((220, 80), "G", fontsize=10, fontname="helv")  # G chord symbol well above
    _save(doc, "generated_pdf_string_assignment_chords.pdf")


def make_pdf_string_assignment_grouped_success() -> None:
    # 9. Valid grouped page where system, bar, and string assignment all succeed.
    doc, page = _new_page("Grouped Success String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[88, 205, 322])
    _write_fret(page, "3", 100, line_ys[1])
    _write_fret(page, "5", 220, line_ys[2])
    _save(doc, "generated_pdf_string_assignment_grouped_success.pdf")


def make_pdf_string_assignment_upstream_blocked() -> None:
    # 10. Fixture where string assignment succeeds but edge-boundary/bar-box failure remains.
    doc, page = _new_page("Upstream Blocked String Assignment")
    line_ys = [120, 134, 148, 162, 176, 190]
    _draw_tab_lines(page, line_ys=line_ys, x0=72, x1=332)
    # Exactly one accepted barline at x=180, and one rejected at x=220 (produces upstream boundary blocker)
    _draw_barlines(page, line_ys=line_ys, bar_xs=[180])
    page.draw_line((220, 120), (220, 138), color=(0, 0, 0), width=0.6)  # rejected barline
    _write_fret(page, "3", 100, line_ys[1])
    _write_fret(page, "5", 240, line_ys[2])
    _save(doc, "generated_pdf_string_assignment_upstream_blocked.pdf")


def main() -> None:
    make_pdf_string_assignment_valid()
    make_pdf_string_assignment_multidigit()
    make_pdf_string_assignment_offset_tolerant()
    make_pdf_string_assignment_between_lines()
    make_pdf_string_assignment_outside_staff()
    make_pdf_string_assignment_compact_staff()
    make_pdf_string_assignment_techniques()
    make_pdf_string_assignment_chords()
    make_pdf_string_assignment_grouped_success()
    make_pdf_string_assignment_upstream_blocked()


if __name__ == "__main__":
    main()
