"""NOTAB-01: genuine-source partial tie ownership, including final GPIF.

The printed-page ledger is retained as a digest (counts and indices only).
Neither source has a reference: they are not independently verified.
Synthetic tests carry zero acceptance weight; none are used here.
DROP_UNRELATED_UNISON_RULE restores the old all-heads-must-be-unique rule.
"""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import pymupdf
from typer.testing import CliRunner

from chord_gpif import gpif_beats, gpif_root, gpif_chords
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"
SOURCE = "Melodic_Expressions_Chap_19_.pdf"
BAR = 28
ROW_LEDGER = "af4348f863c11e40308eb850fa535d7d2fef5b69eb887a450c37e639c79e11fd"
WORD_LEDGER = "930002af1f385393c9a3fe69d6e72ab5519b70fd5c32c769059e60a18fe7ad11"


def _ledger(output, bar=BAR, *, palm_mute=False):
    """Read native relationships directly, independently of the product reader."""
    root = gpif_root(output)
    chords = gpif_chords(root)
    notes = {n.get("id"): n for n in root.findall("Notes/Note")}
    rhythms = {r.get("id"): r for r in root.findall("Rhythms/Rhythm")}
    result = []
    for (bi, ei), beat in sorted(gpif_beats(root).items()):
        if bi != bar:
            continue
        rhythm = rhythms[beat.find("Rhythm").get("ref")]
        dot = rhythm.find("AugmentationDot")
        tuplet = rhythm.find("PrimaryTuplet")
        played = []
        for ident in beat.findtext("Notes", "").split():
            note = notes[ident]
            props = {p.get("name"): p for p in note.findall("Properties/Property")}
            tie = note.find("Tie")
            played.append([int(props["String"].findtext("String")),
                           int(props["Fret"].findtext("Fret")),
                           tie is not None and tie.get("origin") == "true",
                           tie is not None and tie.get("destination") == "true"])
            if palm_mute:
                played[-1].append(note.find("PalmMute") is not None)
        result.append({"written": rhythm.findtext("NoteValue"),
                       "dots": int(dot.get("count")) if dot is not None else 0,
                       "tuplet": dict(tuplet.attrib) if tuplet is not None else None,
                       "chord": chords.get((bi, ei)),
                       "notes": sorted(played)})
    return result


def _check_partial_tie(tmp_path):
    source = PRIVATE / SOURCE
    assert source.is_file(), "REQUIRED_NOTAB_01_SOURCE_MISSING"
    output = tmp_path / "output.gp"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                     "--out", str(output), "--work-dir", str(tmp_path / "build")])
    assert result.exit_code == 0, result.output[-1000:]
    route = json.loads((tmp_path / "build/note-type-route.json").read_bytes())
    durations = json.loads((tmp_path / "build/note-durations.json").read_bytes())
    chord = next(e for e in durations["events"] if e["bar_index"] == BAR and e["event_index"] == 1)
    assert len(chord["tie"].get("stop_head_ranks", [])) == 2, "UNIQUE_TIED_HEADS_NOT_READ"
    assert route["bars"][BAR]["reason"] == "tab_chord_arrow_unread", "UNREAD_STROKE_WRITTEN"
    assert route["bars"][BAR]["refusal_evidence"]["cause"] == "straight_chord_arrow_unread"
    assert _ledger(output) == [], "UNREAD_STROKE_WRITTEN"


def test_unique_tied_heads_survive_unrelated_duplicate_head_position(tmp_path):
    """Read the unique endpoints; reject writing the chord while its stroke arrow is unread."""
    _check_partial_tie(tmp_path)


def test_mutant_drop_unrelated_unison_rule_fails_real_source(tmp_path, monkeypatch):
    """DROP_UNRELATED_UNISON_RULE must fail the same final-output contract."""
    real = nd._record_tie_end

    def old_rule(tie, side, event, head, staff, space):
        real(tie, side, event, head, staff, space)
        positions = [nd._staff_position(h, staff, space) for h in event["_heads"]]
        if len(set(positions)) != len(positions):
            tie.pop(f"{side}_head_ranks", None)

    monkeypatch.setattr(nd, "_record_tie_end", old_rule)
    with pytest.raises(AssertionError, match="UNIQUE_TIED_HEADS_NOT_READ"):
        _check_partial_tie(tmp_path)


