"""MEM-04 scan reuse on approved real glyphs.

Mutant M2 (remove the per-glyph fill-ratio cache) repeats the identical paint
queries and fails this infrastructure check. It is not a recognition oracle;
conversion acceptance requires the corpus-wide inner-GPIF byte comparison.
"""

from pathlib import Path

import pytest

from score2gp.notation_omr import note_duration as reader


def test_repeated_real_glyph_fill_scan_is_reused_without_changing_ratio(monkeypatch):
    source = Path(__file__).resolve().parents[1] / "fixtures/private/Lesson-6.pdf"
    if not source.is_file():
        pytest.fail("mandatory real source missing: Lesson-6.pdf")
    import pymupdf

    with pymupdf.open(source) as document:
        glyphs = reader.extract_page_symbols(document[0], 0).glyphs
    assert glyphs, "real source must exercise fill scanning"
    inside = reader._inside_fill
    calls = 0

    def counted(*args):
        nonlocal calls
        calls += 1
        return inside(*args)

    monkeypatch.setattr(reader, "_inside_fill", counted)
    first = [reader._fill_ratio(glyph) for glyph in glyphs]
    for glyph, ratio in zip(glyphs, first):
        x0, y0, x1, y1 = glyph.bbox
        expected = sum(inside(x0 + (i + .5) * (x1 - x0) / 12,
                              y0 + (j + .5) * (y1 - y0) / 12, glyph.shape)
                       for i in range(12) for j in range(12)) / 144
        assert ratio == expected
    first_calls = calls
    assert first_calls > 0
    assert [reader._fill_ratio(glyph) for glyph in glyphs] == first
    assert calls == first_calls, "M2: identical glyph fill scans were repeated"
    # The resolution is part of the query: a different grid must not reuse a
    # previous ratio. Calculate its oracle directly from the original predicate.
    for glyph in glyphs:
        x0, y0, x1, y1 = glyph.bbox
        expected = sum(inside(x0 + (i + .5) * (x1 - x0) / 5,
                              y0 + (j + .5) * (y1 - y0) / 5, glyph.shape)
                       for i in range(5) for j in range(5)) / 25
        assert reader._fill_ratio(glyph, n=5) == expected
