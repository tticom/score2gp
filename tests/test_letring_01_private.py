"""LETRING-01 real pages. Mutants: whole bar, first beat, drop mark, drop refusal.

Private conversion products stay in TemporaryDirectory below work. Reference
files are independent oracles only; the converter never receives them.
"""
from pathlib import Path
import json
import tempfile
import subprocess
import sys
from functools import lru_cache
import re
import zipfile
from xml.etree import ElementTree as ET

from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


@lru_cache(maxsize=None)
def convert(stem, disabled=False):
    assert (PRIVATE / f"{stem}.pdf").is_file(), "required approved PDF absent"
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        scratch = Path(directory)
        entry = [sys.executable, "-m", "score2gp.cli"]
        if disabled:
            entry = [sys.executable, "-c", "import score2gp.pdf_let_ring as reader; "
                     "reader.attach_pdf_let_ring = lambda *a: "
                     "{'counts_by_reason': {}, 'decisions': [], 'warnings': []}; "
                     "from score2gp.cli import app; app()"]
        result = subprocess.run([*entry,
            "convert", "--pdf", str(PRIVATE / f"{stem}.pdf"), "--pdf-only-tab",
            "--out", str(scratch / "out.gp"),
            "--work-dir", str(scratch / "work"),
        ], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-1000:]
        output = scratch / "out.gp"
        data = zipfile.ZipFile(output).read("Content/score.gpif") if output.exists() else None
        report_path = scratch / "work/let-ring.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        warnings = json.loads((scratch / "work/warnings.json").read_text())
        return data, report, warnings


def read_written_bars(data):
    import io
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("Content/score.gpif", data)
    return read_gp_bars(package.getvalue())


def test_lesson_5_let_ring_is_only_reference_bar_31_beat_8_note():
    """Reject whole-bar, first-note-only and ignore-mark implementations."""
    reference = PRIVATE / "Lesson-5.gp"
    assert reference.is_file(), "required approved reference absent"
    expected = read_gp_bars(reference)
    data, report, _ = convert("Lesson-5")
    actual = read_written_bars(data)
    locations = lambda bars: [(i + 1, j + 1, e["let_ring"])
                             for i, b in enumerate(bars)
                             for j, e in enumerate(b["events"] or []) if e["let_ring"]]
    assert [(i, j, len(notes)) for i, j, notes in locations(expected)] == [(31, 8, 1)]
    assert locations(actual) == locations(expected)
    assert report["counts_by_reason"] == {"pdf_let_ring_attached": 1}


def test_derek_dashed_let_ring_locates_span_and_refuses_unwritten_bar():
    """Reject first-note-only reading, ignored span, and techniques on refused bars."""
    reference = PRIVATE / "Derek Trucks BB King.gp"
    assert reference.is_file(), "required approved reference absent"
    expected = read_gp_bars(reference, track_id="0", staff_index=0)
    assert [(i + 1, j + 1, len(e["let_ring"])) for i, b in enumerate(expected)
            for j, e in enumerate(b["events"] or []) if e["let_ring"]] == [
                (10, 7, 1), (10, 8, 1), (10, 9, 1)]
    data, report, warnings = convert("Derek Trucks BB King")
    assert ET.fromstring(data).find(".//LetRing") is None
    actual = read_written_bars(data)
    assert actual[9]["events"] is None, "the unread source bar must remain empty"
    assert sum(b["events"] is not None for b in actual) == 2
    [decision] = report["decisions"]
    assert decision["bar_index"] == 10
    assert decision["beat_indices"] == [7, 8, 9]
    assert decision["span"] == "dashed"
    assert decision["code"] == "pdf_let_ring_bar_unavailable"
    [warning] = [w for w in warnings if w["code"] == decision["code"]]
    [where] = warning["provenance"]
    assert (where["page"], where["bar_index"]) == (1, 10)
    assert where["raw"]["bbox"]


def test_chapter_19_dashed_spans_cover_exactly_the_printed_note_columns():
    """Reject first-note-only, whole-bar and ignored-mark implementations.

    Oracle: visual inspection of the three real marks on page 2. The first
    dashed span covers beats 2-7 (the last is a chord); the second covers 3-4;
    the final centred label covers only beat 6. No reference GP is available.
    """
    data, report, _ = convert("Melodic_Expressions_Chap_19_")
    actual = read_written_bars(data)
    assert [(i + 1, j + 1, len(e["let_ring"])) for i, b in enumerate(actual)
            for j, e in enumerate(b["events"] or []) if e["let_ring"]] == [
                (16, 2, 1), (16, 3, 1), (16, 4, 1), (16, 5, 1), (16, 6, 1), (16, 7, 2),
                (18, 3, 1), (18, 4, 1), (20, 6, 1)]
    assert report["counts_by_reason"] == {"pdf_let_ring_attached": 3}


def test_let_ring_preserves_every_other_gpif_byte():
    """Reject incidental changes to other techniques, rhythms, positions or bars."""
    for stem in ("Lesson-5", "Derek Trucks BB King", "Melodic_Expressions_Chap_19_"):
        data, _, _ = convert(stem)
        baseline, _, _ = convert(stem, disabled=True)
        if data is None:
            assert baseline is None
        else:
            assert re.sub(rb"(?m)^[ \t]*<LetRing />\r?\n", b"", data) == baseline
