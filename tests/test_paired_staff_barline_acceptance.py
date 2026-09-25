"""L3-01: paired-staff barline acceptance.

A notation-staff (partner) vertical is inherited as a system barline only when it is not a note
stem. A stem is recognised by a notehead-sized filled shape attached to one of its ends (H2).
H1, requiring a TAB-staff stroke at the same x, is refuted by
tests/test_barline_recovery.py::test_notation_to_tab_barline_inheritance, whose genuine barlines
cross only the notation staff.

Synthetic pages exercise the detector's geometry. The real-source tests run production code on
the original Lesson 3 PDF and assert only counts, never private coordinates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import pytest

import score2gp.pdf as pdf
from score2gp.pdf import _detect_tab_systems


class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class MockPage:
    def __init__(self, drawings: list[dict[str, Any]]):
        self.drawings = drawings
        self.rect = type("MockRect", (object,), {"width": 600.0, "height": 800.0})()

    def get_drawings(self) -> list[dict[str, Any]]:
        return self.drawings

    def get_text(self, kind: str) -> list[Any] | str:
        return [] if kind == "words" else ""


def line(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    return {"items": [("l", MockPoint(x0, y0), MockPoint(x1, y1))]}


def filled(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    # A filled notehead is an oval: a closed path of four Bezier curves, as PyMuPDF reports it.
    cx, cy, rx, ry, k = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 0.5523
    P = MockPoint
    items = [
        ("c", P(x0, cy), P(x0, cy + k * ry), P(cx - k * rx, y1), P(cx, y1)),
        ("c", P(cx, y1), P(cx + k * rx, y1), P(x1, cy + k * ry), P(x1, cy)),
        ("c", P(x1, cy), P(x1, cy - k * ry), P(cx + k * rx, y0), P(cx, y0)),
        ("c", P(cx, y0), P(cx - k * rx, y0), P(x0, cy - k * ry), P(x0, cy)),
    ]
    return {"items": items, "fill": (0.0, 0.0, 0.0), "rect": fitz.Rect(x0, y0, x1, y1)}


def paired_system(scale: float = 1.0, extra: list[dict[str, Any]] | None = None) -> MockPage:
    """Notation staff (5 lines, space 18) over a TAB staff (6 lines); outer barlines span both."""
    s = scale
    drawings = [line(50 * s, y * s, 500 * s, y * s) for y in (100.0, 118.0, 136.0, 154.0, 172.0)]
    drawings += [line(50 * s, y * s, 500 * s, y * s) for y in (200.0, 227.0, 254.0, 281.0, 308.0, 335.0)]
    drawings += [line(50 * s, 80 * s, 50 * s, 350 * s), line(500 * s, 80 * s, 500 * s, 350 * s)]
    return MockPage(drawings + (extra or []))


def stem_with_notehead(x: float, s: float = 1.0) -> list[dict[str, Any]]:
    # Like the Lesson 3 stems: it crosses the whole staff but overshoots the outer lines by about
    # 0.3 staff spaces, ending inside a notehead on the notehead's right edge. A barline runs exactly
    # line to line.
    return [line(x * s, 94 * s, x * s, 177 * s), filled((x - 19) * s, 165 * s, x * s, 181 * s)]


def notation_only_barline(x: float, s: float = 1.0) -> dict[str, Any]:
    return line(x * s, 80 * s, x * s, 180 * s)


def stem_rejections(system) -> list[float]:
    return sorted(
        round(d["x"], 1) for d in system.barline_candidates_details if d.get("rejection_reason") == "pdf_barline_note_stem"
    )


def test_stem_with_attached_notehead_is_not_inherited_as_a_barline() -> None:
    page = paired_system(extra=[notation_only_barline(200.0), *stem_with_notehead(300.0)])
    (system,) = _detect_tab_systems(page, 1)
    assert system.barlines == [50.0, 200.0, 500.0]
    assert stem_rejections(system) == [300.0]
    assert system.rejection_reasons.get("pdf_barline_note_stem") == 1


def test_negative_control_the_stem_is_inherited_when_the_notehead_check_is_disabled(monkeypatch) -> None:
    # Without the H2 check, the same page reproduces the Lesson 3 defect: the stem becomes a barline.
    monkeypatch.setattr(pdf, "_has_attached_notehead", lambda *args, **kwargs: False)
    page = paired_system(extra=[notation_only_barline(200.0), *stem_with_notehead(300.0)])
    (system,) = _detect_tab_systems(page, 1)
    assert system.barlines == [50.0, 200.0, 300.0, 500.0]
    assert stem_rejections(system) == []


def test_tab_missed_barline_is_still_recovered_through_the_partner_path() -> None:
    # Genuine barlines crossing only the notation staff (no TAB stroke) must still be inherited
    # when note stems are present elsewhere in the system.
    page = paired_system(extra=[notation_only_barline(200.0), notation_only_barline(350.0), *stem_with_notehead(270.0)])
    (system,) = _detect_tab_systems(page, 1)
    assert system.barlines == [50.0, 200.0, 350.0, 500.0]


def test_a_note_standing_beside_a_barline_does_not_reject_it() -> None:
    # A notehead just clear of a barline (a gap wider than the attachment tolerance) is not attached.
    beside = filled(206.0, 165.0, 225.0, 181.0)
    page = paired_system(extra=[notation_only_barline(200.0), beside])
    (system,) = _detect_tab_systems(page, 1)
    assert system.barlines == [50.0, 200.0, 500.0]
    assert stem_rejections(system) == []


def test_non_notehead_fills_do_not_reject_a_barline() -> None:
    # A beam (much wider than a notehead) touching a barline's end is not notehead evidence.
    beam = filled(150.0, 176.0, 260.0, 184.0)
    page = paired_system(extra=[notation_only_barline(200.0), beam])
    (system,) = _detect_tab_systems(page, 1)
    assert system.barlines == [50.0, 200.0, 500.0]


@pytest.mark.parametrize("scale", [0.25, 1.0, 4.0])
def test_notehead_attachment_is_rendered_contact_in_staff_spaces(scale: float) -> None:
    # Sizes are dimensionless; attachment is rendered contact with no horizontal allowance.
    s = scale
    notehead = pdf._notehead_candidate_shapes([filled(281.0 * s, 165.0 * s, 300.0 * s, 181.0 * s)])
    space = 18.0 * s
    touching = (299.9 * s, 300.1 * s)
    assert pdf._has_attached_notehead(touching, 98.0 * s, 174.0 * s, notehead, space)            # stem on its edge
    assert not pdf._has_attached_notehead((300.01 * s, 300.3 * s), 98.0 * s, 174.0 * s, notehead, space)  # a visible gap
    assert not pdf._has_attached_notehead(touching, 98.0 * s, 140.0 * s, notehead, space)        # ends away from it
    too_wide = pdf._notehead_candidate_shapes([filled(250.0 * s, 165.0 * s, 300.0 * s, 181.0 * s)])                                     # a beam, not a notehead
    assert not pdf._has_attached_notehead(touching, 98.0 * s, 174.0 * s, too_wide, space)


# --- Real source: the original Lesson 3 PDF through production code (counts only) ---

# Same resolution as tests/test_lesson3_native_acceptance.py: a sibling checkout locally, or the
# copy CI mounts at fixtures/private. The tests stay mandatory: a missing corpus fails, never skips.
ROOT = Path(__file__).resolve().parents[1]
SIBLING = ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private"
CORPUS = SIBLING if SIBLING.exists() else ROOT / "fixtures" / "private"


def lesson3() -> fitz.Document:
    path = CORPUS / "Lesson-3.pdf"
    assert path.is_file(), "mandatory real-source corpus file is unavailable: Lesson-3.pdf; CI must mount score2gp-private-fixtures"
    return fitz.open(path)


def test_lesson3_first_system_has_exactly_three_bar_boxes() -> None:
    doc = lesson3()
    first = _detect_tab_systems(doc[0], 1)[0]
    assert len(first.barlines) == 4, "page 1 system 1 must have exactly the 4 adjudicated boundaries"
    assert len(first.barlines) - 1 == 3
    assert len(stem_rejections(first)) == 4, "the 4 inherited note stems must be rejected as stems"


def test_lesson3_whole_document_topology_matches_the_pdf() -> None:
    doc = lesson3()
    systems_per_page, measures_per_page = [], []
    for index in range(len(doc)):
        systems = _detect_tab_systems(doc[index], index + 1)
        systems_per_page.append(len(systems))
        measures_per_page.append(sum(max(len(s.barlines) - 1, 0) for s in systems))
    assert sum(systems_per_page) == 23
    assert measures_per_page == [15, 22, 19, 10]
    assert sum(measures_per_page) == 66


# --- Review 5309174891 / 5309393727: production-path regressions on real PyMuPDF vector pages ---

NOTATION_YS = (100.0, 118.0, 136.0, 154.0, 172.0)  # staff space 18
TAB_YS = (200.0, 227.0, 254.0, 281.0, 308.0, 335.0)
BARLINE_WIDTH = 0.7  # engraved barlines are thicker than stems (Lessons 3-7: 0.68 vs 0.51 pt)
STEM_WIDTH = 0.5


def vector_page(barlines: list[tuple[float, float, float, float]] = (),
                stems: list[tuple[float, float, float, float]] = (),
                noteheads: list[tuple[fitz.Rect, bool]] = (),
                background: tuple[float, float, float] | None = None,
                underlay: tuple[fitz.Rect, dict[str, Any]] | None = None,
                patches: list[tuple[fitz.Rect, tuple[float, float, float]]] = ()) -> fitz.Page:
    """An in-memory PDF page with paired staves and outer barlines spanning both staves.

    ``barlines`` and ``stems`` are (x, y0, y1, width) notation-staff verticals. ``noteheads``
    holds (rect, filled); unfilled heads are stroked ovals drawn with curves.
    """
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    shape = page.new_shape()
    if background is not None:
        shape.draw_rect(page.rect)
        shape.finish(color=None, fill=background)
    for rect, colour in patches:  # background patches, painted before everything else on the page
        shape.draw_rect(rect)
        shape.finish(color=None, fill=colour)
    if underlay is not None:  # an oval painted beneath all score lines, over the background
        shape.draw_oval(underlay[0])
        shape.finish(**underlay[1])
    for y in (*NOTATION_YS, *TAB_YS):
        shape.draw_line((50, y), (500, y))
    shape.finish(color=(0, 0, 0), width=0.4)
    for x in (50.0, 500.0):
        shape.draw_line((x, 80), (x, 350))
    shape.finish(color=(0, 0, 0), width=BARLINE_WIDTH)
    for x, y0, y1, width in (*barlines, *stems):
        shape.draw_line((x, y0), (x, y1))
        shape.finish(color=(0, 0, 0), width=width)
    for rect, is_filled in noteheads:
        shape.draw_oval(rect)
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0) if is_filled else None, width=0.8)
    shape.commit()
    page._keep_doc = doc  # keep the document alive for the page's lifetime
    return page


def barline(x: float, y0: float = 100.0, y1: float = 172.0, width: float = BARLINE_WIDTH):
    return (x, y0, y1, width)


def stem(x: float, y0: float = 94.0, y1: float = 177.0, width: float = STEM_WIDTH):
    return (x, y0, y1, width)


HEAD_ON_BOTTOM_LINE_LEFT_OF_300 = fitz.Rect(281, 164, 300, 180)


def boundaries(page) -> tuple[list[float], list[float], list[str]]:
    (system,) = _detect_tab_systems(page, 1)
    ambiguous = [d.get("stem_evidence") for d in system.barline_candidates_details if d.get("stem_evidence")]
    return [round(b, 1) for b in system.barlines], stem_rejections(system), ambiguous


@pytest.mark.parametrize("gap_spaces", [0.0, 0.1, 0.25])
@pytest.mark.parametrize("side", ["right", "left"])
def test_a_genuine_barline_with_a_touching_or_nearby_notehead_is_kept(gap_spaces: float, side: str) -> None:
    gap = gap_spaces * 18.0
    head = fitz.Rect(200 + gap, 164, 219 + gap, 180) if side == "right" else fitz.Rect(181 - gap, 164, 200 - gap, 180)
    assert boundaries(vector_page([barline(200.0)], noteheads=[(head, True)])) == ([50.0, 200.0, 500.0], [], [])


@pytest.mark.parametrize("is_filled", [True, False], ids=["black-notehead", "hollow-notehead"])
def test_stems_of_filled_and_hollow_noteheads_are_rejected(is_filled: bool) -> None:
    page = vector_page([barline(200.0)], stems=[stem(300.0)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, is_filled)])
    assert boundaries(page) == ([50.0, 200.0, 500.0], [300.0], [])


def test_an_exact_span_stem_is_rejected_by_its_thickness() -> None:
    # Review 5309393727 probe 1: a stem drawn exactly line to line with an attached notehead.
    page = vector_page(stems=[stem(300.0, 100.0, 172.0)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == ([50.0, 500.0], [300.0], [])


@pytest.mark.parametrize("overshoot_spaces", [0.14, 0.161, 0.5])
def test_a_genuine_touching_barline_beyond_the_span_tolerance_is_kept_by_its_thickness(overshoot_spaces: float) -> None:
    # Review 5309393727 probe 2: a barline overshooting the bottom line, with a touching notehead.
    y1 = 172.0 + overshoot_spaces * 18.0
    page = vector_page([barline(300.0, 100.0, y1)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == ([50.0, 300.0, 500.0], [], [])


@pytest.mark.parametrize(("overshoot_spaces", "expected"), [
    (0.0, ([50.0, 500.0], [], ["ambiguous_not_promoted"])),
    (0.14, ([50.0, 500.0], [], ["ambiguous_not_promoted"])),
    (0.16, ([50.0, 500.0], [300.0], [])),
    # 0.5 spaces beyond the line the vertical passes out of the notehead's painted height: a stem
    # ends inside its head, so this is not attachment and the barline stays.
    (0.5, ([50.0, 300.0, 500.0], [], [])),
])
def test_equal_thickness_falls_back_to_the_staff_span_with_explicit_ambiguity(monkeypatch, overshoot_spaces, expected) -> None:
    # Without thickness evidence, an attached vertical spanning exactly the staff has conflicting
    # evidence: it is recorded and not promoted (fail-safe). Beyond the 0.15-space tolerance it is a stem.
    monkeypatch.setattr(pdf, "_thickness_near", lambda *args, **kwargs: None)
    y1 = 172.0 + overshoot_spaces * 18.0
    page = vector_page([barline(300.0, 100.0, y1)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == expected


def test_negative_control_hollow_notehead_stem_survives_without_outline_detection(monkeypatch) -> None:
    real = pdf._notehead_candidate_shapes
    monkeypatch.setattr(pdf, "_notehead_candidate_shapes", lambda drawings, *rest: real([d for d in drawings if d.get("fill") is not None], *rest))
    page = vector_page([barline(200.0)], stems=[stem(300.0)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, False)])
    assert boundaries(page)[0] == [50.0, 200.0, 300.0, 500.0]


def test_exact_span_stem_without_thickness_evidence_is_recorded_not_promoted(monkeypatch) -> None:
    # Absent TAB reference thickness: the conflicting candidate never becomes a boundary.
    monkeypatch.setattr(pdf, "_thickness_near", lambda *args, **kwargs: None)
    page = vector_page(stems=[stem(300.0, 100.0, 172.0)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == ([50.0, 500.0], [], ["ambiguous_not_promoted"])


def test_notation_only_recovery_is_unaffected_by_ambiguity_handling() -> None:
    # A genuine TAB-missed barline with no attached notehead is still inherited.
    page = vector_page([barline(200.0), barline(350.0)], stems=[stem(300.0)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == ([50.0, 200.0, 350.0, 500.0], [300.0], [])



@pytest.mark.parametrize("gap_spaces", [0.1, 0.2])
@pytest.mark.parametrize("side", ["right", "left"])
@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_a_thin_genuine_barline_with_a_separate_nearby_note_is_kept(gap_spaces: float, side: str, as_rectangle: bool) -> None:
    # Review 5310053328: a visible gap means the note is separate, not attached; only contact is stem evidence.
    gap = gap_spaces * 18.0
    head = fitz.Rect(300 + gap, 164, 319 + gap, 180) if side == "right" else fitz.Rect(281 - gap, 164, 300 - gap, 180)
    if as_rectangle:
        page = vector_page(noteheads=[(head, True)])
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(299.75, 100.0, 300.25, 172.0 + 0.161 * 18.0))
        shape.finish(color=None, fill=(0, 0, 0))
        shape.commit()
    else:
        page = vector_page([barline(300.0, 100.0, 172.0 + 0.161 * 18.0, width=STEM_WIDTH)], noteheads=[(head, True)])
    bars, stems_rejected, ambiguous = boundaries(page)
    assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5
    assert stems_rejected == [] and ambiguous == []


def test_negative_control_a_thin_stem_that_touches_its_notehead_is_still_rejected() -> None:
    # The same thin vertical, now touching the notehead, is stem evidence and is rejected.
    page = vector_page(stems=[stem(300.0)], noteheads=[(fitz.Rect(300.0, 164, 319.0, 180), True)])
    assert boundaries(page) == ([50.0, 500.0], [300.0], [])



HEAD_OUTLINE_HALF = 0.4  # vector_page strokes noteheads at width 0.8, painting 0.4 beyond the path
THIN_HALF = STEM_WIDTH / 2


def thin_barline_page(side: str, painted_gap: float, as_rectangle: bool):
    """A thin genuine barline at x=300 and a separate notehead ``painted_gap`` pt from its painted edge."""
    y1 = 172.0 + 0.161 * 18.0
    if side == "right":
        x0 = 300.0 + THIN_HALF + painted_gap + HEAD_OUTLINE_HALF
        head = fitz.Rect(x0, 164, x0 + 19, 180)
    else:
        x1 = 300.0 - THIN_HALF - painted_gap - HEAD_OUTLINE_HALF
        head = fitz.Rect(x1 - 19, 164, x1, 180)
    if not as_rectangle:
        return vector_page([barline(300.0, 100.0, y1, width=STEM_WIDTH)], noteheads=[(head, True)])
    page = vector_page(noteheads=[(head, True)])
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(300.0 - THIN_HALF, 100.0, 300.0 + THIN_HALF, y1))
    shape.finish(color=None, fill=(0, 0, 0))
    shape.commit()
    return page


@pytest.mark.parametrize("gap_spaces", [0.005, 0.04])
@pytest.mark.parametrize("side", ["right", "left"])
@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_any_visible_gap_keeps_a_thin_genuine_barline(gap_spaces: float, side: str, as_rectangle: bool) -> None:
    # Review 5310255195: gaps inside the former 0.05-space allowance, measured between painted edges.
    bars, stems_rejected, ambiguous = boundaries(thin_barline_page(side, gap_spaces * 18.0, as_rectangle))
    assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5
    assert stems_rejected == [] and ambiguous == []


def test_negative_control_the_former_padded_attachment_deletes_the_barline(monkeypatch) -> None:
    # Re-apply the reviewed defect (a 0.05-space pad around the vertical): the 0.04-space case is deleted.
    real = pdf._rendered_x_extent
    monkeypatch.setattr(pdf, "_rendered_x_extent",
                        lambda segments, x, y0, y1: (real(segments, x, y0, y1)[0] - 0.9, real(segments, x, y0, y1)[1] + 0.9))
    bars, stems_rejected, _ = boundaries(thin_barline_page("right", 0.04 * 18.0, False))
    assert bars == [50.0, 500.0] and len(stems_rejected) == 1



@pytest.mark.parametrize("gap_spaces", [0.04, 0.2])
@pytest.mark.parametrize("end", ["below", "above"])
@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_a_note_separated_vertically_from_a_barline_end_is_not_attached(gap_spaces: float, end: str, as_rectangle: bool) -> None:
    # Review 5310525340: a thin barline whose end is a visible vertical gap from a note overlapping
    # its x is kept. The stem end must lie inside the notehead's painted height.
    y0, y1 = 100.0, 172.0 + 0.161 * 18.0
    gap = gap_spaces * 18.0 + HEAD_OUTLINE_HALF
    head = fitz.Rect(290, y1 + gap, 309, y1 + gap + 16) if end == "below" else fitz.Rect(290, y0 - gap - 16, 309, y0 - gap)
    if as_rectangle:
        page = vector_page(noteheads=[(head, True)])
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(300.0 - THIN_HALF, y0, 300.0 + THIN_HALF, y1))
        shape.finish(color=None, fill=(0, 0, 0))
        shape.commit()
    else:
        page = vector_page([barline(300.0, y0, y1, width=STEM_WIDTH)], noteheads=[(head, True)])
    bars, stems_rejected, ambiguous = boundaries(page)
    assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5
    assert stems_rejected == [] and ambiguous == []


def test_a_notehead_sized_triangle_is_not_notehead_evidence() -> None:
    # Review 5310525340: a straight-edged decoration touching a thin barline does not make it a stem.
    y1 = 172.0 + 0.161 * 18.0
    page = vector_page([barline(300.0, 100.0, y1, width=STEM_WIDTH)])
    shape = page.new_shape()
    shape.draw_polyline([(281, 180), (300, 180), (290.5, 164), (281, 180)])
    shape.finish(color=None, fill=(0, 0, 0), closePath=True)
    shape.commit()
    bars, stems_rejected, _ = boundaries(page)
    assert len(bars) == 3 and stems_rejected == []


def test_negative_control_the_same_touching_shape_as_an_oval_is_a_notehead() -> None:
    # The touching thin pair is the accepted residual: drawn as an oval, it reads as a stem.
    y1 = 172.0 + 0.161 * 18.0
    page = vector_page([barline(300.0, 100.0, y1, width=STEM_WIDTH)], noteheads=[(fitz.Rect(281, 164, 300, 180), True)])
    assert len(boundaries(page)[1]) == 1


# Accepted residual (maintainer decision 2026-09-24, L3-01). These pairs are indistinguishable in
# the vector evidence: an attached vertical at barline thickness looks like a barline with a touching
# notehead, and a thin one like a stem. Engraving never places a notehead against a barline, and
# Lessons 3-7 contain none. These tests pin today's behaviour so any change to it is deliberate.

def test_accepted_residual_equal_width_exact_span_stem_reads_as_a_barline() -> None:
    page = vector_page(stems=[stem(300.0, 100.0, 172.0, width=BARLINE_WIDTH)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == ([50.0, 300.0, 500.0], [], [])


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_accepted_residual_thin_touching_barline_reads_as_a_stem(as_rectangle: bool) -> None:
    y1 = 172.0 + 0.161 * 18.0
    if as_rectangle:
        page = vector_page(noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(299.75, 100.0, 300.25, y1))
        shape.finish(color=None, fill=(0, 0, 0))
        shape.commit()
    else:
        page = vector_page([barline(300.0, 100.0, y1, width=STEM_WIDTH)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    bars, stems_rejected, _ = boundaries(page)
    assert bars == [50.0, 500.0]
    # A filled rectangle's vertical is reported at its right edge (x 300.25).
    assert len(stems_rejected) == 1 and abs(stems_rejected[0] - 300.0) <= 0.5


def test_negative_control_touching_barline_is_deleted_without_thickness_or_span(monkeypatch) -> None:
    monkeypatch.setattr(pdf, "_thickness_near", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf, "_spans_staff_exactly", lambda *args, **kwargs: False)
    page = vector_page([barline(200.0)], noteheads=[(fitz.Rect(200, 164, 219, 180), True)])
    assert boundaries(page)[0] == [50.0, 500.0]


# --- Review 5310799558: contact is with the painted notehead, not its bounding box ---
#
# An oval leaves the corners of its bounding box unpainted. A thin genuine barline ending in that
# corner region has a box overlap but no painted contact: the two shapes are disconnected on the
# rendered page. Each page's connectivity is checked independently by rasterising it.

CORNER_BAR_Y1 = 172.0 + 0.161 * 18.0  # overshoots the bottom line beyond the span tolerance
# (head top, filled): the bar end at x=300 lies inside every box's height and width.
CORNER_HEADS = {"disconnected": 172.0, "touching": 170.0}


def corner_page(placement: str, as_rectangle: bool, is_filled: bool = True):
    """A thin barline at x=300 and an oval whose box starts at x=299, left of the bar's painted edge."""
    head = (fitz.Rect(299.0, CORNER_HEADS[placement], 318.0, CORNER_HEADS[placement] + 16.0)
            if placement in CORNER_HEADS else fitz.Rect(305.0, 172.0, 324.0, 188.0))
    if not as_rectangle:
        return vector_page([barline(300.0, 100.0, CORNER_BAR_Y1, width=STEM_WIDTH)], noteheads=[(head, is_filled)])
    page = vector_page(noteheads=[(head, is_filled)])
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(300.0 - THIN_HALF, 100.0, 300.0 + THIN_HALF, CORNER_BAR_Y1))
    shape.finish(color=None, fill=(0, 0, 0))
    shape.commit()
    return page


