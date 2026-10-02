"""PARTIAL-01: write the readable TAB systems and refuse only the one unboxed system.

Every page here is engraved like the real source: one page of several systems, each a notation staff
over a TAB staff, drawn with the DUR-01 vocabulary (``scripts/dur_01_make_fixtures.py``). A system is
*unboxed* the way the source's are: its TAB barlines do not cross the string gaps and its notation
barlines are a hair short of the strict height the TAB staff inherits, so no bar box can be built.
The notation staff still reads, so the bar count of that system is known and numbers every later bar.

The tests fail if the unboxed system is written (as is, or with guessed boxes), if the whole file stays
refused, or if any case the rule does not cover (two unboxed systems, an unpaired TAB system, a refused
system whose notation does not add up) stops being refused whole.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf
import pytest

from score2gp.pdf_tab_system_partition import (
    CODE_BOXES_INVALID, CODE_UNBOXED, BOX_WARNING_CODES, partition_tab_systems,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load("dur_01_make_fixtures", ROOT / "scripts" / "dur_01_make_fixtures.py")
oracle = _load("dur_02_oracle", ROOT / "tests" / "test_dur_02_oracle.py")

PITCH = 130.0  # vertical distance between systems
TOP0 = 50.0
STEP = 2 * fx.EVENT_STEP
MIDDLE_BARLINE = 310.0
REFUSAL = "pdf_only_tab_grouping_unsafe"


@pytest.fixture
def work():
    """A scratch directory under <repo>/work whose path has no "test" in it (see test_dur_02_note_type_route)."""
    root = ROOT / "work"
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="partial01_", dir=root) as directory:
        path = Path(directory)
        assert "test" not in str(path).lower()
        yield path


def _digit(score, cx: float, string: int, fret: int) -> None:
    y = fx.TAB_TOP + (string - 1) * fx.TAB_GAP
    text = str(fret)
    width = pymupdf.get_text_length(text, fontname="helv", fontsize=7)
    score.page.draw_rect(pymupdf.Rect(cx - width / 2 - 0.8, y - 3, cx + width / 2 + 0.8, y + 3),
                         color=None, fill=(1, 1, 1), width=0)
    score.page.insert_text((cx - width / 2, y + 2.5), text, fontname="helv", fontsize=7)


def _staves(page, barlines, tab_gaps: int, notation_cut: float, notation: bool = True) -> None:
    cuts = [fx.STAFF_X0, *barlines, fx.STAFF_X1]
    shape = page.new_shape()
    for i in range(5 if notation else 0):
        for a, b in zip(cuts, cuts[1:]):
            shape.draw_line((a, fx.line_y(i)), (b, fx.line_y(i)))
    for i in range(6):
        for a, b in zip(cuts, cuts[1:]):
            shape.draw_line((a, fx.TAB_TOP + i * fx.TAB_GAP), (b, fx.TAB_TOP + i * fx.TAB_GAP))
    shape.finish(color=(0, 0, 0), fill=None, width=fx.STAFF_LINE_W, closePath=False)
    shape.commit()
    for x in [fx.STAFF_X0, *barlines, fx.STAFF_X1]:
        half = fx.BARLINE_W / 2
        if notation:
            page.draw_rect(pymupdf.Rect(x - half, fx.line_y(0) + notation_cut, x + half, fx.line_y(4)),
                           color=None, fill=(0, 0, 0), width=0)
        page.draw_rect(pymupdf.Rect(x - half, fx.TAB_TOP, x + half, fx.TAB_TOP + tab_gaps * fx.TAB_GAP),
                       color=None, fill=(0, 0, 0), width=0)


def make_pdf(path: Path, boxed: list[bool], *, tab_only_system: bool = False, short_bar: int | None = None) -> Path:
    """One page of ``len(boxed)`` systems of two 4/4 bars (four quarters each); ``False`` = unboxed.

    System ``k`` (0-based) puts its digits on string ``k + 1``; fret = 4 * bar-in-system + beat + 1, so
    no two bars carry the same digits. ``short_bar`` drops the last beat of that system's first bar, so
    its notation does not add up to 4/4. ``tab_only_system`` adds a boxed TAB staff with no notation above.
    """
    rows = len(boxed) + (1 if tab_only_system else 0)
    doc = pymupdf.open()
    page = doc.new_page(width=fx.PAGE_W, height=TOP0 + rows * PITCH)
    score = fx.Score(page)
    saved = fx.STAFF_TOP, fx.TAB_TOP
    try:
        for k, ok in enumerate(boxed):
            fx.STAFF_TOP = TOP0 + k * PITCH
            fx.TAB_TOP = fx.STAFF_TOP + 4 * fx.S + 30.0
            _staves(page, [MIDDLE_BARLINE], 5 if ok else 2, 0.0 if ok else 0.4)
            if k == 0:
                x = score.clef_and_time(4, 4)
            else:
                score.fill(lambda sh: fx._ellipse(sh, fx.STAFF_X0 + 9, fx.line_y(2), 4.5, 3.4 * fx.S))
                x = fx.STAFF_X0 + 40
            for bar, start in enumerate((x + 4, MIDDLE_BARLINE + 16)):
                for beat in range(4):
                    if short_bar == k and bar == 0 and beat == 3:
                        continue
                    cx = start + beat * (STEP - 8)
                    fx.note(score, cx, 5, "quarter")
                    _digit(score, cx, k + 1, 4 * bar + beat + 1)
        if tab_only_system:
            fx.TAB_TOP = TOP0 + len(boxed) * PITCH + 4 * fx.S + 30.0
            _staves(page, [MIDDLE_BARLINE], 5, 0.0, notation=False)
            for bar, start in enumerate((fx.STAFF_X0 + 44, MIDDLE_BARLINE + 16)):
                for beat in range(4):
                    _digit(score, start + beat * (STEP - 8), 6, 4 * bar + beat + 1)
    finally:
        fx.STAFF_TOP, fx.TAB_TOP = saved
    doc.save(path)
    return path


def convert(pdf: Path, work: Path, name: str):
    """The production CLI in its own process: the GPIF writer changes its layout when pytest is loaded."""
    out, report = work / f"{name}.gp", work / f"{name}.json"
    result = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out),
         "--work-dir", str(work / name), "--json-report", str(report)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
    )
    result.exit_code = result.returncode
    result.output = result.stdout + result.stderr
    return result, out, json.loads(report.read_text(encoding="utf-8")) if report.exists() else None


@pytest.fixture
def complete(work):
    """The all-boxed page as converted today: the reference every partial file is compared with."""
    result, out, report = convert(make_pdf(work / "all.pdf", [True] * 4), work, "all")
    assert result.exit_code == 0, result.output[-800:]
    return out, report


def test_all_boxed_page_converts_completely_and_is_not_marked_partial(complete):
    out, report = complete
    assert report["status"] == "success"
    assert report["pdf_only_diagnostics"]["pdf_grouping_status"] == "safe"
    assert "refused_tab_systems" not in report["pdf_only_diagnostics"]
    assert "conversion_complete" not in report["pdf_only_diagnostics"]
    bars = oracle.read_gp_bars(out)
    assert len(bars) == 8 and all(bar["events"] and len(bar["events"]) == 4 for bar in bars)


def test_exactly_one_unboxed_system_is_refused_and_the_others_are_written(work, complete):
    truth, _ = complete
    result, out, report = convert(make_pdf(work / "one.pdf", [True, True, False, True]), work, "one")
    assert result.exit_code == 0, result.output[-800:]

    # Not a complete conversion, and the report says where and why.
    diag = report["pdf_only_diagnostics"]
    assert report["status"] == "success"
    assert diag["pdf_grouping_status"] == "partial" and diag["conversion_complete"] is False
    (refused,) = diag["refused_tab_systems"]
    assert (refused["page_index"], refused["system_index"], refused["code"]) == (0, 2, CODE_UNBOXED)
    assert refused["tab_digits"] == 8
    route = json.loads((work / "one" / "note-type-route.json").read_text(encoding="utf-8"))
    assert route["summary"]["refused_tab_systems"] == 1
    refused_bars = [bar for bar in route["bars"] if bar["status"] == "refused"]
    assert [bar["output_bar_index"] for bar in refused_bars] == [5, 6]
    for bar in refused_bars:
        assert bar["reason"] == CODE_UNBOXED
        assert (bar["location"]["page_index"], bar["location"]["system_index"]) == (0, 2)
    assert any(w["code"] == "pdf_partial_tab_system_refused" for w in json.loads(
        (work / "one" / "warnings.json").read_text(encoding="utf-8")))

    # Read back independently: the numbering is the notation's, the gap is empty, and every written
    # bar equals the same bar of the complete conversion (no bar is paired with another system's digits).
    bars = oracle.read_gp_bars(out)
    assert len(bars) == 8
    assert [bar["events"] is None for bar in bars] == [False] * 4 + [True, True] + [False] * 2
    comparison = oracle.compare_gp(truth, out)
    assert comparison["refused_bars"] == [4, 5]
    assert comparison["written_bars"] == 6 and comparison["compared_events"] == 24
    assert comparison["differences"] == []
    # No digit of the refused system (string 3) is written anywhere.
    written_strings = {s for bar in bars for e in bar["events"] or [] for s, _ in e["positions"]}
    truth_strings = {s for bar in oracle.read_gp_bars(truth) for e in bar["events"] for s, _ in e["positions"]}
    assert len(written_strings) == len(truth_strings) - 1


@pytest.mark.parametrize("boxed", [[True, False, False, True], [False, True, False, True], [False, False, False, False]])
def test_two_or_more_unboxed_systems_keep_the_whole_file_refused(work, boxed):
    result, out, report = convert(make_pdf(work / "many.pdf", boxed), work, "many")
    assert result.exit_code == 4 and not out.exists()
    assert report["status"] == "refused" and report["refusal_code"] == REFUSAL


def test_a_boxed_system_without_a_notation_partner_keeps_the_whole_file_refused(work):
    # The extra TAB staff's digits would pair with the notation system above it: ambiguous, so refused whole.
    result, out, report = convert(make_pdf(work / "extra.pdf", [True, True, False, True], tab_only_system=True),
                                  work, "extra")
    assert result.exit_code == 4 and not out.exists()
    assert report["refusal_code"] == REFUSAL


def test_a_refused_system_whose_notation_does_not_add_up_keeps_the_whole_file_refused(work):
    # Its bar count would number every later bar; a bar that does not add up cannot vouch for it.
    result, out, report = convert(make_pdf(work / "short.pdf", [True, True, False, True], short_bar=2), work, "short")
    assert result.exit_code == 4 and not out.exists()
    assert report["refusal_code"] == REFUSAL


def test_a_page_with_a_single_system_that_is_unboxed_stays_refused(work):
    result, out, report = convert(make_pdf(work / "single.pdf", [False]), work, "single")
    assert result.exit_code == 4 and report["refusal_code"] == REFUSAL


def test_the_partition_rule_refuses_nothing_it_cannot_locate(work):
    """Direct check of the rule on the extracted TabRaw: unlocated and non-attributable warnings refuse whole."""
    from score2gp.notation_omr.note_duration import read_note_durations
    from score2gp.tabraw import TabRaw

    pdf = make_pdf(work / "rule.pdf", [True, True, False, True])
    tabraw_path = work / "rule.tabraw.json"
    from score2gp.pdf import extract_tab as extract_tab_file
    extract_tab_file(pdf, tabraw_path)
    tabraw = TabRaw.from_json_file(tabraw_path)
    durations = read_note_durations(pdf)
    digits = [c for c in tabraw.candidates if c.kind == "fret" and c.parsed_fret is not None]
    unsafe = {"pdf_bar_box_construction_not_enough_for_build_ir", "pdf_candidates_unassigned_to_bar",
              "pdf_system_order_ambiguous", "missing_pdf_barlines", "pdf_barlines_missing", "pdf_bar_boxes_missing"}

    refused, readable = partition_tab_systems(tabraw, digits, durations, unsafe)
    assert (refused.page_index, refused.system_index, refused.code) == (1, 3, CODE_UNBOXED)
    assert len(readable) == 24 and all(d.system_index != 3 for d in readable)
    assert "pdf_bar_box_too_narrow" in BOX_WARNING_CODES and CODE_BOXES_INVALID

    # A page-level ordering warning is not a system's own: refuse whole.
    tabraw.warnings.append({"code": "pdf_system_order_ambiguous", "page_index": 1})
    assert partition_tab_systems(tabraw, digits, durations, unsafe) is None
    tabraw.warnings.pop()
    # An unsafe warning located in a readable system: refuse whole.
    tabraw.warnings.append({"code": "pdf_candidates_unassigned_to_bar", "page_index": 1, "system_index": 2})
    assert partition_tab_systems(tabraw, digits, durations, unsafe) is None
    tabraw.warnings.pop()
    # Two refused systems, or a digit without a system: refuse whole.
    broken = [d.model_copy(update={"bar_index": None}) if d.system_index == 1 else d for d in digits]
    assert partition_tab_systems(tabraw, broken, durations, unsafe) is None
    assert partition_tab_systems(
        tabraw, [d.model_copy(update={"system_index": None}) if d is digits[0] else d for d in digits],
        durations, unsafe) is None
