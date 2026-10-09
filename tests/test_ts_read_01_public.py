"""Public synthetic checks of the time-signature reader (TS-READ-01): supplementary, no acceptance weight.

Rationale: the mounted sources print only 4/4 and 12/8, so the other numerals, common time and cut time can
only be exercised on drawn shapes. Digits are outlines of the PDF library's built-in fonts, converted to filled
vector paths (as the real sources draw theirs) and sized to two staff spaces. Acceptance rests on
``test_ts_read_01_private.py``; these tests only guard the reader's refusals and its shape rules on inputs
the corpus does not contain.
"""

from __future__ import annotations

import re

import pymupdf

TOKEN = re.compile(r"[MLHVCQZ]|-?(?:\d+\.?\d*|\.\d+)")


def _outline(char: str, font: str) -> list[list[tuple[float, float]]]:
    """The glyph's contours as lists of cubic-bezier segments flattened to (cmd, points) tuples."""
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 150), char, fontname=font, fontsize=100)
    svg = page.get_svg_image(text_as_path=True)
    d = re.search(r' d="([^"]+)"', svg).group(1)
    transform = re.search(r"matrix\(([^)]+)\)", svg).group(1).split(",")
    a, _, _, dd, e, f = (float(v) for v in transform)
    tokens = TOKEN.findall(d)
    contours: list[list] = []
    i, cmd, cur = 0, None, (0.0, 0.0)

    def num() -> float:
        nonlocal i
        i += 1
        return float(tokens[i - 1])

    while i < len(tokens):
        if tokens[i] in "MLHVCQZ":
            cmd = tokens[i]
            i += 1
            if cmd == "Z":
                continue
        if cmd == "M":
            cur = (num(), num())
            contours.append([("M", cur)])
            cmd = "L"
        elif cmd == "L":
            cur = (num(), num())
            contours[-1].append(("L", cur))
        elif cmd == "H":
            cur = (num(), cur[1])
            contours[-1].append(("L", cur))
        elif cmd == "V":
            cur = (cur[0], num())
            contours[-1].append(("L", cur))
        elif cmd == "C":
            p1, p2, p3 = (num(), num()), (num(), num()), (num(), num())
            contours[-1].append(("C", (p1, p2, p3)))
            cur = p3
        elif cmd == "Q":
            q, p = (num(), num()), (num(), num())
            c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            contours[-1].append(("C", (c1, c2, p)))
            cur = p
    # to page coordinates of the 100-pt rendering
    def tx(p):
        return (a * p[0] + e, dd * p[1] + f)
    out = []
    for contour in contours:
        row = []
        for kind, data in contour:
            row.append((kind, tuple(tx(q) for q in data) if kind == "C" else tx(data)))
        out.append(row)
    return out


def _glyph_width(char: str, height: float, font: str) -> float:
    pts = [p for c in _outline(char, font) for kind, data in c for p in (data if kind == "C" else (data,))]
    return (max(p[0] for p in pts) - min(p[0] for p in pts)) * height / (max(p[1] for p in pts) - min(p[1] for p in pts))


def draw_glyph(page: pymupdf.Page, char: str, x: float, y_top: float, height: float, font: str = "helv") -> tuple[float, float]:
    """Draw ``char`` as a filled vector path whose box is ``height`` tall with top-left at (x, y_top); return (w, h)."""
    contours = _outline(char, font)
    pts = [p for c in contours for kind, data in c for p in (data if kind == "C" else (data,))]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = height / (y1 - y0)

    def at(p):
        return pymupdf.Point(x + (p[0] - x0) * k, y_top + (p[1] - y0) * k)

    shape = page.new_shape()
    for contour in contours:
        for kind, data in contour:
            if kind == "M":
                cur = at(data)
            elif kind == "L":
                shape.draw_line(cur, at(data))
                cur = at(data)
            else:
                shape.draw_bezier(cur, at(data[0]), at(data[1]), at(data[2]))
                cur = at(data[2])
    shape.finish(fill=(0, 0, 0), color=None, closePath=True, even_odd=True)
    shape.commit()
    return (x1 - x0) * k, height


def draw_staff_header(page: pymupdf.Page, top: float, space: float, left: float = 40.0, right: float = 400.0) -> float:
    """Five staff lines, a tall clef-sized contour, a first notehead; returns the x where the signature belongs."""
    for i in range(5):
        y = top + i * space
        page.draw_line((left, y), (right, y), color=(0, 0, 0), width=0.6)
    clef = page.new_shape()
    cx, cy = left + 0.67 * space + 1.3 * space, top + 2 * space
    clef.draw_oval(pymupdf.Rect(cx - 1.3 * space, cy - 3.5 * space, cx + 1.3 * space, cy + 3.5 * space))
    clef.finish(fill=(0, 0, 0), color=None)
    clef.commit()
    return left + 4.35 * space


def draw_notehead(page: pymupdf.Page, x: float, top: float, space: float) -> None:
    head = page.new_shape()
    head.draw_oval(pymupdf.Rect(x, top + 1.5 * space, x + 1.18 * space, top + 2.5 * space))
    head.finish(fill=(0, 0, 0), color=None)
    head.commit()
    page.draw_line((x + 1.18 * space, top + 2 * space), (x + 1.18 * space, top - 1.0 * space), color=(0, 0, 0), width=0.5)


