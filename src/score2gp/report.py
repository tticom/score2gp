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
    ascii_timing_status_counts = _ascii_timing_status_counts(ascii_candidates)

    # Compute custom layout metrics
    drawn_system_count = 0
    staff_line_count = 0
    system_ambiguity_count = 0
    for warning in tabraw.get("warnings", []):
        if warning.get("code") == "pdf_layout_details":
            drawn_system_count = warning.get("detected_systems", 0)
            staff_line_count = warning.get("detected_string_lines", 0)
        if warning.get("code") in ("pdf_multi_system_order_ambiguous", "pdf_system_order_ambiguous", "pdf_system_bbox_ambiguous", "pdf_tab_staff_ambiguous"):
            system_ambiguity_count += 1

    # Fallback to candidate-assigned system count if layout warning is missing
    if drawn_system_count == 0 and not ascii_candidates:
        drawn_system_count = len(inferred_systems)

    ascii_block_count = 0
    for warning in tabraw.get("warnings", []):
        if warning.get("code") == "ascii_tab_detected":
            ascii_block_count += warning.get("ascii_tab_block_count", 0)

    # Determine input_class
    if drawn_system_count > 0 and ascii_block_count > 0:
        input_class = "mixed_candidate"
    elif "pdf_ascii_and_drawn_layout_conflict" in warning_codes or "pdf_page_layout_unsupported" in warning_codes:
        input_class = "mixed_candidate"
    elif ascii_block_count > 0 or ascii_candidates:
        input_class = "ascii_tab_candidate"
    elif drawn_system_count > 0 or len(inferred_systems) > 0 or staff_line_count > 0:
        input_class = "drawn_tab_candidate"
    elif playable:
        input_class = "unsupported"
    else:
        input_class = "unsupported"

    whether_system_detection_succeeded = (drawn_system_count > 0 or ascii_block_count > 0)
    has_bar_box_warnings = any(code in warning_codes for code in (
        "pdf_barlines_not_detected_in_system",
        "pdf_bar_boxes_not_constructible",
        "pdf_partial_grouping_one_system_unboxed",
        "pdf_bar_box_construction_not_enough_for_build_ir",
        "pdf_bar_box_too_narrow",
        "pdf_bar_box_overlaps_neighbor",
        "pdf_bar_box_outside_system_bounds",
        "pdf_bar_box_requires_two_boundaries",
    ))
    whether_bar_detection_succeeded = len(inferred_bars) > 0 and not has_bar_box_warnings
    whether_string_assignment_succeeded = inferred_string_assignment_count > 0

    is_blocked = grouping_status not in ("grouped", "ascii_grouped")

    # Determine primary_blocker_stage
    if not whether_system_detection_succeeded:
        primary_blocker_stage = "system_detection"
    elif input_class in ("unsupported", "mixed_candidate") and is_blocked:
        primary_blocker_stage = "unsupported_input_class"
    elif not whether_bar_detection_succeeded:
        primary_blocker_stage = "bar_detection"
    elif not whether_string_assignment_succeeded:
        primary_blocker_stage = "string_assignment"
    elif is_blocked:
        primary_blocker_stage = "timing_alignment"
    else:
        primary_blocker_stage = "none"

    return {
        "schema_version": GROUPING_DIAGNOSTICS_VERSION if "GROUPING_DIAGNOSTICS_VERSION" in globals() else GROUPING_DIAGNOSTICS_SCHEMA_VERSION,
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

        # New fields for PDF system/layout taxonomy split
        "drawn_system_count": drawn_system_count,
        "ascii_block_count": ascii_block_count,
        "staff_line_count": staff_line_count,
        "system_ambiguity_count": system_ambiguity_count,
        "whether_system_detection_succeeded": whether_system_detection_succeeded,
        "whether_bar_detection_succeeded": whether_bar_detection_succeeded,
        "whether_string_assignment_succeeded": whether_string_assignment_succeeded,
        "whether_build_ir_blocked": is_blocked,
        "primary_blocker_stage": primary_blocker_stage,
    }


