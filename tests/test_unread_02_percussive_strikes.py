"""Real-source strike acceptance. The two model checks supplement infrastructure only."""
import json
import importlib.util
import io
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from score2gp.ir import Note, ScoreIR
from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.black_key_spelling import apply_black_key_spelling
from score2gp.gpif import percussive_strike_storage
from score2gp.gp_package import extract_score_ir_from_gp, write_gp
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import _extract_pdf_text_candidates
from score2gp.tabraw import TabRaw, make_tab_candidate
from score2gp.compare import compare_bar_scores, load_bar_data

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "G-Am-C-Lick": [(bar, 6, 240) for bar in (3, 5, 7) for _ in range(2)],
    "E_Chord_Lick_Chord": [(bar, 6, 480) for bar in (5, 7, 13)],
}


def _strikes(bars):
    return [(event.timing.bar_index, note.string, event.timing.duration_ticks)
            for bar in bars for event in bar.events for note in event.notes if note.is_dead]


def _assert_strikes(bars, name):
    assert _strikes(bars) == EXPECTED[name]
    assert all(note.fret is None and note.pitch is None and note.spelling is None
               for bar in bars for event in bar.events for note in event.notes if note.is_dead)


@pytest.fixture(scope="module", params=list(EXPECTED))
def converted(request):
    name = request.param
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread02-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        result = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf",
            str(ROOT / "fixtures/private" / (name + ".pdf")), "--out", str(output),
            "--work-dir", str(folder / "build"), "--pdf-only-tab",
            "--time-signature", "4/4", "--no-strict",
        ], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-1200:]
        score = ScoreIR.from_json_file(folder / "build/score.ir.json")
        reading = json.loads((folder / "build/note-durations.json").read_text())
        tab = TabRaw.from_json_file(folder / "build/tab/tab_raw.json")
        yield name, score, output, reading, tab, folder


def test_real_source_written_strikes_keep_string_duration_and_absence(converted):
    name, score, output, reading, tab, folder = converted
    _assert_strikes(score.bars, name)
    apply_black_key_spelling(score.bars)
    _assert_strikes(score.bars, name)
    for bar in score.bars:
        if bar.events:
            assert sum(e.timing.duration_ticks for e in bar.events) == 3840


def test_real_source_strike_events_round_trip_through_summary_with_absence(converted):
    name, score, output, reading, tab, folder = converted
    if name == "G-Am-C-Lick":
        _assert_strikes(extract_score_ir_from_gp(output).bars, name)
    # Reproducible strike-event extract from the normal source conversion:
    # retain source IDs, string, timing and provenance, with no invented event.
    # E_Chord also contains grace/empty-beat summary-reader limitations outside
    # this absence contract; this is not a whole-file round-trip claim.
    strike_score = score.model_copy(deep=True)
    strike_score.bars = [b for b in strike_score.bars
                        if any(n.is_dead for e in b.events for n in e.notes)]
    for bar in strike_score.bars:
        bar.events = [e for e in bar.events if any(n.is_dead for n in e.notes)]
    summary = folder / "summary.gp"
    write_gp(strike_score, summary)
    _assert_strikes(extract_score_ir_from_gp(summary).bars, name)
    compared = load_bar_data(summary)
    assert sum(n.is_dead for b in compared for e in b.events for n in e.notes) == len(EXPECTED[name])
    assert compare_bar_scores(compared, strike_score)["matches"]


def test_real_source_storage_fret_is_writer_only_with_rule_receipts(converted):
    name, score, output, reading, tab, folder = converted
    with zipfile.ZipFile(output) as package:
        root = ET.fromstring(package.read("Content/score.gpif"))
    written = [int(n.findtext("Properties/Property[@name='Fret']/Fret"))
               for n in root.findall("Notes/Note") if n.find("DeadNote") is not None]
    expected = ([12] * 6, "printed_head_position") if name == "G-Am-C-Lick" else ([9, 5, 9], "next_same_string")
    receipts = [percussive_strike_storage(score, event, note)
                for bar in score.bars for event in bar.events for note in event.notes if note.is_dead]
    assert written == expected[0] == [fret for fret, pitch, rule in receipts]
    assert [rule for fret, pitch, rule in receipts] == [expected[1]] * len(written)
    _assert_strikes(score.bars, name)