def painted_components(page, clip: fitz.Rect, zoom: float = 24.0) -> int:
    """Connected dark regions in a rasterised clip (8-connectivity)."""
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY, alpha=False)
    w, h, data = pix.width, pix.height, pix.samples
    dark = {(x, y) for y in range(h) for x in range(w) if data[y * w + x] < 128}
    components = 0
    while dark:
        components += 1
        stack = [dark.pop()]
        while stack:
            x, y = stack.pop()
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if (nx, ny) in dark:
                        dark.remove((nx, ny))
                        stack.append((nx, ny))
    return components


# Below the bottom staff line and right of the outer barline region: only the bar end and the head.
CORNER_CLIP = fitz.Rect(296.0, 173.0, 322.0, 190.0)


@pytest.mark.parametrize("is_filled", [True, False], ids=["black-notehead", "hollow-notehead"])
@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_an_oval_whose_box_overlaps_but_whose_paint_does_not_keeps_the_barline(as_rectangle: bool, is_filled: bool) -> None:
    page = corner_page("disconnected", as_rectangle, is_filled)
    assert painted_components(page, CORNER_CLIP) == 2, "fixture must be disconnected on the rendered page"
    head = next(s for s in pdf._notehead_candidate_shapes(page.get_drawings()) if s.bbox[0] < 300.0 < s.bbox[2])
    assert head.bbox[1] <= CORNER_BAR_Y1 <= head.bbox[3], "the box overlaps the bar end"
    bars, stems_rejected, ambiguous = boundaries(page)
    assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5
    assert stems_rejected == [] and ambiguous == []


