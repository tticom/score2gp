"""DUR-02: the PDF conversion route takes every duration from its note type, and positions from the TAB.

Each synthetic page is one system, a notation staff over a TAB staff, drawn with the DUR-01 fixture
vocabulary (``scripts/dur_01_make_fixtures.py``) plus TAB fret digits under the noteheads. Spacing is
uniform, so it carries no rhythm: a count-, spacing- or default-derived duration disagrees with the
note types drawn, and these tests fail if any such rule comes back.
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
from score2gp.cli import app
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import extract_tab

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load("dur_01_make_fixtures", ROOT / "scripts" / "dur_01_make_fixtures.py")
oracle = _load("dur_02_oracle", ROOT / "tests" / "test_dur_02_oracle.py")

STEP = 2 * fx.EVENT_STEP  # uniform: every event the same distance from the next


# --- drawing -------------------------------------------------------------------------------------

def _digit(score, cx: float, string: int, fret: int) -> None:
    y = fx.TAB_TOP + (string - 1) * fx.TAB_GAP
    text = str(fret)
    width = pymupdf.get_text_length(text, fontname="helv", fontsize=7)
    score.page.draw_rect(pymupdf.Rect(cx - width / 2 - 0.8, y - 3, cx + width / 2 + 0.8, y + 3),
                         color=None, fill=(1, 1, 1), width=0)
    score.page.insert_text((cx - width / 2, y + 2.5), text, fontname="helv", fontsize=7)


def _system(doc, barlines: list[float], time_signature: bool = True):
    page = doc.new_page(width=fx.PAGE_W, height=fx.PAGE_H)
    score = fx.Score(page)
    score.staves(barlines)
    for top, height in ((fx.line_y(0), 4 * fx.S), (fx.TAB_TOP, 5 * fx.TAB_GAP)):
        page.draw_rect(pymupdf.Rect(fx.STAFF_X0 - fx.BARLINE_W / 2, top, fx.STAFF_X0 + fx.BARLINE_W / 2, top + height),
                       color=None, fill=(0, 0, 0), width=0)
    if time_signature:
        start = score.clef_and_time(4, 4)
    else:
        score.fill(lambda sh: fx._ellipse(sh, fx.STAFF_X0 + 9, fx.line_y(2), 4.5, 3.4 * fx.S))
        start = fx.STAFF_X0 + 40
    score.bar_number(start - 4, 1)
    return score, start


def _save(doc, path: Path) -> Path:
    doc.save(path)
    return path


def clean_pdf(path: Path) -> Path:
    """Three 4/4 bars with uniform spacing and mixed note types.

    Bar 1: eighth, eighth (beamed), quarter, four sixteenths (beamed), quarter.
    Bar 2: half note, half rest.
    Bar 3: dotted quarter, eighth, a half-note chord of two notes.
    """
    doc = pymupdf.open()
    bar2, bar3 = 300.0, 440.0
    score, x = _system(doc, [bar2, bar3])
    step = fx.EVENT_STEP + 2
    xs = [x + 4 + i * step for i in range(9)]
    fx.beamed(score, [(xs[0], 6, 1, 0), (xs[1], 5, 1, 0)], up=True)
    fx.note(score, xs[2], 4, "quarter")
    fx.beamed(score, [(xs[3 + i], p, 2, 0) for i, p in enumerate([5, 6, 7, 6])], up=True)
    fx.note(score, xs[7], 5, "quarter")
    for cx, (string, fret) in zip([xs[0], xs[1], xs[2], xs[3], xs[4], xs[5], xs[6], xs[7]],
                                  [(3, 2), (3, 4), (2, 3), (3, 5), (3, 4), (3, 2), (3, 4), (2, 1)]):
        _digit(score, cx, string, fret)
    score.bar_number(bar2, 2)
    fx.note(score, bar2 + 16, 5, "half")
    _digit(score, bar2 + 16, 3, 7)
    score.block_rest(bar2 + 16 + STEP, whole=False)
    score.bar_number(bar3, 3)
    fx.note(score, bar3 + 14, 6, "quarter", dots=1)
    _digit(score, bar3 + 14, 4, 5)
    fx.note(score, bar3 + 14 + fx.EVENT_STEP * 1.5, 5, "eighth")
    _digit(score, bar3 + 14 + fx.EVENT_STEP * 1.5, 3, 9)
    chord = bar3 + 14 + fx.EVENT_STEP * 3.5
    fx.note(score, chord, 6, "half", up=True)
    score.head(chord, 4, hollow=True)
    _digit(score, chord, 2, 5)
    _digit(score, chord, 3, 5)
    return _save(doc, path)


def triplet_tie_pdf(path: Path, tie_stop_digit: bool) -> Path:
    """Two 4/4 bars. Bar 1: an eighth-note triplet, a quarter, a half tied over the barline.
    Bar 2: the tied quarter, a dotted half. The tie's stop has its own TAB digit or none."""
    doc = pymupdf.open()
    bar2 = 330.0
    score, x = _system(doc, [bar2])
    xs = [x + 4 + i * STEP for i in range(3)]
    fx.beamed(score, [(cx, p, 1, 0) for cx, p in zip(xs, [6, 5, 4])], up=True)
    score.tuplet(xs[0] - fx.HEAD_W / 2, xs[-1] + fx.HEAD_W / 2, fx.line_y(0) - 5.2 * fx.S, 3)
    for cx, (string, fret) in zip(xs, [(3, 2), (3, 4), (2, 3)]):
        _digit(score, cx, string, fret)
    fx.note(score, xs[-1] + STEP, 5, "quarter")
    _digit(score, xs[-1] + STEP, 3, 4)
    last = fx.note(score, xs[-1] + 2 * STEP, 6, "half")
    _digit(score, xs[-1] + 2 * STEP, 3, 2)
    score.bar_number(bar2, 2)
    first = fx.note(score, bar2 + 16, 6, "quarter")
    if tie_stop_digit:
        _digit(score, bar2 + 16, 3, 2)
    fx.note(score, bar2 + 16 + STEP, 4, "half", dots=1)
    _digit(score, bar2 + 16 + STEP, 2, 3)
    score.tie(last["cx"] + fx.HEAD_W / 2 + 0.3, first["cx"] - fx.HEAD_W / 2 - 0.3, 6)
    return _save(doc, path)


