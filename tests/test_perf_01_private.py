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
from slide_gpif import (
    gpif_without_slides_sha256, gpif_with_legacy_double_barlines,
    without_verified_default_template_sizes,
)
from typer.testing import CliRunner

from score2gp import pdf
from score2gp.cli import app
from score2gp.pdf_resource_budget import (
    INSPECTION_BUDGET_CODE, INSPECTION_PAGE_NODE_LIMIT, PdfInspectionResourceLimit,
)

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
    # PERF-02: the convert path now releases per-page geometry, so the 34-page
    # source fits the unchanged budget there. The budget itself is exercised on
    # the real source through the default (fully retaining) inspection.
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
        try:
            pdf.inspect_pdf(_source("Melodic_Expressions.pdf"), scratch / "inspect")
        except PdfInspectionResourceLimit as exc:
            refusal = exc
        else:
            raise AssertionError("resource gate did not refuse")
        assert not (scratch / "inspect/inspect_pdf.json").exists()
        assert refusal.count == observed[-1][0]
        assert refusal.page_index == observed[-1][1]
        assert str(refusal).startswith(INSPECTION_BUDGET_CODE)
        # Independently counted from the base inspection JSON, using a recursive
        # value walk rather than the production iterative counter.
        assert observed[-1] == (2_060_433, 10)
        assert len(observed) == 10
        assert all(count <= INSPECTION_PAGE_NODE_LIMIT for count, _ in observed[:-1])
        assert observed[-1][0] > INSPECTION_PAGE_NODE_LIMIT
    return observed


def test_main_source_refuses_at_inspection_budget(monkeypatch):
    _assert_main_refusal(monkeypatch)


def test_old_unbounded_behavior_is_rejected_on_main_source(monkeypatch):
    monkeypatch.setattr(pdf, "check_inspection_budget", lambda count, page: None)
    with pytest.raises(AssertionError, match="unbounded inspection continued|resource gate did not refuse"):
        _assert_main_refusal(monkeypatch)


# REFUSE-03 deliberately writes two more Melodic_Expressions bars (source bars 2 and 3: eighth, dotted half
# with a legato slide, eighth rest; each totals 4/4) whose rest was hidden by a page-background shape. The
# Melodic_Expressions digests below are the new head values; every other source digest is unchanged.
# SLIDE-01 deliberately changes written slide marks, so the Melodic_Expressions whole-GPIF digest is the
# new head value; its digest with slide marks removed is the base digest (unchanged apart from slides).
@pytest.mark.parametrize("name,nodes,gpif_digest,without_slides_digest", [
    ("Lesson-6.pdf", 17533,
     "902d5262822a5944a650d981c776feec3ea1bb4ce541c471456c02c17d1072b6", None),
    ("Melodic_Expressions_Chap_19_.pdf", 11460,
     "6a8edd68f46b4388c2c7f3e1c1042d73915901b2d428835ef82715fd16573e2f",
     "72a242fc55283c603fb04f715330261b7dc947ce228908235842ef8e0944060b"),
])
# PERF-02: the node counts are of the retained (released-geometry) inspection written by convert;
# the fully retained counts (676202 / 581458) are pinned in test_perf_02_inspection_retention.py.
def test_real_control_inspection_count_and_gpif_are_unchanged(name, nodes, gpif_digest, without_slides_digest):
    # Counts and GPIF SHA-256 come from fresh CLI conversions at product base
    # 7ff8c66cebf9fd147de5b64a59a4a4f867729b64, without sidecars/references.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="perf01-control-", dir=work) as directory:
        scratch = Path(directory)
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
        # OMIT-05-FU1 adds only verified default template sizes. Keep every
        # original digest and count after removing those seven attributes.
        before_sizes = without_verified_default_template_sizes(actual)
        before_let_ring = re.sub(rb"(?m)^[ \t]*<LetRing />\r?\n", b"", before_sizes)
        legacy = gpif_with_legacy_double_barlines(before_let_ring)
        assert hashlib.sha256(legacy).hexdigest() == gpif_digest
        if without_slides_digest:
            assert gpif_without_slides_sha256(legacy) == without_slides_digest
