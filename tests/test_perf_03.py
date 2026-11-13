"""Real-contour scan equivalence and work bound for PERF-03.

REVERT_SCANLINE_CROSSINGS restores the pre-PERF-03 _runs implementation.
It must fail the horizontal midpoint-query assertion on each real source.
The legacy reader is the compatibility oracle, not a musical truth oracle;
whole-corpus CLI artifact comparisons supply the output-preservation evidence.
No synthetic input carries acceptance weight.
"""

from pathlib import Path
import weakref

import pytest

from score2gp.notation_omr import note_duration as reader


def _legacy_runs(shape, vertical, at, lo, hi):
    """Frozen baseline algorithm: split the line, then query each midpoint."""
    cuts = {lo, hi}
    for ax, ay, bx, by in shape.fill_edges:
        a, b, p, q = (ax, bx, ay, by) if vertical else (ay, by, ax, bx)
        if a != b and min(a, b) <= at <= max(a, b):
            value = p + (at - a) * (q - p) / (b - a)
            if lo < value < hi:
                cuts.add(value)
    result = []
    ordered = sorted(cuts)
    for a, b in zip(ordered, ordered[1:]):
        if b - a <= 1e-9:
            continue
        midpoint = (a + b) / 2
        if not (reader._inside_fill(at, midpoint, shape) if vertical
                else reader._inside_fill(midpoint, at, shape)):
            continue
        if result and abs(result[-1][1] - a) <= 1e-6:
            result[-1] = (result[-1][0], b)
        else:
            result.append((a, b))
    return result


@pytest.mark.parametrize("name,page_index", [
    ("Melodic_Expressions.pdf", 1), ("Lesson-6.pdf", 0),
])
def test_real_contour_runs_preserve_boundaries_without_midpoint_rescans(name, page_index, monkeypatch):
    import pymupdf

    source = Path(__file__).resolve().parents[1] / "fixtures/private" / name
    if not source.is_file():
        pytest.fail(f"mandatory real source missing: {name}")
    with pymupdf.open(source) as document:
        glyphs = reader.extract_page_symbols(document[page_index], page_index).glyphs
    assert glyphs
    inside = reader._inside_fill
    queries = 0

    def counted(*args):
        nonlocal queries
        queries += 1
        return inside(*args)

    monkeypatch.setattr(reader, "_inside_fill", counted)
    painted = 0
    for glyph in glyphs:
        x0, y0, x1, y1 = glyph.bbox
        # Interior scans plus every vertex height cover half-open edge ownership,
        # coincident crossings and horizontal edges using actual PDF contours.
        heights = {y0, y1, (y0 + y1) / 2}
        heights.update(y for _, ay, _, by in glyph.shape.fill_edges for y in (ay, by))
        for height in heights:
            expected = _legacy_runs(glyph.shape, False, height, x0 - 1, x1 + 1)
            before = queries
            actual = reader._runs(glyph.shape, False, height, x0 - 1, x1 + 1)
            assert actual == expected
            assert queries == before, "REVERT_SCANLINE_CROSSINGS: repeated horizontal midpoint queries"
            painted += bool(actual)
        for x in (x0, (x0 + x1) / 2, x1):
            assert reader._runs(glyph.shape, True, x, y0 - 1, y1 + 1) == _legacy_runs(
                glyph.shape, True, x, y0 - 1, y1 + 1)
    assert painted > 0


def test_real_conversion_releases_parsed_tabraw_before_builder_reload(tmp_path, monkeypatch):
    """RETAIN_PARSED_TABRAW keeps the CLI's first parse alive during the reload."""
    from typer.testing import CliRunner

    from score2gp import build_ir
    from score2gp.cli import app
    from score2gp.tabraw import TabRaw

    source = Path(__file__).resolve().parents[1] / "fixtures/private/Lesson-6.pdf"
    if not source.is_file():
        pytest.fail("mandatory real source missing: Lesson-6.pdf")
    load = TabRaw.from_json_file
    build = build_ir.build_ir_from_tabraw_only
    loaded = []
    retained = []
    checked = False

    def tracked_load(cls, path):
        value = load(path)
        loaded.append(weakref.ref(value))
        return value

    def checked_build(**kwargs):
        nonlocal checked
        assert loaded, "real conversion must exercise the earlier TabRaw parse"
        retained.extend(ref() is not None for ref in loaded)
        checked = True
        return build(**kwargs)

    monkeypatch.setattr(TabRaw, "from_json_file", classmethod(tracked_load))
    monkeypatch.setattr(build_ir, "build_ir_from_tabraw_only", checked_build)
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab", "--time-signature", "4/4",
        "--work-dir", str(tmp_path / "conversion"), "--out", str(tmp_path / "result.gp"),
    ])
    assert result.exit_code == 0, result.output
    assert checked
    assert not any(retained), "RETAIN_PARSED_TABRAW: duplicate parse retained"