@pytest.mark.parametrize("dead", [False, True])
def test_real_source_comparison_rejects_fret_zero_in_both_directions(converted, dead):
    name, score, output, reading, tab, folder = converted
    expected = load_bar_data(score)
    assert compare_bar_scores(expected, expected)["matches"]
    mutant = score.model_copy(deep=True)
    for bar in mutant.bars:
        for event in bar.events:
            for note in event.notes:
                if note.is_dead:
                    note.is_dead = dead
                    note.fret = 0
                    note.pitch = 40
    changed = load_bar_data(mutant)
    for actual, reference in ((changed, expected), (expected, changed)):
        result = compare_bar_scores(actual, reference)
        assert not result["matches"]
        fields = [m["field"].rsplit(".", 1)[-1] for m in result["mismatches"]]
        assert fields.count("fret") == len(EXPECTED[name])
        assert fields.count("pitch") == len(EXPECTED[name])
        assert fields.count("is_dead") == (0 if dead else len(EXPECTED[name]))


def test_real_source_comparison_summary_keeps_strike_absence(converted):
    name, score, output, reading, tab, folder = converted
    summary = [bar.to_dict() for bar in load_bar_data(score)]
    strikes = [n for bar in summary for event in bar["events"] for n in event["notes"]
               if n.get("is_dead")]
    assert len(strikes) == len(EXPECTED[name])
    assert all(n["fret"] is None and n["pitch"] is None for n in strikes)
    assert compare_bar_scores(load_bar_data(summary), load_bar_data(score))["matches"]