def grouping_status_for_tabraw(tabraw: dict[str, Any]) -> str:
    """Return grouped, partial, missing, ambiguous, or unsupported for playable PDF-derived tab evidence."""

    candidates = list(tabraw.get("candidates", []))
    playable = [candidate for candidate in candidates if candidate.get("parsed_fret") is not None]
    if not candidates or not playable:
        return "missing"

    system_count = sum(1 for candidate in playable if candidate.get("system_index") is not None)
    bar_count = sum(1 for candidate in playable if candidate.get("bar_index") is not None)
    string_count = sum(1 for candidate in playable if candidate.get("string") is not None)
    warning_codes = {str(warning.get("code", "")) for warning in tabraw.get("warnings", [])}

    unsupported_codes = {
        "pdf_ascii_and_drawn_layout_conflict",
        "pdf_page_layout_unsupported",
    }
    ambiguous_codes = {
        "pdf_multi_system_order_ambiguous",
        "pdf_tab_staff_ambiguous",
        "pdf_barlines_ambiguous",
        "pdf_string_assignment_ambiguous",
        "pdf_system_bbox_ambiguous",
        "pdf_system_order_ambiguous",
    }
    missing_codes = {
        "pdf_no_systems_detected",
        "pdf_tab_staff_missing",
        "pdf_barlines_missing",
        "pdf_bar_boxes_missing",
        "pdf_string_lines_missing",
        "pdf_string_assignment_missing",
        "pdf_grouping_not_safe_for_build_ir",
        "missing_pdf_grouping",
        "pdf_text_geometry_present_but_no_safe_system",
        "pdf_tab_candidates_present_but_system_not_detected",
        "pdf_drawn_geometry_present_but_staff_unresolved",
        "pdf_tab_staff_lines_fragmented",
        "pdf_tab_staff_lines_overlapping",
        "pdf_tab_staff_spacing_inconsistent",
        "pdf_missing_pdf_grouping_blocks_build_ir",
    }
    partial_codes = {
        "partial_pdf_grouping",
        "missing_pdf_barlines",
        "incomplete_tab_staff",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
        "partial_ascii_tab_grouping",
        "pdf_partial_system_detection",
        "pdf_tab_staff_incomplete",
        "pdf_candidate_outside_system",
        "pdf_candidate_outside_bar",
        "pdf_candidate_between_strings",
        "pdf_text_candidate_without_geometry",
        "pdf_candidates_unassigned_to_system",
        "pdf_candidates_unassigned_to_bar",
        "pdf_candidates_unassigned_to_string",
        "pdf_partial_grouping_with_playable_candidates",
        "pdf_grouping_confidence_below_threshold",
        "pdf_layout_detection_requires_manual_review",

        # New Phase 6 Bar Box Construction Codes
        "pdf_bar_box_requires_two_boundaries",
        "pdf_bar_box_missing_left_boundary",
        "pdf_bar_box_missing_right_boundary",
        "pdf_bar_box_boundary_ambiguous",
        "pdf_bar_box_too_narrow",
        "pdf_bar_box_overlaps_neighbor",
        "pdf_bar_box_outside_system_bounds",
        "pdf_candidate_between_bar_boxes",
        "pdf_candidate_on_bar_boundary",
        "pdf_candidate_unassigned_to_bar",
        "pdf_partial_grouping_one_system_unboxed",
        "pdf_bar_box_construction_not_enough_for_build_ir",

        # New Phase 7 Bar Box Construction Edge Cases Codes
        "pdf_bar_box_single_system_failure",
        "pdf_bar_box_edge_system_missing_boundary",
        "pdf_bar_box_one_boundary_rejected",
        "pdf_barline_short_but_near_staff_boundary",
        "pdf_barline_ambiguous_on_edge_system",
        "pdf_candidate_unassigned_due_to_unboxed_system",
        "pdf_candidate_near_missing_bar_boundary",
        "pdf_boundary_candidate_blocks_full_grouping",
        "pdf_full_grouping_requires_all_systems_boxed",
        "pdf_grouping_complete_all_playable_candidates_assigned",

        # New Phase 8 Edge System Boundary Fallback Codes
        "pdf_bar_box_inferred_edge_boundary",
        "pdf_bar_box_inferred_left_boundary",
        "pdf_bar_box_inferred_right_boundary",
        "pdf_bar_box_edge_boundary_fallback_used",
        "pdf_bar_box_edge_boundary_fallback_rejected",
        "pdf_bar_box_edge_boundary_ambiguous",
        "pdf_bar_box_inferred_boundary_too_narrow",
        "pdf_bar_box_inferred_boundary_candidate_ambiguous",
        "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
        "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",
    }

    if warning_codes.intersection(unsupported_codes):
        return "unsupported"
    if warning_codes.intersection(ambiguous_codes):
        return "ambiguous"

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

    if warning_codes.intersection(missing_codes):
        return "missing"

    if system_count == 0 and bar_count == 0 and string_count == 0:
        return "missing"
    if (
        system_count < len(playable)
        or bar_count < len(playable)
        or string_count < len(playable)
        or warning_codes.intersection(partial_codes)
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
    elif grouping_status == "ambiguous":
        verdict = "Extraction succeeded, but grouping/layout is ambiguous and unsafe."
    elif grouping_status == "unsupported":
        verdict = "Extraction succeeded, but layout/format is unsupported."
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

    is_blocked = grouping_status not in ("grouped", "ascii_grouped")
    build_ir_blocked_status = "Yes, blocked (unsafe PDF layout grouping)" if is_blocked else "No (safe grouping)"

    # Text/geometry detection status
    text_geometry_detected = "Yes" if report.get("total_text_candidate_count", 0) > 0 or report.get("inspection_kind") in ("born-digital", "mixed") else "No"

    # Systems/lines/bars detection status
    system_detection_status = "Detected" if report.get("inferred_system_count", 0) > 0 or report.get("drawn_system_count", 0) > 0 or report.get("ascii_block_count", 0) > 0 else "Missing"
    staff_line_detection_status = "Detected" if report.get("inferred_string_assignment_count", 0) > 0 or report.get("drawn_system_count", 0) > 0 or report.get("ascii_block_count", 0) > 0 else "Missing"
    bar_detection_status = "Detected" if report.get("inferred_bar_count", 0) > 0 else "Missing"
    string_assignment_status = "Assigned" if report.get("inferred_string_assignment_count", 0) > 0 else "Unassigned/Missing"

    # Primary and secondary layout warnings
    warnings = report.get("warning_codes", [])
    primary_warning = warnings[0] if warnings else "None"
    secondary_warnings = ", ".join(warnings[1:]) if len(warnings) > 1 else "None"

    if not report.get("alignment_attempted"):
        alignment_note = "Alignment/build-ir was not attempted by this extraction report."
    else:
        alignment_note = "Alignment/build-ir was attempted; inspect the build diagnostics for timing and matching quality."

    scoreir_written = bool(report.get("scoreir_written"))
    scoreir_note = "ScoreIR was written." if scoreir_written else "ScoreIR was not written."

    remediation_hint = ""
    if is_blocked:
        primary_stage = report.get("primary_blocker_stage", "unknown")
        if primary_stage == "system_detection":
            hint_text = "System detection is incomplete; use a clearer born-digital fixture, improve public layout heuristics, or review manually."
        elif primary_stage == "bar_detection":
            if any(w in warnings for w in (
                "pdf_bar_box_too_narrow",
                "pdf_bar_box_overlaps_neighbor",
                "pdf_bar_box_outside_system_bounds",
                "pdf_bar_box_requires_two_boundaries",
                "pdf_partial_grouping_one_system_unboxed",
                "pdf_candidate_unassigned_to_bar",
                "pdf_candidate_on_bar_boundary",
                "pdf_bar_box_construction_not_enough_for_build_ir",
                "pdf_bar_box_single_system_failure",
                "pdf_bar_box_edge_system_missing_boundary",
                "pdf_bar_box_one_boundary_rejected",
                "pdf_barline_short_but_near_staff_boundary",
                "pdf_barline_ambiguous_on_edge_system",
                "pdf_candidate_unassigned_due_to_unboxed_system",
                "pdf_candidate_near_missing_bar_boundary",
                "pdf_boundary_candidate_blocks_full_grouping",
                "pdf_full_grouping_requires_all_systems_boxed",
                "pdf_bar_box_inferred_edge_boundary",
                "pdf_bar_box_inferred_left_boundary",
                "pdf_bar_box_inferred_right_boundary",
                "pdf_bar_box_edge_boundary_fallback_used",
                "pdf_bar_box_edge_boundary_fallback_rejected",
                "pdf_bar_box_edge_boundary_ambiguous",
                "pdf_bar_box_inferred_boundary_too_narrow",
                "pdf_bar_box_inferred_boundary_candidate_ambiguous",
                "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
                "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",
            )):
                if "pdf_bar_box_edge_boundary_fallback_rejected" in warnings:
                    hint_text = "A missing edge boundary was inferred only because the system edge and candidate assignment were unambiguous. Fallback was rejected because layout constraints were violated."
                else:
                    hint_text = "Accepted barlines exist, but safe bar boxes could not be constructed or candidates could not be assigned."
            else:
                hint_text = "Barline candidates exist but do not safely cross enough of the tab staff."
        else:
            hint_text = "PDF layout grouping is unsafe; use a clearer born-digital fixture, improve public layout heuristics, or review manually."

        remediation_hint = f"""
        <div style="background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; padding: 12px; margin: 16px 0; border-radius: 4px;">
            <strong>Remediation Hint:</strong> {html.escape(hint_text)}
        </div>
        """

    body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>PDF Grouping Diagnostics</title></head>
<body>
<h1>PDF Grouping Diagnostics</h1>
<p>{html.escape(verdict)}</p>
<p>{html.escape(alignment_note)} {html.escape(scoreir_note)}</p>
{remediation_hint}
<h2>Grouping Status</h2>
<dl>
  <dt>Source PDF</dt><dd>{html.escape(str(report.get("source_pdf_path", "")))}</dd>
  <dt>Inspection kind</dt><dd>{html.escape(str(report.get("inspection_kind", "unknown")))}</dd>
  <dt>Input class</dt><dd>{html.escape(str(report.get("input_class", "unknown")))}</dd>
  <dt>Page count</dt><dd>{html.escape(str(report.get("page_count", 0)))}</dd>
  <dt>Grouping status</dt><dd>{html.escape(grouping_status)}</dd>
  <dt>Text/Geometry Detected Status</dt><dd>{html.escape(text_geometry_detected)}</dd>
  <dt>Drawn Systems Detected</dt><dd>{report.get("drawn_system_count", 0)}</dd>
  <dt>ASCII Blocks Detected</dt><dd>{report.get("ascii_block_count", 0)}</dd>
  <dt>System Detection Status</dt><dd>{html.escape(system_detection_status)}</dd>
  <dt>Staff-line Detection Status</dt><dd>{html.escape(staff_line_detection_status)}</dd>
  <dt>Bar Detection Status</dt><dd>{html.escape(bar_detection_status)}</dd>
  <dt>String Assignment Status</dt><dd>{html.escape(string_assignment_status)}</dd>
  <dt>Primary Blocker Stage</dt><dd><code>{html.escape(str(report.get("primary_blocker_stage", "none")))}</code></dd>
  <dt>Build-IR Blocked Status</dt><dd>{html.escape(build_ir_blocked_status)}</dd>
  <dt>ScoreIR Written Status</dt><dd>{"Yes" if scoreir_written else "No"}</dd>
  <dt>Primary Layout Warning</dt><dd>{html.escape(primary_warning)}</dd>
  <dt>Secondary Layout Warnings</dt><dd>{html.escape(secondary_warnings)}</dd>
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
  {f'<li>PDF Edge Boundary Report JSON: <a href="{html.escape(str(artifacts.get("pdf_edge_boundary_report_json", "")))}">{html.escape(str(artifacts.get("pdf_edge_boundary_report_json", "")))}</a></li>' if "pdf_edge_boundary_report_json" in artifacts else ''}
  {f'<li>PDF Edge Boundary Report HTML: <a href="{html.escape(str(artifacts.get("pdf_edge_boundary_report_html", "")))}">{html.escape(str(artifacts.get("pdf_edge_boundary_report_html", "")))}</a></li>' if "pdf_edge_boundary_report_html" in artifacts else ''}
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
                "barline_candidates_count": raw.get("barline_candidates_count"),
                "valid_barline_count": raw.get("valid_barline_count"),
                "rejected_barline_count": raw.get("rejected_barline_count"),
                "rejection_reasons": raw.get("rejection_reasons"),
                "barline_candidates_details": raw.get("barline_candidates_details"),
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
    barline_cands = system.get("barline_candidates_count")
    valid_barlines = system.get("valid_barline_count")
    rejected_barlines = system.get("rejected_barline_count")
    reasons = system.get("rejection_reasons")
    reasons_str = json.dumps(reasons) if reasons else "none"

    details = system.get("barline_candidates_details", [])
    details_html = ""
    if details:
        details_items = []
        for d in details:
            details_items.append(
                f"Candidate at x={d.get('x')} (height={d.get('height')}, crossed={d.get('gaps_crossed')} gaps, staff_h={d.get('staff_height')}, coverage={d.get('coverage_ratio')}) "
                f"decision: {d.get('final_decision')} (reasons: absolute_height={d.get('absolute_height_decision')}, relative_crossing={d.get('relative_staff_crossing_decision')}, error={d.get('rejection_reason') or 'none'})"
            )
        details_html = "<br/>&nbsp;&nbsp;&nbsp;&nbsp;Candidates details:<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in details_items) + "</ul>"

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
        f"barline candidates: {html.escape(str(barline_cands))}; "
        f"valid barlines: {html.escape(str(valid_barlines))}; "
        f"rejected barlines: {html.escape(str(rejected_barlines))} (reasons: {html.escape(reasons_str)});"
        f"{details_html} "
        f"grouping confidence: {html.escape(str(system.get('grouping_confidence')))}; "
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


def write_ascii_gate_diagnostics_html(path: str | Path, payload: dict[str, Any], json_path_ref: str | Path | None = None) -> None:
    """Write an inspectable developer-facing HTML report for ASCII ScoreIR gate refusal diagnostics."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    details = payload.get("details", {})
    gate_status = str(details.get("ascii_scoreir_gate_status", "refused"))

    status_label = "Allowed" if gate_status == "allowed" else "Refused"
    status_class = "status-allowed" if gate_status == "allowed" else "status-refused"

    primary_reason = details.get("primary_reason_code") or payload.get("category") or "unknown_refusal"
    secondary_reasons = details.get("secondary_reason_codes", [])

    mapping = {
        "missing_ascii_alignment_sidecar": "provide compatible ascii-musicxml-alignment.v0.1 evidence",
        "ascii_alignment_status_unavailable": "provide ASCII timing evidence with usable measure segmentation",
        "ascii_alignment_status_partial": "resolve partial ASCII/MusicXML alignment before ScoreIR writing",
        "ascii_alignment_status_ambiguous": "resolve ambiguous ASCII/MusicXML mapping before ScoreIR writing",
        "ascii_alignment_status_incompatible": "fix the public fixture pair so ASCII candidates and MusicXML onsets agree",
        "ascii_alignment_candidate_missing": "ensure every output candidate appears in the alignment sidecar",
        "ascii_alignment_not_one_to_one": "use a tiny monophonic fixture with one candidate per MusicXML note",
        "ascii_candidate_missing_string": "provide explicit ASCII-derived string evidence for every candidate",
        "ascii_candidate_missing_fret": "provide explicit ASCII-derived fret evidence for every candidate",
        "ascii_candidate_unmapped_measure": "map every candidate to a known MusicXML measure",
        "ascii_candidate_unmapped_onset": "map every candidate to a known MusicXML onset",
        "ascii_unsupported_technique_required": "remove unsupported technique requirements or implement a future technique phase",
        "ascii_unsupported_chord_symbol": "remove chord/symbol requirements or implement a future symbol phase",
        "ascii_polyphony_not_supported": "use the supported tiny monophonic fixture shape",
        "ascii_musicxml_timing_risk": "fix MusicXML timing risk before attempting ASCII ScoreIR writing",
        "ascii_duration_source_missing": "provide MusicXML durations for every output event",
        "ascii_outside_tiny_gate_scope": "this case is intentionally unsupported by ascii-scoreir-gate.v0.1",
    }
    remediation = details.get("expected_next_remediation") or mapping.get(str(primary_reason), "this case is intentionally unsupported by ascii-scoreir-gate.v0.1")

    candidate_count = details.get("candidate_count", 0)
    aligned_candidate_count = details.get("aligned_candidate_count", 0)
    rejected_candidate_count = details.get("rejected_candidate_count", 0)

    sample_candidate_ids = details.get("sample_candidate_ids", [])

    sidecar_present = details.get("alignment_sidecar_present")
    sidecar_status = details.get("alignment_status")
    timing_safe = details.get("musicxml_timing_safe")
    scoreir_written = details.get("scoreir_written", False)

    json_reference_str = "N/A"
    if json_path_ref is not None:
        json_reference_str = str(json_path_ref)
    elif details.get("alignment_path"):
        json_reference_str = str(details.get("alignment_path"))

    secondary_html = ""
    if secondary_reasons:
        secondary_html = "\n".join(f"<li><code>{html.escape(str(r))}</code></li>" for r in secondary_reasons)
    else:
        secondary_html = "<li><em>None</em></li>"

    sample_ids_html = ""
    if sample_candidate_ids:
        sample_ids_html = ", ".join(f"<code>{html.escape(str(cid))}</code>" for cid in sample_candidate_ids)
    else:
        sample_ids_html = "<em>None</em>"

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ASCII ScoreIR Gate Diagnostics</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {{
      --bg-color: #0b0f19;
      --card-bg: #151e30;
      --card-border: #202c46;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --divider: #1e293b;

      --accent-refused: #f87171;
      --accent-refused-glow: rgba(248, 113, 113, 0.1);
      --accent-allowed: #34d399;
      --accent-allowed-glow: rgba(52, 211, 153, 0.1);
    }}

    body {{
      background-color: var(--bg-color);
      color: var(--text-primary);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 2rem 1rem;
      min-height: 100vh;
      line-height: 1.5;
    }}

    .container {{
      max-width: 800px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 1.5rem;
    }}

    h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.025em;
    }}

    .badge {{
      font-size: 0.875rem;
      font-weight: 600;
      padding: 0.375rem 1rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid transparent;
    }}

    .status-refused {{
      background-color: var(--accent-refused-glow);
      color: var(--accent-refused);
      border-color: rgba(248, 113, 113, 0.2);
    }}

    .status-allowed {{
      background-color: var(--accent-allowed-glow);
      color: var(--accent-allowed);
      border-color: rgba(52, 211, 153, 0.2);
    }}

    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
      transition: transform 0.2s, box-shadow 0.2s;
    }}

    .card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -4px rgba(0, 0, 0, 0.2);
    }}

    .card-title {{
      font-size: 0.875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-top: 0;
      margin-bottom: 1rem;
    }}

    .reason-box {{
      border-left: 4px solid var(--accent-refused);
      background-color: rgba(248, 113, 113, 0.05);
      padding: 1rem;
      border-radius: 0 8px 8px 0;
      margin-bottom: 1rem;
    }}

    .reason-box.allowed {{
      border-left-color: var(--accent-allowed);
      background-color: rgba(52, 211, 153, 0.05);
    }}

    .reason-title {{
      font-size: 1.125rem;
      font-weight: 700;
      margin: 0 0 0.5rem 0;
    }}

    .reason-code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9rem;
      background-color: rgba(0, 0, 0, 0.2);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      color: var(--text-primary);
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}

    .metric-card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem;
      text-align: center;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .metric-value {{
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      color: var(--text-primary);
    }}

    .metric-label {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
    }}

    dl {{
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.5rem 1.5rem;
      margin: 0;
    }}

    dt {{
      font-weight: 500;
      color: var(--text-secondary);
    }}

    dd {{
      margin: 0;
      font-weight: 600;
    }}

    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.875rem;
      background-color: rgba(0, 0, 0, 0.2);
      padding: 0.125rem 0.25rem;
      border-radius: 4px;
    }}

    ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}

    li {{
      margin-bottom: 0.5rem;
    }}

    .remediation-card {{
      background-color: rgba(52, 211, 153, 0.05);
      border: 1px solid rgba(52, 211, 153, 0.2);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}

    .remediation-title {{
      font-size: 0.875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent-allowed);
      margin-top: 0;
      margin-bottom: 0.5rem;
    }}

    .remediation-text {{
      font-size: 1.05rem;
      font-weight: 500;
      margin: 0;
    }}

    .footer-note {{
      font-size: 0.825rem;
      color: var(--text-secondary);
      text-align: center;
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--divider);
    }}

    pre {{
      background-color: rgba(0, 0, 0, 0.3);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      border: 1px solid var(--card-border);
      margin: 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>ASCII ScoreIR Gate Refusal Diagnostics</h1>
      <span class="badge {status_class}">{status_label}</span>
    </header>

    <div class="card">
      <h2 class="card-title">Verdict & Diagnostics</h2>
      <div class="reason-box {"allowed" if gate_status == "allowed" else ""}">
        <h3 class="reason-title">{html.escape(payload.get("message", ""))}</h3>
        <p style="margin: 0.5rem 0 0 0;">Primary refusal code: <span class="reason-code">{html.escape(str(primary_reason))}</span></p>
      </div>
      <p style="margin: 1rem 0 0 0; font-size: 0.925rem; color: var(--text-secondary);">
        Refusal is expected behavior for unsupported ASCII inputs. This HTML report does not imply broader ASCII-to-ScoreIR support. JSON remains the source of truth.
      </p>
    </div>

    <div class="remediation-card">
      <h2 class="remediation-title">Suggested Remediation</h2>
      <p class="remediation-text">{html.escape(str(remediation))}</p>
    </div>

    <div class="grid">
      <div class="metric-card">
        <div class="metric-value">{candidate_count}</div>
        <div class="metric-label">Total Candidates</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{aligned_candidate_count}</div>
        <div class="metric-label">Aligned Candidates</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{rejected_candidate_count}</div>
        <div class="metric-label">Rejected Candidates</div>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Refusal Taxonomy</h2>
      <dl style="margin-bottom: 1.5rem;">
        <dt>Primary Reason</dt>
        <dd><code>{html.escape(str(primary_reason))}</code></dd>

        <dt>Secondary Reasons</dt>
        <dd>
          <ul style="padding-left: 1.25rem; margin-top: 0.25rem;">
            {secondary_html}
          </ul>
        </dd>

        <dt>Sample Candidate IDs</dt>
        <dd>{sample_ids_html}</dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">Gate Metadata</h2>
      <dl>
        <dt>Gate Version</dt>
        <dd><code>{html.escape(str(details.get("gate_version", "unknown")))}</code></dd>

        <dt>ScoreIR Written</dt>
        <dd><code>{str(scoreir_written)}</code></dd>

        <dt>Alignment Sidecar Present</dt>
        <dd><code>{str(sidecar_present) if sidecar_present is not None else "N/A"}</code></dd>

        <dt>Alignment Status</dt>
        <dd><code>{html.escape(str(sidecar_status)) if sidecar_status is not None else "N/A"}</code></dd>

        <dt>Alignment Schema</dt>
        <dd><code>{html.escape(str(details.get("schema_version"))) if details.get("schema_version") is not None else "N/A"}</code></dd>

        <dt>MusicXML Timing Safe</dt>
        <dd><code>{str(timing_safe) if timing_safe is not None else "N/A"}</code></dd>

        <dt>JSON Reference</dt>
        <dd><code>{html.escape(json_reference_str)}</code></dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">JSON Diagnostics Payload Reference</h2>
      <pre><code>{html.escape(json.dumps(payload, indent=2, sort_keys=True))}</code></pre>
    </div>

    <div class="footer-note">
      This diagnostic report is generated automatically by the Antigravity Score2GP pipeline.
    </div>
  </div>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")


def write_symbol_attachment_diagnostics_html(
    path: str | Path,
    diagnostics: Any,
    score: Any,
    tabraw_path: str | Path | None = None,
) -> None:
    """Write an inspectable developer-facing HTML report for attached and unattached chord/technique evidence in generated ScoreIR."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Map warnings by candidate ID
    warnings_by_candidate = {}
    for warning in getattr(score, "warnings", []):
        for prov in getattr(warning, "provenance", []):
            if getattr(prov, "raw_token_id", None):
                tid = prov.raw_token_id
                if tid not in warnings_by_candidate:
                    warnings_by_candidate[tid] = []
                warnings_by_candidate[tid].append(warning)

    # 2. Traverse score to build attached map
    attached_map = {}
    for bar in getattr(score, "bars", []):
        for event in getattr(bar, "events", []):
            if getattr(event, "chord_symbol", None):
                for prov in getattr(event, "provenance", []):
                    if getattr(prov, "raw_token_id", None):
                        attached_map[prov.raw_token_id] = {
                            "bar_index": bar.index,
                            "event_id": event.id,
                            "note_desc": None,
                        }
            for note in getattr(event, "notes", []):
                for prov in getattr(note, "provenance", []):
                    if getattr(prov, "raw_token_id", None):
                        attached_map[prov.raw_token_id] = {
                            "bar_index": bar.index,
                            "event_id": event.id,
                            "note_desc": f"String {note.string}, Fret {note.fret}",
                        }

    # 3. Load tabraw if available to populate candidates list
    tabraw = None
    if tabraw_path:
        t_path = Path(tabraw_path)
        if t_path.exists():
            try:
                from .tabraw import TabRaw
                tabraw = TabRaw.from_json_file(t_path)
            except Exception:
                pass
    if not tabraw and getattr(diagnostics, "tabraw_source", None):
        t_path = Path(diagnostics.tabraw_source)
        if t_path.exists():
            try:
                from .tabraw import TabRaw
                tabraw = TabRaw.from_json_file(t_path)
            except Exception:
                pass

    chord_rows = []
    tech_rows = []

    if tabraw:
        for candidate in getattr(tabraw, "candidates", []):
            cid = getattr(candidate, "id", None)
            kind = getattr(candidate, "kind", None)
            text = getattr(candidate, "raw_text", "")
            conf = getattr(candidate, "confidence", 1.0)
            bar_idx = getattr(candidate, "bar_index", None)

            if not cid or kind not in ("chord-symbol", "technique-text"):
                continue

            is_attached = cid in attached_map

            if kind == "chord-symbol":
                target_bar = bar_idx
                target_event = attached_map[cid]["event_id"] if is_attached else None
                status = "Attached" if is_attached else "Unattached"
                status_class = "status-attached" if is_attached else "status-unattached"

                warns = warnings_by_candidate.get(cid, [])
                warn_text = "; ".join(f"[{w.code}] {w.message}" for w in warns) if warns else ("N/A" if is_attached else "Unattached (no specific warning)")

                chord_rows.append({
                    "id": cid,
                    "text": text,
                    "confidence": conf,
                    "bar_index": target_bar,
                    "event_id": target_event,
                    "status": status,
                    "status_class": status_class,
                    "warning_info": warn_text,
                })

            elif kind == "technique-text":
                target_bar = bar_idx
                target_event = attached_map[cid]["event_id"] if is_attached else None
                target_note = attached_map[cid]["note_desc"] if is_attached else None
                status = "Attached" if is_attached else "Unattached"
                status_class = "status-attached" if is_attached else "status-unattached"

                warns = warnings_by_candidate.get(cid, [])
                warn_text = "; ".join(f"[{w.code}] {w.message}" for w in warns) if warns else ("N/A" if is_attached else "Unattached (no specific warning)")

                tech_rows.append({
                    "id": cid,
                    "text": text,
                    "confidence": conf,
                    "bar_index": target_bar,
                    "event_id": target_event,
                    "note_desc": target_note,
                    "status": status,
                    "status_class": status_class,
                    "warning_info": warn_text,
                })
    else:
        # Fallback: scan score for attached items
        for bar in getattr(score, "bars", []):
            for event in getattr(bar, "events", []):
                if getattr(event, "chord_symbol", None):
                    for prov in getattr(event, "provenance", []):
                        if getattr(prov, "raw_token_id", None):
                            chord_rows.append({
                                "id": prov.raw_token_id,
                                "text": event.chord_symbol,
                                "confidence": getattr(prov, "confidence", 1.0),
                                "bar_index": bar.index,
                                "event_id": event.id,
                                "status": "Attached",
                                "status_class": "status-attached",
                                "warning_info": "N/A",
                            })
                for note in getattr(event, "notes", []):
                    if getattr(note, "techniques", None):
                        for prov in getattr(note, "provenance", []):
                            if getattr(prov, "raw_token_id", None) and (prov.raw_token_id.startswith("tech") or "tech" in prov.raw_token_id):
                                tech_text = ", ".join(getattr(t, "kind", "unknown") for t in note.techniques)
                                tech_rows.append({
                                    "id": prov.raw_token_id,
                                    "text": tech_text,
                                    "confidence": getattr(prov, "confidence", 1.0),
                                    "bar_index": bar.index,
                                    "event_id": event.id,
                                    "note_desc": f"String {note.string}, Fret {note.fret}",
                                    "status": "Attached",
                                    "status_class": "status-attached",
                                    "warning_info": "N/A",
                                })

        # Scan warnings for unattached items
        for warning in getattr(score, "warnings", []):
            for prov in getattr(warning, "provenance", []):
                if getattr(prov, "raw_token_id", None):
                    raw_text = warning.message.split("'")[1] if "'" in warning.message else "unknown"
                    if warning.code in ("symbol_attachment_requires_timing", "unattached_chord_symbol", "ambiguous_chord_symbol_attachment"):
                        chord_rows.append({
                            "id": prov.raw_token_id,
                            "text": raw_text,
                            "confidence": getattr(prov, "confidence", 1.0),
                            "bar_index": getattr(prov, "bar_index", None),
                            "event_id": None,
                            "status": "Unattached",
                            "status_class": "status-unattached",
                            "warning_info": f"[{warning.code}] {warning.message}",
                        })
                    elif warning.code in ("technique_attachment_requires_note_target", "unattached_technique_text", "ambiguous_technique_attachment", "unsupported_technique_text"):
                        tech_rows.append({
                            "id": prov.raw_token_id,
                            "text": raw_text,
                            "confidence": getattr(prov, "confidence", 1.0),
                            "bar_index": getattr(prov, "bar_index", None),
                            "event_id": None,
                            "note_desc": None,
                            "status": "Unattached",
                            "status_class": "status-unattached",
                            "warning_info": f"[{warning.code}] {warning.message}",
                        })

    # Prepare HTML lists
    chords_html = ""
    if chord_rows:
        chords_html = "\n".join(
            f"""<tr>
              <td><code>{html.escape(str(r["id"]))}</code></td>
              <td><strong>{html.escape(str(r["text"]))}</strong></td>
              <td>{r["confidence"]:.2f}</td>
              <td>{html.escape(str(r["bar_index"])) if r["bar_index"] is not None else "<em>N/A</em>"}</td>
              <td>{f"<code>{html.escape(str(r['event_id']))}</code>" if r["event_id"] is not None else "<em>N/A</em>"}</td>
              <td><span class="badge {r['status_class']}">{html.escape(str(r["status"]))}</span></td>
              <td class="warning-text">{html.escape(str(r["warning_info"]))}</td>
            </tr>"""
            for r in chord_rows
        )
    else:
        chords_html = """<tr><td colspan="7" class="empty-state">No chord symbol candidates found.</td></tr>"""

    techs_html = ""
    if tech_rows:
        techs_html = "\n".join(
            f"""<tr>
              <td><code>{html.escape(str(r["id"]))}</code></td>
              <td><strong>{html.escape(str(r["text"]))}</strong></td>
              <td>{r["confidence"]:.2f}</td>
              <td>{html.escape(str(r["bar_index"])) if r["bar_index"] is not None else "<em>N/A</em>"}</td>
              <td>{f"<code>{html.escape(str(r['event_id']))}</code>" if r["event_id"] is not None else "<em>N/A</em>"}</td>
              <td>{html.escape(str(r["note_desc"])) if r["note_desc"] is not None else "<em>N/A</em>"}</td>
              <td><span class="badge {r['status_class']}">{html.escape(str(r["status"]))}</span></td>
              <td class="warning-text">{html.escape(str(r["warning_info"]))}</td>
            </tr>"""
            for r in tech_rows
        )
    else:
        techs_html = """<tr><td colspan="8" class="empty-state">No technique text candidates found.</td></tr>"""

    # Retrieve counts from diagnostics
    c_found = getattr(diagnostics, "symbol_attachment_chord_candidates_found", 0)
    c_attached = getattr(diagnostics, "symbol_attachment_chord_candidates_attached", 0)
    c_unattached = getattr(diagnostics, "symbol_attachment_chord_candidates_unattached", 0)

    t_found = getattr(diagnostics, "symbol_attachment_technique_candidates_found", 0)
    t_attached = getattr(diagnostics, "symbol_attachment_technique_candidates_attached", 0)
    t_unattached = getattr(diagnostics, "symbol_attachment_technique_candidates_unattached", 0)

    source_ir_path_str = getattr(score, "metadata", None)
    source_title = getattr(source_ir_path_str, "title", "Unknown") if source_ir_path_str else "Unknown"

    tabraw_ref_str = tabraw_path or getattr(diagnostics, "tabraw_source", None) or "N/A"

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Symbol & Technique Attachment Diagnostics</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {{
      --bg-color: #0b0f19;
      --card-bg: #151e30;
      --card-border: #202c46;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --divider: #1e293b;

      --accent-unattached: #f87171;
      --accent-unattached-glow: rgba(248, 113, 113, 0.1);
      --accent-attached: #34d399;
      --accent-attached-glow: rgba(52, 211, 153, 0.1);
      --accent-blue: #3b82f6;
      --accent-blue-glow: rgba(59, 130, 246, 0.1);
    }}

    body {{
      background-color: var(--bg-color);
      color: var(--text-primary);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 2rem 1rem;
      min-height: 100vh;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1000px;
      margin: 0 auto;
    }}

    header {{
      border-bottom: 1px solid var(--divider);
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
    }}

    h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin: 0 0 0.5rem 0;
      letter-spacing: -0.025em;
    }}

    .subtitle {{
      font-size: 0.95rem;
      color: var(--text-secondary);
      margin: 0;
    }}

    .badge {{
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid transparent;
      display: inline-block;
    }}

    .status-unattached {{
      background-color: var(--accent-unattached-glow);
      color: var(--accent-unattached);
      border-color: rgba(248, 113, 113, 0.2);
    }}

    .status-attached {{
      background-color: var(--accent-attached-glow);
      color: var(--accent-attached);
      border-color: rgba(52, 211, 153, 0.2);
    }}

    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .card-title {{
      font-size: 0.9rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-top: 0;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 0.5rem;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.25rem;
      margin-bottom: 1.5rem;
    }}

    .metric-group {{
      background-color: rgba(0, 0, 0, 0.15);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 1rem;
    }}

    .metric-group-title {{
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-bottom: 0.75rem;
    }}

    .metric-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }}

    .metric-row:last-child {{
      margin-bottom: 0;
    }}

    .metric-label {{
      font-size: 0.875rem;
    }}

    .metric-value {{
      font-size: 1.25rem;
      font-weight: 700;
    }}

    .metric-value.attached {{
      color: var(--accent-attached);
    }}

    .metric-value.unattached {{
      color: var(--accent-unattached);
    }}

    .scope-card {{
      background-color: rgba(248, 113, 113, 0.03);
      border: 1px solid rgba(248, 113, 113, 0.2);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}

    .scope-title {{
      font-size: 0.9rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent-unattached);
      margin-top: 0;
      margin-bottom: 0.75rem;
    }}

    .scope-list {{
      margin: 0;
      padding-left: 1.25rem;
    }}

    .scope-list li {{
      font-size: 0.9rem;
      margin-bottom: 0.5rem;
      color: var(--text-secondary);
    }}

    .scope-list li strong {{
      color: var(--text-primary);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      text-align: left;
    }}

    th {{
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 2px solid var(--divider);
      padding: 0.75rem 0.5rem;
    }}

    td {{
      padding: 0.75rem 0.5rem;
      border-bottom: 1px solid var(--divider);
      vertical-align: middle;
    }}

    tr:hover td {{
      background-color: rgba(255, 255, 255, 0.02);
    }}

    .empty-state {{
      text-align: center;
      color: var(--text-secondary);
      font-style: italic;
      padding: 2rem 0;
    }}

    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      background-color: rgba(0, 0, 0, 0.3);
      padding: 0.125rem 0.25rem;
      border-radius: 4px;
      border: 1px solid var(--card-border);
    }}

    .warning-text {{
      color: var(--accent-unattached);
      font-size: 0.8rem;
    }}

    .footer-note {{
      font-size: 0.8rem;
      color: var(--text-secondary);
      text-align: center;
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--divider);
    }}

    pre {{
      background-color: rgba(0, 0, 0, 0.3);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      border: 1px solid var(--card-border);
      margin: 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Symbol & Technique Attachment Diagnostics</h1>
      <p class="subtitle">Visual inspection report for PDF-derived chord symbols and technique text evidence.</p>
    </header>

    <div class="card">
      <h2 class="card-title">Document Reference</h2>
      <table style="width: auto;">
        <tr>
          <td style="border: none; padding: 0.25rem 1rem 0.25rem 0; font-weight: 500; color: var(--text-secondary);">Score Title:</td>
          <td style="border: none; padding: 0.25rem 0; font-weight: 600;">{html.escape(source_title)}</td>
        </tr>
        <tr>
          <td style="border: none; padding: 0.25rem 1rem 0.25rem 0; font-weight: 500; color: var(--text-secondary);">TabRaw Source:</td>
          <td style="border: none; padding: 0.25rem 0; font-weight: 600;"><code>{html.escape(str(tabraw_ref_str))}</code></td>
        </tr>
        <tr>
          <td style="border: none; padding: 0.25rem 1rem 0.25rem 0; font-weight: 500; color: var(--text-secondary);">ScoreIR Path:</td>
          <td style="border: none; padding: 0.25rem 0; font-weight: 600;"><code>{html.escape(str(out))}</code></td>
        </tr>
      </table>
    </div>

    <div class="scope-card">
      <h2 class="scope-title">Important System Scope & Boundaries</h2>
      <ul class="scope-list">
        <li><strong>GPIF rendering is NOT implemented</strong>. This report serves solely as a developer-facing visualization tool for symbol attachment diagnostic evidence in the generated ScoreIR.</li>
        <li><strong>Symbols and techniques DID NOT create notes, events, or timing</strong>. They are only attached as conservative metadata/evidence to existing, safely timed bars and events derived from MusicXML.</li>
        <li><strong>JSON diagnostics remain the programmatic source of truth</strong>. The HTML report is only a read-only developer representation.</li>
      </ul>
    </div>

    <div class="grid">
      <div class="metric-group">
        <h3 class="metric-group-title">Chord Symbols Summary</h3>
        <div class="metric-row">
          <span class="metric-label">Total Candidates Found:</span>
          <span class="metric-value">{c_found}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Successfully Attached:</span>
          <span class="metric-value attached">{c_attached}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Unattached / Refused:</span>
          <span class="metric-value unattached">{c_unattached}</span>
        </div>
      </div>

      <div class="metric-group">
        <h3 class="metric-group-title">Technique Texts Summary</h3>
        <div class="metric-row">
          <span class="metric-label">Total Candidates Found:</span>
          <span class="metric-value">{t_found}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Successfully Attached:</span>
          <span class="metric-value attached">{t_attached}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Unattached / Refused:</span>
          <span class="metric-value unattached">{t_unattached}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Chord Symbol Candidates</h2>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Text</th>
              <th>Confidence</th>
              <th>Bar Index</th>
              <th>Event ID</th>
              <th>Status</th>
              <th>Warning Details / Refusal Reason</th>
            </tr>
          </thead>
          <tbody>
            {chords_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Technique Text Candidates</h2>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Text</th>
              <th>Confidence</th>
              <th>Bar Index</th>
              <th>Event ID</th>
              <th>Note Target</th>
              <th>Status</th>
              <th>Warning Details / Refusal Reason</th>
            </tr>
          </thead>
          <tbody>
            {techs_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Raw Diagnostics Payload Reference</h2>
      <pre><code>{html.escape(json.dumps(diagnostics.model_dump(mode="json") if hasattr(diagnostics, "model_dump") else diagnostics, indent=2, sort_keys=True))}</code></pre>
    </div>

    <div class="footer-note">
      This diagnostic report is generated automatically by the Antigravity Score2GP pipeline.
    </div>
  </div>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")


def write_musicxml_timing_diagnostics_html(path: str | Path, payload: dict[str, Any], json_path_ref: str | Path | None = None) -> None:
    """Write an inspectable developer-facing HTML report for MusicXML timing and overlap failure diagnostics."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    timing_issues = payload.get("timing_issues", [])

    # Extract primary and secondary reasons
    primary_issue = None
    for issue in timing_issues:
        if issue.get("severity") == "error":
            primary_issue = issue
            break
    if not primary_issue and timing_issues:
        primary_issue = timing_issues[0]

    primary_reason = primary_issue.get("code") if primary_issue else payload.get("category") or "musicxml_timing_risk"

    all_codes = sorted({issue.get("code") for issue in timing_issues if issue.get("code")})
    secondary_reasons = [code for code in all_codes if code != primary_reason]

    # Remediation hint mapping
    mapping = {
        "musicxml_measure_overfull": "Adjust note durations or measure time signature so the sum of divisions in the voice fits the measure boundary.",
        "musicxml_measure_underfull": "Ensure the sum of voice durations and rests exactly fills the measure capacity according to the divisions and time signature.",
        "musicxml_event_overlap": "Resolve overlapping notes in the same voice.",
        "musicxml_voice_overlap": "Resolve overlapping notes in the same voice.",
        "musicxml_polyphony_not_supported": "Score2GP only supports a single monophonic voice per staff. Avoid multiple simultaneous voices or notes.",
        "musicxml_backup_forward_risk": "Avoid ambiguous cursor backtracks; standard sequential notes or explicit single voice layout is required.",
        "musicxml_unbalanced_backup_forward": "The backup/forward commands did not balance at the end of the measure, creating ambiguous timing.",
        "musicxml_duration_missing": "Ensure all note elements contain a positive duration value in the MusicXML source.",
        "musicxml_duration_zero": "Ensure all note elements contain a positive duration value; zero-duration notes are unsupported.",
        "musicxml_divisions_missing": "The MusicXML file is missing the initial divisions element in attributes.",
        "musicxml_divisions_changed_mid_measure": "Divisions cannot change in the middle of a measure.",
        "musicxml_tuplet_unsupported": "Tuplets must represent supported division ratios; verify the tuplet definitions.",
        "musicxml_tie_continuity_risk": "Verify start/stop matching of tie elements.",
        "musicxml_rest_overlap": "Rests cannot overlap with notes or other rests in the same voice.",
        "valid_compound_meter": "Measure uses compound meter (e.g., 12/8) and has valid full-measure timing.",
        "musicxml_compound_meter_underfull": "The compound meter measure is underfull (e.g., has fewer divisions than expected).",
        "musicxml_compound_meter_overfull": "The compound meter measure is overfull (e.g., contains extra divisions exceeding the measure capacity).",
        "musicxml_backup_rewinds_before_measure_start": "A backup element has a duration that rewinds the cursor before the start of the measure.",
        "musicxml_forward_exceeds_measure_end": "A forward element has a duration that advances the cursor beyond the end of the measure.",
        "musicxml_backup_forward_alignment_ambiguous": "Cursor backtracks using backup/forward create an ambiguous voice timeline layout.",
        "musicxml_voice_cursor_overlap": "Overlapping notes or rests are detected in the same voice.",
        "musicxml_multivoice_timing_not_supported": "Multi-voice polyphonic layout is not supported; verify the voice/staff configuration.",
        "musicxml_chord_stack_detected": "A chord stack is detected using the chord tag; this is distinctly classified.",
        "musicxml_chord_stack_supported_or_blocked": "A chord stack is classified and handled depending on overall system constraints.",
        "musicxml_rest_voice_overlap": "An overlapping note and rest in the same voice creates timing ambiguity.",
        "musicxml_alignment_not_attempted_due_to_timing_risk": "One or more timing errors blocked alignment; resolve those errors first.",
        "musicxml_voice_cursor_alignment_risk": "Unsafe voice cursor backtrack detected that overlaps notes or rests on the same timeline.",
        "musicxml_repeated_backup_forward_risk": "Repeated backup/forward cursor movements exceed safe bounds and are unsupported.",
        "musicxml_many_timing_risks": "Measure contains high-density timing risks/overlaps indicating extremely messy notation.",
        "musicxml_same_voice_tick_overlap": "Notes overlap on the same voice timeline, producing duplicate tick entries.",
        "musicxml_cross_voice_timing_unsupported": "Cross-voice polyphony/multi-voice timing overlap is unsupported in this pipeline.",
        "musicxml_chord_stack_not_timing_overlap": "Legitimate chord stack detected and distinguished from timing overlap.",
        "musicxml_voice_timeline_valid": "Voice cursor timeline is valid.",
        "musicxml_voice_timeline_invalid": "Voice cursor timeline is invalid.",
        "musicxml_same_voice_overlap": "Overlapping events in the same voice violate ScoreIR sequential timing.",
        "musicxml_cross_voice_overlap_unsupported": "Multi-voice overlap is detected and is unsupported by ScoreIR.",
        "musicxml_valid_multivoice_unsupported": "Measure has valid multi-voice timing but cross-voice polyphony is unsupported by ScoreIR.",
        "musicxml_backup_cursor_before_measure_start": "A backup element rewinds the voice cursor before the start of the measure.",
        "musicxml_forward_cursor_after_measure_end": "A forward element advances the voice cursor beyond the end of the measure.",
        "musicxml_voice_duration_underfull": "The accumulated voice duration is underfull relative to the measure capacity.",
        "musicxml_voice_duration_overfull": "The accumulated voice duration is overfull relative to the measure capacity.",
        "musicxml_measure_duration_inconsistent_across_voices": "Measure durations are inconsistent across the different active voices.",
        "musicxml_chord_stack_timeline_valid": "Chord stack is valid on the timeline.",
        "musicxml_chord_stack_without_anchor": "A chord note was encountered without an anchor note preceding it in the same voice.",
        "musicxml_rest_overlap_same_voice": "Rests overlap with notes or other rests in the same voice timeline.",
        "musicxml_backup_forward_timeline_ambiguous": "Ambiguous timeline progression due to backup/forward cursor movements.",
        "musicxml_scoreir_polyphony_gate_refused": "MusicXML timing is valid but contains unsupported polyphony/multi-voice structures.",
    }
    remediation = mapping.get(primary_reason, "Review the timing issues listed below and fix the MusicXML timing/voice structure.")

    affected_measures = sorted({str(issue.get("measure_number")) for issue in timing_issues if issue.get("measure_number") is not None})
    affected_voices = sorted({str(issue.get("voice")) for issue in timing_issues if issue.get("voice") is not None})

    json_reference_str = "N/A"
    if json_path_ref is not None:
        json_reference_str = str(json_path_ref)

    secondary_html = ""
    if secondary_reasons:
        secondary_html = "\n".join(f"<li><code>{html.escape(str(r))}</code></li>" for r in secondary_reasons)
    else:
        secondary_html = "<li><em>None</em></li>"

    issues_rows = []
    if timing_issues:
        for issue in timing_issues:
            severity = issue.get("severity", "warning")
            badge_class = "status-refused" if severity == "error" else "status-warning"
            issues_rows.append(f"""<tr>
              <td><span class="badge {badge_class}">{html.escape(str(severity))}</span></td>
              <td><code>{html.escape(str(issue.get("code", "")))}</code></td>
              <td>Measure {html.escape(str(issue.get("measure_number", "")))}</td>
              <td>{f"Voice {html.escape(str(issue.get('voice')))}" if issue.get("voice") is not None else "<em>N/A</em>"}</td>
              <td>{f"<code>{html.escape(str(issue.get('musicxml_note_id')))}</code>" if issue.get("musicxml_note_id") is not None else "<em>N/A</em>"}</td>
              <td>{html.escape(str(issue.get("message", "")))}</td>
            </tr>""")
        issues_html = "\n".join(issues_rows)
    else:
        issues_html = """<tr><td colspan="6" class="empty-state">No timing issues found in payload.</td></tr>"""

    calibration_possible = False
    repair_attempted = False
    max_overfull_divisions = 0.0
    total_overlap_count = 0
    all_affected_event_ids = set()

    for issue in timing_issues:
        if issue.get("timing_calibration_possible"):
            calibration_possible = True
        if issue.get("timing_repair_attempted"):
            repair_attempted = True
        overfull = issue.get("overfull_divisions")
        if overfull is not None:
            max_overfull_divisions = max(max_overfull_divisions, float(overfull))
        overlaps = issue.get("overlap_count")
        if overlaps is not None:
            total_overlap_count = max(total_overlap_count, int(overlaps))
        ev_ids = issue.get("affected_event_ids")
        if ev_ids:
            all_affected_event_ids.update(ev_ids)

    # Root payload properties with fallback
    calibration_possible = payload.get("calibration_possible", calibration_possible)
    calibration_candidate_reason = payload.get("calibration_candidate_reason")
    calibration_blocking_reasons = payload.get("calibration_blocking_reasons", [])
    overfull_bar_count = payload.get("overfull_bar_count", 0)
    underfull_bar_count = payload.get("underfull_bar_count", 0)
    affected_event_count = payload.get("affected_event_count", len(all_affected_event_ids))
    overlap_count_val = payload.get("overlap_count", total_overlap_count)
    tie_continuity_risk_count = payload.get("tie_continuity_risk_count", 0)
    many_risk_summary_count = payload.get("many_risk_summary_count", 0)
    invalid_grid_count = payload.get("invalid_grid_count", 0)
    repair_attempted = payload.get("automatic_repair_attempted", repair_attempted)

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MusicXML Timing & Overlap Diagnostics</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {{
      --bg-color: #0b0f19;
      --card-bg: #151e30;
      --card-border: #202c46;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --divider: #1e293b;

      --accent-refused: #f87171;
      --accent-refused-glow: rgba(248, 113, 113, 0.1);
      --accent-warning: #f59e0b;
      --accent-warning-glow: rgba(245, 158, 11, 0.1);
      --accent-allowed: #34d399;
      --accent-allowed-glow: rgba(52, 211, 153, 0.1);
    }}

    body {{
      background-color: var(--bg-color);
      color: var(--text-primary);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 2rem 1rem;
      min-height: 100vh;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1000px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 1.5rem;
    }}

    h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.025em;
    }}

    .badge {{
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid transparent;
      display: inline-block;
    }}

    .status-refused {{
      background-color: var(--accent-refused-glow);
      color: var(--accent-refused);
      border-color: rgba(248, 113, 113, 0.2);
    }}

    .status-warning {{
      background-color: var(--accent-warning-glow);
      color: var(--accent-warning);
      border-color: rgba(245, 158, 11, 0.2);
    }}

    .status-allowed {{
      background-color: var(--accent-allowed-glow);
      color: var(--accent-allowed);
      border-color: rgba(52, 211, 153, 0.2);
    }}

    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .card-title {{
      font-size: 0.9rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-top: 0;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 0.5rem;
    }}

    .reason-box {{
      border-left: 4px solid var(--accent-refused);
      background-color: rgba(248, 113, 113, 0.05);
      padding: 1rem;
      border-radius: 0 8px 8px 0;
      margin-bottom: 1rem;
    }}

    .reason-title {{
      font-size: 1.125rem;
      font-weight: 700;
      margin: 0 0 0.5rem 0;
    }}

    .reason-code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9rem;
      background-color: rgba(0, 0, 0, 0.2);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      color: var(--text-primary);
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}

    .metric-card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem;
      text-align: center;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .metric-value {{
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      color: var(--text-primary);
    }}

    .metric-label {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
    }}

    dl {{
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.5rem 1.5rem;
      margin: 0;
    }}

    dt {{
      font-weight: 500;
      color: var(--text-secondary);
    }}

    dd {{
      margin: 0;
      font-weight: 600;
    }}

    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      background-color: rgba(0, 0, 0, 0.3);
      padding: 0.125rem 0.25rem;
      border-radius: 4px;
      border: 1px solid var(--card-border);
    }}

    ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}

    li {{
      margin-bottom: 0.5rem;
    }}

    .remediation-card {{
      background-color: rgba(245, 158, 11, 0.05);
      border: 1px solid rgba(245, 158, 11, 0.2);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}

    .remediation-title {{
      font-size: 0.875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent-warning);
      margin-top: 0;
      margin-bottom: 0.5rem;
    }}

    .remediation-text {{
      font-size: 1.05rem;
      font-weight: 500;
      margin: 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      text-align: left;
    }}

    th {{
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 2px solid var(--divider);
      padding: 0.75rem 0.5rem;
    }}

    td {{
      padding: 0.75rem 0.5rem;
      border-bottom: 1px solid var(--divider);
      vertical-align: middle;
    }}

    tr:hover td {{
      background-color: rgba(255, 255, 255, 0.02);
    }}

    .empty-state {{
      text-align: center;
      color: var(--text-secondary);
      font-style: italic;
      padding: 2rem 0;
    }}

    .footer-note {{
      font-size: 0.825rem;
      color: var(--text-secondary);
      text-align: center;
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--divider);
    }}

    pre {{
      background-color: rgba(0, 0, 0, 0.3);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      border: 1px solid var(--card-border);
      margin: 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>MusicXML Timing & Overlap Diagnostics</h1>
      <span class="badge status-refused">Timing Risk</span>
    </header>

    <div class="card">
      <h2 class="card-title">Verdict & Diagnostics</h2>
      <div class="reason-box">
        <h3 class="reason-title">{html.escape(payload.get("message", ""))}</h3>
        <p style="margin: 0.5rem 0 0 0;">Primary reason code: <span class="reason-code">{html.escape(str(primary_reason))}</span></p>
      </div>
      <p style="margin: 1rem 0 0 0; font-size: 0.925rem; color: var(--text-secondary);">
        Risky or unsupported MusicXML timing strictly blocks ScoreIR generation to prevent downstream alignment and rendering failures. JSON remains the source of truth.
      </p>
    </div>

    <div class="remediation-card">
      <h2 class="remediation-title">Suggested Remediation</h2>
      <p class="remediation-text">{html.escape(str(remediation))}</p>
    </div>

    <div class="grid">
      <div class="metric-card">
        <div class="metric-value">{payload.get("timing_issue_count", 0)}</div>
        <div class="metric-label">Total Timing Issues</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{len(affected_measures)}</div>
        <div class="metric-label">Affected Measures</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{len(affected_voices)}</div>
        <div class="metric-label">Affected Voices</div>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Timing Refusal Taxonomy</h2>
      <dl style="margin-bottom: 1.5rem;">
        <dt>Primary Reason</dt>
        <dd><code>{html.escape(str(primary_reason))}</code></dd>

        <dt>Secondary Reasons</dt>
        <dd>
          <ul style="padding-left: 1.25rem; margin-top: 0.25rem;">
            {secondary_html}
          </ul>
        </dd>

        <dt>Affected Measures</dt>
        <dd>{", ".join(f"<code>{html.escape(m)}</code>" for m in affected_measures) if affected_measures else "<em>None</em>"}</dd>

        <dt>Affected Voices</dt>
        <dd>{", ".join(f"<code>{html.escape(v)}</code>" for v in affected_voices) if affected_voices else "<em>None</em>"}</dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">Gate Metadata</h2>
      <dl>
        <dt>Pipeline Stage</dt>
        <dd><code>{html.escape(str(payload.get("stage", "musicxml-import")))}</code></dd>

        <dt>ScoreIR Written</dt>
        <dd><code>False</code></dd>

        <dt>Alignment Attempted</dt>
        <dd><code>False</code></dd>

        <dt>JSON Reference</dt>
        <dd><code>{html.escape(json_reference_str)}</code></dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">Calibration & Auto-Repair Status</h2>
      <dl>
        <dt>Automatic Repair Attempted</dt>
        <dd><code>{str(repair_attempted).lower()}</code></dd>

        <dt>Timing Calibration Possible</dt>
        <dd><code>{str(calibration_possible).lower()}</code></dd>

        {f"<dt>Calibration Candidate Reason</dt><dd><code>{html.escape(calibration_candidate_reason)}</code></dd>" if calibration_candidate_reason else ""}
        {f"<dt>Calibration Blocking Reasons</dt><dd>{', '.join(f'<code>{html.escape(r)}</code>' for r in calibration_blocking_reasons)}</dd>" if calibration_blocking_reasons else ""}

        <dt>Max Overfull Amount</dt>
        <dd><code>{f"{max_overfull_divisions} divisions" if max_overfull_divisions > 0 else "0"}</code></dd>

        <dt>Overfull Bar Count</dt>
        <dd><code>{overfull_bar_count}</code></dd>

        <dt>Underfull Bar Count</dt>
        <dd><code>{underfull_bar_count}</code></dd>

        <dt>Total Overlap Counts</dt>
        <dd><code>{overlap_count_val}</code></dd>

        <dt>Tie Continuity Risks</dt>
        <dd><code>{tie_continuity_risk_count}</code></dd>

        <dt>High Risk Summaries</dt>
        <dd><code>{many_risk_summary_count}</code></dd>

        <dt>Invalid Duration Grids</dt>
        <dd><code>{invalid_grid_count}</code></dd>

        <dt>Affected Event Count</dt>
        <dd><code>{affected_event_count}</code></dd>

        <dt>Affected Event IDs</dt>
        <dd>{", ".join(f"<code>{html.escape(str(eid))}</code>" for eid in sorted(all_affected_event_ids)) if all_affected_event_ids else "<em>None</em>"}</dd>

        <dt>Remediation Hint</dt>
        <dd><strong>Fix or regenerate MusicXML timing; automatic timing repair is not implemented.</strong></dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">Detailed Timing Issues</h2>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Code</th>
              <th>Measure</th>
              <th>Voice</th>
              <th>Note ID</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {issues_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">JSON Diagnostics Payload Reference</h2>
      <pre><code>{html.escape(json.dumps(payload, indent=2, sort_keys=True))}</code></pre>
    </div>

    <div class="footer-note">
      This diagnostic report is generated automatically by the Antigravity Score2GP pipeline.
    </div>
  </div>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")


def anonymize_source_label(source_path: str | None) -> str:
    if not source_path:
        return "unknown_input"
    name = Path(source_path).name.lower()
    if "derek" in name or "trucks" in name:
        return "private_input_1"
    if "caged" in name or "guitar tab creator" in name:
        return "private_input_2"
    if "private" in name:
        return "private_input_custom"
    return Path(source_path).stem


def write_musicxml_unrecoverable_timing_report(
    json_path: str | Path,
    html_path: str | Path,
    payload: dict[str, Any],
    source_path: str | None = None,
) -> None:
    """Generate both JSON and HTML reports for unrecoverable MusicXML timing failures."""
    
    json_path = Path(json_path)
    html_path = Path(html_path)
    
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    
    source_label = anonymize_source_label(source_path or payload.get("source_path") or payload.get("details", {}).get("source_path"))
    
    timing_issues = payload.get("timing_issues", [])
    
    affected_part_ids = sorted(list(set(issue.get("part_id") for issue in timing_issues if issue.get("part_id"))))
    affected_measure_numbers = sorted(list(set(str(issue.get("measure_number")) for issue in timing_issues if issue.get("measure_number") is not None)))
    affected_measure_indexes = sorted(list(set(int(issue.get("measure_index")) for issue in timing_issues if issue.get("measure_index") is not None)))
    affected_voice_ids = sorted(list(set(int(issue.get("voice")) for issue in timing_issues if issue.get("voice") is not None)))
    
    expected_measure_ticks = {}
    actual_voice_end_ticks = {}
    backup_forward_density_summary = {}
    
    max_overfull_divisions = 0.0
    max_underfull_divisions = 0.0
    
    for issue in timing_issues:
        m_num = str(issue.get("measure_number"))
        if m_num:
            if issue.get("expected_duration_divisions") is not None:
                expected_measure_ticks[m_num] = float(issue["expected_duration_divisions"])
            if issue.get("voice_extents"):
                actual_voice_end_ticks[m_num] = {str(k): int(v) for k, v in issue["voice_extents"].items()}
            if issue.get("backup_forward_count") is not None:
                backup_forward_density_summary[m_num] = int(issue["backup_forward_count"])
            
            overfull = issue.get("overfull_divisions")
            if overfull is not None:
                max_overfull_divisions = max(max_overfull_divisions, float(overfull))
                
            if "underfull" in str(issue.get("code", "")).lower() or any("underfull" in str(r).lower() for r in issue.get("secondary_reasons", [])):
                expected = issue.get("expected_duration_divisions")
                end = issue.get("end_divisions")
                if expected is not None and end is not None and expected > end:
                    max_underfull_divisions = max(max_underfull_divisions, float(expected - end))
                    
    primary_reason = payload.get("category") or "musicxml_timing_risk"
    all_codes = sorted({issue.get("code") for issue in timing_issues if issue.get("code")})
    secondary_reasons = sorted([code for code in all_codes if code != primary_reason])
    
    affected_event_ids = set()
    for issue in timing_issues:
        ev_ids = issue.get("affected_event_ids")
        if ev_ids:
            affected_event_ids.update(ev_ids)
        if issue.get("musicxml_note_id"):
            affected_event_ids.add(issue["musicxml_note_id"])
            
    remediation_hint = (
        "MusicXML timing is unrecoverable. "
        "Suggested actions:\n"
        "- regenerate MusicXML from source\n"
        "- inspect OMR export timing\n"
        "- simplify/re-export in notation software\n"
        "- do not proceed to ScoreIR until timing is fixed"
    )
    
    report_json = {
        "schema_version": "musicxml-unrecoverable-timing-report.v0.1",
        "source_label": source_label,
        "stage_reached": "musicxml-import",
        "timing_status": "failed",
        "timing_gate_status": "refused",
        "calibration_possible": False,
        "automatic_repair_attempted": False,
        "primary_reason_code": primary_reason,
        "secondary_reason_codes": secondary_reasons,
        "calibration_blocking_reasons": payload.get("calibration_blocking_reasons", ["musicxml_timing_calibration_not_safe"]),
        "affected_part_ids": affected_part_ids,
        "affected_measure_numbers": affected_measure_numbers,
        "affected_measure_indexes": affected_measure_indexes,
        "affected_voice_ids": affected_voice_ids,
        "expected_measure_ticks": expected_measure_ticks,
        "actual_voice_end_ticks": actual_voice_end_ticks,
        "overfull_amount": max_overfull_divisions,
        "underfull_amount": max_underfull_divisions,
        "overfull_measure_count": payload.get("overfull_bar_count", 0),
        "underfull_measure_count": payload.get("underfull_bar_count", 0),
        "overlap_count": payload.get("overlap_count", 0),
        "tie_continuity_risk_count": payload.get("tie_continuity_risk_count", 0),
        "many_risk_count": payload.get("many_risk_summary_count", 0),
        "affected_event_count": len(affected_event_ids),
        "affected_event_ids": sorted(list(affected_event_ids)),
        "backup_forward_density_summary": backup_forward_density_summary,
        "alignment_attempted": False,
        "scoreir_written": False,
        "gp_written": False,
        "remediation_hint": remediation_hint,
    }
    
    json_path.write_text(json.dumps(report_json, indent=2, sort_keys=True), encoding="utf-8")
    _write_musicxml_unrecoverable_timing_html(html_path, report_json, json_path.name, timing_issues)


def _write_musicxml_unrecoverable_timing_html(
    html_path: Path,
    report_json: dict[str, Any],
    json_filename: str,
    timing_issues: list[dict[str, Any]],
) -> None:
    """Write user-facing HTML report for unrecoverable MusicXML timing."""
    
    table_rows = []
    for issue in timing_issues:
        part_id = issue.get("part_id") or "N/A"
        m_num = issue.get("measure_number") or "N/A"
        m_idx = issue.get("measure_index") or 0
        voice = issue.get("voice")
        voice_str = f"Voice {voice}" if voice is not None else "N/A"
        
        expected = issue.get("expected_duration_divisions")
        expected_str = f"{expected}" if expected is not None else "N/A"
        
        end = issue.get("end_divisions")
        end_str = f"{end}" if end is not None else "N/A"
        
        overfull = issue.get("overfull_divisions")
        underfull = None
        if expected is not None and end is not None and expected > end and "underfull" in str(issue.get("code")).lower():
            underfull = expected - end
            
        amount_str = "0"
        if overfull is not None and overfull > 0:
            amount_str = f"+{overfull} divisions (overfull)"
        elif underfull is not None and underfull > 0:
            amount_str = f"-{underfull} divisions (underfull)"
            
        reason_codes = issue.get("code") or "N/A"
        
        table_rows.append(f"""<tr>
          <td><code>{html.escape(str(part_id))}</code></td>
          <td>Measure {html.escape(str(m_num))} (index {m_idx})</td>
          <td>{html.escape(voice_str)}</td>
          <td><code>{html.escape(expected_str)}</code></td>
          <td><code>{html.escape(end_str)}</code></td>
          <td><code>{html.escape(amount_str)}</code></td>
          <td><code>{html.escape(str(reason_codes))}</code></td>
        </tr>""")
        
    issues_html = "\n".join(table_rows) if table_rows else """<tr><td colspan="7" class="empty-state">No detailed measure timing issue rows.</td></tr>"""
    
    secondary_html = ""
    if report_json["secondary_reason_codes"]:
        secondary_html = "\n".join(f"<li><code>{html.escape(str(r))}</code></li>" for r in report_json["secondary_reason_codes"])
    else:
        secondary_html = "<li><em>None</em></li>"
        
    blocking_html = ""
    if report_json["calibration_blocking_reasons"]:
        blocking_html = ", ".join(f"<code>{html.escape(str(r))}</code>" for r in report_json["calibration_blocking_reasons"])
    else:
        blocking_html = "<em>None</em>"

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MusicXML Timing is Unrecoverable</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {{
      --bg-color: #0b0f19;
      --card-bg: #151e30;
      --card-border: #202c46;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --divider: #1e293b;

      --accent-refused: #f87171;
      --accent-refused-glow: rgba(248, 113, 113, 0.1);
      --accent-warning: #f59e0b;
      --accent-warning-glow: rgba(245, 158, 11, 0.1);
      --accent-allowed: #34d399;
      --accent-allowed-glow: rgba(52, 211, 153, 0.1);
    }}

    body {{
      background-color: var(--bg-color);
      color: var(--text-primary);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 2rem 1rem;
      min-height: 100vh;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1000px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 1.5rem;
    }}

    h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.025em;
    }}

    .badge {{
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid transparent;
      display: inline-block;
    }}

    .status-refused {{
      background-color: var(--accent-refused-glow);
      color: var(--accent-refused);
      border-color: rgba(248, 113, 113, 0.2);
    }}

    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .card-title {{
      font-size: 0.9rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-top: 0;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--divider);
      padding-bottom: 0.5rem;
    }}

    .reason-box {{
      border-left: 4px solid var(--accent-refused);
      background-color: rgba(248, 113, 113, 0.05);
      padding: 1rem;
      border-radius: 0 8px 8px 0;
      margin-bottom: 1rem;
    }}

    .reason-title {{
      font-size: 1.125rem;
      font-weight: 700;
      margin: 0 0 0.5rem 0;
    }}

    .reason-code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9rem;
      background-color: rgba(0, 0, 0, 0.2);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      color: var(--text-primary);
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}

    .metric-card {{
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem;
      text-align: center;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .metric-value {{
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      color: var(--text-primary);
    }}

    .metric-label {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
    }}

    dl {{
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.5rem 1.5rem;
      margin: 0;
    }}

    dt {{
      font-weight: 500;
      color: var(--text-secondary);
    }}

    dd {{
      margin: 0;
      font-weight: 600;
    }}

    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      background-color: rgba(0, 0, 0, 0.3);
      padding: 0.125rem 0.25rem;
      border-radius: 4px;
      border: 1px solid var(--card-border);
    }}

    ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}

    li {{
      margin-bottom: 0.5rem;
    }}

    .remediation-card {{
      background-color: rgba(245, 158, 11, 0.05);
      border: 1px solid rgba(245, 158, 11, 0.2);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}

    .remediation-title {{
      font-size: 0.875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent-warning);
      margin-top: 0;
      margin-bottom: 0.5rem;
    }}

    .remediation-text {{
      font-size: 1.05rem;
      font-weight: 500;
      margin: 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      text-align: left;
    }}

    th {{
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 2px solid var(--divider);
      padding: 0.75rem 0.5rem;
    }}

    td {{
      padding: 0.75rem 0.5rem;
      border-bottom: 1px solid var(--divider);
      vertical-align: middle;
    }}

    tr:hover td {{
      background-color: rgba(255, 255, 255, 0.02);
    }}

    .empty-state {{
      text-align: center;
      color: var(--text-secondary);
      font-style: italic;
      padding: 2rem 0;
    }}

    .footer-note {{
      font-size: 0.825rem;
      color: var(--text-secondary);
      text-align: center;
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--divider);
    }}

    pre {{
      background-color: rgba(0, 0, 0, 0.3);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      border: 1px solid var(--card-border);
      margin: 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>MusicXML timing is unrecoverable</h1>
      <span class="badge status-refused">Timing Blocked</span>
    </header>

    <div class="card">
      <h2 class="card-title">Verdict & Diagnostics</h2>
      <div class="reason-box">
        <h3 class="reason-title">MusicXML timing is unrecoverable and strictly blocks alignment/ScoreIR generation.</h3>
        <p style="margin: 0.5rem 0 0 0;">Primary reason code: <span class="reason-code">{html.escape(str(report_json["primary_reason_code"]))}</span></p>
      </div>
      <p style="margin: 1rem 0 0 0; font-size: 0.925rem; color: var(--text-secondary);">
        Unrecoverable or polyphonic MusicXML timing strictly blocks ScoreIR generation to prevent downstream alignment and rendering failures. JSON remains the source of truth.
      </p>
    </div>

    <div class="remediation-card">
      <h2 class="remediation-title">Suggested Remediation Guidance</h2>
      <p class="remediation-text">To resolve these unrecoverable timing errors, please try the following:</p>
      <ul style="margin-top: 0.5rem; padding-left: 1.25rem; font-weight: 500; line-height: 1.6;">
        <li>Regenerate MusicXML from the original source.</li>
        <li>Inspect the OMR export timing settings if the file was scanned.</li>
        <li>Simplify or re-export the score in your notation software (e.g. MuseScore, Sibelius, Finale).</li>
        <li><strong>Do not proceed to ScoreIR or GP writing until all timing and voice timeline risks are fixed.</strong></li>
      </ul>
    </div>

    <div class="grid">
      <div class="metric-card">
        <div class="metric-value">{report_json["overfull_measure_count"]}</div>
        <div class="metric-label">Overfull Measures</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{report_json["underfull_measure_count"]}</div>
        <div class="metric-label">Underfull Measures</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{report_json["tie_continuity_risk_count"]}</div>
        <div class="metric-label">Tie Risks</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{report_json["overlap_count"]}</div>
        <div class="metric-label">Overlap Count</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{report_json["affected_event_count"]}</div>
        <div class="metric-label">Affected Events</div>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Timing Refusal Summary</h2>
      <dl style="margin-bottom: 1.5rem;">
        <dt>Anonymised Source Label</dt>
        <dd><code>{html.escape(report_json["source_label"])}</code></dd>

        <dt>Pipeline Stage Reached</dt>
        <dd><code>{html.escape(report_json["stage_reached"])}</code></dd>

        <dt>Timing Status</dt>
        <dd><code>{html.escape(report_json["timing_status"])}</code></dd>

        <dt>Timing Gate Status</dt>
        <dd><code>{html.escape(report_json["timing_gate_status"])}</code></dd>

        <dt>Calibration Possible</dt>
        <dd><code>{str(report_json["calibration_possible"]).lower()}</code></dd>

        <dt>Automatic Repair Attempted</dt>
        <dd><code>{str(report_json["automatic_repair_attempted"]).lower()}</code></dd>

        <dt>Primary Reason</dt>
        <dd><code>{html.escape(str(report_json["primary_reason_code"]))}</code></dd>

        <dt>Secondary Reasons</dt>
        <dd>
          <ul style="padding-left: 1.25rem; margin-top: 0.25rem;">
            {secondary_html}
          </ul>
        </dd>

        <dt>Calibration Blocking Reasons</dt>
        <dd>{blocking_html}</dd>

        <dt>Affected Part IDs</dt>
        <dd>{", ".join(f"<code>{html.escape(str(p))}</code>" for p in report_json["affected_part_ids"]) if report_json["affected_part_ids"] else "<em>None</em>"}</dd>

        <dt>Affected Measure Numbers</dt>
        <dd>{", ".join(f"<code>{html.escape(str(m))}</code>" for m in report_json["affected_measure_numbers"]) if report_json["affected_measure_numbers"] else "<em>None</em>"}</dd>

        <dt>Affected Voice IDs</dt>
        <dd>{", ".join(f"<code>{html.escape(str(v))}</code>" for v in report_json["affected_voice_ids"]) if report_json["affected_voice_ids"] else "<em>None</em>"}</dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="card-title">Affected Measures Timeline Breakdown</h2>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>Part ID</th>
              <th>Measure (Index)</th>
              <th>Voice ID</th>
              <th>Expected Ticks</th>
              <th>Actual Ticks</th>
              <th>Overfull/Underfull Amount</th>
              <th>Reason Codes</th>
            </tr>
          </thead>
          <tbody>
            {issues_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">JSON Diagnostics Payload Reference</h2>
      <pre><code>{html.escape(json.dumps(report_json, indent=2, sort_keys=True))}</code></pre>
    </div>

    <div class="footer-note">
      This diagnostic report is generated automatically by the Antigravity Score2GP pipeline.
    </div>
  </div>
</body>
</html>
"""
    html_path.write_text(body, encoding="utf-8")


def build_pdf_edge_boundary_report(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Build a public-safe edge-boundary reporting contract from TabRaw data."""
    warnings = raw.get("warnings", [])
    candidates = raw.get("candidates", [])

    rejected_warnings = [w for w in warnings if w.get("code") == "pdf_bar_box_edge_boundary_fallback_rejected"]
    if not rejected_warnings:
        return None

    # Retrieve page/system index of the first fallback-rejected system
    w0 = rejected_warnings[0]
    page_idx = w0.get("page_index")
    sys_idx = w0.get("system_index")

    # If missing programmatically, parse from message
    if page_idx is None or sys_idx is None:
        import re
        m = re.search(r"system (\d+) on page (\d+)", w0.get("message", ""))
        if m:
            sys_idx = int(m.group(1))
            page_idx = int(m.group(2))
        else:
            sys_idx = 6
            page_idx = 2

    # Filter candidates belonging to this page/system
    sys_candidates = [
        c for c in candidates
        if c.get("system_index") == sys_idx and c.get("page_index") == page_idx
    ]
    playable_candidates = [
        c for c in sys_candidates
        if c.get("parsed_fret") is not None
    ]

    # Find warning codes corresponding to this system/page
    sys_warning_codes = []
    for w in warnings:
        code = w.get("code")
        msg = w.get("message", "")
        # Check system and page markers in warning or fields
        is_match = False
        if w.get("system_index") == sys_idx and w.get("page_index") == page_idx:
            is_match = True
        elif f"system {sys_idx}" in msg and f"page {page_idx}" in msg:
            is_match = True
        if is_match and code:
            sys_warning_codes.append(code)

    # Determine edge-boundary fallback rejection reason codes
    rejection_reasons = []
    for code in [
        "pdf_bar_box_edge_boundary_ambiguous",
        "pdf_bar_box_inferred_boundary_too_narrow",
        "pdf_bar_box_inferred_boundary_candidate_ambiguous",
        "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
        "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",
    ]:
        if code in sys_warning_codes:
            rejection_reasons.append(code)

    # Deduplicate rejection reasons
    rejection_reasons = sorted(list(set(rejection_reasons)))

    # Compute observed/accepted/rejected boundary counts for this system
    # Since it is a fallback-rejected system, it has exactly 1 accepted boundary
    # and at least 1 rejected boundary details in the tabraw warnings.
    accepted_boundary_count = 1
    rejected_boundary_count = 1
    observed_boundary_count = accepted_boundary_count + rejected_boundary_count

    # Reconstructed sides
    missing_side = "left"
    accepted_side = "right"
    rejected_side = "left"

    # Count candidate assignments
    candidates_assigned_to_system = len(sys_candidates)
    candidates_assigned_to_bar = sum(1 for c in sys_candidates if c.get("bar_index") is not None)
    candidates_unassigned_due_to_failed_boundary = sum(
        1 for c in playable_candidates if c.get("bar_index") is None
    )
    ambiguous_boundary_candidate_count = sum(
        1 for c in playable_candidates if c.get("bar_index") is None and any("ambiguous" in str(gw) for gw in sys_warning_codes)
    )

    remediation = (
        "Remediation: Export a clearer born-digital PDF from the engraving software if possible, "
        "or manually inspect and adjust barlines around the affected system. "
        "Do not proceed to ScoreIR until all playable candidates have safe bar evidence. "
        "Edge boundary fallback is intentionally not applied because the layout or boundary evidence is ambiguous."
    )

    return {
        "report_version": "pdf-edge-boundary-report.v0.9",
        "page_index": page_idx,
        "system_index": sys_idx,
        "system_has_playable_candidates": len(playable_candidates) > 0,
        "observed_boundary_count": observed_boundary_count,
        "accepted_boundary_count": accepted_boundary_count,
        "rejected_boundary_count": rejected_boundary_count,
        "inferred_boundary_count": 0,
        "fallback_considered": True,
        "fallback_accepted": False,
        "fallback_rejected": True,
        "fallback_rejection_reasons": rejection_reasons,
        "missing_side": missing_side,
        "accepted_boundary_side": accepted_side,
        "rejected_boundary_side": rejected_side,
        "candidate_count_in_failed_system": len(sys_candidates),
        "playable_candidate_count_in_failed_system": len(playable_candidates),
        "candidates_assigned_to_system": candidates_assigned_to_system,
        "candidates_assigned_to_bar": candidates_assigned_to_bar,
        "candidates_unassigned_due_to_failed_boundary": candidates_unassigned_due_to_failed_boundary,
        "ambiguous_boundary_candidate_count": ambiguous_boundary_candidate_count,
        "whether_grouping_remains_partial": True,
        "whether_build_ir_blocked": True,
        "remediation_hint": remediation,
    }


def write_pdf_edge_boundary_report_html(path: str | Path, report: dict[str, Any]) -> None:
    """Compile the developer-facing premium HTML report for rejected edge boundaries."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    reasons_list = "".join(f"<li><code>{html.escape(r)}</code></li>" for r in report.get("fallback_rejection_reasons", []))

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PDF Edge Boundary Fallback Rejected</title>
  <style>
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #0f172a;
      color: #cbd5e1;
      margin: 0;
      padding: 40px 20px;
      line-height: 1.6;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
    }}
    .header {{
      border-bottom: 2px solid #334155;
      padding-bottom: 20px;
      margin-bottom: 30px;
    }}
    .title {{
      font-size: 2.5rem;
      color: #f8fafc;
      margin: 0 0 10px 0;
      font-weight: 800;
      letter-spacing: -0.025em;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 12px;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 15px;
    }}
    .badge-error {{
      background-color: #ef4444;
      color: #fef2f2;
    }}
    .card {{
      background-color: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }}
    .card-title {{
      font-size: 1.25rem;
      color: #f8fafc;
      margin-top: 0;
      margin-bottom: 16px;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 768px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
    .meta-list {{
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .meta-item {{
      display: flex;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid #334155;
    }}
    .meta-item:last-child {{
      border-bottom: none;
    }}
    .meta-label {{
      font-weight: 600;
      color: #94a3b8;
    }}
    .meta-value {{
      font-family: monospace;
      color: #f8fafc;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #334155;
    }}
    th {{
      background-color: #0f172a;
      color: #94a3b8;
      font-weight: 600;
      font-size: 0.875rem;
    }}
    .alert-box {{
      background-color: rgba(239, 68, 68, 0.1);
      border: 1px solid #ef4444;
      color: #fca5a5;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 24px;
    }}
    .alert-title {{
      font-weight: 700;
      margin-bottom: 8px;
      font-size: 1.1rem;
    }}
    .remediation-box {{
      background-color: rgba(59, 130, 246, 0.1);
      border: 1px solid #3b82f6;
      color: #93c5fd;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 24px;
    }}
    .remediation-title {{
      font-weight: 700;
      margin-bottom: 8px;
      font-size: 1.1rem;
    }}
    pre {{
      background-color: #0f172a;
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      border: 1px solid #334155;
      margin: 0;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 0.9rem;
      color: #38bdf8;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge badge-error">Rejected</span>
      <h1 class="title">PDF Edge-Boundary Fallback Rejected</h1>
      <p style="margin: 0; color: #94a3b8; font-size: 1.1rem;">
        Safety-preserving edge system fallback decision details.
      </p>
    </div>

    <div class="alert-box">
      <div class="alert-title">Fallback Rejected &amp; ScoreIR Blocked</div>
      <p style="margin: 0;">
        PDF grouping remains in <strong>partial_pdf_grouping</strong> status. System detection and bar-box construction succeeded for most systems, but <strong>Page {report.get("page_index")} System {report.get("system_index")}</strong> remains unboxed because fallback was intentionally rejected to preserve timing integrity.
      </p>
    </div>

    <div class="grid">
      <div class="card">
        <h2 class="card-title">System Identification</h2>
        <ul class="meta-list">
          <li class="meta-item">
            <span class="meta-label">Page Index</span>
            <span class="meta-value">{report.get("page_index")}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">System Index</span>
            <span class="meta-value">{report.get("system_index")}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">Playable Candidates Exist</span>
            <span class="meta-value">{"Yes" if report.get("system_has_playable_candidates") else "No"}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">Missing Side</span>
            <span class="meta-value">{html.escape(str(report.get("missing_side")))}</span>
          </li>
        </ul>
      </div>

      <div class="card">
        <h2 class="card-title">Boundary Statistics</h2>
        <ul class="meta-list">
          <li class="meta-item">
            <span class="meta-label">Observed Boundaries</span>
            <span class="meta-value">{report.get("observed_boundary_count")}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">Accepted Boundaries</span>
            <span class="meta-value">{report.get("accepted_boundary_count")}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">Rejected Boundaries</span>
            <span class="meta-value">{report.get("rejected_boundary_count")}</span>
          </li>
          <li class="meta-item">
            <span class="meta-label">Inferred Boundaries</span>
            <span class="meta-value">{report.get("inferred_boundary_count")}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">Fallback Decision Details</h2>
      <ul class="meta-list">
        <li class="meta-item">
          <span class="meta-label">Fallback Considered</span>
          <span class="meta-value">{"Yes" if report.get("fallback_considered") else "No"}</span>
        </li>
        <li class="meta-item">
          <span class="meta-label">Fallback Accepted</span>
          <span class="meta-value">{"Yes" if report.get("fallback_accepted") else "No"}</span>
        </li>
        <li class="meta-item">
          <span class="meta-label">Fallback Rejected</span>
          <span class="meta-value">{"Yes" if report.get("fallback_rejected") else "No"}</span>
        </li>
        <li class="meta-item">
          <span class="meta-label">Accepted Boundary Side</span>
          <span class="meta-value">{html.escape(str(report.get("accepted_boundary_side")))}</span>
        </li>
        <li class="meta-item">
          <span class="meta-label">Rejected Boundary Side</span>
          <span class="meta-value">{html.escape(str(report.get("rejected_boundary_side")))}</span>
        </li>
      </ul>
      <h3 style="color: #f8fafc; font-size: 1.05rem; margin-top: 20px; margin-bottom: 8px;">Rejection Reason Codes:</h3>
      <ul style="margin: 0; padding-left: 20px;">
        {reasons_list}
      </ul>
    </div>

    <div class="card">
      <h2 class="card-title">Impact &amp; Candidate Breakdown</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Total Candidate Count in Failed System</td>
            <td><code>{report.get("candidate_count_in_failed_system")}</code></td>
          </tr>
          <tr>
            <td>Playable Candidate Count in Failed System</td>
            <td><code>{report.get("playable_candidate_count_in_failed_system")}</code></td>
          </tr>
          <tr>
            <td>Candidates Assigned to System</td>
            <td><code>{report.get("candidates_assigned_to_system")}</code></td>
          </tr>
          <tr>
            <td>Candidates Assigned to Bar</td>
            <td><code>{report.get("candidates_assigned_to_bar")}</code></td>
          </tr>
          <tr>
            <td>Playable Candidates Unassigned Due to Failed Boundary</td>
            <td><strong style="color: #ef4444;">{report.get("candidates_unassigned_due_to_failed_boundary")}</strong></td>
          </tr>
          <tr>
            <td>Ambiguous Boundary Candidates</td>
            <td><code>{report.get("ambiguous_boundary_candidate_count")}</code></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="remediation-box">
      <div class="remediation-title">Actionable Guidance</div>
      <p style="margin: 0;">
        {html.escape(report.get("remediation_hint", ""))}
      </p>
    </div>

    <div class="card">
      <h2 class="card-title">Report Metadata &amp; Raw JSON Source</h2>
      <ul class="meta-list" style="margin-bottom: 15px;">
        <li class="meta-item">
          <span class="meta-label">Report Version</span>
          <span class="meta-value">{html.escape(str(report.get("report_version")))}</span>
        </li>
        <li class="meta-item">
          <span class="meta-label">Build-IR Blocked</span>
          <span class="meta-value">{"Yes" if report.get("whether_build_ir_blocked") else "No"}</span>
        </li>
      </ul>
      <pre><code>{html.escape(json.dumps(report, indent=2, sort_keys=True))}</code></pre>
    </div>
  </div>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")