def test_mutant_drop_unread_chord_arrow_guard_fails_real_source(tmp_path, monkeypatch):
    """Reject emitting a chord while dropping the page's unread stroke arrow."""
    from score2gp import pdf_tab_digit_recovery as recovery
    monkeypatch.setattr(recovery, "unread_new_chord_arrows", lambda *args: {})
    with pytest.raises(AssertionError, match="UNREAD_STROKE_WRITTEN"):
        _check_partial_tie(tmp_path)


def _check_printed_rows(tmp_path):
    source = PRIVATE / "PARANOID - BLACK SABBATH.pdf"
    assert source.is_file(), "REQUIRED_NOTAB_01_ROW_SOURCE_MISSING"
    output = tmp_path / "output.gp"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                     "--out", str(output), "--work-dir", str(tmp_path / "build")])
    assert result.exit_code == 0, result.output[-1000:]
    route = json.loads((tmp_path / "build/note-type-route.json").read_bytes())
    for bar in (8, 32):
        assert route["bars"][bar]["status"] == "written", "PRINTED_TAB_ROWS_DISCARDED"
        ledger = _ledger(output, bar, palm_mute=True)
        digest = hashlib.sha256(json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert digest == ROW_LEDGER, "PRINTED_ROWS_NOT_FAITHFUL"
    for bar in (7, 31):
        assert route["bars"][bar]["status"] == "refused", "UNPRINTED_REST_INVENTED"
    for bar in (9, 33):
        assert route["bars"][bar]["status"] == "refused", "UNREAD_REPEAT_MARK_WRITTEN"
        assert route["bars"][bar]["refusal_evidence"]["tab_digit_recovery_withheld_cause"] == "printed_tab_mark_unread"
        assert _ledger(output, bar) == [], "UNREAD_REPEAT_MARK_WRITTEN"


def test_printed_rows_reach_faithful_gpif_without_inventing_rests(tmp_path):
    """Reject DROP_PRINTED_ROW_READER and fabricated completion of a partial bar."""
    _check_printed_rows(tmp_path)


@pytest.mark.parametrize("mutant", ["drop_rows", "drop_tab_heads", "drop_palm", "invent_rest"])
def test_printed_row_mutants_fail_real_output_contract(tmp_path, monkeypatch, mutant):
    """Reject dropping a new reader handoff or completing a bar with an unprinted rest."""
    from score2gp import pdf_tab_bar_assembler as assembler
    from score2gp import pdf_tab_digit_recovery as recovery

    message = "PRINTED_TAB_ROWS_DISCARDED"
    if mutant == "drop_rows":
        monkeypatch.setattr(recovery, "recover_printed_bar_digits", lambda *args: ([], {}))
    elif mutant == "drop_tab_heads":
        monkeypatch.setattr(assembler, "_read_recovered_tab_heads", lambda record, candidates: record)
    elif mutant == "drop_palm":
        monkeypatch.setattr(recovery, "_palm_spans", lambda *args: [])
        message = "PRINTED_ROWS_NOT_FAITHFUL"
    else:
        real = recovery.recover_printed_bar_digits

        def invent_completion(source, reading, route, candidates):
            unguarded = {**reading, "bar_checks": [
                {k: v for k, v in check.items() if k != "implied_rest_quarters"}
                for check in reading["bar_checks"]]}
            return real(source, unguarded, route, candidates)

        monkeypatch.setattr(recovery, "recover_printed_bar_digits", invent_completion)
        message = "UNPRINTED_REST_INVENTED"
    with pytest.raises(AssertionError, match=message):
        _check_printed_rows(tmp_path)


def _check_unread_marks(tmp_path):
    """Exact page extract retains real engraving, not generated notation."""
    source = PRIVATE / "Melodic_Expressions.pdf"
    assert source.is_file(), "REQUIRED_NOTAB_01_MARK_SOURCE_MISSING"
    # The old extractor treats input paths containing 'test' as generated PDFs.
    # Keep the genuine input extract in a neutral, ignored directory.
    work = PRIVATE.parents[1] / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="notab_slice_", dir=work) as directory:
        pdf = Path(directory) / "slice.pdf"
        with pymupdf.open(source) as original, pymupdf.open() as cut:
            cut.insert_pdf(original, from_page=8, to_page=8)
            cut.save(pdf)
        assert "test" not in str(pdf).lower()
        output = tmp_path / "output.gp"
        result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                         "--out", str(output), "--work-dir", str(tmp_path / "build")])
        assert result.exit_code == 0, result.output[-1000:]
    route = json.loads((tmp_path / "build/note-type-route.json").read_bytes())
    for bar, cause, message in ((7, "printed_technique_owner_unread", "UNREAD_TECHNIQUE_WRITTEN"),
                                (9, "printed_tab_mark_unread", "UNREAD_TAB_MARK_WRITTEN")):
        assert route["bars"][bar]["status"] == "refused", message
        assert route["bars"][bar]["refusal_evidence"]["tab_digit_recovery_withheld_cause"] == cause
        assert _ledger(output, bar) == [], message


