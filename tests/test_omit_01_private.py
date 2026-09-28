"""Genuine-source key contour checks; fixtures stay in the private mount."""

from pathlib import Path
from dataclasses import replace
import importlib.util
import os
import subprocess
import sys
import tempfile

import pymupdf
import pytest

from score2gp.notation_omr.key_signature import _kind, read_system_key_signature
from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves, read_note_durations


PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"


def test_real_flat_shape_rejects_natural_shape():
    with pymupdf.open(PRIVATE / "Lesson-4.pdf") as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        flat = next(g for g in symbols.glyphs if g.ident == "p0:d13")
        assert _kind(flat, staves[0].space) == "flat"
    exact = next(PRIVATE.glob("The_EXACT_System_*.pdf"))
    with pymupdf.open(exact) as doc:
        symbols = extract_page_symbols(doc[1], 1)
        staves, _ = find_staves(symbols)
        for ident in ("p1:d124", "p1:d150"):
            natural = next(g for g in symbols.glyphs if g.ident == ident)
            assert _kind(natural, staves[0].space) is None
            space = staves[0].space
            top = natural.bbox[1] - 0.2 * space
            clef_right = natural.bbox[0] - 0.5 * space
            clef_left = clef_right - 2 * space
            clef = replace(natural, ident="test-clef",
                           bbox=(clef_left, top - 0.75 * space,
                                 clef_right, top + 4.75 * space))
            staff = replace(staves[0], lines=[top + i * space for i in range(5)],
                            x0=clef_left - 0.3 * space, x1=natural.bbox[2] + 15 * space)
            header = replace(symbols, glyphs=[clef, natural], texts=[])
            result = read_system_key_signature(staff, header)
            assert result["status"] == "refused"
            assert result["reason"] == "key_signature_partial_or_ambiguous"


def test_real_mid_system_change_is_located():
    exact = next(PRIVATE.glob("The_EXACT_System_*.pdf"))
    sidecar = read_note_durations(exact, pages=(1, 1), time_signature=(4, 4))
    system = sidecar["systems"][3]
    before = system["first_bar_index"] + 3
    after = before + 1
    keys = sidecar["diagnostics"]["bar_key_signatures"]
    assert keys[before]["fifths"] == 1
    assert keys[after]["fifths"] == -1
    assert keys[after]["location"]["page_index"] == 0


def test_ledger_line_note_accidental_does_not_become_key_change():
    sidecar = read_note_durations(PRIVATE / "Lesson-5.pdf", pages=(2, 2), time_signature=(4, 4))
    keys = sidecar["diagnostics"]["bar_key_signatures"]
    assert [keys[i]["fifths"] for i in range(4)] == [0, 0, 0, 0]


@pytest.mark.parametrize(("lesson", "bar_count"), [(3, 66), (4, 79), (5, 43), (6, 72), (7, 50)])
def test_private_lesson_key_counts_against_independent_gp_reader(lesson, bar_count):
    oracle_path = Path(__file__).with_name("test_dur_02_oracle.py")
    spec = importlib.util.spec_from_file_location("dur02_key_oracle", oracle_path)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    root = Path(__file__).resolve().parents[1]
    scratch_root = root / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "lesson.gp"
        env = {**os.environ, "PYTHONPATH": str(root / "src")}
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PRIVATE / f"Lesson-{lesson}.pdf"),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            text=True, capture_output=True, env=env,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        comparison = oracle.compare_gp(PRIVATE / f"Lesson-{lesson}.gp", output)
        assert comparison["source_bars"] == bar_count
        assert not [d for d in comparison["differences"] if d["field"] == "key_accidental_count"]
