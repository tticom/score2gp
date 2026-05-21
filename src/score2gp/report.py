from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

GROUPING_DIAGNOSTICS_SCHEMA_VERSION = "pdf-grouping-diagnostics.v0.1"


def write_warnings(path: str | Path, warnings: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(warnings, indent=2), encoding="utf-8")


def write_conversion_report(path: str | Path, title: str, warnings: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    warning_items = "\n".join(
        f"<li><strong>{html.escape(item.get('code', 'warning'))}</strong>: {html.escape(item.get('message', ''))}</li>"
        for item in warnings
    )
    body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{html.escape(title)}</title></head>
<body>
<h1>{html.escape(title)}</h1>
<p>This report is a first-pass conversion diagnostic. It lists uncertainty instead of hiding it.</p>
<h2>Warnings</h2>
<ul>{warning_items}</ul>
<h2>Summary</h2>
<pre>{html.escape(json.dumps(summary, indent=2))}</pre>
</body>
</html>
"""
    Path(path).write_text(body, encoding="utf-8")


def build_grouping_diagnostics(
    *,
    source_pdf: str | Path | None,
    inspection: dict[str, Any],
    tabraw: dict[str, Any],
    artifacts: dict[str, Any],
    alignment_attempted: bool = False,
    scoreir_written: bool = False,
) -> dict[str, Any]:
    """Build a public-safe summary of PDF grouping quality."""

    candidates = list(tabraw.get("candidates", []))
    playable = [candidate for candidate in candidates if candidate.get("parsed_fret") is not None]
    kind_counts: dict[str, int] = {}
    for candidate in candidates:
        kind = str(candidate.get("kind", "candidate-text"))
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    inferred_systems = {candidate.get("system_index") for candidate in candidates if candidate.get("system_index") is not None}
    inferred_bars = {candidate.get("bar_index") for candidate in candidates if candidate.get("bar_index") is not None}
    inferred_string_assignment_count = sum(1 for candidate in playable if candidate.get("string") is not None)
    warning_codes = [str(warning.get("code", "warning")) for warning in tabraw.get("warnings", [])]
    grouping_status = grouping_status_for_tabraw(tabraw)
    grouping = _grouping_evidence_summary(candidates)
    ascii_candidates = [
        candidate
        for candidate in candidates
        if isinstance(candidate.get("raw"), dict) and candidate["raw"].get("parser_version") == "ascii-tab.v0.1"
    ]
    input_class = "ascii-tab" if ascii_candidates else "drawn-tab-or-text"
    ascii_timing_status_counts = _ascii_timing_status_counts(ascii_candidates)

    return {
        "schema_version": GROUPING_DIAGNOSTICS_SCHEMA_VERSION,
        "source_pdf_path": str(source_pdf) if source_pdf is not None else tabraw.get("source_pdf"),
        "inspection_kind": tabraw.get("inspection_kind") or inspection.get("kind") or "unknown",
        "input_class": input_class,
        "page_count": int(inspection.get("page_count", 0) or 0),
        "total_text_candidate_count": len(candidates),
        "playable_fret_candidate_count": len(playable),
        "chord_symbol_candidate_count": kind_counts.get("chord-symbol", 0),
        "technique_text_candidate_count": kind_counts.get("technique-text", 0),
        "candidate_text_count": kind_counts.get("candidate-text", 0),
        "inferred_system_count": len(inferred_systems),
        "inferred_bar_count": len(inferred_bars),
        "inferred_string_assignment_count": inferred_string_assignment_count,
        "grouping_status": grouping_status,
        "ascii_tab_candidate_count": len(ascii_candidates),
        "ascii_tab_block_count": _warning_sum(tabraw, "ascii_tab_detected", "ascii_tab_block_count"),
        "ascii_tab_complete_block_count": _warning_sum(
            tabraw,
            "ascii_tab_detected",
            "ascii_tab_complete_block_count",
        ),
        "ascii_tab_partial_block_count": _warning_sum(
            tabraw,
            "ascii_tab_detected",
            "ascii_tab_partial_block_count",
        ),
        "ascii_timing_candidate_count": sum(ascii_timing_status_counts.values()),
        "ascii_timing_status_counts": ascii_timing_status_counts,
        "ascii_timing_partial_candidate_count": ascii_timing_status_counts.get("timing_partial", 0),
        "ascii_timing_unavailable_candidate_count": ascii_timing_status_counts.get("timing_unavailable", 0),
        "ascii_timing_safe_candidate_count": ascii_timing_status_counts.get("timing_safe", 0),
        "warning_codes": sorted(set(warning_codes)),
        "alignment_attempted": alignment_attempted,
        "scoreir_written": scoreir_written,
        "grouping": grouping,
        "artifacts": artifacts,
    }


def grouping_status_for_tabraw(tabraw: dict[str, Any]) -> str:
    """Return grouped, partial, or missing for playable PDF-derived tab evidence."""

    candidates = list(tabraw.get("candidates", []))
    playable = [candidate for candidate in candidates if candidate.get("parsed_fret") is not None]
    if not candidates or not playable:
        return "missing"

    system_count = sum(1 for candidate in playable if candidate.get("system_index") is not None)
    bar_count = sum(1 for candidate in playable if candidate.get("bar_index") is not None)
    string_count = sum(1 for candidate in playable if candidate.get("string") is not None)
    warning_codes = {str(warning.get("code", "")) for warning in tabraw.get("warnings", [])}
    partial_warning_codes = {
        "partial_pdf_grouping",
        "missing_pdf_barlines",
        "incomplete_tab_staff",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
        "partial_ascii_tab_grouping",
    }
    if "partial_ascii_tab_grouping" in warning_codes:
        return "partial_ascii"
    ascii_timing_warning_codes = {
        "ascii_tab_timing_unavailable",
        "partial_ascii_tab_timing",
        "ambiguous_ascii_tab_timing",
        "unsupported_ascii_tab_rhythm",
        "ascii_tab_measure_boundary_missing",
    }
    if warning_codes.intersection(ascii_timing_warning_codes) and system_count and string_count:
        return "ascii_grouped"
    if system_count == 0 and bar_count == 0 and string_count == 0:
        return "missing"
    if (
        system_count < len(playable)
        or bar_count < len(playable)
        or string_count < len(playable)
        or warning_codes.intersection(partial_warning_codes)
    ):
        return "partial"
    return "grouped"


def write_grouping_diagnostics_html(path: str | Path, report: dict[str, Any]) -> None:
    """Write an inspectable grouping-failure report."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    artifacts = report.get("artifacts", {})
    overlay_items = "\n".join(
        f'<li><a href="{html.escape(str(overlay))}">{html.escape(str(overlay))}</a></li>'
        for overlay in artifacts.get("overlay_images", [])
    )
    warning_items = "\n".join(f"<li>{html.escape(code)}</li>" for code in report.get("warning_codes", []))
    grouping = report.get("grouping", {})
    system_items = "\n".join(
        _grouping_system_html(system)
        for system in grouping.get("systems", [])
        if isinstance(system, dict)
    )
    grouping_status = str(report.get("grouping_status", "unknown"))
    if grouping_status == "missing":
        verdict = "Extraction succeeded, but grouping failed."
    elif grouping_status == "partial":
        verdict = "Extraction succeeded, but grouping is partial and unsafe for automatic alignment."
    elif grouping_status == "partial_ascii":
        verdict = "Extraction succeeded and ASCII tab was detected, but ASCII grouping is partial."
    elif grouping_status == "ascii_grouped":
        timing_counts = report.get("ascii_timing_status_counts", {})
        if isinstance(timing_counts, dict) and timing_counts.get("timing_partial"):
            verdict = (
                "Extraction succeeded and ASCII tab rows were grouped with partial bar/column timing evidence; "
                "this is not yet safe musical timing."
            )
        else:
            verdict = "Extraction succeeded and ASCII tab rows were grouped, but timing/alignment is unavailable."
    else:
        verdict = "Extraction and grouping are present for the inspected candidates."
    if not report.get("alignment_attempted"):
        alignment_note = "Alignment/build-ir was not attempted by this extraction report."
    else:
        alignment_note = "Alignment/build-ir was attempted; inspect the build diagnostics for timing and matching quality."
    if not report.get("scoreir_written"):
        scoreir_note = "ScoreIR was not written."
    else:
        scoreir_note = "ScoreIR was written."

    body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>PDF Grouping Diagnostics</title></head>
<body>
<h1>PDF Grouping Diagnostics</h1>
<p>{html.escape(verdict)}</p>
<p>{html.escape(alignment_note)} {html.escape(scoreir_note)}</p>
<h2>Grouping Status</h2>
<dl>
  <dt>Source PDF</dt><dd>{html.escape(str(report.get("source_pdf_path", "")))}</dd>
  <dt>Inspection kind</dt><dd>{html.escape(str(report.get("inspection_kind", "unknown")))}</dd>
  <dt>Input class</dt><dd>{html.escape(str(report.get("input_class", "unknown")))}</dd>
  <dt>Page count</dt><dd>{html.escape(str(report.get("page_count", 0)))}</dd>
  <dt>Grouping status</dt><dd>{html.escape(grouping_status)}</dd>
</dl>
<h2>Candidate Counts</h2>
<dl>
  <dt>Candidate count</dt><dd>{report.get("total_text_candidate_count", 0)}</dd>
  <dt>Playable fret candidates</dt><dd>{report.get("playable_fret_candidate_count", 0)}</dd>
  <dt>Chord symbol candidates</dt><dd>{report.get("chord_symbol_candidate_count", 0)}</dd>
  <dt>Technique text candidates</dt><dd>{report.get("technique_text_candidate_count", 0)}</dd>
  <dt>Inferred systems</dt><dd>{report.get("inferred_system_count", 0)}</dd>
  <dt>Inferred bars</dt><dd>{report.get("inferred_bar_count", 0)}</dd>
  <dt>String assignments</dt><dd>{report.get("inferred_string_assignment_count", 0)}</dd>
  <dt>ASCII-tab candidates</dt><dd>{report.get("ascii_tab_candidate_count", 0)}</dd>
  <dt>ASCII-tab blocks</dt><dd>{report.get("ascii_tab_block_count", 0)}</dd>
  <dt>Complete ASCII-tab blocks</dt><dd>{report.get("ascii_tab_complete_block_count", 0)}</dd>
  <dt>Partial ASCII-tab blocks</dt><dd>{report.get("ascii_tab_partial_block_count", 0)}</dd>
  <dt>ASCII timing candidates</dt><dd>{report.get("ascii_timing_candidate_count", 0)}</dd>
  <dt>ASCII timing status counts</dt><dd><code>{html.escape(json.dumps(report.get("ascii_timing_status_counts", {}), sort_keys=True))}</code></dd>
</dl>
<h2>Warning Codes</h2>
<ul>{warning_items}</ul>
<h2>Inferred Grouping</h2>
<dl>
  <dt>System count</dt><dd>{grouping.get("system_count", 0) if isinstance(grouping, dict) else 0}</dd>
  <dt>Bar box count</dt><dd>{grouping.get("bar_box_count", 0) if isinstance(grouping, dict) else 0}</dd>
  <dt>Assigned candidate count</dt><dd>{grouping.get("assigned_candidate_count", 0) if isinstance(grouping, dict) else 0}</dd>
</dl>
<ul>{system_items}</ul>
<h2>Artifacts</h2>
<ul>
  <li>TabRaw: <a href="{html.escape(str(artifacts.get("tab_raw", "")))}">{html.escape(str(artifacts.get("tab_raw", "")))}</a></li>
  <li>Warnings: <a href="{html.escape(str(artifacts.get("warnings", "")))}">{html.escape(str(artifacts.get("warnings", "")))}</a></li>
  <li>Diagnostic HTML: {html.escape(str(artifacts.get("diagnostic_html", "")))}</li>
</ul>
<h2>Overlays</h2>
<ul>{overlay_items}</ul>
<h2>Raw Summary</h2>
<pre>{html.escape(json.dumps(report, indent=2))}</pre>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")


def _grouping_evidence_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    systems: dict[tuple[int, int, int], dict[str, Any]] = {}
    for candidate in candidates:
        raw = candidate.get("raw")
        if not isinstance(raw, dict):
            continue
        staff_bbox = raw.get("tab_staff_bbox")
        line_ys = raw.get("tab_line_ys")
        if not isinstance(staff_bbox, dict) or not isinstance(line_ys, list):
            continue
        page_index = int(candidate.get("page_index") or staff_bbox.get("page") or 0)
        system_index = int(candidate.get("system_index") or 0)
        staff_index = int(candidate.get("staff_index") or 0)
        if not page_index or not system_index or not staff_index:
            continue
        key = (page_index, system_index, staff_index)
        if key not in systems:
            bar_boxes = raw.get("bar_boxes", [])
            if not isinstance(bar_boxes, list):
                bar_boxes = []
            systems[key] = {
                "page_index": page_index,
                "system_index": system_index,
                "staff_index": staff_index,
                "tab_staff_bbox": staff_bbox,
                "tab_line_ys": line_ys,
                "barline_xs": raw.get("barline_xs", []) if isinstance(raw.get("barline_xs"), list) else [],
                "bar_boxes": bar_boxes,
                "grouping_confidence": raw.get("grouping_confidence"),
                "grouping_version": raw.get("grouping_version"),
                "system_inference": raw.get("system_inference"),
                "ascii_timing_status": raw.get("ascii_timing_status"),
                "ascii_timing_confidence": raw.get("ascii_timing_confidence"),
                "ascii_bar_separator_count": raw.get("ascii_bar_separator_count"),
                "ascii_bar_separators_aligned": raw.get("ascii_bar_separators_aligned"),
                "ascii_measure_segment_count": raw.get("ascii_measure_segment_count"),
                "grouping_warnings": raw.get("grouping_warnings", [])
                if isinstance(raw.get("grouping_warnings", []), list)
                else [],
                "candidate_ids": [],
                "string_assigned_candidate_ids": [],
                "bar_assigned_candidate_ids": [],
            }
        systems[key]["candidate_ids"].append(candidate.get("id"))
        if candidate.get("string") is not None:
            systems[key]["string_assigned_candidate_ids"].append(candidate.get("id"))
        if candidate.get("bar_index") is not None:
            systems[key]["bar_assigned_candidate_ids"].append(candidate.get("id"))

    system_values = [systems[key] for key in sorted(systems)]
    return {
        "schema_version": "pdf-grouping.v0.1",
        "system_count": len(system_values),
        "bar_box_count": sum(len(system.get("bar_boxes", [])) for system in system_values),
        "assigned_candidate_count": sum(len(system.get("candidate_ids", [])) for system in system_values),
        "systems": system_values,
    }


def _grouping_system_html(system: dict[str, Any]) -> str:
    bbox = system.get("tab_staff_bbox", {})
    bbox_text = json.dumps(bbox, sort_keys=True)
    warnings = ", ".join(str(item) for item in system.get("grouping_warnings", [])) or "none"
    return (
        "<li>"
        f"page {html.escape(str(system.get('page_index')))}, "
        f"system {html.escape(str(system.get('system_index')))}, "
        f"staff {html.escape(str(system.get('staff_index')))}; "
        f"source: {html.escape(str(system.get('system_inference')))}; "
        f"Tab staff bbox: <code>{html.escape(bbox_text)}</code>; "
        f"string lines: {html.escape(str(len(system.get('tab_line_ys', []))))}; "
        f"bar boxes: {html.escape(str(len(system.get('bar_boxes', []))))}; "
        f"candidate assignments: {html.escape(str(len(system.get('candidate_ids', []))))}; "
        f"grouping confidence: {html.escape(str(system.get('grouping_confidence')))}; "
        f"ASCII timing: {html.escape(str(system.get('ascii_timing_status')))}; "
        f"ASCII bar separators: {html.escape(str(system.get('ascii_bar_separator_count')))}; "
        f"ASCII measure segments: {html.escape(str(system.get('ascii_measure_segment_count')))}; "
        f"warnings: {html.escape(warnings)}"
        "</li>"
    )


def _warning_sum(tabraw: dict[str, Any], code: str, field: str) -> int:
    total = 0
    for warning in tabraw.get("warnings", []):
        if warning.get("code") != code:
            continue
        value = warning.get(field, 0)
        if isinstance(value, int):
            total += value
    return total


def _ascii_timing_status_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        raw = candidate.get("raw")
        if not isinstance(raw, dict):
            continue
        status = raw.get("ascii_timing_status")
        if not isinstance(status, str) or not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))