def test_new_row_reader_refuses_unowned_marks_on_real_page(tmp_path):
    """Reject DROP_TECHNIQUE_GUARD and DROP_TAB_INK_GUARD: no incomplete bar is emitted."""
    _check_unread_marks(tmp_path)


@pytest.mark.parametrize("guard,message", [("_unread_technique", "UNREAD_TECHNIQUE_WRITTEN"),
                                            ("_unread_tab_ink", "UNREAD_TAB_MARK_WRITTEN")])
def test_mutant_drop_unowned_mark_guard_fails_real_page(tmp_path, monkeypatch, guard, message):
    """The genuine-page final-output contract must reject either missing guard."""
    from score2gp import pdf_tab_digit_recovery as recovery
    monkeypatch.setattr(recovery, guard, lambda *args: False)
    if guard == "_unread_technique":
        # The wrong implementation admits unread annotations; independent ink
        # and word guards would otherwise still refuse this same genuine bar.
        monkeypatch.setattr(recovery, "_unread_tab_ink", lambda *args: False)
        monkeypatch.setattr(recovery, "_unread_number_word", lambda *args: None)
    with pytest.raises(AssertionError, match=message):
        _check_unread_marks(tmp_path)


def _check_missing_word(tmp_path):
    source = PRIVATE / "This_039_Boring_039_Scale_Exercise_Will_Save_You_Years_But_Most_Skip_This_.pdf"
    assert source.is_file(), "REQUIRED_NOTAB_01_WORD_SOURCE_MISSING"
    output = tmp_path / "output.gp"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                     "--out", str(output), "--work-dir", str(tmp_path / "build")])
    assert result.exit_code == 0, result.output[-1000:]
    route = json.loads((tmp_path / "build/note-type-route.json").read_bytes())
    assert route["bars"][46]["status"] == "written", "MISSING_PRINTED_WORD_NOT_READ"
    ledger = _ledger(output, 46)
    digest = hashlib.sha256(json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == WORD_LEDGER, "PRINTED_WORD_BAR_NOT_FAITHFUL"
    ir = json.loads((tmp_path / "build/score.ir.json").read_bytes())
    for event in ir["bars"][46]["events"]:
        for note in event["notes"]:
            assert note["provenance"][0]["raw"]["position_basis"] == "six_painted_tab_rows_at_notation_bar"
            assert isinstance(note["provenance"][0]["raw"]["pdf_word_index"], int)


def test_unextracted_printed_word_reaches_faithful_gpif(tmp_path):
    """Reject DROP_MISSING_WORD_READER and pitch-derived substitute positions."""
    _check_missing_word(tmp_path)


def test_mutant_drop_missing_word_reader_fails_real_source(tmp_path, monkeypatch):
    """The same native-output contract must fail without the observed PDF word."""
    from score2gp import pdf_tab_digit_recovery as recovery
    monkeypatch.setattr(recovery, "_missing_numeric_words", lambda *args: [])
    with pytest.raises(AssertionError, match="MISSING_PRINTED_WORD_NOT_READ"):
        _check_missing_word(tmp_path)


def test_mutant_drop_chord_caption_handoff_fails_real_source(tmp_path, monkeypatch):
    """Reject new notes whose printed caption is left on the preceding bar."""
    from score2gp import pdf_tab_digit_recovery as recovery
    monkeypatch.setattr(recovery, "apply_recovered_chord_labels", lambda *args: None)
    with pytest.raises(AssertionError, match="PRINTED_WORD_BAR_NOT_FAITHFUL"):
        _check_missing_word(tmp_path)