@pytest.mark.parametrize("is_filled", [True, False], ids=["black-notehead", "hollow-notehead"])
@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_control_the_same_oval_in_painted_contact_is_attached(as_rectangle: bool, is_filled: bool) -> None:
    # Moved up until its paint meets the bar end: rendered as one shape, it is the accepted
    # thin-touching residual and reads as a stem.
    page = corner_page("touching", as_rectangle, is_filled)
    assert painted_components(page, CORNER_CLIP) == 1, "fixture must touch on the rendered page"
    bars, stems_rejected, _ = boundaries(page)
    assert bars == [50.0, 500.0] and len(stems_rejected) == 1


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
def test_control_a_clearly_separated_oval_keeps_the_barline(as_rectangle: bool) -> None:
    page = corner_page("separated", as_rectangle)
    assert painted_components(page, CORNER_CLIP) == 2
    bars, stems_rejected, ambiguous = boundaries(page)
    assert len(bars) == 3 and stems_rejected == [] and ambiguous == []


def test_negative_control_bounding_box_contact_deletes_the_disconnected_barline(monkeypatch) -> None:
    # Re-apply the reviewed defect (box overlap counted as contact): the disconnected case is deleted.
    monkeypatch.setattr(pdf, "_paints_into", lambda shape, rect: True)
    bars, stems_rejected, _ = boundaries(corner_page("disconnected", as_rectangle=False))
    assert bars == [50.0, 500.0] and len(stems_rejected) == 1


