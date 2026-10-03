"""A TAB staff whose strings are all broken at one x by digits is one staff, bridged by string spacing."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
import pytest

from score2gp.pdf import _detect_tab_systems, extract_tab
from score2gp.pdf_geometry import (
    FULL_CHORD_GAP_MAX_STRING_SPACING_RATIO,
    _is_full_chord_gap,
    _LineSegment,
    merge_collinear_horizontal_segments,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdf" / "pdf_group_02"


def _work_dir() -> Path:
    work = Path(__file__).resolve().parents[1] / "work"
    work.mkdir(parents=True, exist_ok=True)
    return work


def _row(y: float, spans: list[tuple[float, float]]) -> list[_LineSegment]:
    return [_LineSegment(x0, y, x1, y) for x0, x1 in spans]


def _staff(spacing: float, gap: float, rows: int = 6, chord_x: float = 200.0) -> list[_LineSegment]:
    """The top string is broken at ``chord_x`` by ``gap``; the other strings show only their left piece.

    The far side of the break on the other strings is a short piece, which the horizontal-line
    filter drops, so no neighbouring line spans the gap and no row shows a matching right piece:
    only the aligned-edge rule can bridge it.
    """
    pieces = _row(100.0, [(40.0, chord_x), (chord_x + gap, 700.0)])
    for index in range(1, rows):
        pieces += _row(100.0 + index * spacing, [(40.0, chord_x)])
    return pieces


def _full_rows(merged: list[_LineSegment]) -> int:
    return sum(1 for segment in merged if abs(segment.x1 - segment.x0) > 600.0)


def test_full_chord_gap_is_one_staff_that_owns_its_strokes() -> None:
    with pymupdf.open(FIXTURES / "full_chord_gap.pdf") as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    system = systems[0]
    assert len(system.line_ys) == 6
    assert (system.x0, system.x1) == (40.0, 820.0)
    # The joint left stroke (both staves) and the TAB-height rectangle barlines belong to the system.
    assert [round(x) for x in system.barlines] == [40, 300, 500, 820]


def test_full_chord_digits_are_placed_in_bars() -> None:
    with TemporaryDirectory(dir=_work_dir()) as directory:
        raw = extract_tab(FIXTURES / "full_chord_gap.pdf", directory)
    placed = [(c["raw_text"], c.get("string"), c.get("bar_index"))
              for c in sorted(raw["candidates"], key=lambda item: item["bbox"]["x0"])]
    assert placed == [(str(s), s, 1) for s in range(1, 7)] + [(str(s), s, 2) for s in range(1, 7)]


def test_two_staves_on_one_line_are_not_merged() -> None:
    with pymupdf.open(FIXTURES / "wide_gap_two_staves.pdf") as document:
        systems = _detect_tab_systems(document[0], 1)
    assert [(system.x0, system.x1) for system in systems] == [(40.0, 340.0), (400.0, 820.0)]


@pytest.mark.parametrize("spacing", [4.0, 9.66, 19.32, 38.64])
def test_gap_limit_scales_with_string_spacing(spacing: float) -> None:
    gap = 0.76 * spacing
    merged = merge_collinear_horizontal_segments(_staff(spacing, gap))
    assert _full_rows(merged) == 1


@pytest.mark.parametrize("spacing", [9.66, 19.32])
def test_gap_wider_than_the_ratio_is_not_bridged(spacing: float) -> None:
    gap = (FULL_CHORD_GAP_MAX_STRING_SPACING_RATIO + 0.1) * spacing
    merged = merge_collinear_horizontal_segments(_staff(spacing, gap))
    assert _full_rows(merged) == 0


def test_only_four_aligned_rows_are_not_a_chord_column() -> None:
    pieces = _staff(9.66, 7.3, rows=3)
    assert not _is_full_chord_gap(pieces, 100.0, 200.0, 207.3, 1.0)
    pieces = _staff(9.66, 7.3, rows=4)
    assert _is_full_chord_gap(pieces, 100.0, 200.0, 207.3, 1.0)


def test_unevenly_spaced_rows_are_not_a_chord_column() -> None:
    pieces = _row(100.0, [(40.0, 200.0), (207.3, 700.0)])
    for y in (110.0, 135.0, 160.0, 185.0):
        pieces += _row(y, [(40.0, 200.0)])
    assert not _is_full_chord_gap(pieces, 100.0, 200.0, 207.3, 1.0)


def test_staggered_gaps_are_not_a_chord_column() -> None:
    pieces = _row(100.0, [(40.0, 200.0), (207.3, 700.0)])
    for index in range(1, 6):
        pieces += _row(100.0 + 9.66 * index, [(40.0, 200.0 + 40.0 * index)])
    assert not _is_full_chord_gap(pieces, 100.0, 200.0, 207.3, 1.0)
