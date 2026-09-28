"""Public key-signature PDF regression and refusal cases."""

from pathlib import Path
from dataclasses import replace
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

import pymupdf

from score2gp.notation_omr.key_signature import (FLAT_TOPS, SHARP_TOPS,
                                                read_bar_key_signatures, read_system_key_signature)
from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves, read_note_durations


FIXTURE = Path(__file__).parent / "fixtures/pdf/omit_01/key_signatures.pdf"


def test_public_signature_pdf_reads_zero_sharps_flats_and_change():
    sidecar = read_note_durations(FIXTURE, time_signature=(4, 4))
    results = sidecar["diagnostics"]["key_signatures"]
    assert len(results) == 7
    assert [r["fifths"] for r in results[:6]] == [0, 1, 3, -2, 0, 1]
    assert all(r["status"] == "read" for r in results[:6])
    assert results[4]["sources"] == [] and "inherited_from" not in results[4]
    assert results[4]["clef_source"]
    assert all(len(results[i]["sources"]) == abs(results[i]["fifths"]) for i in (0, 1, 2, 3, 5))
    assert results[6]["status"] == "refused"
    assert results[6]["reason"] == "key_signature_partial_or_ambiguous"
    assert results[6]["location"]["page_index"] == 0


def test_mode_is_not_inferred_from_accidental_count():
    with pymupdf.open(FIXTURE) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[1], symbols)
    assert result["fifths"] == 1
    assert result["mode"] is None
    assert result["mode_diagnostic"] == "key_mode_unresolved"


def test_standard_third_sharp_is_read():
    # The third sharp is on G5, half a staff space below the old A5 fixture.
    with pymupdf.open(FIXTURE) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[2], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 3
    assert len(result["sources"]) == 3


def test_mid_system_flat_changes_the_following_bar():
    source = FIXTURE.parent / "mid_system_flat.pdf"
    sidecar = read_note_durations(source, time_signature=(4, 4))
    assert sidecar["diagnostics"]["bar_key_signatures"][2]["fifths"] == 1
    changed = sidecar["diagnostics"]["bar_key_signatures"][3]
    assert changed["status"] == "read"
    assert changed["fifths"] == -1
    assert len(changed["sources"]) == 1


def test_mid_system_three_accidental_runs_are_complete():
    source = FIXTURE.parent / "mid_system_three_keys.pdf"
    sidecar = read_note_durations(source, time_signature=(4, 4))
    keys = sidecar["diagnostics"]["bar_key_signatures"]
    assert [(keys[i]["status"], keys[i]["fifths"], len(keys[i]["sources"]))
            for i in (0, 1, 2, 3)] == [
                ("read", 0, 0), ("read", 3, 3),
                ("read", 1, 1), ("read", -3, 3),
            ]


def test_mid_system_signature_is_split_from_first_note_accidental():
    source = FIXTURE.parent / "mid_system_seven_flats_note_sharp.pdf"
    keys = read_note_durations(source, time_signature=(4, 4))["diagnostics"]["bar_key_signatures"]
    assert keys[0]["fifths"] == 1
    assert keys[1]["status"] == "read"
    assert keys[1]["fifths"] == -7
    assert len(keys[1]["sources"]) == 7


def test_mid_system_three_to_seven_accidentals_are_not_truncated():
    source = FIXTURE.parent / "mid_system_seven_flats_note_sharp.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staff = find_staves(symbols)[0][0]
    bars = read_note_durations(source, time_signature=(4, 4))["systems"][0]["bars"]
    flats = [t for t in symbols.texts if t.text == "b" and 164 <= t.bbox[0] < 200]
    others = [t for t in symbols.texts if t not in flats and t.text != "#"]
    assert len(flats) == 7
    header = read_system_key_signature(staff, symbols)
    for count in range(3, 8):
        for kind, positions, sign in (("b", FLAT_TOPS, -1), ("#", SHARP_TOPS, 1)):
            run = []
            for index, glyph in enumerate(flats[:count]):
                top = staff.top + positions[index] * staff.space
                height = glyph.bbox[3] - glyph.bbox[1]
                run.append(replace(glyph, text=kind,
                                   bbox=(glyph.bbox[0], top, glyph.bbox[2], top + height)))
            key = read_bar_key_signatures(staff, replace(symbols, texts=others + run), bars, header)[1]
            assert (key["status"], key["fifths"], len(key["sources"])) == ("read", sign * count, count)


def test_mid_system_first_note_accidental_does_not_change_key():
    source = FIXTURE.parent / "mid_system_note_sharp_only.pdf"
    keys = read_note_durations(source, time_signature=(4, 4))["diagnostics"]["bar_key_signatures"]
    assert [keys[i]["fifths"] for i in (0, 1)] == [1, 1]
    assert keys[1]["sources"] == keys[0]["sources"]