# --- Reviews 5317098713 and 5317580168: only paint that differs from its backdrop is ink ---
#
# Paint is invisible when it cannot differ from what lies beneath it: zero opacity, or the backdrop's
# own colour (white on the unpainted page, grey on a grey fill). White on grey is visible. Each case is
# checked against the raster of the same page without the oval: an invisible oval changes no pixel at
# all, and a visible one changes at least one, in either direction.

TOUCH_HEAD = fitz.Rect(299.0, CORNER_HEADS["touching"], 318.0, CORNER_HEADS["touching"] + 16.0)
GREY = (0.8, 0.8, 0.8)


def touching_oval_page(finish: dict[str, Any] | None, as_rectangle: bool, background: tuple[float, float, float] | None = None):
    """A thin barline at x=300 whose end the oval touches, drawn with ``finish`` (``None``: no oval).

    The oval is painted beneath every score line, over the optional page ``background``, so a
    same-coloured oval has a uniform backdrop.
    """
    page = vector_page(background=background, underlay=None if finish is None else (TOUCH_HEAD, finish))
    shape = page.new_shape()
    if as_rectangle:
        shape.draw_rect(fitz.Rect(300.0 - THIN_HALF, 100.0, 300.0 + THIN_HALF, CORNER_BAR_Y1))
        shape.finish(color=None, fill=(0, 0, 0))
    else:
        shape.draw_line((300.0, 100.0), (300.0, CORNER_BAR_Y1))
        shape.finish(color=(0, 0, 0), width=STEM_WIDTH)
    shape.commit()
    return page


