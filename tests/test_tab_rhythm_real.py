"""TABRHY-01 acceptance on real approved PDFs: rhythm printed under a staffless TAB.

Every test reads a private corpus PDF (counts and labels only; no musical content is stored here).
Synthetic fixtures carry no weight for these claims, so none is used. The expected values are the
note types, rests, ties and totals hand-checked against the rendered pages of the same PDFs, and the
meter's capacity; they are not copied from the reader's own output. Each mutant test names the wrong
implementation it rejects and shows that implementation failing.

Tuning sources: 5 MUST KNOW Pentatonic Licks In Em, Finger postition tips TAB. 12 Bar Blues Solo
Guitar Jam and PARANOID - BLACK SABBATH are maintainer-judged fixtures used for the mark classes the
tuning sources lack (whole-bar rest, implied rest, digit-less tie end). The Grateful Dead sources are
held out and are never read here.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pymupdf
import pytest

from score2gp import pdf_tab_rhythm as rhythm
from score2gp.build_ir import TRACK_ID
from score2gp.meter import bar_capacity_ticks
from score2gp.pdf_tab_bar_assembler import assemble_note_type_bars
from score2gp.tabraw import TabCandidate, TabRaw

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
PENTATONIC = "5 MUST KNOW Pentatonic Licks In Em"
FINGER = "Finger postition tips TAB"
TWELVE_BAR = "12 Bar Blues Solo Guitar Jam"
PARANOID = "PARANOID - BLACK SABBATH"
SKIP = "mounted private corpus is unavailable"
TPQ = 960


def _pdf(name: str) -> Path:
    path = PRIVATE / f"{name}.pdf"
    if not path.is_file():
        pytest.skip(SKIP)
    return path


@pytest.fixture(scope="module")
def work() -> Path:
    base = ROOT / "work"  # the repository's ignored directory (the TAB route treats paths containing "test" differently)
    base.mkdir(exist_ok=True)
    return base


_CONVERTED: dict[str, Path] = {}


def _convert(name: str, work: Path, declared: str | None = None) -> Path:
    """Run the product CLI on a real PDF once; return its work directory."""
    key = f"{name}|{declared}"
    if key in _CONVERTED:
        return _CONVERTED[key]
    pdf = _pdf(name)
    folder = work / ("tabrhy01-" + re.sub(r"\W+", "_", key))
    folder.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf), "--out", str(folder / "o.gp"),
           "--work-dir", str(folder / "w"), "--json-report", str(folder / "r.json"), "--pdf-only-tab", "--no-strict"]
    if declared:
        cmd += ["--time-signature", declared]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert (folder / "w" / "tab" / "tab_raw.json").is_file(), done.stderr[-400:]
    _CONVERTED[key] = folder / "w"
    return _CONVERTED[key]


def _read(name: str, work: Path, declared: str | None = None, tabraw: TabRaw | None = None):
    folder = _convert(name, work, declared)
    tabraw = tabraw or TabRaw.from_json_file(folder / "tab" / "tab_raw.json")
    time_signature = tuple(int(v) for v in declared.split("/")) if declared else None
    durations = rhythm.read_tab_rhythm(_pdf(name), tabraw, time_signature=time_signature)
    digits = [c for c in tabraw.candidates if (c.parsed_fret is not None and c.kind == "fret") or c.kind == "percussive-strike"]
    bars, route = assemble_note_type_bars(digits, durations, track_id=TRACK_ID)
    return durations, bars, route, tabraw


def _bar_value_names(bar) -> list[str]:
    out = []
    for event in bar.events:
        timing = event.timing
        name = timing.notated_duration.value + "." * timing.notated_duration.dots
        if timing.tuplet:
            name += f" t{timing.tuplet.actual_notes}"
        out.append(("R:" if event.is_rest else "") + name)
    return out


def _capacity_ticks(bar) -> Fraction:
    return bar_capacity_ticks(bar.time_signature.numerator, bar.time_signature.denominator, TPQ)


def _ties(bar) -> list[str]:
    return [t.state for e in bar.events for n in e.notes for t in n.techniques if getattr(t, "kind", None) == "tie"]


# --- acceptance: bars are written from printed marks and total the printed meter -----------------

def test_pentatonic_bars_read_from_printed_marks_total_the_meter(work: Path) -> None:
    """Rejects: durations counted from columns/spacing or defaulted (triplet and 3/4 bars cannot then total)."""
    _, bars, route, _ = _read(PENTATONIC, work)
    assert route["summary"]["written_bars"] == 19 and route["summary"]["refused_bars"] == 0
    assert route["summary"]["implied_rests"] == 0 and route["summary"]["written_bars_printed_marks"] == 19
    for bar in bars:
        assert sum(e.timing.duration_ticks for e in bar.events) == _capacity_ticks(bar)
    names = [_bar_value_names(b) for b in bars]
    assert names[0] == names[1] == ["quarter t3"] * 6  # two triplets of quarter notes per bar, not eighths
    assert [names[i] for i in (2, 5, 8, 18)] == [["whole"]] * 4  # circle, no stem: whole note, 4/4
    assert names[14] == ["half."]  # circle, stem and a dot, in a 3/4 bar: dotted half
    assert all(names[i] == ["quarter"] * 4 for i in (3, 4, 6, 7))
    assert all(names[i] == ["eighth"] * 8 for i in (15, 16, 17))
    assert all(names[i] == ["eighth"] * 6 for i in (11, 12, 13))
    assert [(b.time_signature.numerator, b.time_signature.denominator) for b in bars][9:15] == [(3, 4)] * 6


def test_finger_position_tips_is_music_and_every_bar_is_written(work: Path) -> None:
    """Rejects: stems or beams unread (all four-quarter bars would not total), fingering numerals read as notes."""
    _, bars, route, _ = _read(FINGER, work)
    assert route["summary"]["written_bars"] == 17 and route["summary"]["refused_bars"] == 0
    names = [_bar_value_names(b) for b in bars]
    assert [names[i] for i in (0, 1, 2, 14, 15, 16)] == [["eighth"] * 8] * 6
    assert all(names[i] == ["quarter"] * 4 for i in range(3, 14))
    assert sum(len(e.notes) for b in bars for e in b.events) == 8 * 6 + 4 * 11  # one fret digit per note, none from fingerings


def test_twelve_bar_blues_whole_note_chords_triplets_rest_tie_and_implied_rest(work: Path) -> None:
    _, bars, route, _ = _read(TWELVE_BAR, work)
    names = {b.index: _bar_value_names(b) for b in bars}
    assert all(names[i] == ["whole"] for i in range(2, 13) if len(names[i]) == 1 and not names[i][0].startswith("R"))
    assert names[57] == ["R:whole"]  # whole-rest glyph
    assert names[68] == ["quarter"] + ["eighth t3"] * 9
    # a note tied to a digit-less stem, and a trailing rest the page does not print
    assert _ties(next(b for b in bars if b.index == 26)) == ["start", "stop"]
    summary = route["summary"]
    assert summary["implied_rests"] == 1 and summary["written_bars_with_implied_rest"] == 1
    assert names[26][-1] == "R:quarter"
    # GROUP-01: the leading bar's chord was outside the system (its system started after the short first line
    # piece), so the bar was refused. The staff now reaches its start barline: the chord is read, 6 digits, one whole.
    first = route["bars"][0]
    assert first["status"] == "written" and first["tab_digits"] == 6
    assert names[1] == ["whole"]


def test_implied_rest_is_labelled_and_counted_apart_from_printed_rests(work: Path) -> None:
    """Rejects: an implied rest counted as a printed rest."""
    durations, _, route, _ = _read(TWELVE_BAR, work)
    implied = [r for r in durations["events"] if (r.get("rest") or {}).get("implied")]
    printed = [r for r in durations["events"] if r["kind"] == "rest" and not (r.get("rest") or {}).get("implied")]
    assert len(implied) == 1 and len(printed) == 1
    assert route["summary"]["written_bars_printed_marks"] + route["summary"]["written_bars_with_implied_rest"] \
        == route["summary"]["written_bars"]
    assert durations["diagnostics"]["tab_rhythm"]["implied_rest_bars"][0]["bar_index"] == 25


# --- technique marks are not notes (hard test, real sources) ------------------------------------

def _printed_columns(pdf: Path, durations: dict, bar_index: int) -> int:
    """Independent notehead count: digit words in the bar's TAB band, by column. A parenthesised digit counts only
    where its own stem stands under it (a tied note shown in brackets); a bend target has no stem and is no note."""
    system = next(s for s in durations["systems"] if s["first_bar_index"] <= bar_index < s["first_bar_index"] + s["bar_count"])
    a, z = system["bars"][bar_index - system["first_bar_index"]]
    top, bottom = system["tab_staff"]["top"], system["tab_staff"]["bottom"]
    space = system["staff_space"]
    with pymupdf.open(pdf) as doc:
        page = doc[system["page_index"]]
        words = page.get_text("words")
        verticals = [(it[1].x, min(it[1].y, it[2].y), max(it[1].y, it[2].y)) for d in page.get_drawings() for it in d["items"]
                     if it[0] == "l" and abs(it[1].x - it[2].x) < 0.05 and abs(it[1].y - it[2].y) > space]

    def has_stem(w) -> bool:
        cx = (w[0] + w[2]) / 2
        return any(abs(x - cx) <= 0.6 * space and y1 > w[3] + 0.5 * space for x, _, y1 in verticals)

    xs = sorted((w[0] + w[2]) / 2 for w in words
                if (re.fullmatch(r"\d{1,2}", w[4]) or (re.fullmatch(r"\(\d{1,2}\)", w[4]) and has_stem(w)))
                and a <= (w[0] + w[2]) / 2 <= z and top - 0.45 * space <= (w[1] + w[3]) / 2 <= bottom + 0.45 * space)
    columns = 0
    last = None
    for x in xs:
        if last is None or x - last > 0.75 * space:
            columns += 1
        last = x
    return columns


def _bend_bar_note_counts(name: str, work: Path, declared: str | None = None, tabraw: TabRaw | None = None):
    """(bar index, notes in the written bar, printed noteheads) for every written bar that prints a bend label."""
    durations, bars, route, tabraw = _read(name, work, declared, tabraw)
    pdf = _pdf(name)
    status = {b["output_bar_index"]: b["status"] for b in route["bars"]}
    out = []
    with pymupdf.open(pdf) as doc:
        for system in durations["systems"]:
            words = doc[system["page_index"]].get_text("words")
            labels = [w for w in words if re.fullmatch(r"(?i)full|1/2|3/4|1/4|\(\d+\)", w[4])]
            space = system["staff_space"]
            for k, (a, z) in enumerate(system["bars"]):
                if not any(a <= (w[0] + w[2]) / 2 <= z and system["tab_staff"]["top"] - 4.5 * space <= w[1] <= system["tab_staff"]["bottom"] for w in labels):
                    continue
                bar_index = system["first_bar_index"] + k
                if status.get(bar_index + 1) != "written":
                    continue
                bar = bars[bar_index]
                noteheads = _printed_columns(pdf, durations, bar_index)
                digitless = sum(1 for e in bar.events if not e.is_rest and
                    all((pv.raw or {}).get("derived_from") == "tie_continuation" for pv in e.provenance))
                out.append((bar_index + 1, sum(1 for e in bar.events if not e.is_rest), noteheads + digitless))
    return out


def test_bend_bars_have_exactly_the_printed_noteheads(work: Path) -> None:
    """Rejects: a bend label or parenthesised bend target read as an extra note or fret digit."""
    pent = _bend_bar_note_counts(PENTATONIC, work)
    assert len(pent) >= 8 and all(events == printed for _, events, printed in pent)
    para = _bend_bar_note_counts(PARANOID, work, "4/4")
    assert para and all(events == printed for _, events, printed in para)


def _with_extra_fret(tabraw: TabRaw, pdf: Path, pattern: str, fret_of) -> TabRaw:
    """The mutant TabRaw: one extra fret candidate per matching technique word, on the nearest string line."""
    data = tabraw.model_copy(deep=True)
    extra: list[TabCandidate] = []
    with pymupdf.open(pdf) as doc:
        offsets = [0.0]
        for page in doc:
            offsets.append(offsets[-1] + float(page.rect.height))
        for index, page in enumerate(doc):
            for n, w in enumerate(page.get_text("words")):
                if not re.fullmatch(pattern, w[4]):
                    continue
                near = [c for c in data.candidates if c.kind == "fret" and c.page_index == index + 1
                        and abs(c.x - (w[0] + w[2]) / 2) < 40 and abs((c.y - offsets[index]) - (w[1] + w[3]) / 2) < 60]
                if not near:
                    continue
                base = min(near, key=lambda c: abs(c.x - (w[0] + w[2]) / 2) + abs((c.y - offsets[index]) - (w[1] + w[3]) / 2))
                value = fret_of(w[4])
                extra.append(base.model_copy(update={"id": f"mutant-{index}-{n}", "raw_text": str(value), "parsed_fret": value,
                                                    "x": (w[0] + w[2]) / 2, "y": offsets[index] + (w[1] + w[3]) / 2}))
    data.candidates = list(data.candidates) + extra
    assert extra, "the mutant must change something on the real source"
    return data


def test_mutant_parenthesised_bend_target_read_as_a_note_is_rejected(work: Path) -> None:
    pdf = _pdf(PARANOID)
    tabraw = TabRaw.from_json_file(_convert(PARANOID, work, "4/4") / "tab" / "tab_raw.json")
    mutant = _with_extra_fret(tabraw, pdf, r"\(\d+\)", lambda text: int(text.strip("()")))
    counts = _bend_bar_note_counts(PARANOID, work, "4/4", mutant)
    assert not all(events == printed for _, events, printed in counts) or len(counts) < len(
        _bend_bar_note_counts(PARANOID, work, "4/4"))


def test_mutant_bend_label_read_as_a_fret_digit_is_rejected(work: Path) -> None:
    pdf = _pdf(PENTATONIC)
    tabraw = TabRaw.from_json_file(_convert(PENTATONIC, work) / "tab" / "tab_raw.json")
    mutant = _with_extra_fret(tabraw, pdf, r"(?i)full", lambda text: 0)
    counts = _bend_bar_note_counts(PENTATONIC, work, None, mutant)
    assert not all(events == printed for _, events, printed in counts) or len(counts) < len(
        _bend_bar_note_counts(PENTATONIC, work))


def _vibrato_and_arc_bars(bars) -> list[int]:
    return [i for i in (14, 18) if _ties(bars[i])] + [i for i in (11, 12, 13, 15, 16, 17) if _ties(bars[i])]


def test_vibrato_and_hammer_pull_arcs_never_become_ties(work: Path) -> None:
    """Rejects: a vibrato squiggle or a hammer-on/pull-off arc read as a tie."""
    _, bars, _, _ = _read(PENTATONIC, work)
    assert _vibrato_and_arc_bars(bars) == []


def _vibrato_boxes(pdf: Path) -> list[tuple[float, float, float]]:
    """(x0, x1, y) of every vibrato squiggle: a row of eight or more wave shapes laid end to end (a bend's arrowhead
    is a lone shape of the same kind, so a run is what tells them apart)."""
    found = []
    with pymupdf.open(pdf) as doc:
        rows: dict[int, list[tuple[float, float]]] = {}
        for drawing in doc[0].get_drawings():
            r = drawing["rect"]
            if drawing["type"] == "f" and r.width < 12 and 2 < r.height < 6 and len(drawing["items"]) >= 8:
                rows.setdefault(round(r.y0), []).append((r.x0, r.x1))
        for y, pieces in rows.items():
            pieces.sort()
            if len(pieces) >= 8 and all(b[0] - a[0] <= 8 for a, b in zip(pieces, pieces[1:])):
                found.append((pieces[0][0], pieces[-1][1], float(y)))
    return found


def test_mutant_vibrato_squiggle_read_as_a_tie_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    squiggles = _vibrato_boxes(_pdf(PENTATONIC))
    assert len(squiggles) == 2
    original = rhythm._Reader._record

    def squiggle_is_a_tie(self, staff, system_index, system_number, bar_index, b, index, e, tie_start, tie_stop):
        record = original(self, staff, system_index, system_number, bar_index, b, index, e, tie_start, tie_stop)
        if record["status"] == "read" and any(x0 - 2 <= e["x"] <= x1 and staff.top - 40 <= y <= staff.bottom for x0, x1, y in squiggles):
            record["tie"] = {"start": True, "stop": False, "sources": ["vibrato"]}  # the mutant
        return record

    monkeypatch.setattr(rhythm._Reader, "_record", squiggle_is_a_tie)
    _, bars, _, _ = _read(PENTATONIC, work)
    assert _vibrato_and_arc_bars(bars) != []


def test_mutant_every_arc_is_a_tie_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hammer-on/pull-off arc between different frets read as a tie must fail the same property."""
    monkeypatch.setattr(rhythm, "_same_positions", lambda left, right: bool(left) and bool(right))
    _, bars, _, _ = _read(PENTATONIC, work)
    assert _vibrato_and_arc_bars(bars) != []


