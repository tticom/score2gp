"""PERF-01 real-source resource seam and byte-level GPIF preservation."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from slide_gpif import gpif_without_slides_sha256, gpif_with_legacy_double_barlines
from typer.testing import CliRunner

from score2gp import pdf
from score2gp.cli import app
from score2gp.pdf_resource_budget import INSPECTION_PAGE_NODE_LIMIT

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _source(name):
    path = PRIVATE / name
    if not path.is_file():
        pytest.skip("private corpus absent")
    return path


def _convert(name, scratch):
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(_source(name)), "--pdf-only-tab",
        "--time-signature", "4/4", "--work-dir", str(scratch / "conversion"),
        "--out", str(scratch / "result.gp"),
        "--json-report", str(scratch / "report.json"),
    ])
    return result, json.loads((scratch / "report.json").read_text(encoding="utf-8"))


def _assert_main_refusal(monkeypatch):
    observed = []
    check = pdf.check_inspection_budget

    def monitored_check(count, page):
        observed.append((count, page))
        check(count, page)
        # A no-op mutant must fail here on the real input, before it can retain
        # the rest of the document or allocate the baseline multi-GB JSON string.
        assert count <= INSPECTION_PAGE_NODE_LIMIT, "unbounded inspection continued"

    monkeypatch.setattr(pdf, "check_inspection_budget", monitored_check)
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="perf01-gate-", dir=work) as directory:
        scratch = Path(directory)
        result, report = _convert("Melodic_Expressions.pdf", scratch)
        assert result.exit_code == 1
        assert report["refusal_code"] == "pdf_resource_inspection_page_nodes_exceeded", "resource gate did not refuse"
        assert report["status"] == "refused"
        assert report["stage"] == "pdf-inspection"
        assert not report["output_written"]
        assert not (scratch / "result.gp").exists()
        assert not (scratch / "conversion/inspect/inspect_pdf.json").exists()
        assert not (scratch / "conversion/tab").exists()
        counts = report["summary_counts"]
        assert counts["inspection_page_nodes"] == observed[-1][0]
        assert counts["page_index"] == observed[-1][1]
        assert counts["limit"] == INSPECTION_PAGE_NODE_LIMIT
        # Independently counted from the base inspection JSON, using a recursive
        # value walk rather than the production iterative counter.
        assert observed[-1] == (2_060_433, 10)
        assert len(observed) == 10
        assert all(count <= INSPECTION_PAGE_NODE_LIMIT for count, _ in observed[:-1])
        assert observed[-1][0] > INSPECTION_PAGE_NODE_LIMIT
        warnings = json.loads((scratch / "conversion/warnings.json").read_text(encoding="utf-8"))
        assert any(w["code"] == report["refusal_code"] and w["page_index"] == 10
                   and w["inspection_page_nodes"] == 2_060_433 for w in warnings)
    return observed


def test_main_source_refuses_at_inspection_budget(monkeypatch):
    _assert_main_refusal(monkeypatch)


def test_old_unbounded_behavior_is_rejected_on_main_source(monkeypatch):
    monkeypatch.setattr(pdf, "check_inspection_budget", lambda count, page: None)
    with pytest.raises(AssertionError, match="resource gate did not refuse"):
        _assert_main_refusal(monkeypatch)


# SLIDE-01 deliberately changes written slide marks, so the Melodic_Expressions whole-GPIF digest is the
# new head value; its digest with slide marks removed is the base digest (unchanged apart from slides).
@pytest.mark.parametrize("name,nodes,gpif_digest,without_slides_digest", [
    ("Lesson-6.pdf", 676202,
     "902d5262822a5944a650d981c776feec3ea1bb4ce541c471456c02c17d1072b6", None),
    ("Melodic_Expressions_Chap_19_.pdf", 581458,
     "06822271fe49678a8d562e721715dd506bc17e8434b922df85d1863dd0e4c927",
     "e6d650202f421d0ba083e5b594300e8d9dc154c291b0c4c7c0de79cda386564b"),
])
def test_real_control_inspection_count_and_gpif_are_unchanged(name, nodes, gpif_digest, without_slides_digest):
    # Counts and GPIF SHA-256 come from fresh CLI conversions at product base
    # 7ff8c66cebf9fd147de5b64a59a4a4f867729b64, without sidecars/references.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="perf01-control-", dir=work) as directory:
        scratch = Path(directory)
        # gpif.build_gpif has a pre-existing pytest-specific format branch.
        # A subprocess exercises the normal CLI and the actual shipped GPIF.
        result = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(_source(name)),
            "--pdf-only-tab", "--time-signature", "4/4",
            "--work-dir", str(scratch / "conversion"), "--out", str(scratch / "result.gp"),
            "--json-report", str(scratch / "report.json"),
        ], env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True, timeout=120)
        report = json.loads((scratch / "report.json").read_text(encoding="utf-8"))
        assert result.returncode == 0, result.stderr[-1000:]
        assert report["output_written"]
        inspection = json.loads((scratch / "conversion/inspect/inspect_pdf.json").read_text(encoding="utf-8"))

        def count_values(value):
            children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
            return 1 + sum(count_values(child) for child in children)

        assert sum(count_values(page) for page in inspection["pages"]) == nodes
        with ZipFile(scratch / "result.gp") as package:
            actual = package.read("Content/score.gpif")
        # OMIT-02-FU1 removes only the redundant double-bar extension. Retain
        # every previous whole-file digest by reconstructing that exact old line;
        # the native output must also reject the old writer's redundant element.
        assert b"<Barline>" not in actual
        # LETRING-01 adds ten page-read note tags on this real control source.
        # Keep both original GPIF digests and the exact inspection count: remove
        # only those added tags, whose exact bar/beat membership is also checked
        # by test_letring_01_private. Dropping the feature fails the count here.
        expected_let_ring_notes = 10 if name == "Melodic_Expressions_Chap_19_.pdf" else 0
        assert actual.count(b"<LetRing />") == expected_let_ring_notes
        before_let_ring = re.sub(rb"(?m)^[ \t]*<LetRing />\r?\n", b"", actual)
        legacy = gpif_with_legacy_double_barlines(before_let_ring)
        assert hashlib.sha256(legacy).hexdigest() == gpif_digest
        if without_slides_digest:
            assert gpif_without_slides_sha256(legacy) == without_slides_digest
