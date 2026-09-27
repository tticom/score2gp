#!/usr/bin/env python
"""Generate the public DUR-01 synthetic notation PDFs under tests/fixtures/pdf/dur_01/.

Each fixture is one system (a five-line notation staff above a six-line TAB staff) drawn in the
vector vocabulary of the Guitar Pro exports in the private corpus: filled four-curve noteheads,
even-odd hollow noteheads, stroked stems, filled straight-edged beam quadrilaterals, curved flag
blades, round dots, block, zigzag and hooked rests, italic tuplet digits between bracket strokes,
and crescent ties. Spacing is deliberately uniform, so it carries no rhythm.

Usage::

    python scripts/dur_01_make_fixtures.py [--out tests/fixtures/pdf/dur_01]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pymupdf

S = 4.25  # staff space, points (as in the corpus)
HEAD_W, HEAD_H = 5.02, 4.25
STEM_W = 0.51
BARLINE_W = 0.68
STAFF_LINE_W = 0.55
KAPPA = 0.5523
PAGE_W, PAGE_H = 612.0, 220.0
STAFF_TOP = 70.0
STAFF_X0, STAFF_X1 = 36.0, 576.0
TAB_TOP = STAFF_TOP + 4 * S + 30.0
TAB_GAP = 6.8
EVENT_STEP = 20.0  # uniform spacing: never a source of duration

BASE_FLAGS = {"whole": 0, "half": 0, "quarter": 0, "eighth": 1, "16th": 2, "32nd": 3, "64th": 4}


def line_y(index: int) -> float:
    return STAFF_TOP + index * S


def pos_y(pos: int) -> float:
    """Staff position in half spaces from the top line (0 = top line, 8 = bottom line)."""
    return STAFF_TOP + pos * S / 2


def _signed_area(points: list[tuple[float, float]]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2


def _polygon(shape: pymupdf.Shape, points: list[tuple[float, float]], clockwise: bool = True) -> None:
    if (_signed_area(points) > 0) != clockwise:
        points = list(reversed(points))
    for a, b in zip(points, points[1:]):
        shape.draw_line(a, b)
    shape.draw_line(points[-1], points[0])


def _ellipse(shape: pymupdf.Shape, cx: float, cy: float, rx: float, ry: float, angle: float = 0.0,
             reverse: bool = False) -> None:
    """A closed ellipse of four cubic Beziers, optionally rotated and traversed backwards."""
    ca, sa = math.cos(angle), math.sin(angle)

    def pt(x: float, y: float) -> pymupdf.Point:
        return pymupdf.Point(cx + x * ca - y * sa, cy + x * sa + y * ca)

    quads = [
        ((rx, 0), (rx, KAPPA * ry), (KAPPA * rx, ry), (0, ry)),
        ((0, ry), (-KAPPA * rx, ry), (-rx, KAPPA * ry), (-rx, 0)),
        ((-rx, 0), (-rx, -KAPPA * ry), (-KAPPA * rx, -ry), (0, -ry)),
        ((0, -ry), (KAPPA * rx, -ry), (rx, -KAPPA * ry), (rx, 0)),
    ]
    if reverse:
        quads = [(q[3], q[2], q[1], q[0]) for q in reversed(quads)]
    for p0, c1, c2, p3 in quads:
        shape.draw_bezier(pt(*p0), pt(*c1), pt(*c2), pt(*p3))


class Score:
    """Draws one system: the notation staff, a TAB staff, and the symbols placed on them."""

    def __init__(self, page: pymupdf.Page) -> None:
        self.page = page

    def fill(self, draw, even_odd: bool = False) -> None:
        shape = self.page.new_shape()
        draw(shape)
        shape.finish(fill=(0, 0, 0), color=None, even_odd=even_odd, closePath=True)
        shape.commit()

    def stroke(self, draw, width: float) -> None:
        shape = self.page.new_shape()
        draw(shape)
        shape.finish(color=(0, 0, 0), fill=None, width=width, closePath=False)
        shape.commit()

    # --- staff furniture -------------------------------------------------------------------
    def staves(self, barlines: list[float]) -> None:
        cuts = [STAFF_X0, *barlines, STAFF_X1]

        def lines(shape: pymupdf.Shape) -> None:
            # Split per bar, as the corpus does: one stroked path of many line items.
            for i in range(5):
                for a, b in zip(cuts, cuts[1:]):
                    shape.draw_line((a, line_y(i)), (b, line_y(i)))
            for i in range(6):
                for a, b in zip(cuts, cuts[1:]):
                    shape.draw_line((a, TAB_TOP + i * TAB_GAP), (b, TAB_TOP + i * TAB_GAP))

        self.stroke(lines, STAFF_LINE_W)
        for x in [*barlines, STAFF_X1]:
            self.page.draw_rect(pymupdf.Rect(x - BARLINE_W / 2, line_y(0), x + BARLINE_W / 2, line_y(4)),
                                color=None, fill=(0, 0, 0), width=0)
            self.page.draw_rect(pymupdf.Rect(x - BARLINE_W / 2, TAB_TOP, x + BARLINE_W / 2, TAB_TOP + 5 * TAB_GAP),
                                color=None, fill=(0, 0, 0), width=0)

    def clef_and_time(self, numerator: int, denominator: int) -> float:
        """A treble-clef stand-in (a large curved blob) and a text time signature. Returns content x."""
        self.fill(lambda sh: _ellipse(sh, STAFF_X0 + 9, line_y(2), 4.5, 3.4 * S))
        self.page.insert_text((STAFF_X0 + 18, line_y(2) - 1.2), str(numerator), fontname="hebo", fontsize=12)
        self.page.insert_text((STAFF_X0 + 18, line_y(4) - 1.2), str(denominator), fontname="hebo", fontsize=12)
        return STAFF_X0 + 40

    def bar_number(self, x: float, number: int) -> None:
        self.page.insert_text((x + 1.0, line_y(0) - 3.0), str(number), fontname="tiro", fontsize=6)

    # --- note parts ------------------------------------------------------------------------
    def head(self, cx: float, pos: int, hollow: bool = False) -> None:
        cy = pos_y(pos)

        def draw(sh: pymupdf.Shape) -> None:
            _ellipse(sh, cx, cy, HEAD_W / 2, HEAD_H / 2, angle=-0.35)
            if hollow:
                _ellipse(sh, cx, cy, HEAD_W * 0.30, HEAD_H * 0.22, angle=-0.6, reverse=True)

        self.fill(draw, even_odd=hollow)

    def whole_head(self, cx: float, pos: int) -> None:
        cy = pos_y(pos)

        def draw(sh: pymupdf.Shape) -> None:
            _ellipse(sh, cx, cy, 7.18 / 2, HEAD_H / 2)
            _ellipse(sh, cx, cy, 1.6, 1.3, angle=0.9, reverse=True)

        self.fill(draw, even_odd=True)

    def stem_x(self, cx: float, up: bool) -> float:
        return cx + HEAD_W / 2 - STEM_W / 2 if up else cx - HEAD_W / 2 + STEM_W / 2

    def stem(self, cx: float, pos: int, up: bool, tip: float) -> float:
        x = self.stem_x(cx, up)
        start = pos_y(pos) + (-0.15 if up else 0.15) * S
        self.stroke(lambda sh: sh.draw_line((x, start), (x, tip)), STEM_W)
        return x

    def flags(self, x: float, tip: float, up: bool, count: int, one_path: bool = True,
              segment_rich: bool = False) -> None:
        """``count`` flag blades at the stem tip. ``one_path`` draws them as one glyph (a combined
        sixteenth or thirty-second flag); otherwise each blade is its own drawing."""
        d = 1 if up else -1
        x0 = x - STEM_W / 2

        def blade(sh: pymupdf.Shape, k: int) -> None:
            y0 = tip + d * k * 0.9 * S
            p0 = (x0, y0)
            if segment_rich:
                outer = [_bezier_point((x0, y0), (x0 + 0.2 * S, y0 + d * 1.0 * S), (x0 + 1.5 * S, y0 + d * 1.3 * S),
                                       (x0 + 1.1 * S, y0 + d * 2.9 * S), t / 12) for t in range(13)]
                inner = [_bezier_point((x0 + 1.1 * S, y0 + d * 2.9 * S), (x0 + 1.2 * S, y0 + d * 1.8 * S),
                                       (x0 + 0.3 * S, y0 + d * 1.3 * S), (x0, y0 + d * 0.6 * S), t / 12)
                         for t in range(1, 13)]
                _polygon(sh, outer + inner)
                return
            sh.draw_bezier(p0, (x0 + 0.2 * S, y0 + d * 1.0 * S), (x0 + 1.5 * S, y0 + d * 1.3 * S),
                           (x0 + 1.1 * S, y0 + d * 2.9 * S))
            sh.draw_bezier((x0 + 1.1 * S, y0 + d * 2.9 * S), (x0 + 1.2 * S, y0 + d * 1.8 * S),
                           (x0 + 0.3 * S, y0 + d * 1.3 * S), (x0, y0 + d * 0.6 * S))
            sh.draw_line((x0, y0 + d * 0.6 * S), p0)

        if one_path:
            self.fill(lambda sh: [blade(sh, k) for k in range(count)])
        else:
            for k in range(count):
                self.fill(lambda sh, k=k: blade(sh, k))

    def dots(self, cx: float, pos: int, count: int, width: float = HEAD_W) -> None:
        cy = pos_y(pos) if pos % 2 else pos_y(pos) - S / 2
        for i in range(count):
            dx = cx + width / 2 + 0.55 * S + i * 0.6 * S
            self.fill(lambda sh, dx=dx: _ellipse(sh, dx, cy, 0.2 * S, 0.2 * S))

    def beam(self, x_a: float, y_a: float, x_b: float, y_b: float, up: bool) -> None:
        """A beam band between two stem positions, extending inward from the tip line."""
        t = 0.5 * S * (1 if up else -1)
        self.fill(lambda sh: _polygon(sh, [(x_a, y_a), (x_b, y_b), (x_b, y_b + t), (x_a, y_a + t)]))

    # --- rests -----------------------------------------------------------------------------
    def block_rest(self, cx: float, whole: bool) -> None:
        if whole:
            rect = pymupdf.Rect(cx - 0.6 * S, line_y(1), cx + 0.6 * S, line_y(1) + 0.5 * S)
        else:
            rect = pymupdf.Rect(cx - 0.6 * S, line_y(2) - 0.5 * S, cx + 0.6 * S, line_y(2))
        self.page.draw_rect(rect, color=None, fill=(0, 0, 0), width=0)

    def quarter_rest(self, cx: float, width_scale: float = 1.0) -> None:
        """A zigzag whose centreline is a function of height: one fill run on every horizontal scan.

        ``width_scale`` below 1 condenses it into a form the reader does not recognise as a rest.
        """
        top = line_y(0) + 0.5 * S
        knots = [(0.0, -0.25), (0.9, 0.35), (1.6, -0.3), (2.3, 0.3), (2.7, -0.15), (3.0, 0.1)]

        def centre(y: float) -> float:
            for (ya, xa), (yb, xb) in zip(knots, knots[1:]):
                if ya <= y <= yb:
                    t = (y - ya) / (yb - ya)
                    return xa + (xb - xa) * (0.5 - 0.5 * math.cos(math.pi * t))
            return knots[-1][1]

        ys = [i * 3.0 / 30 for i in range(31)]
        left = [(cx + (centre(y) - 0.2) * width_scale * S, top + y * S) for y in ys]
        right = [(cx + (centre(y) + 0.2) * width_scale * S, top + y * S) for y in reversed(ys)]
        self.fill(lambda sh: _polygon(sh, left + right))

    def hooked_rest(self, cx: float, hooks: int) -> None:
        """An eighth-to-sixty-fourth rest: a slanted straight stem with ``hooks`` ball hooks."""
        top = line_y(1) - (hooks - 1) * 0.5 * S
        bottom = top + (hooks + 1.2) * S
        slope = 0.35  # stem x advance per unit of height, towards the top right

        def sx(y: float) -> float:
            return cx + 0.4 * S - (y - top) * slope

        def draw(sh: pymupdf.Shape) -> None:
            _polygon(sh, [(sx(top), top), (sx(top) + 0.2 * S, top), (sx(bottom) + 0.2 * S, bottom), (sx(bottom), bottom)])
            for k in range(hooks):
                # As engraved: the ball hangs below the arm's outer end; the arm runs over the ball's
                # top into the stem.
                hy = top + k * S
                bx, by = sx(hy) - 0.75 * S, hy + 0.3 * S
                _ellipse(sh, bx, by, 0.27 * S, 0.27 * S)
                _polygon(sh, [(bx - 0.05 * S, by - 0.27 * S), (sx(hy) + 0.1 * S, hy - 0.05 * S),
                              (sx(hy + 0.1 * S) + 0.1 * S, hy + 0.1 * S), (bx + 0.1 * S, by - 0.12 * S)])

        self.fill(draw)

    def final_barline(self) -> None:
        """A thin barline and a thick one closing the staff: the thick one is a filled glyph."""
        thick = 0.5 * S
        self.page.draw_rect(pymupdf.Rect(STAFF_X1 - thick, line_y(0), STAFF_X1, line_y(4)), color=None,
                            fill=(0, 0, 0), width=0)
        x = STAFF_X1 - thick - 3.0
        self.page.draw_rect(pymupdf.Rect(x - BARLINE_W / 2, line_y(0), x + BARLINE_W / 2, line_y(4)), color=None,
                            fill=(0, 0, 0), width=0)

    # --- grouping --------------------------------------------------------------------------
    def tuplet(self, x0: float, x1: float, y: float, number: int, above: bool = True) -> None:
        mid = (x0 + x1) / 2
        hook = 0.5 * S if above else -0.5 * S
        self.page.insert_text((mid - 2.2, y + 3.2), str(number), fontname="tiit", fontsize=9)
        self.stroke(lambda sh: (sh.draw_line((x0, y + hook), (x0, y)), sh.draw_line((x0, y), (mid - 3.5, y))), 0.68)
        self.stroke(lambda sh: (sh.draw_line((mid + 3.5, y), (x1, y)), sh.draw_line((x1, y), (x1, y + hook))), 0.68)

    def tie(self, x_a: float, x_b: float, pos: int, below: bool = True) -> None:
        y = pos_y(pos) + (0.9 if below else -0.9) * S
        d = 1 if below else -1

        def draw(sh: pymupdf.Shape) -> None:
            sh.draw_bezier((x_a, y), (x_a + 3, y + d * 0.9 * S), (x_b - 3, y + d * 0.9 * S), (x_b, y))
            sh.draw_bezier((x_b, y), (x_b - 3, y + d * 0.6 * S), (x_a + 3, y + d * 0.6 * S), (x_a, y))

        self.fill(draw)


def _bezier_point(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


# --- engraving of events --------------------------------------------------------------------

def note(score: Score, cx: float, pos: int, value: str, dots: int = 0, up: bool | None = None,
         flag_mode: str = "one_path") -> dict:
    """A single unbeamed note: head, stem, flags, dots. Returns its geometry for ties."""
    up = pos >= 4 if up is None else up
    if value == "whole":
        score.whole_head(cx, pos)
        score.dots(cx, pos, dots, width=7.18)
        return {"cx": cx, "pos": pos}
    score.head(cx, pos, hollow=value == "half")
    flags = BASE_FLAGS[value]
    length = 3.5 * S + max(0, flags - 1) * 0.9 * S
    tip = pos_y(pos) + (-length if up else length)
    x = score.stem(cx, pos, up, tip)
    if flags:
        score.flags(x, tip, up, flags, one_path=flag_mode != "separate", segment_rich=flag_mode == "segment_rich")
    score.dots(cx, pos, dots)
    return {"cx": cx, "pos": pos}


def beamed(score: Score, notes: list[tuple[float, int, int, int]], up: bool) -> None:
    """A beam group. ``notes`` holds (cx, pos, beam_lines, dots) per note, left to right.

    Beam lines at each stem come from its own value: sub-runs of neighbours sharing a level get a
    full beam; a lone note at a level gets a partial stub towards its neighbour.
    """
    xs = [score.stem_x(cx, up) for cx, _, _, _ in notes]
    far = min(pos_y(p) for _, p, _, _ in notes) if up else max(pos_y(p) for _, p, _, _ in notes)
    tip0 = far + (-3.5 * S if up else 3.5 * S)
    slope = -0.08 if up else 0.08

    def tip(x: float) -> float:
        return tip0 + slope * (x - xs[0])

    for (cx, pos, _, dots), x in zip(notes, xs):
        score.head(cx, pos)
        score.stem(cx, pos, up, tip(x))
        score.dots(cx, pos, dots)
    inward = 1 if up else -1
    levels = max(n[2] for n in notes)
    for level in range(levels):
        offset = inward * level * 0.75 * S
        members = [i for i, n in enumerate(notes) if n[2] > level]
        runs: list[list[int]] = []
        for i in members:
            if runs and runs[-1][-1] == i - 1:
                runs[-1].append(i)
            else:
                runs.append([i])
        for run in runs:
            if len(run) > 1:
                a, b = xs[run[0]] - STEM_W / 2, xs[run[-1]] + STEM_W / 2
            else:
                i = run[0]
                if i == len(notes) - 1:  # the last note's stub points back into the group
                    a, b = xs[i] - 0.9 * S, xs[i] + STEM_W / 2
                else:
                    a, b = xs[i] - STEM_W / 2, xs[i] + 0.9 * S
            score.beam(a, tip(a) + offset, b, tip(b) + offset, up)


def new_score(doc: pymupdf.Document, barlines: list[float], numerator: int, denominator: int) -> tuple[Score, float]:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    score = Score(page)
    score.staves(barlines)
    start = score.clef_and_time(numerator, denominator)
    return score, start


# --- fixtures -------------------------------------------------------------------------------

def half_and_32nds(doc: pymupdf.Document) -> None:
    """3/4: a half note and eight beamed thirty-second notes (the maintainer's example)."""
    score, x = new_score(doc, [], 3, 4)
    score.bar_number(x - 4, 1)
    note(score, x + 4, 6, "half")
    xs = [x + 4 + EVENT_STEP * (i + 1) for i in range(8)]
    beamed(score, [(cx, p, 3, 0) for cx, p in zip(xs, [7, 6, 5, 4, 5, 6, 7, 6])], up=True)


def dotted(doc: pymupdf.Document) -> None:
    """4/4, three bars: dotted and double-dotted notes, with flags drawn three different ways."""
    bar2, bar3 = 250.0, 420.0
    score, x = new_score(doc, [bar2, bar3], 4, 4)
    score.bar_number(x - 4, 1)
    note(score, x + 4, 5, "half", dots=1)
    note(score, x + 4 + EVENT_STEP, 3, "quarter")
    score.bar_number(bar2, 2)
    note(score, bar2 + 12, 4, "half", dots=2)
    note(score, bar2 + 12 + EVENT_STEP, 5, "eighth", flag_mode="segment_rich")
    score.bar_number(bar3, 3)
    note(score, bar3 + 12, 6, "quarter", dots=2)
    note(score, bar3 + 12 + EVENT_STEP, 7, "16th", flag_mode="separate")
    note(score, bar3 + 12 + 2 * EVENT_STEP, 2, "quarter", dots=1)
    note(score, bar3 + 12 + 3 * EVENT_STEP, 3, "eighth")


def mixed_beams(doc: pymupdf.Document) -> None:
    """4/4: an eighth beamed to two sixteenths, partial beams both ways, four sixteenths."""
    score, x = new_score(doc, [], 4, 4)
    score.bar_number(x - 4, 1)
    step = EVENT_STEP
    beamed(score, [(x + 4, 6, 1, 0), (x + 4 + step, 5, 2, 0), (x + 4 + 2 * step, 4, 2, 0)], up=True)
    b = x + 4 + 3 * step + 6
    beamed(score, [(b, 3, 1, 1), (b + step, 2, 2, 0)], up=False)
    c = b + 2 * step + 6
    beamed(score, [(c, 6, 2, 0), (c + step, 5, 1, 1)], up=True)
    d = c + 2 * step + 6
    beamed(score, [(d + i * step, p, 2, 0) for i, p in enumerate([4, 5, 6, 7])], up=True)


def triplet(doc: pymupdf.Document) -> None:
    """4/4: a bracketed eighth-note triplet, a bracketed quarter-note triplet, a quarter note."""
    score, x = new_score(doc, [], 4, 4)
    score.bar_number(x - 4, 1)
    step = EVENT_STEP
    xs = [x + 4 + i * step for i in range(3)]
    beamed(score, [(cx, p, 1, 0) for cx, p in zip(xs, [6, 5, 4])], up=True)
    score.tuplet(xs[0] - HEAD_W / 2, xs[-1] + HEAD_W / 2, line_y(0) - 5.2 * S, 3)
    ys = [xs[-1] + step + 6 + i * step for i in range(3)]
    for cx, p in zip(ys, [2, 3, 2]):
        note(score, cx, p, "quarter")
    score.tuplet(ys[0] - HEAD_W / 2, ys[-1] + HEAD_W / 2, line_y(4) + 5.0 * S, 3, above=False)
    note(score, ys[-1] + step + 6, 5, "quarter")


def rests(doc: pymupdf.Document) -> None:
    """4/4, two bars: a whole rest; then half to sixty-fourth rests and a sixty-fourth note."""
    bar2 = 170.0
    score, x = new_score(doc, [bar2], 4, 4)
    score.bar_number(x - 4, 1)
    score.block_rest((x + bar2) / 2, whole=True)
    score.bar_number(bar2, 2)
    cx = bar2 + 14
    score.block_rest(cx, whole=False)
    score.quarter_rest(cx + EVENT_STEP)
    for i, hooks in enumerate((1, 2, 3, 4)):
        score.hooked_rest(cx + (2 + i) * EVENT_STEP, hooks)
    note(score, cx + 6 * EVENT_STEP, 3, "64th")


def tie_across_barline(doc: pymupdf.Document) -> None:
    """4/4, two bars: half, quarter, quarter tied across the barline to a quarter, dotted half."""
    bar2 = 200.0
    score, x = new_score(doc, [bar2], 4, 4)
    score.bar_number(x - 4, 1)
    note(score, x + 4, 5, "half")
    note(score, x + 4 + EVENT_STEP, 5, "quarter")
    last = note(score, x + 4 + 2 * EVENT_STEP, 6, "quarter")
    score.bar_number(bar2, 2)
    first = note(score, bar2 + 14, 6, "quarter")
    note(score, bar2 + 14 + EVENT_STEP, 4, "half", dots=1)
    score.tie(last["cx"] + HEAD_W / 2 + 0.3, first["cx"] - HEAD_W / 2 - 0.3, 6)


def ambiguous(doc: pymupdf.Document) -> None:
    """4/4: symbols that must be recorded unread, never guessed.

    A filled notehead with no stem; a stem carrying both a flag and a beam; a tuplet digit with no
    bracket and no beam group beneath it; then two readable quarter notes.
    """
    score, x = new_score(doc, [], 4, 4)
    score.bar_number(x - 4, 1)
    score.head(x + 4, 5)
    a, b = x + 4 + EVENT_STEP, x + 4 + 2 * EVENT_STEP
    beamed(score, [(a, 6, 1, 0), (b, 6, 1, 0)], up=True)
    xa = score.stem_x(a, True)
    score.flags(xa, pos_y(6) - 3.5 * S, True, 1)
    c = x + 4 + 3 * EVENT_STEP
    note(score, c, 5, "quarter", up=False)
    score.page.insert_text((c - 2.2, line_y(0) - 3.2 * S), "3", fontname="tiit", fontsize=9)
    note(score, c + EVENT_STEP, 5, "quarter")


def unrecognised_rest(doc: pymupdf.Document) -> None:
    """4/4, two bars, closed by a thin-thick final barline: rests that must never vanish silently.

    Bar 1: a quarter note, a quarter rest condensed into a form the reader does not recognise, two
    quarter notes. Bar 2: an eighth rest printed over a whole note (a second voice's rest).
    """
    bar2 = 200.0
    score, x = new_score(doc, [bar2], 4, 4)
    score.bar_number(x - 4, 1)
    note(score, x + 4, 5, "quarter")
    score.quarter_rest(x + 4 + EVENT_STEP, width_scale=0.4)
    note(score, x + 4 + 2 * EVENT_STEP, 5, "quarter")
    note(score, x + 4 + 3 * EVENT_STEP, 5, "quarter")
    score.bar_number(bar2, 2)
    note(score, bar2 + 14, 6, "whole")
    score.hooked_rest(bar2 + 16, 1)
    score.final_barline()


FIXTURES = {
    "half_and_32nds": half_and_32nds,
    "dotted": dotted,
    "mixed_beams": mixed_beams,
    "triplet": triplet,
    "rests": rests,
    "tie_across_barline": tie_across_barline,
    "ambiguous": ambiguous,
    "unrecognised_rest": unrecognised_rest,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures/pdf/dur_01"))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, build in FIXTURES.items():
        doc = pymupdf.open()
        build(doc)
        doc.set_metadata({"title": f"DUR-01 synthetic fixture: {name}", "creator": "scripts/dur_01_make_fixtures.py",
                          "producer": "PyMuPDF", "creationDate": "", "modDate": ""})
        doc.save(args.out / f"{name}.pdf", garbage=4, deflate=True, no_new_id=True)
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