CONTACT_CLIP, CONTACT_ZOOM = fitz.Rect(296.0, 160.0, 322.0, 190.0), 8


def oval_changes_pixels(finish: dict[str, Any], as_rectangle: bool, background) -> bool:
    """True when drawing the oval changes any rendered pixel, in either direction."""
    def pixels(page):
        return page.get_pixmap(matrix=fitz.Matrix(CONTACT_ZOOM, CONTACT_ZOOM), clip=CONTACT_CLIP, alpha=False).samples
    return pixels(touching_oval_page(finish, as_rectangle, background)) != pixels(touching_oval_page(None, as_rectangle, background))


BLACK_OVAL = {"color": (0, 0, 0), "fill": (0, 0, 0), "width": 0.8}
INVISIBLE_OVALS = {
    "zero-opacity-on-white": ({"color": (0, 0, 0), "fill": (0, 0, 0), "width": 0.8, "fill_opacity": 0, "stroke_opacity": 0}, None),
    "zero-opacity-on-grey": ({"color": (0, 0, 0), "fill": (0, 0, 0), "width": 0.8, "fill_opacity": 0, "stroke_opacity": 0}, GREY),
    "zero-fill-opacity-no-stroke": ({"color": None, "fill": (0, 0, 0), "fill_opacity": 0}, None),
    "white-on-white-page": ({"color": (1, 1, 1), "fill": (1, 1, 1), "width": 0.8}, None),
    "grey-on-grey-fill": ({"color": GREY, "fill": GREY, "width": 0.8}, GREY),
}
VISIBLE_OVALS = {
    "black-on-white": (BLACK_OVAL, None),
    "black-on-grey": (BLACK_OVAL, GREY),
    "white-on-grey": ({"color": (1, 1, 1), "fill": (1, 1, 1), "width": 0.8}, GREY),  # review 5317580168
    "grey-on-white": ({"color": GREY, "fill": GREY, "width": 0.8}, None),
    "invisible-fill-visible-stroke": ({"color": (0, 0, 0), "fill": (0, 0, 0), "width": 0.8, "fill_opacity": 0}, None),
}


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
@pytest.mark.parametrize("case", list(INVISIBLE_OVALS))
def test_paint_matching_its_backdrop_is_not_notehead_evidence(case: str, as_rectangle: bool) -> None:
    finish, background = INVISIBLE_OVALS[case]
    assert not oval_changes_pixels(finish, as_rectangle, background), "fixture must not change the rendered page"
    bars, stems_rejected, ambiguous = boundaries(touching_oval_page(finish, as_rectangle, background))
    assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5
    assert stems_rejected == [] and ambiguous == []


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
@pytest.mark.parametrize("case", list(VISIBLE_OVALS))
def test_visible_paint_in_contact_is_attached(case: str, as_rectangle: bool) -> None:
    finish, background = VISIBLE_OVALS[case]
    assert oval_changes_pixels(finish, as_rectangle, background), "fixture must visibly change the rendered page"
    bars, stems_rejected, _ = boundaries(touching_oval_page(finish, as_rectangle, background))
    assert bars == [50.0, 500.0] and len(stems_rejected) == 1


