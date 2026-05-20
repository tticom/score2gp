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

    return {
        "schema_version": GROUPING_DIAGNOSTICS_SCHEMA_VERSION,
        "source_pdf_path": str(source_pdf) if source_pdf is not None else tabraw.get("source_pdf"),
        "inspection_kind": tabraw.get("inspection_kind") or inspection.get("kind") or "unknown",
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
    if system_count == 0 or bar_count == 0 or string_count == 0:
        return "missing"
    if system_count < len(playable) or bar_count < len(playable) or string_count < len(playable):
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
        f"Tab staff bbox: <code>{html.escape(bbox_text)}</code>; "
        f"string lines: {html.escape(str(len(system.get('tab_line_ys', []))))}; "
        f"bar boxes: {html.escape(str(len(system.get('bar_boxes', []))))}; "
        f"candidate assignments: {html.escape(str(len(system.get('candidate_ids', []))))}; "
        f"grouping confidence: {html.escape(str(system.get('grouping_confidence')))}; "
        f"warnings: {html.escape(warnings)}"
        "</li>"
    )
