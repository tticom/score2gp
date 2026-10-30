"""CFW-05: a read strike does not make an unresolved real-source bar writable.

The negative controls reject premature output with a dropped strike, an open
pitched replacement, or a displaced strike. Reference content stays private.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from score2gp.ir import ScoreIR
from score2gp.pdf_tab_bar_assembler import assemble_note_type_bars
from score2gp.tabraw import TabRaw

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
SOURCE = "Can't Find My Way Home (open chord shenanigans)"
BAR = 6  # source index; output/PDF bar number is 7


def _oracle():
    spec = importlib.util.spec_from_file_location("cfw05_oracle", ROOT / "tests/test_dur_02_oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def converted():
    pdf, reference = PRIVATE / (SOURCE + ".pdf"), PRIVATE / (SOURCE + ".gp")
    assert pdf.is_file() and reference.is_file(), "required CFW private inputs missing"
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfw05-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        run = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
            "--out", str(output), "--work-dir", str(folder / "build"),
            "--pdf-only-tab", "--time-signature", "4/4", "--no-strict",
        ], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        yield folder, output, reference


def _assert_refused(output):
    # Check the final package, independently of the route's success/refusal label.
    assert _oracle().read_gp_bars(output, include_grace=True)[BAR]["events"] is None


def _assert_strike_alignment(output, reference):
    oracle = _oracle()
    def strikes(package):
        events = oracle.read_gp_bars(package, include_grace=True)[BAR]["events"]
        return [(i, e["percussive_strikes"]) for i, e in enumerate(events)
                if e.get("percussive_strikes")]
    assert strikes(output) == strikes(reference)


def _write_probe(score, folder, name):
    source, produced = folder / (name + ".json"), folder / (name + ".gp")
    source.write_text(score.model_dump_json(), encoding="utf-8")
    # Also exercise the default relational GPIF writer in a fresh interpreter.
    run = subprocess.run([sys.executable, "-c",
                          "import sys; from score2gp.ir import ScoreIR; "
                          "from score2gp.gp_package import write_gp; "
                          "write_gp(ScoreIR.from_json_file(sys.argv[1]),sys.argv[2])",
                          str(source), str(produced)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return produced


def test_read_cross_keeps_unresolved_bar_located_and_empty(converted):
    """Reject deleting the overlap gate even though strike/duration reading succeeds."""
    folder, output, reference = converted
    route = json.loads((folder / "build/note-type-route.json").read_text())
    reading = json.loads((folder / "build/note-durations.json").read_text())
    bar = route["bars"][BAR]
    assert route["summary"]["written_bars"] == 18
    assert [(b["source_bar_index"], b["reason"]) for b in route["bars"] if b["status"] == "refused"] == [
        (3, "notehead_digit_count_mismatch"), (6, "note_duration_event_unread"),
        (9, "notehead_digit_count_mismatch"),
    ]
    assert bar["status"] == "refused" and bar["detail"] == "unsupported_overlapping_form"
    assert bar["location"]["bar_index"] == BAR
    assert bar["overlap_preservation_basis"] == "base_equivalent_refused"
    assert len(bar["unread_symbols"]) == 3  # REFUSE-01B: two of the former five are now read as naturals
    assert all(s["location"]["bar_index"] == BAR and len(s["location"]["bbox"]) == 4
               for s in bar["unread_symbols"])
    events = [e for e in reading["events"] if e["bar_index"] == BAR]
    assert all(e["status"] == "read" for e in events)
    assert sum(h["kind"] == "cross" for e in events for h in e["notehead"].get("heads", [])) == 1
    # Native Muted/Enable is the reference's strike flag; no fret is imported
    # into production, and the refused output must contain no invented event.
    expected = _oracle().read_gp_bars(reference, include_grace=True)[BAR]
    assert sum(len(e.get("percussive_strikes", [])) for e in expected["events"]) == 1
    _assert_refused(output)


@pytest.mark.parametrize("mutant", ["drop_strike", "ordinary_fret_zero", "move_one_string"])
def test_real_source_premature_write_mutants_fail_refusal_contract(converted, mutant):
    """All three unsafe writes fail the same final-output assertion as the real run.

    Remove the unresolved-symbol gate only in this negative control, then use
    the real reader/assembler events. This does not claim a faithful written bar.
    """
    folder, output, reference = converted
    _assert_refused(output)
    reading = json.loads((folder / "build/note-durations.json").read_text())
    reading["diagnostics"]["unread_symbols"] = []
    tab = TabRaw.from_json_file(folder / "build/tab/tab_raw.json")
    candidates = [c for c in tab.candidates if c.kind == "percussive-strike"
                  or (c.kind == "fret" and c.parsed_fret is not None)]
    score = ScoreIR.from_json_file(folder / "build/score.ir.json")
    bars, route = assemble_note_type_bars(candidates, reading, track_id=score.tracks[0].id)
    assert route["bars"][BAR]["status"] == "written"
    score.bars[BAR] = bars[BAR]
    probe = _write_probe(score, folder, mutant + "-unproven")
    # A diagnostic probe establishes only the strike's event/string pairing,
    # not fidelity of the other techniques or permission to write this bar.
    _assert_strike_alignment(probe, reference)
    strike_event, strike = next((e, n) for e in bars[BAR].events for n in e.notes if n.is_dead)
    if mutant == "drop_strike":
        strike_event.notes.remove(strike)
    elif mutant == "ordinary_fret_zero":
        strike.is_dead = False
        strike.fret = 0
        strike.pitch = next(s.pitch for s in score.tracks[0].tuning.strings if s.number == strike.string)
    else:
        strike.string = strike.string + 1 if strike.string < 6 else strike.string - 1
    produced = _write_probe(score, folder, mutant)
    with pytest.raises(AssertionError):
        _assert_strike_alignment(produced, reference)
    with pytest.raises(AssertionError):
        _assert_refused(produced)