def test_negative_control_assuming_a_white_page_misses_white_on_grey(monkeypatch) -> None:
    # Re-apply the reviewed defect (every backdrop taken as the white page): the visible white oval is ignored.
    monkeypatch.setattr(pdf, "_backdrop_at", lambda *args, **kwargs: pdf.PAGE_BACKDROP_RGB)
    finish, background = VISIBLE_OVALS["white-on-grey"]
    bars, stems_rejected, _ = boundaries(touching_oval_page(finish, False, background))
    assert len(bars) == 3 and stems_rejected == []


def test_negative_control_counting_any_colour_as_ink_deletes_the_barline(monkeypatch) -> None:
    # Re-apply the first reviewed defect (presence of a colour counts as paint): the invisible oval deletes the barline.
    monkeypatch.setattr(pdf, "_paints_ink", lambda color, opacity, backdrop=None: color is not None)
    finish, background = INVISIBLE_OVALS["zero-opacity-on-white"]
    bars, stems_rejected, _ = boundaries(touching_oval_page(finish, False, background))
    assert bars == [50.0, 500.0] and len(stems_rejected) == 1


def test_an_unknown_backdrop_counts_paint_as_ink() -> None:
    # A raster image beneath the shape hides its backdrop; paint there is treated as visible ink.
    assert pdf._paints_ink((1, 1, 1), 1.0, None)
    assert not pdf._paints_ink((1, 1, 1), 0.0, None)



