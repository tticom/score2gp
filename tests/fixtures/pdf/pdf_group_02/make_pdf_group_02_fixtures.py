"""Generate the synthetic PDF-GROUP-02 fixtures (no private content).

Each page holds one notation staff (5 lines, 6.44 pt space) above one TAB staff (6 lines,
9.66 pt spacing) 37 pt below it, so only the top TAB line has a spanning neighbour within 45 pt.
TAB string lines are drawn in pieces broken by a 7.3 pt gap (0.76 of the string spacing) wherever
a fret digit sits. Only pieces of at least 75 pt reach the merge, so a string that continues as
digit-broken short pieces shows only its first piece.

* ``full_chord_gap.pdf``      - two six-string chord columns break every TAB line at the same x.
                                Strings 3 and 4 continue only as short pieces; string 6 has an
                                earlier digit. Barlines are TAB-height filled rectangles and the
                                left stroke joins both staves.
* ``wide_gap_two_staves.pdf`` - all six lines end at one x and resume 60 pt later, with no notation
                                staff above: two separate staves on one line, which must not join.

Run: ``python make_pdf_group_02_fixtures.py``.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

HERE = Path(__file__).parent
NOTATION_SPACE = 6.44
TAB_SPACE = 9.66
LEFT, RIGHT = 40.0, 820.0
BARS = (LEFT, 300.0, 500.0, RIGHT)


def _hline(page: pymupdf.Page, y: float, x0: float, x1: float) -> None:
    page.draw_line((x0, y), (x1, y), width=0.28)


def _build(name: str, rows: list[list[tuple[float, float]]], digit_xs: list[float], notation: bool) -> None:
    """Draw a notation staff, a TAB staff whose string ``rows`` are given as drawn pieces, the bars."""
    doc = pymupdf.open()
    page = doc.new_page(width=880, height=400)
    notation_ys = [110.0 + i * NOTATION_SPACE for i in range(5)]
    tab_ys = [notation_ys[-1] + 37.0 + i * TAB_SPACE for i in range(6)]
    for y in notation_ys if notation else []:
        _hline(page, y, LEFT, RIGHT)
    for y, spans in zip(tab_ys, rows):
        for x0, x1 in spans:
            _hline(page, y, x0, x1)
    # joint left stroke over both staves, then TAB-height barlines drawn as thin filled rectangles
    page.draw_line((LEFT, notation_ys[0] if notation else tab_ys[0]), (LEFT, tab_ys[-1]), width=1.0)
    for bar_x in BARS[1:]:
        page.draw_rect(pymupdf.Rect(bar_x - 0.4, tab_ys[0], bar_x + 0.4, tab_ys[-1]), color=None, fill=(0, 0, 0))
    for x in digit_xs:
        for string_index, y in enumerate(tab_ys):
            page.insert_text((x, y + 3.0), str(string_index + 1), fontsize=8)
    doc.save(HERE / name)
    doc.close()


def main() -> None:
    gap = 7.3
    # Chord columns end at 150 and 420; every other break is a single-string digit.
    c1, c2 = 150.0, 420.0
    top = [(LEFT, c1), (c1 + gap, c2), (c2 + gap, RIGHT)]
    strings_3_4 = [(LEFT, c1), (c1 + gap, c1 + 60.0), (c1 + 60.0 + gap, 300.0), (700.0, RIGHT)]
    string_2 = [(LEFT, c1), (c1 + gap, 240.0), (360.0, 450.0), (500.0, 650.0), (700.0, RIGHT)]
    string_5 = [(LEFT, c1), (c1 + gap, 300.0), (365.0, 500.0), (560.0, 700.0), (740.0, RIGHT)]
    string_6 = [(LEFT, c1 - 20.0), (c1 + gap, 300.0), (365.0, 500.0), (500.0, 700.0), (700.0, RIGHT)]
    rows = [top, string_2, strings_3_4, strings_3_4, string_5, string_6]
    _build("full_chord_gap.pdf", rows, digit_xs=[c1 + 1.5, c2 + 1.5], notation=True)
    apart = [(LEFT, 340.0), (400.0, RIGHT)]
    _build("wide_gap_two_staves.pdf", [apart] * 6, digit_xs=[], notation=False)


if __name__ == "__main__":
    main()
