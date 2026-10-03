"""SPELL-01: black keys are spelled from printed accidentals, then the read key, else a reported default.

Everything here is public: hand-built IR, public generated PDFs and source-text mutants. No
private score is read.
"""

from __future__ import annotations

import re
import sys
import types
import zipfile
from pathlib import Path

import pytest

import score2gp.black_key_spelling as spelling_module
from score2gp.black_key_spelling import apply_black_key_spelling
from score2gp.gp_package import write_gp
from score2gp.ir import KeySignature, Note, NoteSpelling, ScoreIR, TieTechnique
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf_tab_event_factory import build_note_type_event, unjoined_accidentals

FIXTURES = Path(__file__).parent / "fixtures/pdf/omit_01"
BB4, BB3, FS4, CS4 = 70, 58, 66, 61  # Bb4, Bb3, F#4, C#4 (the pitch is the same for either name)


def _score(bars: list[tuple[int | None, list[list[tuple]]]]) -> ScoreIR:
    """Bars of (fifths or None, events); an event is a list of (pitch, printed, tie) notes."""
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    template = score.bars[0]
    built = []
    for number, (fifths, events) in enumerate(bars, start=1):
        bar = template.model_copy(deep=True)
        bar.index = number
        bar.key_signature = KeySignature(fifths=fifths) if fifths is not None else None
        bar.events = []
        for i, notes in enumerate(events):
            event = template.events[0].model_copy(deep=True)
            event.id = f"bar-{number}-event-{i + 1}"
            event.timing.bar_index = number
            event.timing.onset_ticks = i * 960
            event.notes = [
                Note(string=1, fret=0, pitch=pitch,
                     spelling=NoteSpelling(accidental=printed, source="printed") if printed else None,
                     techniques=[TieTechnique(state=tie)] if tie else [])
                for pitch, printed, tie in notes
            ]
            bar.events.append(event)
        built.append(bar)
    score.bars = built
    return score


def _spelled(bars, apply=apply_black_key_spelling):
    score = _score(bars)
    pitches = [n.pitch for b in score.bars for e in b.events for n in e.notes]
    warnings = apply(score.bars)
    assert [n.pitch for b in score.bars for e in b.events for n in e.notes] == pitches  # pitch never changes
    return [[(n.spelling.accidental, n.spelling.source) if n.spelling else None
             for e in b.events for n in e.notes] for b in score.bars], warnings


def _scenarios(apply) -> list[str]:
    """Every rule, as observed outcomes; the list of failed expectations is empty when all hold."""
    failed = []

    def expect(name, got, want):
        if got != want:
            failed.append(f"{name}: {got!r} != {want!r}")

    spelled, w = _spelled([(-2, [[(BB4, None, None)]])], apply)
    expect("flat key", (spelled, w), ([[("flat", "key")]], []))
    spelled, w = _spelled([(2, [[(FS4, None, None)]])], apply)
    expect("sharp key", (spelled, w), ([[("sharp", "key")]], []))
    spelled, w = _spelled([(0, [[(BB4, "flat", None)]])], apply)
    expect("printed flat in C", (spelled, w), ([[("flat", "printed")]], []))
    spelled, w = _spelled([(-2, [[(BB4, "sharp", None)]])], apply)
    expect("printed sharp beats a flat key", (spelled, w), ([[("sharp", "printed")]], []))
    spelled, w = _spelled([(0, [[(BB4, "flat", None)], [(BB4, None, None)], [(BB3, None, None)]]),
                           (0, [[(BB4, None, None)]])], apply)
    expect("persists in the bar for that pitch class, resets at the barline",
           spelled, [[("flat", "printed"), ("flat", "printed_carried"), ("flat", "printed_carried")],
                     [("sharp", "default")]])
    spelled, w = _spelled([(0, [[(BB4, "flat", None)], [(CS4, None, None)]])], apply)
    expect("persistence is for that pitch class only", spelled, [[("flat", "printed"), ("sharp", "default")]])
    spelled, w = _spelled([(None, [[(BB4, None, None)]]), (0, [[(CS4, None, None)], [(BB4, None, None)]])], apply)
    expect("no evidence writes the sharp default", spelled,
           [[("sharp", "default")], [("sharp", "default"), ("sharp", "default")]])
    expect("no evidence is reported, located by bar",
           [(x.code, x.severity, "Bar 1:" in x.message) for x in w] + [len(w)],
           [("spelling_unevidenced", "warning", True), ("spelling_unevidenced", "warning", False), 2])
    spelled, w = _spelled([(-1, [[(BB4, "flat", "start")]]), (0, [[(BB4, None, "stop")]])], apply)
    expect("a tie carries the spelling over the barline", (spelled, w),
           ([[("flat", "printed")], [("flat", "printed_carried")]], []))
    spelled, w = _spelled([(-1, [[(62, None, None), (60, None, None)]])], apply)
    expect("white keys carry no spelling", (spelled, w), ([[None, None]], []))
    return failed