# --- named mutants of the reader fail on real sources --------------------------------------------

def _pentatonic_written(work: Path) -> int:
    return _read(PENTATONIC, work)[2]["summary"]["written_bars"]


def test_mutant_drop_beam_and_stem_reader_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _pentatonic_written(work) == 19
    monkeypatch.setattr(rhythm, "BEAM_MIN_WIDTH_SPACES", 1e9)  # no beam is ever read
    assert _pentatonic_written(work) < 19
    monkeypatch.undo()
    monkeypatch.setattr(rhythm, "STEM_MIN_BELOW_SPACES", 1e9)  # no stem is ever read
    assert _pentatonic_written(work) < 19


def test_mutant_drop_tie_handling_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    durations = _read(TWELVE_BAR, work)[0]
    assert any(r["tie"]["start"] for r in durations["events"])
    monkeypatch.setattr(rhythm._Reader, "_event_at", staticmethod(lambda *args, **kwargs: None))
    _, bars, route, _ = _read(TWELVE_BAR, work)
    assert route["summary"]["written_bars"] < 56 or not any(_ties(b) for b in bars)
    assert not any(_ties(b) for b in bars)


def test_mutant_drop_whole_note_chord_rule_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _read(PENTATONIC, work)[2]["summary"]["written_bars"] == 19
    monkeypatch.setattr(rhythm, "CIRCLE_MIN_SPACES", 1e9)  # no circle is ever read
    summary = _read(PENTATONIC, work)[2]["summary"]
    assert summary["written_bars"] < 19


def test_mutant_implied_rest_counted_as_printed_is_rejected(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = rhythm._implied_record

    def as_printed(*args, **kwargs):
        record = original(*args, **kwargs)
        record["rest"] = {"glyph": record["rest"]["glyph"], "source": "printed"}  # the mutant: not labelled implied
        return record

    monkeypatch.setattr(rhythm, "_implied_record", as_printed)
    summary = _read(TWELVE_BAR, work)[2]["summary"]
    assert summary.get("implied_rests", 0) == 0  # the honest reading counts exactly one
    with pytest.raises(AssertionError):
        assert summary["implied_rests"] == 1


def test_meter_comes_from_the_printed_numerals_not_a_default(work: Path) -> None:
    """Rejects: reading the heavy 3 of a 3/4 signature as a 1 (1/4 bars would total 960)."""
    durations = _read(PENTATONIC, work)[0]
    printed = Counter(c["time_signature"] for c in durations["bar_checks"])
    assert printed == {"4/4": 13, "3/4": 6}
    basis = durations["diagnostics"]["bar_time_signatures"]
    assert all(v["basis"] == "printed" for v in basis.values())