def refusal_pdf(path: Path, fault: str) -> Path:
    """Two 4/4 bars of four quarters each. Bar 2 carries the named fault; bar 1 is always clean."""
    doc = pymupdf.open()
    bar2 = 300.0
    score, x = _system(doc, [bar2])
    for i in range(4):
        cx = x + 4 + i * STEP
        fx.note(score, cx, 5 - i, "quarter")
        _digit(score, cx, 3, i + 1)
    score.bar_number(bar2, 2)
    xs = [bar2 + 16 + i * (STEP - 8) for i in range(4)]
    for i, cx in enumerate(xs):
        if fault == "unread_event" and i == 1:
            score.head(cx, 5)  # a filled notehead with no stem: its value is not written
            _digit(score, cx, 3, 5)
            continue
        if fault == "wrong_total" and i == 3:
            continue
        if fault == "rest_over_digit" and i == 2:
            score.quarter_rest(cx)
            _digit(score, cx, 3, 9)
            continue
        fx.note(score, cx, 5, "quarter")
        if fault == "missing_digit" and i == 2:
            continue
        _digit(score, cx, 3, 5)
    if fault == "extra_digit":
        _digit(score, xs[1] + (STEP - 8) / 2, 4, 7)
    if fault == "chord_count":
        score.head(xs[0], 3)  # a second notehead on the first chord's stem, but one TAB digit
    return _save(doc, path)


def no_time_signature_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    score, x = _system(doc, [], time_signature=False)
    for i in range(4):
        fx.note(score, x + 4 + i * STEP, 5, "quarter")
        _digit(score, x + 4 + i * STEP, 3, i)
    return _save(doc, path)


# --- helpers -------------------------------------------------------------------------------------

def _build(pdf: Path, tmp_path: Path, time_signature=None):
    tabraw = tmp_path / "tab_raw.json"
    extract_tab(pdf, tabraw)
    records = read_note_durations(pdf, time_signature=time_signature)
    return build_ir_from_tabraw_only(tabraw, note_durations=records)


def _event_fields(event) -> tuple:
    nd = event.timing.notated_duration
    tuplet = (event.timing.tuplet.actual_notes, event.timing.tuplet.normal_notes) if event.timing.tuplet else None
    return ("rest" if event.is_rest else "note", nd.value, nd.dots, tuplet,
            sorted((n.string, n.fret) for n in event.notes))


