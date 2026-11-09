"""PDFG-01 real-source checks; private output exists only in a temporary work directory.

Mutants rejected: restore blanket refusal/ledger topology, accept an unsupported
TAB-only group, or merge two physical groups in the located refusal report.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _convert(name):
    pdf = PRIVATE / name
    if not pdf.is_file():
        pytest.skip("approved private source absent")
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="pdfg01_", dir=work) as directory:
        scratch = Path(directory)
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "out.gp"),
             "--work-dir", str(scratch / "work"), "--json-report", str(scratch / "report.json")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True,
        )
        report = json.loads((scratch / "report.json").read_text(encoding="utf-8"))
        route_path = scratch / "work/note-type-route.json"
        route = json.loads(route_path.read_text(encoding="utf-8")) if route_path.exists() else None
        diagnostics_path = scratch / "work/diagnostics.json"
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8")) if diagnostics_path.exists() else None
        tabraw = json.loads((scratch / "work/tab/tab_raw.json").read_text(encoding="utf-8"))
        return result.returncode, (scratch / "out.gp").exists(), report, route, diagnostics, tabraw


def test_mixing_ledger_lines_do_not_block_the_real_tab_systems():
    """Reject restoring the ledger topology or the whole-file layout refusal."""
    code, written, report, route, _, tabraw = _convert("Mixing Lead & Rhythm pt1.pdf")
    assert code == 0 and written
    assert report["pdf_only_diagnostics"]["pdf_grouping_status"] == "safe"
    assert route["summary"]["source_bars"] == 46
    assert route["summary"]["written_bars"] == 45
    assert route["summary"]["refused_bars"] == 1
    assert route["summary"]["unplaced_tab_digits"] == 0
    digits = [c for c in tabraw["candidates"] if c["kind"] == "fret" and c.get("parsed_fret") is not None]
    assert len(digits) == 575
    assert sorted({(c["page_index"], c["system_index"]) for c in digits}) == [
        (page, system) for page, count in enumerate((5, 6, 6, 6), 1) for system in range(1, count + 1)
    ]
    assert all(c.get("string") is not None and c.get("bar_index") is not None
               and c["raw"]["barline_count"] == 3 for c in digits)
    assert [(b["output_bar_index"], b["reason"]) for b in route["bars"] if b["status"] == "refused"] == [
        (4, "note_duration_event_unread")
    ]


def test_paranoid_tab_groups_are_resolved_and_unsettled_bars_stay_refused_and_located():
    """Reject restoring the blanket refusal, writing a digit that lies outside every detected bar, or refusing a bar
    without a located reason (TABRHY-01 raised the grouping resolution for this source).

    Its TAB staves have a line spacing between the two accepted ranges and lines broken at every digit. They are now
    resolved by evidence (fret digits on the staff's own lines; three intact lines). A bar the printed marks do not
    settle (a flag, a mark this reader does not read, a column with no rhythm mark) stays refused with a located
    reason and the page position of the mark.
    """
    code, written, report, route, diagnostics, _ = _convert("PARANOID - BLACK SABBATH.pdf")
    assert code == 0 and written and diagnostics is None
    # REFUSE-09: five flagged bars are read (three carry an implied trailing rest, so the run is "partial").
    assert report["status"] == "partial"
    summary = route["summary"]
    assert summary["unplaced_tab_digits"] == 0
    assert summary["source_bars"] == 38 and summary["written_bars"] == 25 and summary["refused_bars"] == 13  # NOTAB-01 reads 2 printed-row bars
    assert summary["written_bars_printed_marks"] == 22 and summary["implied_rests"] == 3
    refused = [b for b in route["bars"] if b["status"] == "refused"]
    assert len(refused) == 13  # NOTAB-01
    assert all(b["reason"] and b["location"]["page_index"] >= 0 and "bar_index" in b["location"] for b in refused)
    assert set(summary["refusal_reasons"]) <= {"bar_total_mismatch", "bar_without_notation_event", "notation_note_without_tab_digit",
                                               "note_duration_event_unread"}