# --- Review 5317580168 follow-up (review 5318235825): visibility is judged where the paint touches ---
#
# A background boundary through the oval: the paint may be visible at the stem contact but not at the
# oval's centre, or the reverse. The oracle is a narrow band just beside the bar on the oval's side:
# the oval is visible at the contact exactly when drawing it changes a pixel in that band.

GREY_RIGHT = [(fitz.Rect(301.5, 150.0, 340.0, 200.0), GREY)]   # centre on grey, contact on white (the reviewer's probe)
GREY_LEFT = [(fitz.Rect(260.0, 150.0, 302.0, 200.0), GREY)]    # contact on grey, centre on white
CONTACT_BAND = fitz.Rect(300.0 + THIN_HALF + 0.05, CORNER_HEADS["touching"], 301.2, CORNER_BAR_Y1)


def split_page(finish: dict[str, Any] | None, patches, as_rectangle: bool):
    page = vector_page(patches=patches, underlay=None if finish is None else (TOUCH_HEAD, finish))
    shape = page.new_shape()
    if as_rectangle:
        shape.draw_rect(fitz.Rect(300.0 - THIN_HALF, 100.0, 300.0 + THIN_HALF, CORNER_BAR_Y1))
        shape.finish(color=None, fill=(0, 0, 0))
    else:
        shape.draw_line((300.0, 100.0), (300.0, CORNER_BAR_Y1))
        shape.finish(color=(0, 0, 0), width=STEM_WIDTH)
    shape.commit()
    return page


def visible_at_contact(finish, patches, as_rectangle: bool) -> bool:
    def band(page):
        return page.get_pixmap(matrix=fitz.Matrix(16, 16), clip=CONTACT_BAND, alpha=False).samples
    return band(split_page(finish, patches, as_rectangle)) != band(split_page(None, patches, as_rectangle))