def _route_bar(diagnostics, source_bar: int) -> dict:
    return next(b for b in diagnostics.note_type_route["bars"] if b["source_bar_index"] == source_bar)


# --- written bars ----------------------------------------------------------------------------------

def test_every_event_takes_its_duration_from_its_note_type(tmp_path):
    score, diagnostics = _build(clean_pdf(tmp_path / "clean.pdf"), tmp_path)
    assert [len(bar.events) for bar in score.bars] == [8, 2, 3]
    assert [_event_fields(e) for e in score.bars[0].events] == [
        ("note", "eighth", 0, None, [(3, 2)]),
        ("note", "eighth", 0, None, [(3, 4)]),
        ("note", "quarter", 0, None, [(2, 3)]),
        ("note", "16th", 0, None, [(3, 5)]),
        ("note", "16th", 0, None, [(3, 4)]),
        ("note", "16th", 0, None, [(3, 2)]),
        ("note", "16th", 0, None, [(3, 4)]),
        ("note", "quarter", 0, None, [(2, 1)]),
    ]
    assert [e.timing.duration_ticks for e in score.bars[0].events] == [480, 480, 960, 240, 240, 240, 240, 960]
    assert [_event_fields(e) for e in score.bars[1].events] == [
        ("note", "half", 0, None, [(3, 7)]),
        ("rest", "half", 0, None, []),  # the rest is read from the notation, never padded
    ]
    assert [_event_fields(e) for e in score.bars[2].events] == [
        ("note", "quarter", 1, None, [(4, 5)]),
        ("note", "eighth", 0, None, [(3, 9)]),
        ("note", "half", 0, None, [(2, 5), (3, 5)]),
    ]
    assert [e.timing.onset_ticks for e in score.bars[2].events] == [0, 1440, 1920]
    assert all(bar.time_signature.numerator == 4 and bar.time_signature.denominator == 4 for bar in score.bars)
    route = diagnostics.note_type_route
    assert route["summary"]["written_bars"] == 3 and route["summary"]["refused_bars"] == 0


def test_each_note_event_records_its_tab_column_match(tmp_path):
    _, diagnostics = _build(clean_pdf(tmp_path / "clean.pdf"), tmp_path)
    half_and_rest = _route_bar(diagnostics, 1)  # source bars are zero-based
    matches = [e["match"] for e in half_and_rest["events"]]
    assert matches[0]["kind"] == "tab_column" and len(matches[0]["candidate_ids"]) == 1
    assert matches[0]["dx_spaces"] <= 0.5
    assert matches[1] == {"kind": "rest"}
    chord = _route_bar(diagnostics, 2)["events"][2]["match"]
    assert chord["kind"] == "tab_column" and len(chord["candidate_ids"]) == 2


def test_triplet_and_tie_come_from_the_grouping(tmp_path):
    for tie_stop_digit in (True, False):
        score, diagnostics = _build(triplet_tie_pdf(tmp_path / f"tt{tie_stop_digit}.pdf", tie_stop_digit), tmp_path)
        first, second = score.bars
        assert [_event_fields(e) for e in first.events] == [
            ("note", "eighth", 0, (3, 2), [(3, 2)]),
            ("note", "eighth", 0, (3, 2), [(3, 4)]),
            ("note", "eighth", 0, (3, 2), [(2, 3)]),
            ("note", "quarter", 0, None, [(3, 4)]),
            ("note", "half", 0, None, [(3, 2)]),
        ]
        assert [e.timing.duration_ticks for e in first.events] == [320, 320, 320, 960, 1920]
        assert [_event_fields(e) for e in second.events] == [
            ("note", "quarter", 0, None, [(3, 2)]),
            ("note", "half", 1, None, [(2, 3)]),
        ]
        start_tie = [t.state for n in first.events[-1].notes for t in n.techniques if t.kind == "tie"]
        stop_tie = [t.state for n in second.events[0].notes for t in n.techniques if t.kind == "tie"]
        assert start_tie == ["start"] and stop_tie == ["stop"]
        match = _route_bar(diagnostics, 1)["events"][0]["match"]
        assert match["kind"] == ("tab_column" if tie_stop_digit else "tie_continuation")


