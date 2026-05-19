from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .build_ir import BuildIrDiagnostics, BuildIrInputRiskError, build_ir_with_diagnostics_from_files
from .ir import validate_score_ir_file
from .pdf import extract_tab
from .tabraw import TabRaw


SUMMARY_SCHEMA_VERSION = "private-diagnostic-summary.v0.1"


def run_private_diagnostic_smoke(
    *,
    pdf_path: str | Path,
    musicxml_path: str | Path | None,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Run a local private diagnostic workflow and return a sanitized summary."""

    pdf = Path(pdf_path)
    musicxml = Path(musicxml_path) if musicxml_path is not None else None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not pdf.exists():
        raise FileNotFoundError(f"PDF input not found: {pdf.name}")

    tabraw_path = out / "extracted.tabraw.json"
    ir_path = out / "score.ir.json"
    diagnostics_path = out / "diagnostics.json"
    build_error_path = out / "build_error.json"
    summary_json_path = out / "summary.json"
    summary_markdown_path = out / "summary.md"

    tabraw_payload = extract_tab(pdf, tabraw_path)
    tabraw = TabRaw.model_validate(tabraw_payload)
    summary = _base_summary(pdf, musicxml, tabraw)
    summary["outputs"] = {
        "tabraw": tabraw_path.name,
        "score_ir": ir_path.name,
        "diagnostics": diagnostics_path.name,
        "summary_json": summary_json_path.name,
        "summary_markdown": summary_markdown_path.name,
    }

    if musicxml is None:
        _record_missing_musicxml(summary)
    elif not musicxml.exists():
        summary["musicxml"]["exists"] = False
        _record_missing_musicxml(summary)
    else:
        try:
            prepared_musicxml, preparation = prepare_musicxml_for_import(musicxml, out)
            summary["musicxml"].update(preparation)
            score, diagnostics = build_ir_with_diagnostics_from_files(prepared_musicxml, tabraw_path, ir_path)
            diagnostics.to_json_file(diagnostics_path)
            _add_build_summary(summary, diagnostics)
            validated, validation_errors = validate_score_ir_file(ir_path)
            summary["validation"] = {
                "ran": True,
                "valid": validated is not None and not validation_errors,
                "error_count": len(validation_errors),
            }
            summary["score_ir"] = {
                "bar_count": len(score.bars),
                "event_count": sum(len(bar.events) for bar in score.bars),
                "warning_count": len(score.warnings),
            }
            summary["suitability"] = _suitability(summary)
        except BuildIrInputRiskError as exc:
            payload = exc.to_diagnostics_payload()
            build_error_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            summary["outputs"]["build_error"] = build_error_path.name
            _record_build_ir_risk(summary, exc, build_error_path.name)
        except Exception as exc:  # noqa: BLE001
            sanitized_error = _sanitize_exception_message(exc, [pdf, musicxml])
            build_error_path.write_text(
                json.dumps({"error_type": type(exc).__name__, "message": sanitized_error}, indent=2),
                encoding="utf-8",
            )
            summary["outputs"]["build_error"] = build_error_path.name
            categories = _summary_risk_categories(summary) + ["validation_failed"]
            summary["build_ir"] = {
                "ran": False,
                "failed": True,
                "stage": "build-ir",
                "error_type": type(exc).__name__,
                "error_category": "validation_failed" if type(exc).__name__ == "ValidationError" else "build_ir_failed",
                "message": _compact_error_message(sanitized_error),
                "error_report": build_error_path.name,
                "output_files_produced": {
                    "tabraw": True,
                    "score_ir": ir_path.exists(),
                    "diagnostics": diagnostics_path.exists(),
                },
            }
            summary["validation"] = {"ran": False, "valid": False, "error_count": None}
            summary["suitability"] = {
                "diagnostic_only": True,
                "suitable_for_next_stage_debugging": False,
                "recommendation_categories": _dedupe(categories),
                "recommended_next_action": "fix-build-ir-input-or-import-error-before-private-debugging",
            }

    _write_summary(summary_json_path, summary_markdown_path, summary)
    return summary


def prepare_musicxml_for_import(path: str | Path, out_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    """Return an uncompressed MusicXML path consumable by the current importer."""

    source = Path(path)
    if source.suffix.lower() != ".mxl":
        return source, {
            "exists": True,
            "basename": source.name,
            "input_format": source.suffix.lower().lstrip(".") or "unknown",
            "prepared_basename": source.name,
            "unpacked_mxl": False,
        }

    prepared = Path(out_dir) / "prepared.musicxml"
    with ZipFile(source) as package:
        rootfile = _mxl_rootfile(package)
        prepared.write_bytes(package.read(rootfile))

    return prepared, {
        "exists": True,
        "basename": source.name,
        "input_format": "mxl",
        "prepared_basename": prepared.name,
        "unpacked_mxl": True,
        "mxl_rootfile": rootfile,
    }


def summarize_tabraw(tabraw: TabRaw) -> dict[str, Any]:
    candidates = tabraw.candidates
    playable = [candidate for candidate in candidates if candidate.parsed_fret is not None]
    non_playable = [candidate for candidate in candidates if candidate.parsed_fret is None]
    confidences = [candidate.confidence for candidate in candidates]
    system_indexes = {candidate.system_index for candidate in candidates if candidate.system_index is not None}
    bar_indexes = {candidate.bar_index for candidate in candidates if candidate.bar_index is not None}
    kind_counts = Counter(candidate.kind for candidate in candidates)

    return {
        "total_candidates": len(candidates),
        "playable_candidates": len(playable),
        "non_playable_candidates": len(non_playable),
        "fret_candidates": len(playable),
        "chord_symbol_candidates": kind_counts.get("chord-symbol", 0),
        "technique_text_candidates": kind_counts.get("technique-text", 0),
        "unknown_text_candidates": kind_counts.get("candidate-text", 0),
        "candidates_with_bbox": sum(1 for candidate in candidates if candidate.bbox is not None),
        "candidates_with_x": sum(1 for candidate in candidates if candidate.x is not None),
        "candidates_with_y": sum(1 for candidate in candidates if candidate.y is not None),
        "candidates_with_system": sum(1 for candidate in candidates if candidate.system_index is not None),
        "candidates_with_string": sum(1 for candidate in candidates if candidate.string is not None),
        "candidates_with_bar": sum(1 for candidate in candidates if candidate.bar_index is not None),
        "inferred_system_count": len(system_indexes),
        "inferred_bar_count": len(bar_indexes),
        "confidence": _confidence_summary(confidences),
    }


def summarize_diagnostics(diagnostics: BuildIrDiagnostics) -> dict[str, Any]:
    quality_counts = Counter(bar.quality for bar in diagnostics.per_bar)
    for quality in ("good", "warning", "poor", "unknown"):
        quality_counts.setdefault(quality, 0)

    worst_bars = sorted(
        (
            {
                "bar_index": bar.bar_index,
                "system_index": bar.system_index,
                "quality": bar.quality,
                "max_relative_error": bar.max_relative_error,
                "mean_absolute_relative_error": bar.mean_absolute_relative_error,
                "ambiguous_x_group_count": bar.ambiguous_x_group_count,
                "playable_candidate_onset_group_count": bar.playable_candidate_onset_group_count,
                "musicxml_pitched_onset_group_count": bar.musicxml_pitched_onset_group_count,
            }
            for bar in diagnostics.per_bar
            if bar.max_relative_error is not None
        ),
        key=lambda item: item["max_relative_error"] or 0.0,
        reverse=True,
    )[:5]

    return {
        "matched_playable_candidate_count": diagnostics.matched_candidate_count,
        "unmatched_musicxml_event_count": diagnostics.unmatched_musicxml_event_count,
        "unmatched_musicxml_note_count": diagnostics.unmatched_musicxml_note_count,
        "unmatched_playable_tabraw_candidate_count": diagnostics.unmatched_tabraw_candidate_count,
        "ignored_non_playable_candidate_count": diagnostics.ignored_non_playable_candidate_count,
        "per_bar_quality_counts": dict(sorted(quality_counts.items())),
        "worst_bars_by_max_relative_drift": worst_bars,
        "bars_with_missing_x_evidence": [
            bar.bar_index for bar in diagnostics.per_bar if any("x-position" in warning for warning in bar.x_to_onset_warnings)
        ],
        "bars_with_ambiguous_x_groups": [bar.bar_index for bar in diagnostics.per_bar if bar.ambiguous_x_group_count],
        "bars_with_count_mismatches": [
            bar.bar_index
            for bar in diagnostics.per_bar
            if bar.playable_candidate_onset_group_count != bar.musicxml_pitched_onset_group_count
        ],
        "extraction_quality_flags": diagnostics.extraction_quality_flags,
    }


def _base_summary(pdf: Path, musicxml: Path | None, tabraw: TabRaw) -> dict[str, Any]:
    extraction = summarize_tabraw(tabraw)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "diagnostic_only": True,
        "private_data_policy": {
            "uses_input_basenames_only": True,
            "omits_candidate_text": True,
            "omits_private_file_contents": True,
        },
        "input": {"pdf_basename": pdf.name},
        "musicxml": {
            "exists": musicxml.exists() if musicxml is not None else False,
            "basename": musicxml.name if musicxml is not None else None,
        },
        "extraction": extraction,
        "build_ir": {"ran": False},
        "validation": {"ran": False, "valid": False, "error_count": None},
        "suitability": {
            "diagnostic_only": True,
            "suitable_for_next_stage_debugging": False,
            "recommendation_categories": _extraction_risk_categories(extraction) + ["alignment_not_attempted"],
            "recommended_next_action": "provide-matching-musicxml-before-build-ir",
        },
    }


def _record_missing_musicxml(summary: dict[str, Any]) -> None:
    summary["build_ir"] = {
        "ran": False,
        "failed": False,
        "blocking_reason": "matching MusicXML timing input is missing; build-ir was not run",
    }
    summary["validation"] = {"ran": False, "valid": False, "error_count": None}
    summary["suitability"] = {
        "diagnostic_only": True,
        "suitable_for_next_stage_debugging": False,
        "recommendation_categories": _summary_risk_categories(summary) + ["alignment_not_attempted"],
        "recommended_next_action": "provide-matching-musicxml-before-build-ir",
    }


def _add_build_summary(summary: dict[str, Any], diagnostics: BuildIrDiagnostics) -> None:
    summary["build_ir"] = {
        "ran": True,
        "failed": False,
        **summarize_diagnostics(diagnostics),
    }


def _record_build_ir_risk(summary: dict[str, Any], exc: BuildIrInputRiskError, report_name: str) -> None:
    timing_issue_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for issue in exc.timing_issues:
        timing_issue_counts[issue.code] = timing_issue_counts.get(issue.code, 0) + 1
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

    categories = _summary_risk_categories(summary)
    if exc.category not in categories:
        categories.append(exc.category)
    if "alignment_not_attempted" not in categories:
        categories.append("alignment_not_attempted")

    summary["build_ir"] = {
        "ran": False,
        "failed": True,
        "stage": exc.stage,
        "error_type": type(exc).__name__,
        "error_category": exc.category,
        "message": _compact_error_message(str(exc)),
        "error_report": report_name,
        "musicxml_timing_issue_count": len(exc.timing_issues),
        "musicxml_timing_issue_counts": dict(sorted(timing_issue_counts.items())),
        "musicxml_timing_severity_counts": dict(sorted(severity_counts.items())),
        "output_files_produced": {
            "tabraw": True,
            "score_ir": False,
            "diagnostics": False,
        },
    }
    summary["validation"] = {"ran": False, "valid": False, "error_count": None}
    summary["suitability"] = {
        "diagnostic_only": True,
        "suitable_for_next_stage_debugging": False,
        "recommendation_categories": categories,
        "recommended_next_action": "review-musicxml-timing-risk-before-alignment",
    }


def _suitability(summary: dict[str, Any]) -> dict[str, Any]:
    validation = summary.get("validation", {})
    build = summary.get("build_ir", {})
    extraction = summary.get("extraction", {})
    quality_counts = build.get("per_bar_quality_counts", {})

    categories = _summary_risk_categories(summary)
    if not validation.get("valid"):
        action = "fix-validation-before-private-debugging"
        suitable = False
        categories.append("validation_failed")
    elif extraction.get("playable_candidates", 0) == 0:
        action = "inspect-pdf-extraction-before-build-ir"
        suitable = False
    elif quality_counts.get("poor", 0) or quality_counts.get("unknown", 0):
        action = "inspect-poor-or-unknown-bars-before-conversion"
        suitable = True
    elif quality_counts.get("warning", 0):
        action = "inspect-warning-bars-before-conversion"
        suitable = True
    else:
        action = "safe-to-inspect-next-stage-diagnostics"
        suitable = True

    return {
        "diagnostic_only": True,
        "suitable_for_next_stage_debugging": suitable,
        "recommendation_categories": _dedupe(categories),
        "recommended_next_action": action,
    }


def _summary_risk_categories(summary: dict[str, Any]) -> list[str]:
    return _extraction_risk_categories(summary.get("extraction", {}))


def _extraction_risk_categories(extraction: dict[str, Any]) -> list[str]:
    categories = []
    if extraction.get("total_candidates", 0) == 0:
        categories.append("extraction_empty")
    if extraction.get("playable_candidates", 0) and (
        extraction.get("inferred_system_count", 0) == 0
        or extraction.get("candidates_with_bar", 0) == 0
        or extraction.get("candidates_with_string", 0) == 0
    ):
        categories.append("missing_pdf_grouping")
    return categories


def _dedupe(values: list[str]) -> list[str]:
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _confidence_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(min(values), 3),
        "mean": round(sum(values) / len(values), 3),
        "max": round(max(values), 3),
    }


def _mxl_rootfile(package: ZipFile) -> str:
    try:
        container = ET.fromstring(package.read("META-INF/container.xml"))
    except KeyError:
        return _first_musicxml_member(package)

    for node in container.iter():
        if _local_name(node.tag) == "rootfile" and node.get("full-path"):
            return str(node.get("full-path"))
    return _first_musicxml_member(package)


def _first_musicxml_member(package: ZipFile) -> str:
    for name in package.namelist():
        if name.lower().endswith((".musicxml", ".xml")) and not name.lower().startswith("meta-inf/"):
            return name
    raise ValueError("MXL package does not contain a MusicXML rootfile")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sanitize_exception_message(exc: Exception, paths: list[Path | None]) -> str:
    message = str(exc)
    for path in paths:
        if path is not None:
            message = message.replace(str(path), path.name)
    return message


def _compact_error_message(message: str) -> str:
    first_line = message.splitlines()[0] if message.splitlines() else message
    if len(first_line) <= 180:
        return first_line
    return first_line[:177] + "..."


def _write_summary(json_path: Path, markdown_path: Path, summary: dict[str, Any]) -> None:
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")


def _summary_markdown(summary: dict[str, Any]) -> str:
    extraction = summary["extraction"]
    build = summary["build_ir"]
    validation = summary["validation"]
    quality_counts = build.get("per_bar_quality_counts", {})
    lines = [
        "# Private Diagnostic Summary",
        "",
        "This diagnostic report intentionally contains only basenames, counts, quality buckets, and risk flags.",
        "",
        f"- PDF: `{summary['input']['pdf_basename']}`",
        f"- MusicXML: `{summary['musicxml'].get('basename') or 'missing'}`",
        f"- Total candidates: {extraction['total_candidates']}",
        f"- Playable candidates: {extraction['playable_candidates']}",
        f"- Non-playable candidates: {extraction['non_playable_candidates']}",
        f"- Inferred systems: {extraction['inferred_system_count']}",
        f"- Inferred bars: {extraction['inferred_bar_count']}",
        f"- Build IR ran: {build.get('ran')}",
        f"- Validation valid: {validation.get('valid')}",
    ]
    categories = summary["suitability"].get("recommendation_categories", [])
    if categories:
        lines.append(f"- Recommendation categories: `{', '.join(categories)}`")
    if quality_counts:
        lines.extend(
            [
                f"- Good bars: {quality_counts.get('good', 0)}",
                f"- Warning bars: {quality_counts.get('warning', 0)}",
                f"- Poor bars: {quality_counts.get('poor', 0)}",
                f"- Unknown bars: {quality_counts.get('unknown', 0)}",
            ]
        )
    lines.append(f"- Recommended next action: `{summary['suitability']['recommended_next_action']}`")
    return "\n".join(lines) + "\n"