GREY_OVAL = {"color": GREY, "fill": GREY, "width": 0.8}
WHITE_OVAL = {"color": (1, 1, 1), "fill": (1, 1, 1), "width": 0.8}
SPLIT_CASES = {
    # name: (oval, background patches, attached?)
    "grey-oval-contact-on-white-centre-on-grey": (GREY_OVAL, GREY_RIGHT, True),    # review 5318235825
    "grey-oval-contact-on-grey-centre-on-white": (GREY_OVAL, GREY_LEFT, False),    # visible only away from the stem
    "white-oval-contact-on-grey-centre-on-white": (WHITE_OVAL, GREY_LEFT, True),
    "white-oval-contact-on-white-centre-on-grey": (WHITE_OVAL, GREY_RIGHT, False),
    "black-oval-split-background": (BLACK_OVAL, GREY_RIGHT, True),
}


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
@pytest.mark.parametrize("case", list(SPLIT_CASES))
def test_visibility_is_judged_at_the_contact_on_a_split_background(case: str, as_rectangle: bool) -> None:
    finish, patches, attached = SPLIT_CASES[case]
    assert visible_at_contact(finish, patches, as_rectangle) is attached, "fixture must match its stated contact visibility"
    bars, stems_rejected, ambiguous = boundaries(split_page(finish, patches, as_rectangle))
    if attached:
        assert bars == [50.0, 500.0] and len(stems_rejected) == 1
    else:
        assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5 and stems_rejected == [] and ambiguous == []


def test_negative_control_centre_sampling_misses_the_contact(monkeypatch) -> None:
    # Re-apply the defect of ca93642 (one backdrop, sampled at the oval's centre): the attached stem becomes a barline.
    def centre_rule(shape, rect):
        centre = ((shape.bbox[0] + shape.bbox[2]) / 2, (shape.bbox[1] + shape.bbox[3]) / 2)
        backdrop = pdf._backdrop_at(centre, list(shape.backdrop_fills), list(shape.image_rects))
        return any(pdf._paints_ink(c, o, backdrop) for _, c, o, _ in pdf._contact_points(shape, rect))
    monkeypatch.setattr(pdf, "_paints_into", centre_rule)
    finish, patches, _ = SPLIT_CASES["grey-oval-contact-on-white-centre-on-grey"]
    bars, stems_rejected, _ = boundaries(split_page(finish, patches, False))
    assert len(bars) == 3 and stems_rejected == []


# --- Review 5319790765: the backdrop can change along the contact ---
#
# A narrow background band crosses the stretch where the oval overlaps the stem, falling between
# the discrete points where the oval's outline crosses the stem (about 0.14 pt apart here). Paint is
# judged piece by piece between the band's edges. The ovals are fill-only, so no stroke band adds
# extra contact points. The oracle is the raster of the overlap stretch beside the bar.

NARROW_GREY = [(fitz.Rect(280.0, 174.21, 330.0, 174.30), GREY)]
NARROW_WHITE_ON_GREY = [(fitz.Rect(250.0, 150.0, 350.0, 200.0), GREY), (fitz.Rect(280.0, 174.21, 330.0, 174.30), (1, 1, 1))]
WHITE_FILL = {"color": None, "fill": (1, 1, 1)}
GREY_FILL = {"color": None, "fill": GREY}
BLACK_FILL = {"color": None, "fill": (0, 0, 0)}
OVERLAP_BAND = fitz.Rect(300.0 + THIN_HALF + 0.05, 173.0, 301.2, CORNER_BAR_Y1)


def visible_along_contact(finish, patches, as_rectangle: bool) -> bool:
    def band(page):
        return page.get_pixmap(matrix=fitz.Matrix(24, 24), clip=OVERLAP_BAND, alpha=False).samples
    return band(split_page(finish, patches, as_rectangle)) != band(split_page(None, patches, as_rectangle))


NARROW_CASES = {
    "white-oval-over-narrow-grey-band": (WHITE_FILL, NARROW_GREY, True),      # review 5319790765
    "grey-oval-over-narrow-white-band-on-grey": (GREY_FILL, NARROW_WHITE_ON_GREY, True),
    "white-oval-on-white-without-band": (WHITE_FILL, [], False),
    "black-oval-over-narrow-grey-band": (BLACK_FILL, NARROW_GREY, True),
}


@pytest.mark.parametrize("as_rectangle", [False, True], ids=["stroke", "filled-rectangle"])
@pytest.mark.parametrize("case", list(NARROW_CASES))
def test_visibility_is_judged_along_the_whole_contact(case: str, as_rectangle: bool) -> None:
    finish, patches, attached = NARROW_CASES[case]
    assert visible_along_contact(finish, patches, as_rectangle) is attached, "fixture must match its stated visibility"
    bars, stems_rejected, ambiguous = boundaries(split_page(finish, patches, as_rectangle))
    if attached:
        assert bars == [50.0, 500.0] and len(stems_rejected) == 1
    else:
        assert len(bars) == 3 and abs(bars[1] - 300.0) <= 0.5 and stems_rejected == [] and ambiguous == []


def test_negative_control_contact_points_alone_miss_a_narrow_band(monkeypatch) -> None:
    # Re-apply the defect of 7fdd5f7 (visibility only at discrete contact points): the attached stem stays a barline.
    monkeypatch.setattr(pdf, "_backdrop_cuts", lambda *args, **kwargs: [])
    monkeypatch.setattr(pdf, "_paints_at", lambda *args, **kwargs: False)
    finish, patches, _ = NARROW_CASES["white-oval-over-narrow-grey-band"]
    bars, stems_rejected, _ = boundaries(split_page(finish, patches, False))
    assert len(bars) == 3 and stems_rejected == []