# --- refusals --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("fault", "reason", "event_index"),
    [
        ("unread_event", "note_duration_event_unread", 1),
        ("wrong_total", "bar_total_mismatch", None),
        ("missing_digit", "notation_note_without_tab_digit", 2),
        ("extra_digit", "tab_digit_without_notation_event", None),
        ("rest_over_digit", "rest_over_tab_digit", 2),
        ("chord_count", "notehead_digit_count_mismatch", 0),
    ],
)
def test_a_faulty_bar_is_refused_with_a_located_reason_and_never_filled(tmp_path, fault, reason, event_index):
    score, diagnostics = _build(refusal_pdf(tmp_path / f"{fault}.pdf", fault), tmp_path)
    assert len(score.bars) == 2
    assert [_event_fields(e)[1] for e in score.bars[0].events] == ["quarter"] * 4
    assert score.bars[1].events == []  # refused: written empty, no invented rest or duration
    refused = _route_bar(diagnostics, 1)
    assert refused["status"] == "refused" and refused["reason"] == reason
    assert refused["location"]["page_index"] == 0 and refused["location"]["bar_index"] == 1
    assert refused["location"].get("event_index") == event_index
    assert _route_bar(diagnostics, 0)["status"] == "written"
    assert any(w.code == "pdf_only_tab_bar_refused" for w in score.warnings)
    assert diagnostics.note_type_route["summary"]["refusal_reasons"] == {reason: 1}


def test_an_unread_event_names_the_reader_reason(tmp_path):
    _, diagnostics = _build(refusal_pdf(tmp_path / "u.pdf", "unread_event"), tmp_path)
    assert _route_bar(diagnostics, 1)["detail"] == "filled_notehead_without_stem"


def test_an_unread_time_signature_refuses_the_conversion(tmp_path):
    pdf = no_time_signature_pdf(tmp_path / "nots.pdf")
    with pytest.raises(BuildIrInputRiskError) as err:
        _build(pdf, tmp_path)
    assert err.value.category == "pdf_only_tab_time_signature_unread"
    score, diagnostics = _build(pdf, tmp_path, time_signature=(4, 4))
    assert [_event_fields(e)[1] for e in score.bars[0].events] == ["quarter"] * 4
    assert diagnostics.note_type_route["bars"][0]["time_signature_source"] == "caller_declared"


def test_without_note_duration_records_the_route_refuses(tmp_path):
    pdf = clean_pdf(tmp_path / "clean.pdf")
    tabraw = tmp_path / "tab_raw.json"
    extract_tab(pdf, tabraw)
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(tabraw)
    assert err.value.category == "pdf_only_tab_note_durations_missing"


def test_a_page_with_every_bar_refused_writes_nothing(tmp_path):
    doc = pymupdf.open()
    score, x = _system(doc, [])
    for i in range(4):
        score.head(x + 4 + i * STEP, 5)
        _digit(score, x + 4 + i * STEP, 3, i)
    pdf = _save(doc, tmp_path / "allunread.pdf")
    with pytest.raises(BuildIrInputRiskError) as err:
        _build(pdf, tmp_path)
    assert err.value.category == "pdf_only_tab_no_bar_written"
    assert err.value.details["refusal_reasons"] == {"note_duration_event_unread": 1}


# --- end to end ------------------------------------------------------------------------------------

def _expected_clean() -> list[list[dict]]:
    def n(written, positions, dots=0):
        # GPIF strings count from the lowest string, zero-based: TAB string s is 6 - s.
        return {"kind": "note", "written": written, "dots": dots, "tuplet": None, "tie": (False, False),
                "positions": sorted((6 - s, f) for s, f in positions)}
    return [
        [n("eighth", [(3, 2)]), n("eighth", [(3, 4)]), n("quarter", [(2, 3)]), n("16th", [(3, 5)]),
         n("16th", [(3, 4)]), n("16th", [(3, 2)]), n("16th", [(3, 4)]), n("quarter", [(2, 1)])],
        [n("half", [(3, 7)]), {"kind": "rest", "written": "half", "dots": 0, "tuplet": None,
                                "tie": (False, False), "positions": []}],
        [n("quarter", [(4, 5)], dots=1), n("eighth", [(3, 9)]), n("half", [(2, 5), (3, 5)])],
    ]