def test_real_source_native_gp_flag_and_independent_oracle_reject_dropped_flag(converted):
    name, score, output, reading, tab, folder = converted
    spec = importlib.util.spec_from_file_location("unread02_oracle", ROOT / "tests/test_dur_02_oracle.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    bars = oracle.read_gp_bars(output)
    assert sum(len(e.get("percussive_strikes", [])) for b in bars for e in b["events"] or []) == len(EXPECTED[name])
    with zipfile.ZipFile(output) as package:
        root = ET.fromstring(package.read("Content/score.gpif"))
    strikes = [n for n in root.findall("Notes/Note") if n.find("DeadNote") is not None]
    assert len(strikes) == len(EXPECTED[name])
    for note in strikes:
        props = note.find("Properties")
        native = props.find("Property[@name='Muted']")
        assert native is not None and native.find("Enable") is not None
        props.remove(native)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("Content/score.gpif", ET.tostring(root))
    result = oracle.compare_gp(output, buffer.getvalue())
    assert len(result["differences"]) == len(EXPECTED[name])
    assert {d["field"] for d in result["differences"]} == {"percussive_strikes"}


def test_real_source_native_gp_reader_keeps_absence_without_legacy_summary(converted):
    name, score, output, reading, tab, folder = converted
    # A provenance-preserving extract avoids unrelated empty-beat/grace reader
    # limitations. Keep the source events, but require the native GPIF flag
    # alone to carry the class, without Score/Bars or DeadNote fallback.
    strike_score = score.model_copy(deep=True)
    # Keep the complete bar topology and source bar numbers in this extract.
    for bar in strike_score.bars:
        bar.events = [e for e in bar.events if any(n.is_dead for n in e.notes)]
    package_path = folder / "native-only.gp"
    source_ir = folder / "native-only.json"
    source_ir.write_text(strike_score.model_dump_json(), encoding="utf-8")
    # The existing writer selects hierarchical output inside pytest. A normal
    # process must exercise its production relational tables instead.
    run = subprocess.run([sys.executable, "-c",
                          "import sys; from score2gp.ir import ScoreIR; "
                          "from score2gp.gp_package import write_gp; "
                          "write_gp(ScoreIR.from_json_file(sys.argv[1]),sys.argv[2])",
                          str(source_ir), str(package_path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    with zipfile.ZipFile(package_path) as package:
        root = ET.fromstring(package.read("Content/score.gpif"))
    summary = root.find("Score/Bars")
    if summary is not None:
        root.find("Score").remove(summary)
    assert root.find("Beats") is not None
    for note in root.findall("Notes/Note"):
        if note.find("DeadNote") is not None:
            note.remove(note.find("DeadNote"))
    with zipfile.ZipFile(package_path, "w") as package:
        package.writestr("Content/score.gpif", ET.tostring(root))
    recovered = extract_score_ir_from_gp(package_path)
    # Relational GPIF renumbers this event extract's bars from one.
    assert [(n.string, e.timing.duration_ticks, n.is_dead, n.fret, n.pitch)
            for b in recovered.bars for e in b.events for n in e.notes] == [
                (string, duration, True, None, None) for bar, string, duration in EXPECTED[name]]


def _assemble(reading, tab):
    candidates = [c for c in tab.candidates if (c.kind == "fret" and c.parsed_fret is not None)
                  or c.kind == "percussive-strike"]
    return assembler.assemble_note_type_bars(candidates, reading, track_id="guitar")[0]


def test_drop_x_mutant_fails_the_real_source_assertions(converted):
    name, score, output, reading, tab, folder = converted
    _assert_strikes(_assemble(reading, tab), name)
    dropped = tab.model_copy(update={"candidates": [c for c in tab.candidates if c.kind != "percussive-strike"]})
    with pytest.raises(AssertionError):
        _assert_strikes(_assemble(reading, dropped), name)


def test_fret_zero_mutant_fails_the_real_source_assertions(converted, monkeypatch):
    name, score, output, reading, tab, folder = converted
    _assert_strikes(_assemble(reading, tab), name)
    original = assembler.build_note_type_event
    def fret_zero(*args, **kwargs):
        event = original(*args, **kwargs)
        for note in event.notes:
            if note.is_dead:
                note.fret = 0
                note.pitch = 40
        return event
    monkeypatch.setattr(assembler, "build_note_type_event", fret_zero)
    with pytest.raises(AssertionError):
        _assert_strikes(_assemble(reading, tab), name)


def test_real_source_x_without_notation_owners_stays_located_and_unwritten():
    # These X tokens omit strings from chord voicings; there is no notation
    # owner from which a strike duration could be read. Keep that distinction.
    source = ROOT / "fixtures/private/5_Grateful_Dead_Intros.pdf"
    assert source.is_file(), "required approved private source missing"
    reading = read_note_durations(source)
    candidates = _extract_pdf_text_candidates(source, [], defaultdict(int))
    tab = TabRaw.model_validate({"candidates": candidates})
    strikes = [c for c in tab.candidates if c.kind == "percussive-strike"]
    assert len(strikes) == 6
    assert all(c.string == 5 and c.parsed_fret is None for c in strikes)
    bars, route = assembler.assemble_note_type_bars(strikes, reading, track_id="guitar")
    assert bars == [] and route["summary"]["written_bars"] == 0
    refused = route["located_refusals"]
    assert len(refused) == len(strikes)
    assert {r["candidate_id"] for r in refused} == {c.id for c in strikes}
    assert all(r["class"] == "percussive_strike"
               and r["reason"] == "percussive_strike_without_owning_note"
               and r["location"]["page_index"] == 0
               and r["location"]["string"] == 5
               and r["location"]["bar_index"] == 5
               and r["location"]["bbox"] for r in refused)


def test_real_source_muted_strums_stay_out_of_scope_at_their_events():
    source = ROOT / "fixtures/private/Melodic_Expressions.pdf"
    assert source.is_file(), "required approved private source missing"
    reading = read_note_durations(source, pages=(2, 2))
    strums = [e for e in reading["events"] if sum(
        h["kind"] == "cross" for h in (e.get("notehead") or {}).get("heads", [])) > 1]
    assert len(strums) == 29  # 25 three-head and four four-head source events.
    system_space = {s["system_index"]: s["staff_space"] for s in reading["systems"]}
    for event in strums:
        matched, refusal = assembler._match_bar([event], [], system_space[event["system_index"]], None)
        assert matched == []
        assert refusal["reason"] == "multiple_percussive_heads_out_of_scope"
        assert refusal["event_index"] == event["event_index"]


def test_percussive_strike_candidate_never_parses_as_a_fret():
    candidate = make_tab_candidate(candidate_id="strike", raw_text="X", page_index=1,
                                   bbox_values=None, confidence=1, string=3)
    assert candidate.kind == "percussive-strike"
    assert candidate.parsed_strike == "X"
    assert candidate.parsed_fret is None


def test_percussive_strike_has_no_source_fret_or_pitch():
    strike = Note(string=3, is_dead=True)
    assert strike.fret is None and strike.pitch is None
    with pytest.raises(ValueError):
        Note(string=3)


@pytest.mark.parametrize("name,count", [("G-Am-C-Lick", 20), ("E_Chord_Lick_Chord", 3),
                                      ("Can't Find My Way Home (open chord shenanigans)", 1)])
def test_real_source_crosses_have_owned_durations(name, count):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    heads = [(event, head) for event in result["events"]
             for head in (event.get("notehead") or {}).get("heads", [])
             if head["kind"] == "cross"]
    assert len(heads) == count
    assert all(event["status"] == "read" and event["stem"] and event["duration_quarters"]
               for event, head in heads)
