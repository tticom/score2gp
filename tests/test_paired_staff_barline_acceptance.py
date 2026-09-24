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
    return {"items": [], "fill": (0.0, 0.0, 0.0), "rect": fitz.Rect(x0, y0, x1, y1)}


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
    notehead = [(281.0 * s, 165.0 * s, 300.0 * s, 181.0 * s)]
    space = 18.0 * s
    touching = (299.9 * s, 300.1 * s)
    assert pdf._has_attached_notehead(touching, 98.0 * s, 174.0 * s, notehead, space)            # stem on its edge
    assert not pdf._has_attached_notehead((300.01 * s, 300.3 * s), 98.0 * s, 174.0 * s, notehead, space)  # a visible gap
    assert not pdf._has_attached_notehead(touching, 98.0 * s, 140.0 * s, notehead, space)        # ends away from it
    too_wide = [(250.0 * s, 165.0 * s, 300.0 * s, 181.0 * s)]                                     # a beam, not a notehead
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
                noteheads: list[tuple[fitz.Rect, bool]] = ()) -> fitz.Page:
    """An in-memory PDF page with paired staves and outer barlines spanning both staves.

    ``barlines`` and ``stems`` are (x, y0, y1, width) notation-staff verticals. ``noteheads``
    holds (rect, filled); unfilled heads are stroked ovals drawn with curves.
    """
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    shape = page.new_shape()
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
    (0.5, ([50.0, 500.0], [300.0], [])),
])
def test_equal_thickness_falls_back_to_the_staff_span_with_explicit_ambiguity(monkeypatch, overshoot_spaces, expected) -> None:
    # Without thickness evidence, an attached vertical spanning exactly the staff has conflicting
    # evidence: it is recorded and not promoted (fail-safe). Beyond the 0.15-space tolerance it is a stem.
    monkeypatch.setattr(pdf, "_thickness_near", lambda *args, **kwargs: None)
    y1 = 172.0 + overshoot_spaces * 18.0
    page = vector_page([barline(300.0, 100.0, y1)], noteheads=[(HEAD_ON_BOTTOM_LINE_LEFT_OF_300, True)])
    assert boundaries(page) == expected


def test_negative_control_hollow_notehead_stem_survives_without_outline_detection(monkeypatch) -> None:
    real = pdf._filled_shape_boxes
    monkeypatch.setattr(pdf, "_filled_shape_boxes", lambda drawings: real([d for d in drawings if d.get("fill") is not None]))
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