def test_all_rules_hold() -> None:
    assert _scenarios(apply_black_key_spelling) == []


# --- mutants: each rule removed must fail the scenarios ---------------------------------------

_MUTANTS = {
    "printed accidental ignored": ("if note.spelling is not None:", "if False:"),
    "persistence removed": ("elif note.pitch % 12 in carried:", "elif False:"),
    "key direction removed": ("elif fifths != 0:", "elif False:"),
    "key direction inverted": ('"flat" if fifths < 0 else "sharp"', '"sharp" if fifths < 0 else "flat"'),
    "default unreported": ("if unevidenced:", "if False:"),
    "persistence never reset": ("        carried: dict[int, str] = {}\n", "        pass\n"),
    "tie carry removed": ("elif _tied_from_before(note) and note.pitch in tie_spellings:", "elif False:"),
}


def _mutant(old: str, new: str):
    source = Path(spelling_module.__file__).read_text(encoding="utf-8")
    assert source.count(old) == 1
    source = source.replace(old, new)
    if old.startswith("        carried"):
        source = source.replace("    tie_spellings: dict[int, NoteSpelling] = {}\n",
                                "    tie_spellings: dict[int, NoteSpelling] = {}\n    carried: dict[int, str] = {}\n")
    module = types.ModuleType("score2gp._spell_mutant")
    module.__package__ = "score2gp"
    exec(compile(source, "mutant", "exec"), module.__dict__)
    return module.apply_black_key_spelling


@pytest.mark.parametrize("name", sorted(_MUTANTS))
def test_each_rule_removed_fails(name: str) -> None:
    assert _scenarios(_mutant(*_MUTANTS[name])), f"mutant {name!r} survived"


# --- writer and IR ----------------------------------------------------------------------------

@pytest.fixture
def product_gpif_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "modules", {k: v for k, v in sys.modules.items() if "pytest" not in k})
    monkeypatch.setattr(sys, "argv", [a for a in sys.argv if "pytest" not in a])


def _written(tmp_path: Path, spelling: NoteSpelling | None, pitch: int) -> tuple[list[str], list[str], list[str]]:
    score = _score([(None, [[(pitch, None, None)]])])
    score.bars[0].events[0].notes[0].spelling = spelling
    out = tmp_path / "s.gp"
    write_gp(score, out)
    with zipfile.ZipFile(out) as zf:
        text = zf.read("Content/score.gpif").decode("utf-8")
    return (re.findall(r"<Step>(\w)</Step>", text), re.findall(r"<Accidental>([^<]*)</Accidental>", text),
            re.findall(r"<Number>(\d+)</Number>", text))


def test_writer_spells_flats_with_b(tmp_path: Path, product_gpif_path: None) -> None:
    steps, accidentals, _ = _written(tmp_path, NoteSpelling(accidental="flat", source="key"), BB4)
    assert steps == ["B", "B"] and accidentals == ["b", "b"]


