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


def test_paranoid_unsupported_tab_groups_stay_refused_and_separate():
    """Reject accepting unsafe groups and merging physical groups in diagnostics."""
    code, written, report, route, diagnostics, _ = _convert("PARANOID - BLACK SABBATH.pdf")
    assert code == 4 and not written and route is None
    assert report["refusal_code"] == "pdf_only_tab_grouping_unsafe"
    groups = diagnostics["details"]["located_grouping_refusals"]
    assert [(g["page_index"], g["system_index"]) for g in groups] == [
        (page, system) for page, count in enumerate((5, 6, 4)) for system in range(count)
    ]
    assert all(g["code"] == "tab_group_staff_spacing_unclassified" for g in groups)
    assert all(g["line_count"] == 6 for g in groups)
    assert all(g["notation_bar_count"] == 0 for g in groups)
    assert all(g["timing_code"] == "tab_group_without_notation_timing" for g in groups)
    assert report["pdf_only_diagnostics"]["located_grouping_refusals"] == groups
