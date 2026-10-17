"""SLIDE-01 on genuine sources: slide type read from the drawn mark, unextracted marks reported.

Private PDFs convert under ``<repo>/work`` and only counts, codes and flags are asserted.
Mutants these tests reject (each shown failing in the SLIDE-01 handback):
  * always write Flags 2 (legato)                  -> test_bebop_shift_slides_are_flags_1
  * invert the arc rule (legato <-> shift)          -> Lesson 4 and Bebop tests
  * inject a default type, keep the warning         -> test_lesson_5_unextracted_mark_writes_no_slide
  * drop the diagnostic                             -> Lesson 5 / Bebop diagnostic tests
  * restrict slur evidence to each string height     -> test_chord_slide_uses_one_slur_for_all_strings
  * swap slide-in and slide-out                     -> test_leading_slide_into_a_note_is_slide_in
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from score2gp.pdf import extract_tab

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
CODE = "slide_mark_not_extracted"


def _require(*names: str) -> None:
    missing = [n for n in names if not (PRIVATE / n).exists()]
    if missing:
        pytest.skip(f"private corpus not mounted: {', '.join(missing)}")


_converted: dict[str, tuple[Counter, list[dict]]] = {}
_gpifs: dict[str, ET.Element] = {}


def _convert(stem: str) -> tuple[Counter, list[dict]]:
    """Convert a private PDF; return its GPIF Slide flag counts and the conversion-report slide diagnostics."""
    _require(f"{stem}.pdf")
    if stem not in _converted:
        scratch_root = ROOT / "work"
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
            scratch = Path(directory)
            output = scratch / "out.gp"
            result = subprocess.run(
                [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PRIVATE / f"{stem}.pdf"),
                 "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
                 "--work-dir", str(scratch / "work")],
                text=True, capture_output=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            )
            assert result.returncode == 0, result.stderr[-1000:]
            gpif = ET.fromstring(zipfile.ZipFile(output).read("Content/score.gpif"))
            _gpifs[stem] = gpif
            flags = Counter(n.findtext("Flags") for n in gpif.findall('.//Property[@name="Slide"]'))
            warnings = json.loads((scratch / "work" / "warnings.json").read_text(encoding="utf-8"))
        _converted[stem] = (flags, [w for w in warnings if w["code"] == CODE])
    return _converted[stem]


def _slide_candidates(stem: str) -> list[dict]:
    _require(f"{stem}.pdf")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        raw = extract_tab(PRIVATE / f"{stem}.pdf", directory)
    return [c for c in raw["candidates"] if c["kind"] == "visual-slide"]


@pytest.mark.parametrize("lesson, flags, diagnostics", [
    (3, {}, 0), (4, {"2": 1}, 0), (5, {}, 1), (6, {}, 0), (7, {}, 0)])
def test_lessons_3_to_7_slide_types_and_diagnostics(lesson, flags, diagnostics):
    written, reported = _convert(f"Lesson-{lesson}")
    assert dict(written) == flags
    assert len(reported) == diagnostics


def test_lesson_4_connecting_slide_with_slur_is_legato():
    [mark] = _slide_candidates("Lesson-4")
    assert mark["raw"]["placement"] == "between-notes"
    assert mark["raw"]["reading"] == {"status": "read", "style": "legato"}
    assert mark["raw"]["direction"] == "down"


def test_lesson_5_unextracted_mark_writes_no_slide_and_is_located():
    written, reported = _convert("Lesson-5")
    assert sum(written.values()) == 0, "a slide whose type the page cannot decide must not be written"
    [diagnostic] = reported
    [where] = diagnostic["provenance"]
    assert (where["page"], where["system_id"], where["bar_index"]) == (1, "system-5", 17)
    assert "slide_endpoint_not_bound_to_digit" in diagnostic["message"]
    assert "slide_not_written" in diagnostic["message"]
    [mark] = _slide_candidates("Lesson-5")
    assert mark["raw"]["reading"] == {"status": "refused", "reason": "slide_endpoint_not_bound_to_digit"}


def test_bebop_shift_slides_are_flags_1():
    written, reported = _convert("Bebop Licks in Am")
    assert dict(written) == {"1": 4}
    reasons = Counter(d["message"].split(": ")[1].split(";")[0] for d in reported)
    assert reasons == {"slide_endpoints_in_different_bars": 1, "slide_label_without_drawn_mark": 2}


def test_bebop_marks_without_a_slur_are_shift_and_the_slurred_one_crosses_a_bar():
    marks = _slide_candidates("Bebop Licks in Am")
    readings = Counter((m["raw"]["reading"]["status"], m["raw"]["reading"].get("style") or
                        m["raw"]["reading"]["reason"]) for m in marks)
    assert readings == {("read", "shift"): 4, ("refused", "slide_endpoints_in_different_bars"): 1}


def test_leading_slide_into_a_note_is_slide_in():
    marks = _slide_candidates("Can't Find My Way Home (open chord shenanigans)")
    leading = [m for m in marks if m["raw"]["placement"] == "before-note"]
    assert [(m["raw"]["direction"]) for m in leading] == ["up"]
    readings = Counter(m["raw"]["reading"].get("style") or m["raw"]["reading"]["reason"]
                       for m in marks if "reading" in m["raw"])
    assert readings == {"legato": 4, "slide_endpoint_not_bound_to_digit": 1}
    written, _ = _convert("Can't Find My Way Home (open chord shenanigans)")
    assert written["16"] == 1 and written["1"] == 0


def test_chord_slide_uses_one_slur_for_all_strings():
    """Reject the old per-string arc window: it reads shift on the lowest chord string.

    The actual page has one slur over each three-string chord slide in bars 3 and 4.
    Check each drawn reading and preserve the final GPIF bar refusals.
    """
    stem = "Melodic_Expressions_Chap_19_"
    marks = [m for m in _slide_candidates(stem) if m["page_index"] == 1
             and m["bar_index"] in (3, 4)]
    _convert(stem)
    gpif = _gpifs[stem]
    bars = gpif.findall("./Bars/Bar")
    for bar in (3, 4):
        # The normal pipeline currently refuses these bars for other reasons.
        # Sharing slur evidence must not bypass that bar-level gate.
        assert bars[bar - 1].findtext("Voices").split() == ["-1"] * 4

    for bar in (3, 4):
        chord = [m for m in marks if m["bar_index"] == bar]
        assert len(chord) == 3
        assert all(m["system_index"] == 2 for m in chord)
        assert all(m["raw"]["reading"] == {"status": "read", "style": "legato"} for m in chord)