def test_mid_system_ambiguous_run_is_refused():
    # The trailing sharp is near the note horizontally, but at a different
    # staff position; geometry cannot assign it to that note.
    source = FIXTURE.parent / "mid_system_ambiguous.pdf"
    keys = read_note_durations(source, time_signature=(4, 4))["diagnostics"]["bar_key_signatures"]
    assert keys[1]["status"] == "refused"
    assert keys[1]["fifths"] is None
    assert keys[1]["reason"] == "key_signature_partial_or_ambiguous"
    assert keys[1]["location"]["bar_index"] == 1
    assert len(keys[1]["sources"]) == 7


def test_natural_cancellation_header_is_refused():
    source = FIXTURE.parent / "natural_cancellation.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "refused"
    assert result["fifths"] is None
    assert result["reason"] == "key_signature_partial_or_ambiguous"
    assert len(result["sources"]) == 1


def test_first_note_accidental_is_not_key_signature():
    source = FIXTURE.parent / "note_accidental.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 0
    assert result["sources"] == []


def test_key_glyph_before_first_note_accidental_is_preserved():
    source = FIXTURE.parent / "key_and_note_accidental.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 1
    assert len(result["sources"]) == 1


def test_exact_printed_key_name_supplies_mode():
    source = FIXTURE.parent / "named_mode.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 1
    assert result["mode"] == "minor"
    assert len(result["mode_sources"]) == 1
    assert result["mode_diagnostic"] is None


def test_negative_key_gp_round_trip(tmp_path):
    # A fresh process exercises the production GPIF writer (which switches
    # format when pytest is imported).
    script = """from score2gp.ir import ScoreIR, KeySignature
from score2gp.gp_package import write_gp, extract_score_ir_from_gp
import sys
score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
score.bars[0].events = []
score.bars[0].key_signature = KeySignature(fifths=-2, mode='minor')
write_gp(score, sys.argv[1])
print(extract_score_ir_from_gp(sys.argv[1]).bars[0].key_signature.fifths)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path / "flat.gp")],
                            text=True, capture_output=True, env=env, check=True)
    assert result.stdout.strip() == "-2"


def test_public_pdf_to_gpif_has_signed_key_on_every_bar():
    source = FIXTURE.parent / "pdf_to_gpif_keys.pdf"
    # The extractor selects a fixture-specific heuristic for paths containing
    # "test". Copy the public PDF to a neutral path to exercise production.
    scratch_root = Path(__file__).resolve().parents[1] / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        input_pdf = scratch / "input.pdf"
        shutil.copyfile(source, input_pdf)
        output = scratch / "keys.gp"
        source_root = os.environ.get("SCORE2GP_OMIT01_MUTANT_SRC", str(Path(__file__).resolve().parents[1] / "src"))
        env = {**os.environ, "PYTHONPATH": source_root}
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(input_pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            text=True, capture_output=True, env=env,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        with zipfile.ZipFile(output) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
    counts = [int(bar.findtext("Key/AccidentalCount"))
              for bar in root.findall("MasterBars/MasterBar")]
    assert counts == [1, -1, 0]


def test_public_mid_system_changes_reach_gpif():
    source = FIXTURE.parent / "pdf_to_gpif_mid_system.pdf"
    # Use a neutral input path so the production PDF route is selected.
    scratch_root = Path(__file__).resolve().parents[1] / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        input_pdf = scratch / "input.pdf"
        shutil.copyfile(source, input_pdf)
        output = scratch / "keys.gp"
        source_root = os.environ.get("SCORE2GP_OMIT01_MUTANT_SRC", str(Path(__file__).resolve().parents[1] / "src"))
        env = {**os.environ, "PYTHONPATH": source_root}
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(input_pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            text=True, capture_output=True, env=env,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        with zipfile.ZipFile(output) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
        score_ir = json.loads((scratch / "work" / "score.ir.json").read_text())
    counts = [bar.findtext("Key/AccidentalCount")
              for bar in root.findall("MasterBars/MasterBar")]
    assert counts == ["1", "-3"]
    assert any(w["code"] == "key_mode_unresolved" and "bar 2" in w["message"]
               for w in score_ir["warnings"])


def test_seven_flat_change_with_note_accidental_reaches_gpif():
    source = FIXTURE.parent / "mid_system_seven_flats_note_sharp.pdf"
    scratch_root = Path(__file__).resolve().parents[1] / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        input_pdf = scratch / "input.pdf"
        shutil.copyfile(source, input_pdf)
        output = scratch / "keys.gp"
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(input_pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            text=True, capture_output=True, env=env,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        with zipfile.ZipFile(output) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
    counts = [bar.findtext("Key/AccidentalCount")
              for bar in root.findall("MasterBars/MasterBar")]
    assert counts == ["1", "-7"]