def test_convert_writes_the_note_type_rhythm_into_the_guitar_pro_file(tmp_path):
    pdf = clean_pdf(tmp_path / "clean.pdf")
    out = tmp_path / "clean.gp"
    report = tmp_path / "report.json"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--out", str(out), "--work-dir", str(tmp_path / "wd"),
                                      "--json-report", str(report), "--pdf-only-tab"])
    assert result.exit_code == 0, result.output
    bars = oracle.read_gp_bars(out)
    assert [b["time"] for b in bars] == ["4/4"] * 3
    assert [b["events"] for b in bars] == _expected_clean()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["pdf_only_diagnostics"]["inferred_rhythm_status"] == "note_type"
    route = json.loads((tmp_path / "wd" / "note-type-route.json").read_text(encoding="utf-8"))
    assert route["summary"]["written_bars"] == 3
    assert (tmp_path / "wd" / "note-durations.json").exists()


def test_convert_passes_a_declared_time_signature_to_the_bar_check_only(tmp_path):
    pdf = no_time_signature_pdf(tmp_path / "nots.pdf")
    base = ["convert", "--pdf", str(pdf), "--pdf-only-tab"]
    refused = CliRunner().invoke(app, [*base, "--out", str(tmp_path / "a.gp"), "--work-dir", str(tmp_path / "a")])
    assert refused.exit_code != 0 and "pdf_only_tab_time_signature_unread" in refused.output
    written = CliRunner().invoke(app, [*base, "--out", str(tmp_path / "b.gp"), "--work-dir", str(tmp_path / "b"),
                                       "--time-signature", "4/4"])
    assert written.exit_code == 0, written.output
    assert [e["written"] for e in oracle.read_gp_bars(tmp_path / "b.gp")[0]["events"]] == ["quarter"] * 4


def test_the_editable_draft_quarter_default_is_gone(tmp_path):
    pdf = clean_pdf(tmp_path / "clean.pdf")
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--out", str(tmp_path / "d.gp"),
                                      "--work-dir", str(tmp_path / "wd"), "--editable-draft"])
    assert result.exit_code == 2 and "No such option" in result.output


# --- the deleted rules stay deleted -------------------------------------------------------------------

def test_the_count_rule_and_the_placeholders_are_deleted_from_src():
    import score2gp.pdf_tab_event_factory as factory
    import score2gp.pdf_tab_measure_timing as timing

    for name in ("select_pdf_tab_grid_spacing_and_duration_name", "decompose_pdf_tab_measure_remainder_to_rests",
                 "REST_DURATION_HIERARCHY", "is_within_pdf_tab_measure_capacity"):
        assert not hasattr(timing, name)
    for name in ("determine_pdf_tab_event_duration", "build_pdf_tab_editable_draft_annotation_text",
                 "_infer_dots_from_duration", "build_pdf_tab_event_from_subgroup"):
        assert not hasattr(factory, name)
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "score2gp").rglob("*.py"))
    for token in ("equal_spacing_fallback", "is_fallback_placeholder", "editable_draft",
                  "select_pdf_tab_grid_spacing", "decompose_pdf_tab_measure_remainder"):
        assert token not in source, token


def test_duration_evidence_no_longer_admits_a_placeholder_source():
    from score2gp.pdf_tab_duration_types import TabDurationEvidence
    from score2gp.tabraw import _parse_tab_duration_evidence

    with pytest.raises(ValueError):
        TabDurationEvidence(duration_name="quarter", duration_ticks=960, source="equal_spacing_fallback")
    legacy = {"duration_name": "quarter", "duration_ticks": 960, "source": "equal_spacing_fallback",
              "is_fallback_placeholder": True}
    assert _parse_tab_duration_evidence(legacy) is None


def test_an_unstemmed_event_gets_no_duration_evidence():
    from score2gp.pdf_tab_duration_associator import StaffSystemContext, resolve_tab_duration_evidence_for_events

    context = StaffSystemContext(line_y_coords=[100.0, 107.0, 114.0, 121.0, 128.0, 135.0])
    assert resolve_tab_duration_evidence_for_events([50.0, 80.0], [], [], [], context) == {}


def test_ticks_come_from_the_record_fraction_exactly():
    from score2gp.pdf_tab_measure_timing import PdfTabBarAssemblerError, ticks_for_quarters

    assert ticks_for_quarters(Fraction(1, 3)) == 320
    assert ticks_for_quarters(Fraction(3, 2)) == 1440
    with pytest.raises(PdfTabBarAssemblerError):
        ticks_for_quarters(Fraction(1, 7))