@pytest.mark.parametrize("spelling", [None, NoteSpelling(accidental="sharp", source="key"),
                                      NoteSpelling(accidental="sharp", source="default")])
def test_writer_keeps_the_sharp_for_sharps_and_old_ir(tmp_path: Path, product_gpif_path: None, spelling) -> None:
    steps, accidentals, _ = _written(tmp_path, spelling, BB4)
    assert steps == ["A", "A"] and accidentals == ["#", "#"]


def test_flat_and_sharp_spellings_write_the_same_midi(tmp_path: Path, product_gpif_path: None) -> None:
    flat = _written(tmp_path, NoteSpelling(accidental="flat", source="key"), BB4)[2]
    sharp = _written(tmp_path, NoteSpelling(accidental="sharp", source="key"), BB4)[2]
    assert flat == sharp and str(BB4) in flat


def test_a_flat_spelling_on_a_white_key_is_ignored(tmp_path: Path, product_gpif_path: None) -> None:
    steps, accidentals, _ = _written(tmp_path, NoteSpelling(accidental="flat", source="key"), 62)
    assert steps == ["D", "D"] and "b" not in accidentals and "#" not in accidentals


def test_old_ir_without_spelling_still_loads() -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    assert score.schema_version in ("0.1.0", "0.1.1", "0.1.2")
    assert all(n.spelling is None for b in score.bars for e in b.events for n in e.notes)


# --- reading and joining the printed accidental -----------------------------------------------

def test_public_pdfs_read_printed_flat_and_sharp_beside_heads() -> None:
    flat = read_note_durations(FIXTURES / "key_and_note_accidental.pdf", time_signature=(4, 4))["events"]
    sharp = read_note_durations(FIXTURES / "note_accidental.pdf", time_signature=(4, 4))["events"]
    assert [a["direction"] for e in flat for a in e.get("accidentals", [])] == ["flat"]
    assert [a["direction"] for e in sharp for a in e.get("accidentals", [])] == ["sharp"]
    assert flat[0]["accidentals"][0]["pitch_class"] == 10  # the head's staff step names B; a flat gives Bb


def test_a_pdf_with_no_accidental_beside_a_head_records_none() -> None:
    events = read_note_durations(FIXTURES / "key_signatures.pdf", time_signature=(4, 4))["events"]
    assert not any("accidentals" in e for e in events)


def _record(accidentals):
    return {"kind": "note", "tie": {}, "tuplet": None, "dots": {"count": 0}, "written": "quarter",
            "duration_quarters": "1", "accidentals": accidentals}


def test_factory_joins_the_printed_accidental_to_the_note_of_that_pitch_class_only() -> None:
    positions = [(1, 6), (2, 3)]  # Bb4/A#4 (70) and D4 (62)
    record = _record([{"direction": "flat", "pitch_class": 10, "source": "p0:t1"}])
    event = build_note_type_event(record, positions=positions, candidates=[], output_bar_idx=1, event_idx=0,
                                  onset_ticks=0, track_id="g")
    assert [(n.pitch, n.spelling and (n.spelling.accidental, n.spelling.source)) for n in event.notes] == [
        (70, ("flat", "printed")), (62, None)]
    assert unjoined_accidentals(record, positions) == []


def test_an_accidental_no_tab_note_has_is_reported_not_forced() -> None:
    record = _record([{"direction": "flat", "pitch_class": 3, "source": "p0:t9"}])
    assert unjoined_accidentals(record, [(1, 0)]) == record["accidentals"]
    event = build_note_type_event(record, positions=[(1, 0)], candidates=[], output_bar_idx=1, event_idx=0,
                                  onset_ticks=0, track_id="g")
    assert event.notes[0].spelling is None
    warnings = apply_black_key_spelling([], [{"output_bar_index": 4, "unjoined_accidentals": [
        {"event_index": 2, "sources": ["p0:t9"]}]}])
    assert [w.code for w in warnings] == ["printed_accidental_unjoined"] and "Bar 4" in warnings[0].message