def build_signature_pdf(path, numerator: str, denominator: str, *, space: float = 5.0, font: str = "helv") -> None:
    """A one-system PDF whose header prints numerator over denominator, then one note."""
    doc = pymupdf.open()
    page = doc.new_page(width=450, height=300)
    top = 100.0
    x = draw_staff_header(page, top, space)
    gap = 0.1 * space
    widths = [sum(_glyph_width(ch, 2 * space, font) + gap for ch in text) - gap if text else 0.0
              for text in (numerator, denominator)]
    for row, text in ((0, numerator), (1, denominator)):
        cursor = x + (max(widths) - widths[row]) / 2  # the narrower number is centred on the wider
        for ch in text:
            w, _ = draw_glyph(page, ch, cursor, top + row * 2 * space, 2 * space, font)
            cursor += w + gap
    draw_notehead(page, x + max(widths) + 5 * space, top, space)
    doc.save(str(path))
    doc.close()


def build_common_pdf(path, *, cut: bool, space: float = 5.0, font: str = "helv") -> None:
    """A one-system PDF whose header prints common time (a C) or cut time (a C with a stroke through it)."""
    doc = pymupdf.open()
    page = doc.new_page(width=450, height=300)
    top = 100.0
    x = draw_staff_header(page, top, space)
    height = 3.0 * space
    w, _ = draw_glyph(page, "C", x, top + 2 * space - height / 2, height, font)
    if cut:
        page.draw_line((x + w / 2, top - 0.8 * space), (x + w / 2, top + 4.8 * space), color=(0, 0, 0), width=0.7)
    draw_notehead(page, x + w + 5 * space, top, space)
    doc.save(str(path))
    doc.close()


# --- tests -----------------------------------------------------------------------------------------------

import pymupdf as _pymupdf  # noqa: E402
import pytest  # noqa: E402

from score2gp.notation_omr.note_duration import _governing_signature, extract_page_symbols, find_staves  # noqa: E402
from score2gp.notation_omr.time_signature import read_system_time_signature  # noqa: E402


def _read(path):
    with _pymupdf.open(str(path)) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        return read_system_time_signature(staves[0], symbols)


@pytest.mark.parametrize("font", ["helv", "cour"])
@pytest.mark.parametrize("numerator,denominator", [("2", "4"), ("3", "4"), ("4", "4"), ("5", "4"),
                                                   ("6", "8"), ("9", "8"), ("12", "8")])
def test_numerals_are_told_apart(tmp_path, font, numerator, denominator):
    path = tmp_path / f"{font}-{numerator}-{denominator}.pdf"
    build_signature_pdf(path, numerator, denominator, font=font)
    result = _read(path)
    assert result["status"] == "read", result
    assert (result["numerator"], result["denominator"]) == (int(numerator), int(denominator))
    assert result["shape"] == "numerals"


@pytest.mark.parametrize("cut,expected", [(False, (4, 4)), (True, (2, 2))])
def test_common_and_cut_time(tmp_path, cut, expected):
    path = tmp_path / f"c-{cut}.pdf"
    build_common_pdf(path, cut=cut)
    result = _read(path)
    assert result["status"] == "read", result
    assert (result["numerator"], result["denominator"]) == expected
    assert result["shape"] == ("cut_time" if cut else "common_time")


def test_a_glyph_that_is_not_unambiguous_is_not_read(tmp_path):
    path = tmp_path / "serif-five.pdf"
    build_signature_pdf(path, "5", "4", font="tiro")  # this serif 5 has no stem the rules can tell from a 3's
    result = _read(path)
    assert result["status"] == "unreadable"
    assert result["reason"] == "numeral_two_three_five_ambiguous"
    assert result["numerator"] is None and result["sources"] and result["location"]["page_index"] == 0


def test_a_numerator_without_a_denominator_is_not_a_signature(tmp_path):
    path = tmp_path / "lone.pdf"
    build_signature_pdf(path, "3", "", font="helv")
    result = _read(path)
    assert result["status"] == "absent" and result["numerator"] is None
    assert result["ignored_sources"]


def test_a_numeral_beyond_the_header_reach_is_not_read(tmp_path):
    doc = _pymupdf.open()
    page = doc.new_page(width=450, height=300)
    space = 5.0
    x = draw_staff_header(page, 100.0, space)
    for row in (0, 1):
        draw_glyph(page, "4", x + 6 * space, 100.0 + row * 2 * space, 2 * space)
    draw_notehead(page, x + 20 * space, 100.0, space)
    path = tmp_path / "far.pdf"
    doc.save(str(path))
    doc.close()
    assert _read(path)["status"] == "absent"


def test_printed_wins_and_a_differing_declared_value_is_a_conflict():
    printed = {"value": (12, 8), "source": "vector_glyphs", "sources": ["a"], "shape": "numerals"}
    declared = {"value": (4, 4), "source": "caller_declared", "sources": []}
    chosen = _governing_signature(printed, "system_start", declared, None)
    assert chosen["value"] == (12, 8) and chosen["basis"] == "printed" and chosen["conflict"] is True
    agreed = _governing_signature(printed, "carried", {**declared, "value": (12, 8)}, None)
    assert agreed["basis"] == "printed" and "conflict" not in agreed and agreed["origin"] == "carried"
    assert _governing_signature(printed, "system_start", None, None)["basis"] == "printed"
    fallback = _governing_signature(None, None, declared, {"reason": "numeral_two_three_five_ambiguous"})
    assert fallback["basis"] == "caller_declared" and fallback["value"] == (4, 4) and fallback["unread"]
    assert _governing_signature(None, None, None, None) is None
