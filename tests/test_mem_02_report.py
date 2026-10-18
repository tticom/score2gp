"""MEM-02: real CLI reports, independent census, and lossless debug opt-in.

Rejects: dump always enabled, summary removed, examples unbounded, incorrect
counts/locations, and dropping non-dump report data. No generated score oracle.
"""
from collections import defaultdict
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from score2gp.report import write_conversion_report

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
SOURCES = sorted(p.name for p in PRIVATE.glob("*.pdf"))
# Per-source allowance above every byte of the unchanged base content. This
# rejects reintroducing the repeated dump even where other diagnostics are large.
SUMMARY_ALLOWANCE = 512_000
MAX_REPORT_BYTES = 41_000_000

# Observe the actual renderer input before downstream artifact rewrites. This
# wrapper calls the real writer and leaves the normal CLI pipeline intact.
CAPTURE_RENDER_INPUT = """import json, os
from pathlib import Path
from score2gp import cli
writer = cli.write_conversion_report
def capture(path, title, warnings, summary, **options):
    Path(os.environ['MEM02_REPORT_INPUT']).write_text(json.dumps(summary), encoding='utf-8')
    writer(path, title, warnings, summary, **options)
cli.write_conversion_report = capture
cli.app()
"""


def _read_report(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<pre>(.*?)</pre>", text, re.S)
    return text, json.loads(html.unescape(match[1]))


def _without_dump(value):
    if isinstance(value, dict):
        return {key: _without_dump(item) for key, item in value.items()
                if key not in ("barline_candidates_details", "barline_candidate_summary")}
    if isinstance(value, list):
        return [_without_dump(item) for item in value]
    return value


def _convert(name, scratch, debug=False):
    source = PRIVATE / name
    if not source.is_file():
        pytest.skip("private corpus absent")
    args = [sys.executable, "-c", CAPTURE_RENDER_INPUT, "convert", "--pdf", str(source),
            "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "result.gp"),
            "--work-dir", str(scratch / "conversion"), "--json-report", str(scratch / "result.json")]
    if debug:
        args.append("--debug-barline-candidates")
    result = subprocess.run(args, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src"),
                                 "MEM02_REPORT_INPUT": str(scratch / "report-input.json")})
    path = scratch / "conversion/conversion-report.html"
    payload = json.loads((scratch / "result.json").read_text(encoding="utf-8"))
    assert result.returncode == payload["exit_code"]
    assert payload["status"] in ("success", "refused")
    if not path.exists():
        # Base refuses this resource-heavy source before an HTML report exists.
        # Keep that early gate intact; any other missing report is a failure.
        assert payload["refusal_code"] == "pdf_resource_inspection_page_nodes_exceeded", result.stderr[-1000:]
        assert not payload["output_written"]
        assert not (scratch / "result.gp").exists()
        return None
    return path


def _census(tab):
    systems = {}
    for candidate in tab.get("candidates", []):
        raw = candidate.get("raw", {})
        if not isinstance(raw.get("barline_candidates_details"), list):
            continue
        location = {"page_index": candidate.get("page_index"),
                    "system_index": candidate.get("system_index"),
                    "staff_bbox": raw.get("tab_staff_bbox")}
        key = json.dumps(location, sort_keys=True)
        details = raw["barline_candidates_details"]
        if key in systems:
            assert systems[key][1] == details
        else:
            systems[key] = (location, details)
    rejected = defaultdict(list)
    accepted = []
    for location, details in systems.values():
        for item in details or []:
            located = {**location, "candidate": item}
            if item["final_decision"] == "rejected":
                rejected[item["rejection_reason"]].append(located)
            else:
                accepted.append(located)
    return systems, rejected, accepted


@pytest.mark.parametrize("name", SOURCES or ["Lesson-3.pdf"])
def test_default_real_report_is_bounded_and_preserves_other_content(name):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="mem02-test-", dir=work) as directory:
        scratch = Path(directory)
        path = _convert(name, scratch)
        if path is None:
            return
        text, summary = _read_report(path)
        assert path.stat().st_size < MAX_REPORT_BYTES
        original = json.loads((scratch / "report-input.json").read_text(encoding="utf-8"))
        tab = original.get("tab", {})
        systems, rejected, accepted = _census(tab)
        stripped_text = re.sub(r"<pre>.*?</pre>",
                               lambda _: "<pre>" + html.escape(json.dumps(_without_dump(summary), indent=2)) + "</pre>",
                               text, flags=re.S)
        unchanged_bytes = len(stripped_text.replace("\n", os.linesep).encode())
        assert path.stat().st_size <= unchanged_bytes + SUMMARY_ALLOWANCE, "report size budget exceeded"
        assert "barline_candidates_details" not in text, "full dump returned by default"
        if systems:
            bounded = summary["barline_candidate_summary"]
            assert bounded["system_count"] == len(systems)
            assert bounded["accepted_candidates"] == accepted
            expected_counts = {reason: len(items) for reason, items in rejected.items()}
            assert bounded["rejected_counts_by_reason"] == expected_counts
            assert set(bounded["rejected_examples_by_reason"]) == set(rejected)
            for reason, examples in bounded["rejected_examples_by_reason"].items():
                assert len(examples) == min(3, expected_counts[reason]), "examples are unbounded or missing"
                for example in examples:
                    assert example["page_index"] is not None
                    assert example["system_index"] is not None
                    assert example in rejected[reason], "example has incorrect geometry or location"

        # The debug report must preserve the captured original input exactly, while the default
        # preserves every field outside the designated dump.
        warnings = json.loads((scratch / "conversion/warnings.json").read_text(encoding="utf-8"))
        debug_path = scratch / "debug.html"
        write_conversion_report(debug_path, "score2gp conversion report", warnings, original,
                                debug_barline_candidates=True)
        debug_text, debug_summary = _read_report(debug_path)
        assert debug_summary == original
        assert _without_dump(summary) == _without_dump(original)
        # All HTML outside the JSON block (warnings, title, provenance) survives.
        assert re.sub(r"<pre>.*?</pre>", "<pre></pre>", text, flags=re.S) == re.sub(
            r"<pre>.*?</pre>", "<pre></pre>", debug_text, flags=re.S)


def test_real_cli_full_dump_requires_explicit_debug_flag():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="mem02-debug-", dir=work) as directory:
        scratch = Path(directory)
        path = _convert("Lesson-3.pdf", scratch, debug=True)
        assert path is not None
        text, summary = _read_report(path)
        original = json.loads((scratch / "report-input.json").read_text(encoding="utf-8"))
        tab = original["tab"]
        assert summary == original
        assert "barline_candidates_details" in text
        _, rejected, _ = _census(tab)
        assert sum(map(len, rejected.values())) > 3
