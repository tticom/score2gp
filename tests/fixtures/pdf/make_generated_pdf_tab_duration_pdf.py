from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]

# Oracle definition mapping rhythmic sections/bars to expected duration structures
EXPECTED_DURATION_ORACLE = {
    "bar_1": [
        {"fret": "0", "duration": "quarter", "stem": True, "beam_count": 0, "flag_count": 0},
        {"fret": "0", "duration": "quarter", "stem": True, "beam_count": 0, "flag_count": 0},
        {"fret": "0", "duration": "quarter", "stem": True, "beam_count": 0, "flag_count": 0},
        {"fret": "0", "duration": "quarter", "stem": True, "beam_count": 0, "flag_count": 0},
    ],
    "bar_2": [
        # Flagged eighth notes
        {"fret": "2", "duration": "eighth", "stem": True, "beam_count": 0, "flag_count": 1},
        {"fret": "3", "duration": "eighth", "stem": True, "beam_count": 0, "flag_count": 1},
        # Beamed eighth notes (single beam)
        {"fret": "4", "duration": "eighth", "stem": True, "beam_count": 1, "flag_count": 0},
        {"fret": "5", "duration": "eighth", "stem": True, "beam_count": 1, "flag_count": 0},
        # Beamed sixteenth notes (double beam)
        {"fret": "7", "duration": "sixteenth", "stem": True, "beam_count": 2, "flag_count": 0},
        {"fret": "7", "duration": "sixteenth", "stem": True, "beam_count": 2, "flag_count": 0},
        {"fret": "7", "duration": "sixteenth", "stem": True, "beam_count": 2, "flag_count": 0},
        {"fret": "7", "duration": "sixteenth", "stem": True, "beam_count": 2, "flag_count": 0},
    ],
}


def _draw_tab_system(page: fitz.Page, *, line_ys: list[float], x0: float, x1: float, bar_xs: list[float]) -> None:
    for y in line_ys:
        page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs:
        page.draw_line((x, line_ys[0]), (x, line_ys[-1]), color=(0, 0, 0), width=0.6)


def _write_fret(page: fitz.Page, text: str, x: float, y: float) -> None:
    page.insert_text((x, y + 3), text, fontsize=10, fontname="cour")


def _draw_stem(page: fitz.Page, x: float, top_y: float, bottom_y: float) -> None:
    page.draw_line((x, top_y), (x, bottom_y), color=(0, 0, 0), width=1.0)


def _draw_beam(page: fitz.Page, x0: float, x1: float, y: float) -> None:
    page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=3.0)


def _draw_flag(page: fitz.Page, stem_x: float, stem_y: float) -> None:
    # Simple diagonal flag line attached to stem end
    page.draw_line((stem_x, stem_y), (stem_x + 8, stem_y + 12), color=(0, 0, 0), width=1.0)


def generate_pdf_tab_duration_fixture(out_path: Path | None = None) -> Path:
    out = out_path if out_path is not None else Path(__file__).with_name("generated_pdf_tab_duration.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=360)

    x0 = 72
    x1 = 540
    line_ys = [150, 164, 178, 192, 206, 220]
    bar_xs = [88, 306, 526]

    page.insert_text((72, 72), "Generated PDF Tab Duration", fontsize=13, fontname="helv")
    _draw_tab_system(page, line_ys=line_ys, x0=x0, x1=x1, bar_xs=bar_xs)

    # Bar 1: Four quarter notes with vertical stems
    for x in [110, 150, 190, 230]:
        _write_fret(page, "0", x, line_ys[0])
        stem_top_y = line_ys[-1]
        stem_bottom_y = stem_top_y + 18
        _draw_stem(page, x + 3, stem_top_y, stem_bottom_y)

    # Bar 2: Flagged eighth notes, beamed eighth notes, beamed sixteenth notes
    stem_top_y = line_ys[-1]
    stem_bottom_y = stem_top_y + 18

    # Eighth notes (flagged)
    x = 330
    _write_fret(page, "2", x, line_ys[1])
    _draw_stem(page, x + 3, stem_top_y, stem_bottom_y)
    _draw_flag(page, x + 3, stem_bottom_y)

    x = 370
    _write_fret(page, "3", x, line_ys[2])
    _draw_stem(page, x + 3, stem_top_y, stem_bottom_y)
    _draw_flag(page, x + 3, stem_bottom_y)

    # Two Eighth notes (beamed)
    x2, x3 = 410, 450
    _write_fret(page, "4", x2, line_ys[3])
    _write_fret(page, "5", x3, line_ys[4])
    _draw_stem(page, x2 + 3, stem_top_y, stem_bottom_y)
    _draw_stem(page, x3 + 3, stem_top_y, stem_bottom_y)
    _draw_beam(page, x2 + 3, x3 + 3, stem_bottom_y)

    # Four Sixteenth notes (beamed with double beam)
    x_coords = [470, 485, 500, 515]
    for x_i in x_coords:
        _write_fret(page, "7", x_i, line_ys[5])
        _draw_stem(page, x_i + 3, stem_top_y, stem_bottom_y)
    _draw_beam(page, x_coords[0] + 3, x_coords[-1] + 3, stem_bottom_y)
    _draw_beam(page, x_coords[0] + 3, x_coords[-1] + 3, stem_bottom_y - 4)

    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return out


if __name__ == "__main__":
    generate_pdf_tab_duration_fixture()
