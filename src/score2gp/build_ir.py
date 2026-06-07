from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .ascii_alignment import ALIGNMENT_SCHEMA_VERSION, AsciiMusicXmlAlignment, compute_sha256
from . import __version__
from .ir import (
    DEFAULT_TICKS_PER_QUARTER,
    Bar,
    ConversionInfo,
    Event,
    KeySignature,
    Metadata,
    Note,
    NotatedDuration,
    Provenance,
    ScoreIR,
    SourceStage,
    Technique,
    Tempo,
    TimeSignature,
    Timing,
    Tuning,
    TuningString,
    Tuplet,
    Track,
    WarningItem,
    SlideTechnique,
    BendTechnique,
    VibratoTechnique,
    HammerOnTechnique,
    PullOffTechnique,
    UnsupportedTechnique,
    LetRingTechnique,
    PalmMuteTechnique,
    GraceTiming,
    GraceTechnique,
)
from .musicxml import (
    MusicXmlHarmony,
    MusicXmlImport,
    MusicXmlMeasure,
    MusicXmlNote,
    MusicXmlPart,
    MusicXmlTechnique,
    MusicXmlTimingIssue,
    analyze_musicxml_timing,
    parse_musicxml,
)
from .tabraw import TabCandidate, TabRaw

TRACK_ID = "gtr-1"
DIAGNOSTICS_SCHEMA_VERSION = "build-ir-diagnostics.v0.1"
ASCII_SCOREIR_GATE_VERSION = "ascii-scoreir-gate.v0.1"
PDF_TIMING_REFINEMENT_VERSION = "pdf-timing-refinement.v1.0"
PDF_ONLY_CHORD_X_TOLERANCE_PT = 10.0

_MUSICXML_INVALID_TIMING_CODES = {
    "musicxml-overfull-bar",
    "musicxml-underfull-bar",
    "musicxml_backup_forward_alignment_ambiguous",
    "musicxml_backup_forward_risk",
    "musicxml_backup_rewinds_before_measure_start",
    "musicxml_compound_meter_overfull",
    "musicxml_divisions_changed_mid_measure",
    "musicxml_divisions_missing",
    "musicxml_duration_missing",
    "musicxml_duration_zero",
    "musicxml_forward_exceeds_measure_end",
    "musicxml_invalid_duration_grid",
    "musicxml_many_timing_risks",
    "musicxml_repeated_backup_forward_risk",
    "musicxml_rest_overlap",
    "musicxml_rest_voice_overlap",
    "musicxml_tuplet_unsupported",
    "musicxml_unbalanced_backup_forward",
    "musicxml_voice_cursor_overlap",
    "musicxml_voice_duration_overfull",
    "musicxml-voice-overlap",
}

_MUSICXML_UNSUPPORTED_POLYPHONY_CODES = {
    "musicxml_cross_voice_overlap_unsupported",
    "musicxml_cross_voice_timing_unsupported",
    "musicxml_multivoice_timing_not_supported",
    "musicxml_polyphony_not_supported",
    "musicxml_valid_multivoice_unsupported",
}

_MUSICXML_DERIVED_BLOCKER_CODES = {
    "musicxml_alignment_not_attempted_due_to_timing_risk",
    "musicxml_voice_cursor_alignment_risk",
}


def _musicxml_timing_refinement_summary(issues: list[MusicXmlTimingIssue]) -> dict[str, object]:
    """Return private-safe MusicXML timing classification telemetry."""

    issue_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    primary_reason_counts: dict[str, int] = {}
    secondary_reason_counts: dict[str, int] = {}
    affected_measures: set[tuple[str, int]] = set()
    affected_voices: set[tuple[str, int, int]] = set()
    affected_events: set[str] = set()
    invalid_timing_issue_count = 0
    unsupported_polyphony_issue_count = 0
    derived_blocker_issue_count = 0

    for issue in issues:
        issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        affected_measures.add((issue.part_id, issue.measure_index))
        if issue.voice is not None:
            affected_voices.add((issue.part_id, issue.measure_index, issue.voice))
        if issue.musicxml_note_id:
            affected_events.add(issue.musicxml_note_id)
        affected_events.update(issue.affected_event_ids)
        if issue.primary_reason:
            primary_reason_counts[issue.primary_reason] = primary_reason_counts.get(issue.primary_reason, 0) + 1
        for reason in issue.secondary_reasons:
            secondary_reason_counts[reason] = secondary_reason_counts.get(reason, 0) + 1

        if issue.severity == "error":
            if _issue_has_code(issue, _MUSICXML_INVALID_TIMING_CODES):
                invalid_timing_issue_count += 1
            elif _issue_has_code(issue, _MUSICXML_UNSUPPORTED_POLYPHONY_CODES):
                unsupported_polyphony_issue_count += 1
            elif _issue_has_code(issue, _MUSICXML_DERIVED_BLOCKER_CODES):
                derived_blocker_issue_count += 1

    error_count = severity_counts.get("error", 0)
    if error_count == 0 and not issues:
        classification = "timing_safe"
    elif error_count == 0:
        classification = "timing_warning_or_info_only"
    elif invalid_timing_issue_count and unsupported_polyphony_issue_count:
        classification = "mixed_invalid_timing_and_unsupported_polyphony_refused"
    elif invalid_timing_issue_count:
        classification = "invalid_timing_refused"
    elif unsupported_polyphony_issue_count:
        classification = "unsupported_polyphony_refused"
    elif derived_blocker_issue_count:
        classification = "derived_timing_blocker_refused"
    else:
        classification = "timing_refused"

    return {
        "contract_version": PDF_TIMING_REFINEMENT_VERSION,
        "timing_classification": classification,
        "issue_counts": dict(sorted(issue_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "invalid_timing_issue_count": invalid_timing_issue_count,
        "unsupported_polyphony_issue_count": unsupported_polyphony_issue_count,
        "derived_blocker_issue_count": derived_blocker_issue_count,
        "affected_measure_count": len(affected_measures),
        "affected_voice_count": len(affected_voices),
        "affected_event_count": len(affected_events),
        "primary_reason_counts": dict(sorted(primary_reason_counts.items())),
        "secondary_reason_counts": dict(sorted(secondary_reason_counts.items())),
        "automatic_repair_attempted": False,
        "remediation_hint": _musicxml_timing_refinement_remediation(classification),
    }


def _issue_has_code(issue: MusicXmlTimingIssue, codes: set[str]) -> bool:
    return issue.code in codes or any(reason in codes for reason in issue.secondary_reasons)


def _musicxml_timing_refinement_remediation(classification: str) -> str:
    if classification == "unsupported_polyphony_refused":
        return "MusicXML timing is valid enough to classify, but ScoreIR writing for multi-voice/polyphonic structures is unsupported."
    if classification == "mixed_invalid_timing_and_unsupported_polyphony_refused":
        return "Resolve invalid timing first, then handle unsupported polyphony explicitly; automatic repair is not implemented."
    if classification == "invalid_timing_refused":
        return "Fix or regenerate MusicXML timing; automatic timing repair is not implemented."
    if classification == "timing_warning_or_info_only":
        return "Review timing warnings before trusting alignment; no automatic timing repair was attempted."
    if classification == "timing_safe":
        return "MusicXML timing preflight did not find blocking timing errors."
    return "Timing refinement is diagnostic only; unsafe or unsupported timing remains refused."


class BuildIrInputRiskError(ValueError):
    """Raised when input timing/grouping risk would produce invalid ScoreIR."""

    def __init__(
        self,
        *,
        category: str,
        stage: str,
        message: str,
        timing_issues: list[MusicXmlTimingIssue] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.stage = stage
        self.timing_issues = timing_issues or []
        self.details = details or {}

    def to_diagnostics_payload(self) -> dict[str, object]:
        issue_counts: dict[str, int] = {}
        for issue in self.timing_issues:
            issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1

        payload = {
            "schema_version": "build-ir-failure-diagnostics.v0.1",
            "stage": self.stage,
            "category": self.category,
            "message": str(self),
            "timing_refinement_contract_version": PDF_TIMING_REFINEMENT_VERSION,
            "timing_issue_count": len(self.timing_issues),
            "timing_issue_counts": dict(sorted(issue_counts.items())),
            "timing_issues": [issue.model_dump(mode="json", exclude_none=True) for issue in self.timing_issues],
            "details": self.details,
        }

        # Promote or construct pdf_timing_mapping
        if "pdf_timing_mapping" in self.details:
            payload["pdf_timing_mapping"] = self.details["pdf_timing_mapping"]
        else:
            refusal_reason_codes = []
            grouping_safe = True
            timing_source_safe = True
            musicxml_timing_preflight_status = "safe"
            grouping_status = "grouped"

            if self.stage == "musicxml-import" and self.category == "musicxml_timing_risk":
                refusal_reason_codes.append("pdf_timing_mapping_not_attempted_musicxml_unsafe")
                timing_source_safe = False
                musicxml_timing_preflight_status = "unsafe"
            elif self.stage == "musicxml-import" and self.category == "musicxml_scoreir_polyphony_gate_refused":
                refusal_reason_codes.append("pdf_timing_mapping_polyphony_not_supported")
                timing_source_safe = False
                musicxml_timing_preflight_status = "unsafe"
            elif self.stage == "tabraw-import":
                refusal_reason_codes.append("pdf_timing_mapping_not_attempted_grouping_unsafe")
                grouping_safe = False
                grouping_status = "partial_pdf_grouping"

            if not refusal_reason_codes:
                refusal_reason_codes.append("pdf_timing_mapping_refused")

            payload["pdf_timing_mapping"] = {
                "contract_version": "pdf-timing-mapping.v0.7",
                "refinement_contract_version": PDF_TIMING_REFINEMENT_VERSION,
                "input_class": "drawn_tab_candidate",
                "grouping_status": grouping_status,
                "grouping_safe": grouping_safe,
                "timing_source_safe": timing_source_safe,
                "musicxml_timing_preflight_status": musicxml_timing_preflight_status,
                "whether_mapping_attempted": False,
                "whether_mapping_refused": True,
                "refusal_reason_codes": sorted(list(set(refusal_reason_codes))),
                "mapping_quality_classification": "refused",
                "refinement_reason_codes": sorted(list(set(refusal_reason_codes + ["pdf_timing_refinement_refused"]))),
                "safe_layout_evidence": False,
                "partial_layout_evidence": False,
                "ambiguous_layout_evidence": False,
                "incompatible_layout_evidence": False,
                "quality": "refused",
                "whether_scoreir_written": False,
                "remediation_hint": "Timing mapping is diagnostic evidence only and cannot repair unsafe PDF grouping or unsafe MusicXML timing.",
                "per_bar": [],
                "matched_x_onset_group_count": 0,
                "unmatched_x_group_count": 0,
                "unmatched_onset_group_count": 0,
                "mean_absolute_relative_error": None,
                "max_relative_error": None,
                "monotonic": None,
                "ambiguity_count": 0,
            }

        if self.stage == "musicxml-import":
            # 1. Counts
            overfull_bars = set()
            underfull_bars = set()
            affected_events = set()
            tie_continuity_risks = 0
            many_risk_summaries = 0
            invalid_grids = 0

            # Gather overlaps: max overlap count per (part_id, measure_index)
            overlap_by_measure = {}

            for issue in self.timing_issues:
                # overfull bar check
                if (issue.code in ("musicxml-overfull-bar", "musicxml_compound_meter_overfull", "musicxml_voice_duration_overfull")
                        or "musicxml_voice_duration_overfull" in issue.secondary_reasons
                        or "musicxml_same_voice_measure_overfull" in issue.secondary_reasons):
                    overfull_bars.add((issue.part_id, issue.measure_index))

                # underfull bar check
                if (issue.code in ("musicxml-underfull-bar", "musicxml_compound_meter_underfull", "musicxml_voice_duration_underfull")
                        or "musicxml_voice_duration_underfull" in issue.secondary_reasons):
                    underfull_bars.add((issue.part_id, issue.measure_index))

                # affected event ids
                if issue.affected_event_ids:
                    affected_events.update(issue.affected_event_ids)
                if issue.musicxml_note_id:
                    affected_events.add(issue.musicxml_note_id)

                # overlaps per measure
                if issue.overlap_count is not None:
                    key = (issue.part_id, issue.measure_index)
                    overlap_by_measure[key] = max(overlap_by_measure.get(key, 0), issue.overlap_count)

                # tie continuity
                if issue.code == "musicxml_tie_continuity_risk":
                    tie_continuity_risks += 1

                # many timing risks
                if issue.code in ("musicxml_many_timing_risks", "musicxml_repeated_backup_forward_risk"):
                    many_risk_summaries += 1

                # invalid duration grid
                if issue.code == "musicxml_invalid_duration_grid":
                    invalid_grids += 1

            overfull_bar_count = len(overfull_bars)
            underfull_bar_count = len(underfull_bars)
            affected_event_count = len(affected_events)
            overlap_count = sum(overlap_by_measure.values())

            # 2. Calibration details
            calibration_possible = False
            if self.timing_issues:
                # Check if any issue is considered calibratable
                any_candidate = any(issue.timing_calibration_possible for issue in self.timing_issues)

                # Check blocking reasons
                blocking_reasons = []
                if tie_continuity_risks > 0:
                    blocking_reasons.append("musicxml_tie_continuity_blocks_calibration")
                if overlap_count > 0:
                    blocking_reasons.append("musicxml_overlap_blocks_calibration")
                if many_risk_summaries > 0:
                    blocking_reasons.append("musicxml_many_risks_block_calibration")
                if invalid_grids > 0:
                    blocking_reasons.append("musicxml_invalid_grid_blocks_calibration")
                if overfull_bar_count > 0 and underfull_bar_count > 0:
                    blocking_reasons.append("musicxml_mixed_underfull_overfull_blocks_calibration")

                has_large_overfull = any(
                    "musicxml_overfull_too_large_for_calibration" in issue.secondary_reasons
                    for issue in self.timing_issues
                )
                if has_large_overfull:
                    blocking_reasons.append("musicxml_overfull_too_large_for_calibration")

                has_non_calibratable_error = any(
                    not issue.timing_calibration_possible
                    for issue in self.timing_issues
                    if issue.severity == "error" and issue.code != "musicxml_alignment_not_attempted_due_to_timing_risk"
                )
                if has_non_calibratable_error and "musicxml_timing_calibration_not_safe" not in blocking_reasons:
                    blocking_reasons.append("musicxml_timing_calibration_not_safe")

                if any_candidate and not blocking_reasons:
                    calibration_possible = True
                    calibration_candidate_reason = "musicxml_timing_calibration_candidate"
                    calibration_blocking_reasons = []
                else:
                    calibration_possible = False
                    calibration_candidate_reason = None
                    calibration_blocking_reasons = sorted(list(set(blocking_reasons)))
                    if not calibration_blocking_reasons:
                        calibration_blocking_reasons = ["musicxml_timing_calibration_not_safe"]
            else:
                calibration_possible = False
                calibration_candidate_reason = None
                calibration_blocking_reasons = []

            payload.update({
                "calibration_possible": calibration_possible,
                "calibration_candidate_reason": calibration_candidate_reason,
                "calibration_blocking_reasons": calibration_blocking_reasons,
                "overfull_bar_count": overfull_bar_count,
                "underfull_bar_count": underfull_bar_count,
                "affected_event_count": affected_event_count,
                "overlap_count": overlap_count,
                "tie_continuity_risk_count": tie_continuity_risks,
                "many_risk_summary_count": many_risk_summaries,
                "invalid_grid_count": invalid_grids,
                "automatic_repair_attempted": False,
                "remediation_hint": "Fix or regenerate MusicXML timing; automatic timing repair is not implemented.",
                "unrecoverable_timing_report_json": "musicxml-unrecoverable-timing-report.json",
                "unrecoverable_timing_report_html": "musicxml-unrecoverable-timing-report.html",
                "musicxml_timing_refinement": _musicxml_timing_refinement_summary(self.timing_issues),
            })

        return payload


class CandidateXGroupDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    x_min: float
    x_max: float
    candidate_count: int
    candidate_ids: list[str] = Field(default_factory=list)
    strings: list[int] = Field(default_factory=list)
    is_chord_stack: bool = False


class MusicXmlOnsetGroupDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onset_ticks: int
    event_count: int
    musicxml_note_ids: list[str] = Field(default_factory=list)


class BarAlignmentDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bar_index: int
    system_index: int | None = None
    musicxml_event_count: int
    musicxml_pitched_event_count: int
    musicxml_rest_event_count: int
    scoreir_event_count: int
    matched_candidate_count: int
    unmatched_musicxml_event_count: int
    unmatched_musicxml_note_count: int
    unmatched_tabraw_candidate_count: int
    chord_event_count: int
    playable_candidate_count: int = 0
    playable_candidate_onset_group_count: int = 0
    musicxml_pitched_onset_group_count: int = 0
    bar_x_min: float | None = None
    bar_x_max: float | None = None
    x_span: float | None = None
    onset_tick_min: int | None = None
    onset_tick_max: int | None = None
    candidate_x_positions: list[float] = Field(default_factory=list)
    candidate_x_groups: list[CandidateXGroupDiagnostics] = Field(default_factory=list)
    musicxml_onsets: list[int] = Field(default_factory=list)
    musicxml_onset_groups: list[MusicXmlOnsetGroupDiagnostics] = Field(default_factory=list)
    relative_x_positions: list[float] = Field(default_factory=list)
    relative_onsets: list[float] = Field(default_factory=list)
    mean_absolute_relative_error: float | None = None
    max_relative_error: float | None = None
    monotonic_x: bool | None = None
    has_chord_stack: bool = False
    ambiguous_x_group_count: int = 0
    quality: Literal["good", "warning", "poor", "unknown"] = "unknown"
    x_to_onset_warnings: list[str] = Field(default_factory=list)
    average_event_confidence: float | None = None
    ambiguity_flags: list[str] = Field(default_factory=list)


class SystemAlignmentDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int
    system_index: int
    tabraw_candidate_count: int
    fret_candidate_count: int
    non_fret_candidate_count: int
    matched_playable_candidate_count: int
    unmatched_playable_candidate_count: int
    ignored_non_playable_candidate_count: int
    candidates_with_string: int
    candidates_with_bar: int


class BuildIrDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["build-ir-diagnostics.v0.1"] = DIAGNOSTICS_SCHEMA_VERSION
    alignment_strategy: str = "bar-x-order"
    musicxml_source: str
    tabraw_source: str | None = None
    musicxml_events_imported: int
    musicxml_pitched_events_imported: int
    musicxml_rest_events_imported: int
    tabraw_candidates_loaded: int
    tabraw_fret_candidate_count: int
    tabraw_non_fret_candidate_count: int
    tabraw_chord_symbol_candidate_count: int
    tabraw_technique_text_candidate_count: int
    tabraw_unknown_candidate_count: int
    tabraw_candidates_with_bbox: int
    tabraw_candidates_with_x: int
    tabraw_candidates_with_y: int
    tabraw_candidates_with_system: int
    tabraw_candidates_with_string: int
    tabraw_candidates_with_bar: int
    tabraw_source_stage_counts: dict[str, int] = Field(default_factory=dict)
    matched_candidate_count: int
    unmatched_musicxml_event_count: int
    unmatched_musicxml_note_count: int
    unmatched_tabraw_candidate_count: int
    ignored_non_playable_candidate_count: int
    symbol_attachment_chord_candidates_found: int = 0
    symbol_attachment_chord_candidates_attached: int = 0
    symbol_attachment_chord_candidates_unattached: int = 0
    symbol_attachment_technique_candidates_found: int = 0
    symbol_attachment_technique_candidates_attached: int = 0
    symbol_attachment_technique_candidates_unattached: int = 0
    unsupported_construct_warnings: list[str] = Field(default_factory=list)
    warning_count: int
    confidence_flags: list[dict[str, object]] = Field(default_factory=list)
    extraction_quality_flags: list[str] = Field(default_factory=list)
    ascii_scoreir_gate_status: Literal["not-applicable", "allowed", "refused"] = "not-applicable"
    ascii_scoreir_gate_reason_codes: list[str] = Field(default_factory=list)
    ascii_scoreir_gate_primary_reason_code: str | None = None
    ascii_scoreir_gate_candidate_count: int = 0
    ascii_scoreir_gate_aligned_candidate_count: int = 0
    ascii_scoreir_gate_rejected_candidate_count: int = 0
    ascii_scoreir_gate_output_event_count: int = 0
    ascii_scoreir_gate_scoreir_written: bool = False
    ascii_scoreir_gate_alignment_sidecar_present: bool = False
    ascii_scoreir_gate_alignment_status: str | None = None
    ascii_scoreir_gate_musicxml_timing_safe: bool | None = None
    ascii_scoreir_gate_expected_next_remediation: str | None = None
    per_system: list[SystemAlignmentDiagnostics] = Field(default_factory=list)
    per_bar: list[BarAlignmentDiagnostics] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)
    pdf_timing_mapping: dict[str, object] | None = None

    def to_json_file(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.model_dump_json(indent=2), encoding="utf-8")


def build_ir_from_files(
    musicxml_path: str | Path,
    tabraw_path: str | Path,
    out_path: str | Path | None = None,
    diagnostics_out_path: str | Path | None = None,
    ascii_alignment_path: str | Path | None = None,
    *,
    allow_remediation: bool = False,
    allow_skip_unboxed: bool = False,
    optimize_fret_snapping: bool = False,
    page_range: tuple[int, int] | None = None,
) -> ScoreIR:
    try:
        score, diagnostics = build_ir_with_diagnostics_from_files(
            musicxml_path,
            tabraw_path,
            out_path,
            ascii_alignment_path=ascii_alignment_path,
            allow_remediation=allow_remediation,
            allow_skip_unboxed=allow_skip_unboxed,
            optimize_fret_snapping=optimize_fret_snapping,
            page_range=page_range,
        )
        if diagnostics_out_path is not None:
            diagnostics.to_json_file(diagnostics_out_path)
            from .report import write_symbol_attachment_diagnostics_html, write_pdf_timing_mapping_diagnostics_html
            html_path = Path(diagnostics_out_path).parent / "symbol-attachment-diagnostics.html"
            write_symbol_attachment_diagnostics_html(html_path, diagnostics, score, tabraw_path=tabraw_path)

            # Write PDF timing mapping HTML!
            mapping_html_path = Path(diagnostics_out_path).parent / "pdf-timing-mapping-diagnostics.html"
            write_pdf_timing_mapping_diagnostics_html(mapping_html_path, diagnostics.model_dump(mode="json"), json_path_ref=Path(diagnostics_out_path).name)
        return score
    except BuildIrInputRiskError as exc:
        if diagnostics_out_path is not None:
            import json
            payload = exc.to_diagnostics_payload()
            out_path_p = Path(diagnostics_out_path)
            out_path_p.parent.mkdir(parents=True, exist_ok=True)
            out_path_p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            # Write PDF timing mapping HTML!
            from .report import write_pdf_timing_mapping_diagnostics_html
            mapping_html_path = out_path_p.parent / "pdf-timing-mapping-diagnostics.html"
            write_pdf_timing_mapping_diagnostics_html(mapping_html_path, payload, json_path_ref=out_path_p.name)

            if exc.stage == "ascii-scoreir-gate":
                from .report import write_ascii_gate_diagnostics_html
                html_path = out_path_p.parent / "ascii-scoreir-gate-diagnostics.html"
                write_ascii_gate_diagnostics_html(html_path, payload, json_path_ref=out_path_p.name)
            elif exc.stage == "musicxml-import":
                from .report import write_musicxml_timing_diagnostics_html, write_musicxml_unrecoverable_timing_report
                html_path = out_path_p.parent / "musicxml-timing-diagnostics.html"
                write_musicxml_timing_diagnostics_html(html_path, payload, json_path_ref=out_path_p.name)
                
                # Write unrecoverable timing reports as sidecars
                unrec_json_path = out_path_p.parent / "musicxml-unrecoverable-timing-report.json"
                unrec_html_path = out_path_p.parent / "musicxml-unrecoverable-timing-report.html"
                write_musicxml_unrecoverable_timing_report(
                    unrec_json_path,
                    unrec_html_path,
                    payload,
                    source_path=str(musicxml_path),
                )
            elif exc.stage == "tabraw-import":
                # Reference edge-boundary reports if they exist
                if (out_path_p.parent / "pdf-edge-boundary-report.html").exists():
                    payload["pdf_edge_boundary_report_html"] = "pdf-edge-boundary-report.html"
                    payload["pdf_edge_boundary_report_json"] = "pdf-edge-boundary-report.json"
                if (out_path_p.parent / "grouping-diagnostics.html").exists():
                    payload["grouping_diagnostics_html"] = "grouping-diagnostics.html"
                out_path_p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        raise



def build_ir_with_diagnostics_from_files(
    musicxml_path: str | Path | None,
    tabraw_path: str | Path,
    out_path: str | Path | None = None,
    ascii_alignment_path: str | Path | None = None,
    *,
    allow_remediation: bool = False,
    allow_skip_unboxed: bool = False,
    optimize_fret_snapping: bool = False,
    page_range: tuple[int, int] | None = None,
    include_polyphony_diagnostics: bool = False,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    tabraw = TabRaw.from_json_file(tabraw_path)

    # Gate on known refusal layout warnings (except ASCII requiring sidecar)
    refusal_warnings = {
        "pdf_input_class_scanned_pdf_unsupported",
        "pdf_input_class_no_extractable_tab_geometry",
    }
    if not allow_skip_unboxed:
        refusal_warnings.add("pdf_input_class_drawn_tab_requires_barlines")

    for code in tabraw.pdf_layout_warnings:
        if code in refusal_warnings:
            details = {
                "pdf_layout_class": tabraw.pdf_layout_class,
                "tabraw_warning_codes": [w.get("code") for w in tabraw.warnings if w.get("code")],
                "playable_fret_candidate_count": sum(1 for c in tabraw.candidates if c.parsed_fret is not None),
            }
            raise BuildIrInputRiskError(
                category=code,
                stage="layout-gating",
                message=f"PDF layout is unsupported for direct alignment: {code}",
                details=details,
            )

    if musicxml_path is None or not Path(musicxml_path).exists():
        details = {
            "pdf_layout_class": tabraw.pdf_layout_class,
            "tabraw_warning_codes": [w.get("code") for w in tabraw.warnings if w.get("code")],
            "playable_fret_candidate_count": sum(1 for c in tabraw.candidates if c.parsed_fret is not None),
        }
        raise BuildIrInputRiskError(
            category="pdf_input_class_missing_musicxml_sidecar",
            stage="orchestration-gate",
            message="Matching MusicXML sidecar is missing or not provided.",
            details=details,
        )

    musicxml = parse_musicxml(musicxml_path, allow_remediation=allow_remediation)

    # Now handle ASCII requiring sidecar if alignment path is missing
    if "pdf_input_class_ascii_tab_requires_alignment" in tabraw.pdf_layout_warnings and ascii_alignment_path is None:
        candidates = _ascii_gate_candidates(tabraw)
        timing_issues = analyze_musicxml_timing(musicxml)
        fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
        details = _ascii_scoreir_gate_details(
            candidates=candidates,
            aligned_candidate_count=0,
            alignment_sidecar_present=False,
            alignment_status=None,
            musicxml_timing_safe=not fatal_timing_issues,
        )
        warning_codes = [str(warning.get("code")) for warning in tabraw.warnings if warning.get("code")]
        details.update(
            {
                "tabraw_warning_codes": warning_codes,
                "ascii_timing_status_counts": _ascii_timing_status_counts(candidates),
                "grouping_status": "partial_ascii_tab_grouping"
                if "partial_ascii_tab_grouping" in warning_codes
                else "ascii_grouped",
            }
        )
        _apply_ascii_gate_refusal_details(details, ["pdf_input_class_ascii_tab_requires_alignment"])
        raise BuildIrInputRiskError(
            category="pdf_input_class_ascii_tab_requires_alignment",
            stage="ascii-scoreir-gate",
            message="ASCII TabRaw candidates require a compatible ascii-musicxml-alignment.v0.1 sidecar",
            details=details,
        )
    ascii_gate_details = None
    if ascii_alignment_path is not None:
        gate = _ascii_scoreir_gate(musicxml, tabraw, ascii_alignment_path)
        if not gate.allowed:
            raise BuildIrInputRiskError(
                category=gate.category,
                stage="ascii-scoreir-gate",
                message=gate.message,
                timing_issues=gate.timing_issues,
                details=gate.details,
            )
        tabraw = gate.tabraw or tabraw
        ascii_gate_details = gate.details
    else:
        gate = _ascii_scoreir_missing_sidecar_gate(musicxml, tabraw)
        if gate is not None:
            raise BuildIrInputRiskError(
                category=gate.category,
                stage="ascii-scoreir-gate",
                message=gate.message,
                timing_issues=gate.timing_issues,
                details=gate.details,
            )
    score, diagnostics = build_ir_with_diagnostics_from_imports(
        musicxml,
        tabraw,
        ascii_gate_details=ascii_gate_details,
        allow_skip_unboxed=allow_skip_unboxed,
        optimize_fret_snapping=optimize_fret_snapping,
        page_range=page_range,
        include_polyphony_diagnostics=include_polyphony_diagnostics,
    )
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        score.to_json_file(out)
    return score, diagnostics


@dataclass
class AsciiScoreIrGateDecision:
    allowed: bool
    category: str
    message: str
    details: dict[str, object]
    tabraw: TabRaw | None = None
    timing_issues: list[MusicXmlTimingIssue] = field(default_factory=list)


def _ascii_scoreir_gate(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    ascii_alignment_path: str | Path,
) -> AsciiScoreIrGateDecision:
    alignment = AsciiMusicXmlAlignment.model_validate_json(Path(ascii_alignment_path).read_text(encoding="utf-8"))
    timing_issues = analyze_musicxml_timing(musicxml)
    fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
    playable = _ascii_gate_candidates(tabraw)

    # Cryptographic SHA-256 Source Hash Validation
    pdf_path_str = tabraw.source_pdf
    musicxml_path_str = musicxml.source_path

    active_pdf_hash = None
    if pdf_path_str and Path(pdf_path_str).exists():
        active_pdf_hash = compute_sha256(Path(pdf_path_str))

    active_musicxml_hash = None
    if musicxml_path_str and Path(musicxml_path_str).exists():
        active_musicxml_hash = compute_sha256(Path(musicxml_path_str))

    sidecar_pdf_hash = alignment.source_pdf_hash
    sidecar_musicxml_hash = alignment.source_musicxml_hash

    hash_diagnostics = {}
    has_hash_error = False

    # Check PDF hash
    if not sidecar_pdf_hash or not isinstance(sidecar_pdf_hash, str) or len(sidecar_pdf_hash) != 64:
        has_hash_error = True
        hash_diagnostics["pdf_hash_status"] = "missing" if not sidecar_pdf_hash else "malformed"
    elif not active_pdf_hash:
        has_hash_error = True
        hash_diagnostics["pdf_hash_status"] = "missing_active_file"
    elif active_pdf_hash != sidecar_pdf_hash:
        has_hash_error = True
        hash_diagnostics["pdf_hash_status"] = "mismatch"

    # Check MusicXML hash
    if not sidecar_musicxml_hash or not isinstance(sidecar_musicxml_hash, str) or len(sidecar_musicxml_hash) != 64:
        has_hash_error = True
        hash_diagnostics["musicxml_hash_status"] = "missing" if not sidecar_musicxml_hash else "malformed"
    elif not active_musicxml_hash:
        has_hash_error = True
        hash_diagnostics["musicxml_hash_status"] = "missing_active_file"
    elif active_musicxml_hash != sidecar_musicxml_hash:
        has_hash_error = True
        hash_diagnostics["musicxml_hash_status"] = "mismatch"

    if has_hash_error:
        details = _ascii_scoreir_gate_details(
            candidates=playable,
            aligned_candidate_count=0,
            alignment_sidecar_present=True,
            alignment_status=alignment.overall_status,
            musicxml_timing_safe=not fatal_timing_issues,
            schema_version=alignment.schema_version,
            alignment_path=str(ascii_alignment_path),
        )
        details.update({
            "primary_reason_code": "ascii_alignment_stale_sidecar_hash",
            "reason_codes": ["ascii_alignment_stale_sidecar_hash"],
            "hash_diagnostics": hash_diagnostics,
        })
        _apply_ascii_gate_refusal_details(details, ["ascii_alignment_stale_sidecar_hash"])
        return AsciiScoreIrGateDecision(
            allowed=False,
            category="ascii_alignment_stale_sidecar_hash",
            message="ASCII alignment sidecar hashes are stale, missing, or mismatched.",
            details=details,
            timing_issues=timing_issues,
        )

    compatible_mappings = [mapping for mapping in alignment.candidate_mappings if mapping.result == "compatible"]
    mappings_by_candidate = {mapping.candidate_id: mapping for mapping in alignment.candidate_mappings}
    details = _ascii_scoreir_gate_details(
        candidates=playable,
        aligned_candidate_count=len(compatible_mappings),
        alignment_sidecar_present=True,
        alignment_status=alignment.overall_status,
        musicxml_timing_safe=not fatal_timing_issues,
        schema_version=alignment.schema_version,
        alignment_path=str(ascii_alignment_path),
    )

    def refused(category: str, message: str, reason_codes: list[str]) -> AsciiScoreIrGateDecision:
        _apply_ascii_gate_refusal_details(details, reason_codes)
        return AsciiScoreIrGateDecision(
            allowed=False,
            category=category,
            message=message,
            details=details,
            timing_issues=timing_issues,
        )

    if fatal_timing_issues or any(warning.code == "musicxml_timing_risk" for warning in alignment.warnings):
        return refused(
            "ascii_musicxml_timing_risk",
            "MusicXML timing risk prevents ASCII ScoreIR output.",
            ["ascii_musicxml_timing_risk"],
        )
    if alignment.schema_version != ALIGNMENT_SCHEMA_VERSION:
        return refused(
            "ascii_scoreir_gate_invalid_alignment_schema",
            "ASCII alignment sidecar uses an unsupported schema version.",
            ["ascii_scoreir_gate_invalid_alignment_schema"],
        )
    if alignment.overall_status != "compatible":
        status = alignment.overall_status
        category = _ascii_alignment_status_reason(status)
        return refused(
            category,
            f"ASCII/MusicXML alignment status is {status}; build-ir will not write ScoreIR.",
            [category],
        )

    reason_codes = _ascii_scoreir_gate_reason_codes(musicxml, tabraw, playable, mappings_by_candidate)
    if reason_codes:
        category = reason_codes[0]
        return refused(
            category,
            "ASCII ScoreIR writing gate refused this input because it is outside the tiny controlled v0.1 scope.",
            reason_codes,
        )

    transformed_candidates = []
    for candidate in tabraw.candidates:
        mapping = mappings_by_candidate.get(candidate.id)
        if mapping is None:
            transformed_candidates.append(candidate)
            continue
        raw = {
            **candidate.raw,
            "ascii_scoreir_gate_version": ASCII_SCOREIR_GATE_VERSION,
            "ascii_scoreir_gate_status": "allowed",
            "ascii_alignment_schema_version": alignment.schema_version,
            "ascii_alignment_result": mapping.result,
            "ascii_alignment_onset_distance": mapping.onset_distance,
            "ascii_alignment_confidence": mapping.confidence,
            "aligned_musicxml_note_ids": mapping.nearest_musicxml_note_ids,
            "aligned_musicxml_measure_index": mapping.musicxml_measure_index,
            "aligned_musicxml_measure_number": mapping.musicxml_measure_number,
            "aligned_musicxml_onset_ticks": mapping.nearest_musicxml_onset_ticks,
            "alignment_strategy": "ascii-musicxml-alignment.v0.1",
            "safe_grouping": True,
        }
        transformed_candidates.append(
            candidate.model_copy(
                update={
                    "bar_index": mapping.musicxml_measure_index,
                    "raw": raw,
                }
            )
        )

    warnings = [
        warning
        for warning in tabraw.warnings
        if warning.get("code")
        not in {
            "missing_pdf_grouping",
            "partial_ascii_tab_timing",
            "pdf-tab-system-not-detected",
        }
    ]
    warnings.append(
        {
            "code": "ascii_scoreir_gate_allowed",
            "message": "ASCII TabRaw is allowed through the tiny public ScoreIR-writing gate; durations still come from MusicXML.",
            "severity": "info",
            "gate_version": ASCII_SCOREIR_GATE_VERSION,
        }
    )
    details.update(
        {
            "ascii_scoreir_gate_status": "allowed",
            "reason_codes": ["ascii_scoreir_gate_allowed"],
            "primary_reason_code": "ascii_scoreir_gate_allowed",
            "secondary_reason_codes": [],
            "rejected_candidate_count": 0,
            "output_event_count": len(playable),
            "scoreir_written": True,
            "expected_next_remediation": "none",
        }
    )
    return AsciiScoreIrGateDecision(
        allowed=True,
        category="ascii_scoreir_gate_allowed",
        message="ASCII ScoreIR writing gate allowed this tiny controlled public fixture.",
        details=details,
        tabraw=tabraw.model_copy(update={"candidates": transformed_candidates, "warnings": warnings}),
        timing_issues=timing_issues,
    )


def _ascii_scoreir_missing_sidecar_gate(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
) -> AsciiScoreIrGateDecision | None:
    candidates = _ascii_gate_candidates(tabraw)
    if not candidates:
        return None
    timing_issues = analyze_musicxml_timing(musicxml)
    fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
    if fatal_timing_issues:
        reason_codes = ["ascii_musicxml_timing_risk"]
        category = "ascii_musicxml_timing_risk"
        message = "MusicXML timing risk prevents ASCII ScoreIR output."
    else:
        reason_codes = ["pdf_input_class_ascii_tab_requires_alignment"]
        category = "pdf_input_class_ascii_tab_requires_alignment"
        message = (
            "ASCII TabRaw candidates require a compatible ascii-musicxml-alignment.v0.1 sidecar; "
            "build-ir will not write ScoreIR from ASCII text without explicit alignment evidence."
        )
    details = _ascii_scoreir_gate_details(
        candidates=candidates,
        aligned_candidate_count=0,
        alignment_sidecar_present=False,
        alignment_status=None,
        musicxml_timing_safe=not fatal_timing_issues,
    )
    warning_codes = [str(warning.get("code")) for warning in tabraw.warnings if warning.get("code")]
    details.update(
        {
            "tabraw_warning_codes": warning_codes,
            "ascii_timing_status_counts": _ascii_timing_status_counts(candidates),
            "grouping_status": "partial_ascii_tab_grouping"
            if "partial_ascii_tab_grouping" in warning_codes
            else "ascii_grouped",
        }
    )
    _apply_ascii_gate_refusal_details(details, reason_codes)
    return AsciiScoreIrGateDecision(
        allowed=False,
        category=category,
        message=message,
        details=details,
        timing_issues=timing_issues,
    )


def _ascii_gate_candidates(tabraw: TabRaw) -> list[TabCandidate]:
    return [
        candidate
        for candidate in tabraw.candidates
        if candidate.raw.get("parser_version") == "ascii-tab.v0.1"
        and (candidate.kind == "fret" or candidate.parsed_fret is not None)
    ]


def _ascii_scoreir_gate_reason_codes(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    playable: list[TabCandidate],
    mappings_by_candidate: dict[str, object],
) -> list[str]:
    reason_codes: list[str] = []
    if not playable:
        reason_codes.append("ascii_outside_tiny_gate_scope")
    if any(candidate.parsed_fret is not None and candidate.raw.get("parser_version") != "ascii-tab.v0.1" for candidate in tabraw.candidates):
        reason_codes.append("ascii_outside_tiny_gate_scope")
    for candidate in tabraw.candidates:
        if candidate.raw.get("parser_version") != "ascii-tab.v0.1" or candidate.kind == "fret":
            continue
        if candidate.kind == "chord-symbol":
            reason_codes.append("ascii_unsupported_chord_symbol")
        elif candidate.kind == "technique-text" or candidate.raw.get("technique_context"):
            reason_codes.append("ascii_unsupported_technique_required")

    part = musicxml.parts[0] if musicxml.parts else None
    if part is None:
        reason_codes.append("ascii_outside_tiny_gate_scope")
        return _dedupe(reason_codes)
    if len(musicxml.parts) != 1:
        reason_codes.append("ascii_outside_tiny_gate_scope")
    if len(part.measures) > 2:
        reason_codes.append("ascii_outside_tiny_gate_scope")
    if any(measure.harmonies for measure in part.measures):
        reason_codes.append("ascii_unsupported_chord_symbol")

    pitched_notes: list[MusicXmlNote] = []
    for measure in part.measures:
        for group in _note_groups(measure.notes):
            first = group[0]
            if first.grace:
                reason_codes.append("ascii_outside_tiny_gate_scope")
            if len([note for note in group if not note.is_rest and note.pitch is not None]) > 1 or any(note.chord for note in group):
                reason_codes.append("ascii_polyphony_not_supported")
            if first.voice != 1:
                reason_codes.append("ascii_polyphony_not_supported")
            if first.tuplet is not None or any(note.tuplet is not None for note in group):
                reason_codes.append("ascii_outside_tiny_gate_scope")
            if first.duration_divisions <= 0 and (not first.is_rest or first.pitch is not None):
                reason_codes.append("ascii_duration_source_missing")
            for note in group:
                if note.techniques or note.ties:
                    reason_codes.append("ascii_unsupported_technique_required")
                if not note.is_rest and note.pitch is not None and not note.grace:
                    if note.duration_divisions <= 0:
                        reason_codes.append("ascii_duration_source_missing")
                    pitched_notes.append(note)

    if len(playable) != len(pitched_notes):
        reason_codes.append("ascii_alignment_not_one_to_one")

    mapped_note_ids: list[str] = []
    for candidate in playable:
        mapping = mappings_by_candidate.get(candidate.id)
        if mapping is None:
            reason_codes.append("ascii_alignment_candidate_missing")
            continue
        result = getattr(mapping, "result", None)
        if result != "compatible":
            reason_codes.append(_ascii_alignment_status_reason(str(result or "unavailable")))
        note_ids = list(getattr(mapping, "nearest_musicxml_note_ids", []) or [])
        if len(note_ids) != 1:
            reason_codes.append("ascii_alignment_not_one_to_one")
        mapped_note_ids.extend(note_ids)
        if getattr(mapping, "musicxml_measure_index", None) is None:
            reason_codes.append("ascii_candidate_unmapped_measure")
        if getattr(mapping, "nearest_musicxml_onset_ticks", None) is None:
            reason_codes.append("ascii_candidate_unmapped_onset")
        if candidate.string is None:
            reason_codes.append("ascii_candidate_missing_string")
        if candidate.parsed_fret is None:
            reason_codes.append("ascii_candidate_missing_fret")
        if candidate.raw.get("timing_parser_version") != "ascii-timing.v0.1":
            reason_codes.append("ascii_outside_tiny_gate_scope")
        if candidate.raw.get("ascii_measure_segment_id") is None:
            reason_codes.append("ascii_candidate_unmapped_measure")
        if candidate.raw.get("ascii_timing_status") not in {"timing_partial", "timing_safe"}:
            reason_codes.append("ascii_alignment_status_unavailable")
        if any(code in (candidate.raw.get("ascii_timing_warnings") or []) for code in {"ambiguous_ascii_tab_timing", "unsupported_ascii_tab_rhythm"}):
            reason_codes.append("ascii_alignment_status_ambiguous")

    pitched_note_ids = {note.id for note in pitched_notes}
    if set(mapped_note_ids) != pitched_note_ids or len(mapped_note_ids) != len(set(mapped_note_ids)):
        reason_codes.append("ascii_alignment_not_one_to_one")
    return _dedupe(reason_codes)


def _ascii_scoreir_gate_details(
    *,
    candidates: list[TabCandidate],
    aligned_candidate_count: int,
    alignment_sidecar_present: bool,
    alignment_status: str | None,
    musicxml_timing_safe: bool,
    schema_version: str | None = None,
    alignment_path: str | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "gate_version": ASCII_SCOREIR_GATE_VERSION,
        "ascii_scoreir_gate_status": "refused",
        "schema_version": schema_version,
        "alignment_status": alignment_status,
        "alignment_sidecar_present": alignment_sidecar_present,
        "musicxml_timing_safe": musicxml_timing_safe,
        "reason_codes": [],
        "primary_reason_code": None,
        "secondary_reason_codes": [],
        "candidate_count": len(candidates),
        "aligned_candidate_count": aligned_candidate_count,
        "rejected_candidate_count": len(candidates),
        "sample_candidate_ids": [candidate.id for candidate in candidates[:5]],
        "output_event_count": 0,
        "scoreir_written": False,
        "expected_next_remediation": None,
    }
    if alignment_path is not None:
        details["alignment_path"] = alignment_path
    return details


def _apply_ascii_gate_refusal_details(details: dict[str, object], reason_codes: list[str]) -> None:
    deduped = _dedupe(reason_codes)
    primary = deduped[0] if deduped else "ascii_outside_tiny_gate_scope"
    candidate_count = _int_detail(details, "candidate_count")
    remediation = _ascii_gate_remediation(primary)
    details.update(
        {
            "ascii_scoreir_gate_status": "refused",
            "reason_codes": deduped or [primary],
            "primary_reason_code": primary,
            "secondary_reason_codes": deduped[1:],
            "rejected_candidate_count": candidate_count,
            "output_event_count": 0,
            "scoreir_written": False,
            "expected_next_remediation": remediation,
            "remediation_hint": remediation,
        }
    )



def _ascii_alignment_status_reason(status: str) -> str:
    if status in {"unavailable", "partial", "ambiguous", "incompatible"}:
        return f"ascii_alignment_status_{status}"
    return "ascii_outside_tiny_gate_scope"


def _ascii_gate_remediation(reason_code: str) -> str:
    mapping = {
        "pdf_input_class_ascii_tab_requires_alignment": "provide compatible ascii-musicxml-alignment.v0.1 evidence",
        "ascii_alignment_stale_sidecar_hash": "re-align the source PDF and MusicXML files to update the stale hashes",
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
    return mapping.get(reason_code, "this case is intentionally unsupported by ascii-scoreir-gate.v0.1")


def _int_detail(details: dict[str, object], key: str) -> int:
    value = details.get(key)
    return value if isinstance(value, int) else 0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _pdf_timing_refinement_classification(
    *,
    total_playable_count: int,
    matched_x_onset_group_count: int,
    unmatched_x_group_count: int,
    unmatched_onset_group_count: int,
    total_ambiguity_count: int,
    overall_quality: str,
    all_monotonic: bool,
) -> tuple[str, list[str]]:
    if total_playable_count == 0 or matched_x_onset_group_count == 0:
        return "unavailable", ["pdf_timing_refinement_unavailable_layout_evidence"]
    if overall_quality == "poor" or all_monotonic is False:
        return "incompatible", ["pdf_timing_refinement_incompatible_layout_evidence"]
    if total_ambiguity_count > 0:
        return "ambiguous", ["pdf_timing_refinement_ambiguous_layout_evidence"]
    if unmatched_x_group_count > 0 or unmatched_onset_group_count > 0 or overall_quality == "warning":
        return "partial", ["pdf_timing_refinement_partial_layout_evidence"]
    if overall_quality == "good":
        return "safe", ["pdf_timing_refinement_safe_layout_evidence"]
    return "partial", ["pdf_timing_refinement_partial_layout_evidence"]


def build_ir_from_imports(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    *,
    optimize_fret_snapping: bool = False,
    page_range: tuple[int, int] | None = None,
) -> ScoreIR:
    score, _ = build_ir_with_diagnostics_from_imports(
        musicxml, tabraw, optimize_fret_snapping=optimize_fret_snapping, page_range=page_range
    )
    return score


def build_ir_with_diagnostics_from_imports(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    *,
    ascii_gate_details: dict[str, object] | None = None,
    allow_skip_unboxed: bool = False,
    optimize_fret_snapping: bool = False,
    page_range: tuple[int, int] | None = None,
    include_polyphony_diagnostics: bool = False,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    from .musicxml import deduplicate_suspected_staff_tab_voices
    musicxml = deduplicate_suspected_staff_tab_voices(musicxml)

    if page_range is not None:
        start_page, end_page = page_range
        # Filter candidates: keep only selected pages, and strip explicitly excluded text/digits (like page numbers)
        tabraw.candidates = [
            c for c in tabraw.candidates
            if c.page_index is not None and start_page <= c.page_index <= end_page
            and not (
                isinstance(c.raw, dict)
                and any(
                    w in (c.raw.get("assignment_warnings") or [])
                    for w in (
                        "pdf_fret_technique_marker_excluded",
                        "pdf_fret_chord_text_digit_excluded",
                        "pdf_fret_page_or_legend_number_excluded",
                    )
                )
            )
        ]
        # Filter warnings: remove page-specific warnings outside range,
        # and strip general/global grouping or suitability warnings that are stale under page range constraints.
        filtered_warnings = []
        for w in tabraw.warnings:
            code = w.get("code")
            p_idx = w.get("page_index") or w.get("page_number")
            if p_idx is not None:
                try:
                    p = int(p_idx)
                    if start_page <= p <= end_page:
                        filtered_warnings.append(w)
                except (ValueError, TypeError):
                    filtered_warnings.append(w)
            else:
                # Strip global/general suitability or layout warnings that are stale when page range constraints are active
                if code in {
                    "pdf_grouping_not_safe_for_build_ir",
                    "pdf_missing_pdf_grouping_blocks_build_ir",
                    "pdf_partial_grouping_one_system_unboxed",
                    "pdf_playable_candidate_requires_string_assignment",
                    "pdf_partial_grouping_with_playable_candidates",
                    "pdf_layout_detection_requires_manual_review",
                    "partial_pdf_grouping",
                    "missing_pdf_grouping",
                    "missing_pdf_barlines",
                    "incomplete_tab_staff",
                    "ambiguous_string_assignment",
                    "ambiguous_bar_assignment",
                    "pdf_system_detection_not_enough_for_build_ir",
                    "pdf_bar_detection_not_enough_for_build_ir",
                    "pdf_bar_box_construction_not_enough_for_build_ir",
                    "pdf_string_assignment_not_enough_for_build_ir",
                    "pdf_fret_refinement_not_enough_for_build_ir",
                    "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
                    "pdf_timing_mapping_refused",
                    "pdf_timing_mapping_not_enough_for_build_ir",
                } or (isinstance(code, str) and (code.startswith("pdf_") or code.startswith("ascii_"))):
                    continue
                filtered_warnings.append(w)
        tabraw.warnings = filtered_warnings
    if allow_skip_unboxed:
        unboxed_systems = set()
        skipped_systems = set()
        for w in tabraw.warnings:
            code = w.get("code")
            if code in (
                "pdf_barlines_not_detected_in_system",
                "pdf_bar_boxes_not_constructible",
                "pdf_bar_box_construction_not_enough_for_build_ir",
                "pdf_bar_box_one_boundary_rejected",
                "pdf_bar_box_edge_system_missing_boundary",
                "pdf_bar_boxes_missing",
            ):
                p_idx = w.get("page_index") or w.get("page_number")
                s_idx = w.get("system_index")
                if p_idx is not None and s_idx is not None:
                    unboxed_systems.add((int(p_idx), int(s_idx)))

        if unboxed_systems:
            recovered_systems = set()
            for p_idx, s_idx in unboxed_systems:
                has_rejected_barlines = False
                for w in tabraw.warnings:
                    if w.get("severity") == "info":
                        continue
                    code = str(w.get("code", ""))
                    if not code.startswith("pdf_barline_") and code != "pdf_barline_candidates_present_but_invalid":
                        continue

                    w_page = w.get("page_index") or w.get("page_number")
                    w_sys = w.get("system_index")
                    msg = str(w.get("message", "")).lower()

                    if w_page is None:
                        if f"page {p_idx}" in msg:
                            w_page = p_idx
                    if w_sys is None:
                        if f"system {s_idx}" in msg:
                            w_sys = s_idx

                    if w_page is not None and w_sys is not None:
                        try:
                            if int(w_page) == p_idx and int(w_sys) == s_idx:
                                has_rejected_barlines = True
                                break
                        except (ValueError, TypeError):
                            pass

                if not has_rejected_barlines:
                    recovered_systems.add((p_idx, s_idx))
                else:
                    skipped_systems.add((p_idx, s_idx))

            # Recover zero-barline systems
            # Recover zero-barline systems
            if recovered_systems:
                new_candidates = []
                for candidate in tabraw.candidates:
                    if candidate.page_index is not None and candidate.system_index is not None:
                        if (candidate.page_index, candidate.system_index) in recovered_systems:
                            candidate = candidate.model_copy(update={"bar_index": 1})
                    new_candidates.append(candidate)
                tabraw.candidates = new_candidates

                # Filter out missing bar warnings for recovered systems
                filtered_warnings = []
                for w in tabraw.warnings:
                    p_idx = w.get("page_index") or w.get("page_number")
                    s_idx = w.get("system_index")
                    code = w.get("code")
                    if p_idx is not None and s_idx is not None:
                        if (int(p_idx), int(s_idx)) in recovered_systems:
                            if code in (
                                "pdf_barlines_not_detected_in_system",
                                "pdf_bar_boxes_not_constructible",
                                "pdf_bar_detection_not_enough_for_build_ir",
                                "pdf_barlines_missing",
                                "pdf_bar_boxes_missing",
                                "pdf_bar_box_construction_not_enough_for_build_ir",
                                "pdf_candidate_unassigned_due_to_unboxed_system",
                                "pdf_candidate_unassigned_to_bar",
                            ):
                                continue
                    filtered_warnings.append(w)
                tabraw.warnings = filtered_warnings

                # Log recovered warnings
                for p_idx, s_idx in sorted(recovered_systems):
                    tabraw.warnings.extend([
                        {"code": "pdf_system_recovered_as_single_measure", "message": f"System {s_idx} on page {p_idx} recovered.", "severity": "info", "page_index": p_idx, "system_index": s_idx},
                        {"code": "pdf_bar_box_system_wide_fallback", "message": f"System-wide fallback used for system {s_idx} on page {p_idx}.", "severity": "info", "page_index": p_idx, "system_index": s_idx}
                    ])

            # Skip remaining unboxed systems and unassigned candidates
            new_candidates = []
            for candidate in tabraw.candidates:
                if candidate.page_index is None or candidate.system_index is None:
                    continue
                if skipped_systems and (candidate.page_index, candidate.system_index) in skipped_systems:
                    continue
                new_candidates.append(candidate)
            tabraw.candidates = new_candidates

            if skipped_systems:
                # Filter out all warnings for skipped systems
                filtered_warnings = []
                for w in tabraw.warnings:
                    p_idx = w.get("page_index") or w.get("page_number")
                    s_idx = w.get("system_index")
                    if p_idx is not None and s_idx is not None:
                        if (int(p_idx), int(s_idx)) in skipped_systems:
                            continue
                    filtered_warnings.append(w)
                tabraw.warnings = filtered_warnings

                for p_idx, s_idx in sorted(skipped_systems):
                    tabraw.warnings.append({
                        "code": "pdf_unboxed_system_skipped",
                        "message": f"Unassigned candidates from unboxed system {s_idx} on page {p_idx} were skipped.",
                        "severity": "warning",
                        "page_index": p_idx,
                        "system_index": s_idx,
                    })

        # Clean up page-level unboxed system warning and grouping taxonomy warning codes
        UNSAFE_GROUPING_CODES = set(_tabraw_unsafe_grouping_warning_codes(tabraw))
        UNSAFE_GROUPING_CODES.update({
            "pdf_barlines_not_detected_in_system",
            "pdf_bar_boxes_not_constructible",
            "pdf_bar_detection_not_enough_for_build_ir",
            "pdf_barlines_missing",
            "pdf_bar_boxes_missing",
            "pdf_bar_box_construction_not_enough_for_build_ir",
            "pdf_candidate_unassigned_due_to_unboxed_system",
            "pdf_candidate_unassigned_to_bar",
            "pdf_candidates_unassigned_to_bar",
            "pdf_candidates_unassigned_to_system",
            "pdf_candidates_unassigned_to_string",
            "pdf_string_assignment_missing",
            "pdf_string_assignment_not_enough_for_build_ir",
            "pdf_candidate_outside_system",
            "pdf_candidate_outside_bar",
            "pdf_fret_optical_bounds_confidence_below_threshold",
            "pdf_fret_refinement_not_enough_for_build_ir",
            "pdf_grouping_confidence_below_threshold",
            "pdf_grouping_not_safe_for_build_ir",
            "pdf_input_class_drawn_tab_requires_barlines",
            "pdf_layout_detection_requires_manual_review",
            "pdf_missing_pdf_grouping_blocks_build_ir",
            "pdf_partial_grouping_with_playable_candidates",
            "pdf_system_detected_bar_detection_missing",
            "missing_pdf_grouping",
            "partial_pdf_grouping",
            "pdf_partial_grouping_one_system_unboxed",
            "pdf_string_assignment_succeeded_upstream_grouping_still_blocks",
            "pdf_candidate_near_missing_bar_boundary",
            "pdf_partial_system_detection",
            "pdf_playable_candidate_requires_string_assignment",
            "pdf_string_assignment_confidence_below_threshold",
            "pdf_string_assignment_outside_staff",
            "pdf_tab_staff_incomplete",
            "pdf_fret_bbox_too_tall",
            "pdf_fret_digit_symbol_overlap_ambiguous",
            "pdf_fret_digits_not_merged_gap_too_large",
            "incomplete_tab_staff",
            "missing_pdf_barlines",
            "ambiguous_bar_assignment",
        })
        filtered_warnings = []
        for w in tabraw.warnings:
            code = w.get("code")
            if code in UNSAFE_GROUPING_CODES:
                continue
            filtered_warnings.append(w)
        tabraw.warnings = filtered_warnings
        _synchronize_skipped_system_measures(musicxml, tabraw, skipped_systems)






    warnings = _musicxml_warnings(musicxml)
    timing_issues = analyze_musicxml_timing(musicxml, include_polyphony_diagnostics=include_polyphony_diagnostics)
    if ascii_gate_details is None:
        for issue in timing_issues:
            if issue.code in ("musicxml_duration_missing", "musicxml_duration_zero"):
                issue.severity = "error"
    warnings.extend(_musicxml_timing_issue_warnings(timing_issues))
    fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
    if fatal_timing_issues:
        category = "musicxml_timing_risk"
        if all(
            issue.code in (
                "musicxml_polyphony_not_supported",
                "musicxml_multivoice_timing_not_supported",
                "musicxml_cross_voice_timing_unsupported",
                "musicxml_valid_multivoice_unsupported",
                "musicxml_voice_cursor_alignment_risk",
                "musicxml_alignment_not_attempted_due_to_timing_risk",
                "musicxml_many_timing_risks",
            )
            for issue in fatal_timing_issues
        ):
            category = "musicxml_scoreir_polyphony_gate_refused"
            message = "MusicXML timing is valid but contains unsupported polyphony/multi-voice structures."
        else:
            message = (
                "MusicXML timing risk prevents ScoreIR output: "
                f"{len(fatal_timing_issues)} overfull or overlapping event(s) would violate ScoreIR timing."
            )
        raise BuildIrInputRiskError(
            category=category,
            stage="musicxml-import",
            message=message,
            timing_issues=timing_issues,
        )
    grouping_risk = None if ascii_gate_details is not None else _tabraw_grouping_risk(tabraw)
    if grouping_risk is not None:
        category = str(grouping_risk.get("category", "missing_pdf_grouping"))
        if category == "ascii_tab_timing_unavailable":
            message = (
                "TabRaw extraction found ASCII-tab fret candidates with row/string evidence, but no safe "
                "MusicXML timing or bar alignment; build-ir will not guess timing from character positions."
            )
        elif category == "partial_ascii_tab_timing":
            message = (
                "TabRaw extraction found ASCII-tab fret candidates with partial bar/column timing evidence, "
                "but character columns are alignment hints rather than musical timing; build-ir will not "
                "write ScoreIR from ASCII timing guesses."
            )
        elif category == "ambiguous_ascii_tab_timing":
            message = (
                "TabRaw extraction found ASCII-tab fret candidates, but ASCII bar separators or row widths "
                "make timing evidence ambiguous; build-ir will not guess timing from character positions."
            )
        elif category == "partial_ascii_tab_grouping":
            message = (
                "TabRaw extraction found ASCII-tab fret candidates, but the ASCII row grouping is partial; "
                "build-ir will not treat incomplete ASCII tab text as reliable musical evidence."
            )
        else:
            grouping_phrase = "partial or missing" if category == "partial_pdf_grouping" else "missing"
            message = (
                f"TabRaw extraction found playable fret candidates, but system/string/bar grouping is {grouping_phrase}; "
                "build-ir will not treat unsafe PDF text as reliable musical evidence."
            )
        raise BuildIrInputRiskError(
            category=category,
            stage="tabraw-import",
            message=message,
            details=grouping_risk,
        )
    warnings.extend(_tabraw_warnings(tabraw))
    if musicxml.tempo_bpm is None:
        warnings.append(
            WarningItem(
                code="musicxml-tempo-missing",
                message="MusicXML did not contain a tempo; ScoreIR uses 120 bpm as an explicit placeholder.",
                severity="warning",
            )
        )

    if not musicxml.parts:
        warnings.append(
            WarningItem(
                code="musicxml-no-parts",
                message="MusicXML contains no parts; generated ScoreIR contains no bars.",
                severity="error",
            )
        )
        part = None
    else:
        part = musicxml.parts[0]
        if len(musicxml.parts) > 1:
            warnings.append(
                WarningItem(
                    code="musicxml-extra-parts-ignored",
                    message="Only the first MusicXML part is converted during this synthetic build-ir phase.",
                    severity="warning",
                )
            )

    candidate_pools = CandidatePools.from_tabraw(tabraw)
    bars: list[Bar] = []
    if part is not None:
        staves_in_part = {note.staff for measure in part.measures for note in measure.notes if note.staff is not None and not note.is_suppressed}
        target_staff = max(staves_in_part) if staves_in_part else 1
        for measure in part.measures:
            measure.notes = [note for note in measure.notes if (note.staff is None or note.staff == target_staff) and not note.is_suppressed]
            bar_warnings: list[WarningItem] = []
            events = _measure_events(measure, candidate_pools, bar_warnings)
            warnings.extend(bar_warnings)
            bars.append(
                Bar(
                    index=measure.index,
                    time_signature=measure.time_signature,
                    key_signature=KeySignature(fifths=measure.key_fifths) if measure.key_fifths is not None else None,
                    events=events,
                )
            )
        warnings.extend(_unused_candidate_warnings(candidate_pools))

    score = ScoreIR(
        metadata=Metadata(
            title=musicxml.metadata.title,
            composer=musicxml.metadata.composer,
            copyright=musicxml.metadata.rights,
            source=musicxml.source_path,
        ),
        conversion=ConversionInfo(
            tool_name="score2gp",
            tool_version=__version__,
            conversion_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            source_file_hash=musicxml.source_sha256,
        ),
        tempo=Tempo(bpm=musicxml.tempo_bpm or 120),
        tracks=[_standard_guitar_track()],
        bars=bars,
        warnings=warnings,
    )
    _attach_symbols_and_techniques(score, tabraw)
    if optimize_fret_snapping:
        globals()["optimize_fret_snapping"](score)
    diagnostics = _build_diagnostics(musicxml, tabraw, score, candidate_pools, ascii_gate_details=ascii_gate_details)
    if diagnostics.pdf_timing_mapping:
        mapping = diagnostics.pdf_timing_mapping
        is_monotonic = mapping.get("monotonic")
        if is_monotonic is False:
            reason_codes = mapping.get("refusal_reason_codes") or []
            category = "pdf_timing_mapping_non_monotonic"
            raise BuildIrInputRiskError(
                category=category,
                stage="tabraw-import",
                message=f"PDF timing mapping is unsafe: {', '.join(reason_codes)}",
                details={"pdf_timing_mapping": mapping, "grouping_status": "grouped", "grouping_safe": True},
            )
    return score, diagnostics


def build_ir_from_tabraw_only(
    tabraw_path: str | Path,
    *,
    tempo_bpm: float = 120.0,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    tabraw = TabRaw.from_json_file(tabraw_path)

    # Safety checks
    if not tabraw.candidates:
        raise BuildIrInputRiskError(
            category="pdf_only_tab_grouping_unsafe",
            stage="layout-gating",
            message="PDF-only tab building refused: no candidates found in TabRaw.",
        )

    # 1. Check layout warnings
    unsafe_warning_codes = {
        # No systems
        "pdf_no_systems_detected",
        "pdf_input_class_no_extractable_tab_geometry",
        "pdf_drawn_system_not_detected",
        "pdf_candidates_unassigned_to_system",
        # Missing string lines
        "pdf_string_lines_missing",
        "pdf_tab_staff_missing",
        "pdf_tab_staff_incomplete",
        "incomplete_tab_staff",
        "pdf_candidates_unassigned_to_string",
        # Missing bar boxes
        "pdf_barlines_missing",
        "pdf_bar_boxes_missing",
        "missing_pdf_barlines",
        "pdf_bar_box_construction_not_enough_for_build_ir",
        "pdf_candidates_unassigned_to_bar",
        "pdf_full_grouping_requires_all_systems_boxed",
        # Ambiguous string assignment
        "pdf_string_assignment_ambiguous",
        "ambiguous_string_assignment",
        "pdf_tab_staff_ambiguous",
        # Ambiguous bar assignment
        "pdf_barlines_ambiguous",
        "ambiguous_bar_assignment",
        "pdf_system_order_ambiguous",
        "pdf_system_bbox_ambiguous",
    }

    found_unsafe = None
    for warning_code in tabraw.pdf_layout_warnings:
        if warning_code in unsafe_warning_codes:
            found_unsafe = warning_code
            break

    if not found_unsafe:
        for w in tabraw.warnings:
            code = w.get("code")
            if code in unsafe_warning_codes:
                found_unsafe = code
                break

    if found_unsafe:
        raise BuildIrInputRiskError(
            category="pdf_only_tab_grouping_unsafe",
            stage="layout-gating",
            message=f"PDF-only tab building refused due to unsafe layout warning: {found_unsafe}",
            details={"refusal_warning_code": found_unsafe},
        )

    fret_candidates = [c for c in tabraw.candidates if c.parsed_fret is not None and c.kind == "fret"]
    if not fret_candidates:
        raise BuildIrInputRiskError(
            category="pdf_only_tab_grouping_unsafe",
            stage="layout-gating",
            message="PDF-only tab building refused: no playable fret candidates found.",
        )

    for candidate in fret_candidates:
        if candidate.string is None or candidate.bar_index is None or candidate.system_index is None or candidate.x is None:
            raise BuildIrInputRiskError(
                category="pdf_only_tab_grouping_unsafe",
                stage="layout-gating",
                message=f"PDF-only tab building refused: candidate {candidate.id} has missing required layout fields (string={candidate.string}, bar_index={candidate.bar_index}, system_index={candidate.system_index}, x={candidate.x}).",
            )

    # 2. Rhythmic alignment & ScoreIR generation
    _STRING_TO_BASE_PITCH = {
        1: 64,  # E4
        2: 59,  # B3
        3: 55,  # G3
        4: 50,  # D3
        5: 45,  # A2
        6: 40,  # E2
    }

    def split_duplicate_strings(candidates: list[TabCandidate]) -> list[list[TabCandidate]]:
        sorted_cands = sorted(candidates, key=lambda c: (c.x or 0.0, c.string or 0, c.id))
        subgroups = []
        current_subgroup = []
        current_strings = set()
        for c in sorted_cands:
            if c.string in current_strings:
                subgroups.append(current_subgroup)
                current_subgroup = [c]
                current_strings = {c.string} if c.string is not None else set()
            else:
                current_subgroup.append(c)
                if c.string is not None:
                    current_strings.add(c.string)
        if current_subgroup:
            subgroups.append(current_subgroup)
        return subgroups

    # Get unique source bar keys in stable reading order:
    # (page_index, system_index, staff_index, bar_index)
    source_bar_keys = sorted(list({(c.page_index or 1, c.system_index, c.staff_index or 1, c.bar_index) for c in fret_candidates}))

    bars = []
    output_bar_to_frets = {}

    for output_bar_idx, source_bar_key in enumerate(source_bar_keys, start=1):
        page_idx, sys_idx, staff_idx, local_bar_idx = source_bar_key
        bar_frets = [
            c for c in fret_candidates
            if (c.page_index or 1) == page_idx
            and c.system_index == sys_idx
            and (c.staff_index or 1) == staff_idx
            and c.bar_index == local_bar_idx
        ]

        output_bar_to_frets[output_bar_idx] = bar_frets

        if not bar_frets:
            # Create a rest event filling the bar (should be unreachable as keys are from fret_candidates)
            rest_event = Event(
                id=f"bar-{output_bar_idx}-rest",
                track_id=TRACK_ID,
                timing=Timing(
                    bar_index=output_bar_idx,
                    onset_ticks=0,
                    duration_ticks=3840,
                    ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                    notated_duration=NotatedDuration(value="whole", dots=0),
                ),
                is_rest=True,
                notes=[],
                confidence=1.0,
            )
            bars.append(
                Bar(
                    index=output_bar_idx,
                    time_signature=TimeSignature(numerator=4, denominator=4),
                    events=[rest_event],
                )
            )
            continue

        # Group by x-position
        x_groups = _candidate_x_groups(bar_frets, tolerance=PDF_ONLY_CHORD_X_TOLERANCE_PT)

        # Split duplicate strings to prevent false stacking
        id_to_cand = {c.id: c for c in bar_frets}
        event_subgroups = []
        for group_diag in x_groups:
            group_candidates = [id_to_cand[cid] for cid in group_diag.candidate_ids if cid in id_to_cand]
            if not group_candidates:
                continue
            split_groups = split_duplicate_strings(group_candidates)
            event_subgroups.extend(split_groups)

        N = len(event_subgroups)
        if N > 64:
            raise BuildIrInputRiskError(
                category="pdf_only_tab_grouping_unsafe",
                stage="layout-gating",
                message=f"PDF-only tab building refused: too many events ({N}) in bar {output_bar_idx}.",
            )

        if N <= 8:
            grid_spacing = 480
            duration_name = "eighth"
        elif N <= 16:
            grid_spacing = 240
            duration_name = "16th"
        elif N <= 32:
            grid_spacing = 120
            duration_name = "32nd"
        else:
            grid_spacing = 60
            duration_name = "64th"

        events = []
        for i, subgroup_candidates in enumerate(event_subgroups):
            onset_ticks = i * grid_spacing
            duration_ticks = grid_spacing if i < N - 1 else 3840 - onset_ticks

            notes = []
            for candidate in subgroup_candidates:
                base_pitch = _STRING_TO_BASE_PITCH.get(candidate.string, 40)
                pitch = base_pitch + (candidate.parsed_fret or 0)
                notes.append(
                    Note(
                        string=candidate.string,
                        fret=candidate.parsed_fret or 0,
                        pitch=pitch,
                        confidence=candidate.confidence,
                        provenance=[candidate.to_provenance()],
                    )
                )

            events.append(
                Event(
                    id=f"bar-{output_bar_idx}-event-{i+1}",
                    track_id=TRACK_ID,
                    timing=Timing(
                        bar_index=output_bar_idx,
                        onset_ticks=onset_ticks,
                        duration_ticks=duration_ticks,
                        ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                        notated_duration=NotatedDuration(value=duration_name, dots=0),
                    ),
                    notes=notes,
                    confidence=sum(c.confidence for c in subgroup_candidates) / len(subgroup_candidates),
                    provenance=[c.to_provenance() for c in subgroup_candidates],
                )
            )

        bars.append(
            Bar(
                index=output_bar_idx,
                time_signature=TimeSignature(numerator=4, denominator=4),
                events=events,
            )
        )

    # Create warnings and add timing inferred timing warning
    warnings_list = [
        WarningItem(
            code="pdf_only_tab_inferred_timing",
            message="Timing and rhythmic durations are approximate and inferred from PDF horizontal layout positioning, not source notation.",
            severity="warning",
        )
    ]

    for candidate in tabraw.candidates:
        if candidate.kind in ("chord-symbol", "technique-text"):
            warnings_list.append(
                WarningItem(
                    code=f"tabraw-{candidate.kind}-not-aligned",
                    message=f"Tab candidate '{candidate.raw_text}' of kind '{candidate.kind}' is not yet aligned to score timeline.",
                    severity="warning",
                    provenance=[candidate.to_provenance()],
                )
            )

    score = ScoreIR(
        metadata=Metadata(
            title="PDF-Only Inferred Score",
            composer="Unknown Composer",
            copyright="Unknown",
            source=str(tabraw_path),
        ),
        conversion=ConversionInfo(
            tool_name="score2gp",
            tool_version=__version__,
            conversion_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            source_file_hash=None,
        ),
        tempo=Tempo(bpm=tempo_bpm),
        tracks=[_standard_guitar_track()],
        bars=bars,
        warnings=warnings_list,
    )

    # Attach symbols and techniques
    _attach_symbols_and_techniques(score, tabraw)

    # Construct diagnostics
    tabraw_candidates_loaded = len(tabraw.candidates)
    tabraw_fret_candidate_count = len(fret_candidates)
    tabraw_chord_symbol_candidate_count = sum(1 for c in tabraw.candidates if c.kind == "chord-symbol")
    tabraw_technique_text_candidate_count = sum(1 for c in tabraw.candidates if c.kind == "technique-text")
    tabraw_unknown_candidate_count = sum(1 for c in tabraw.candidates if c.kind not in ("fret", "chord-symbol", "technique-text"))
    tabraw_non_fret_candidate_count = tabraw_candidates_loaded - tabraw_fret_candidate_count

    tabraw_candidates_with_bbox = sum(1 for c in tabraw.candidates if c.bbox is not None)
    tabraw_candidates_with_x = sum(1 for c in tabraw.candidates if c.x is not None)
    tabraw_candidates_with_y = sum(1 for c in tabraw.candidates if c.y is not None)
    tabraw_candidates_with_system = sum(1 for c in tabraw.candidates if c.system_index is not None)
    tabraw_candidates_with_string = sum(1 for c in tabraw.candidates if c.string is not None)
    tabraw_candidates_with_bar = sum(1 for c in tabraw.candidates if c.bar_index is not None)

    matched_candidates_set = {
        n.provenance[0].raw_token_id
        for b in bars
        for ev in b.events
        if not ev.is_rest
        for n in ev.notes
        if n.provenance and n.provenance[0].raw_token_id
    }
    matched_candidate_count = len(matched_candidates_set)
    unmatched_tabraw_candidate_count = tabraw_candidates_loaded - matched_candidate_count

    per_bar_diagnostics = []
    for b in bars:
        bar_idx = b.index
        bar_frets = output_bar_to_frets.get(bar_idx, [])
        if not bar_frets:
            per_bar_diagnostics.append(
                BarAlignmentDiagnostics(
                    bar_index=bar_idx,
                    musicxml_event_count=0,
                    musicxml_pitched_event_count=0,
                    musicxml_rest_event_count=0,
                    scoreir_event_count=len(b.events),
                    matched_candidate_count=0,
                    unmatched_musicxml_event_count=0,
                    unmatched_musicxml_note_count=0,
                    unmatched_tabraw_candidate_count=0,
                    chord_event_count=0,
                    playable_candidate_count=0,
                    playable_candidate_onset_group_count=0,
                )
            )
        else:
            bar_x_groups = _candidate_x_groups(bar_frets, tolerance=PDF_ONLY_CHORD_X_TOLERANCE_PT)
            per_bar_diagnostics.append(
                BarAlignmentDiagnostics(
                    bar_index=bar_idx,
                    musicxml_event_count=0,
                    musicxml_pitched_event_count=0,
                    musicxml_rest_event_count=0,
                    scoreir_event_count=len(b.events),
                    matched_candidate_count=sum(len(ev.notes) for ev in b.events if not ev.is_rest),
                    unmatched_musicxml_event_count=0,
                    unmatched_musicxml_note_count=0,
                    unmatched_tabraw_candidate_count=0,
                    chord_event_count=sum(1 for g in bar_x_groups if g.is_chord_stack),
                    playable_candidate_count=len(bar_frets),
                    playable_candidate_onset_group_count=len(bar_x_groups),
                    bar_x_min=min(c.x for c in bar_frets if c.x is not None),
                    bar_x_max=max(c.x for c in bar_frets if c.x is not None),
                    x_span=max(c.x for c in bar_frets if c.x is not None) - min(c.x for c in bar_frets if c.x is not None),
                    candidate_x_positions=sorted([c.x for c in bar_frets if c.x is not None]),
                    candidate_x_groups=bar_x_groups,
                    has_chord_stack=any(g.is_chord_stack for g in bar_x_groups),
                )
            )

    pdf_timing_mapping = {
        "contract_version": "pdf-timing-mapping.v0.7",
        "refinement_contract_version": PDF_TIMING_REFINEMENT_VERSION,
        "input_class": "drawn_tab_candidate",
        "grouping_status": "safe",
        "grouping_safe": True,
        "timing_source_safe": False,
        "musicxml_timing_preflight_status": "not-applicable",
        "whether_mapping_attempted": False,
        "whether_mapping_refused": False,
        "refusal_reason_codes": [],
        "mapping_quality_classification": "inferred",
        "refinement_reason_codes": [],
        "safe_layout_evidence": True,
        "partial_layout_evidence": False,
        "ambiguous_layout_evidence": False,
        "incompatible_layout_evidence": False,
        "quality": "inferred",
        "whether_scoreir_written": True,
        "remediation_hint": "Timing is layout-inferred. No timing source sidecar was provided.",
        "per_bar": [],
        "matched_x_onset_group_count": 0,
        "unmatched_x_group_count": 0,
        "unmatched_onset_group_count": 0,
        "mean_absolute_relative_error": None,
        "max_relative_error": None,
        "monotonic": None,
        "ambiguity_count": 0,
    }

    diagnostics = BuildIrDiagnostics(
        alignment_strategy="bar-x-order",
        musicxml_source="none",
        tabraw_source=str(tabraw_path),
        musicxml_events_imported=0,
        musicxml_pitched_events_imported=0,
        musicxml_rest_events_imported=0,
        tabraw_candidates_loaded=tabraw_candidates_loaded,
        tabraw_fret_candidate_count=tabraw_fret_candidate_count,
        tabraw_non_fret_candidate_count=tabraw_non_fret_candidate_count,
        tabraw_chord_symbol_candidate_count=tabraw_chord_symbol_candidate_count,
        tabraw_technique_text_candidate_count=tabraw_technique_text_candidate_count,
        tabraw_unknown_candidate_count=tabraw_unknown_candidate_count,
        tabraw_candidates_with_bbox=tabraw_candidates_with_bbox,
        tabraw_candidates_with_x=tabraw_candidates_with_x,
        tabraw_candidates_with_y=tabraw_candidates_with_y,
        tabraw_candidates_with_system=tabraw_candidates_with_system,
        tabraw_candidates_with_string=tabraw_candidates_with_string,
        tabraw_candidates_with_bar=tabraw_candidates_with_bar,
        matched_candidate_count=matched_candidate_count,
        unmatched_musicxml_event_count=0,
        unmatched_musicxml_note_count=0,
        unmatched_tabraw_candidate_count=unmatched_tabraw_candidate_count,
        ignored_non_playable_candidate_count=tabraw_non_fret_candidate_count,
        warning_count=len(score.warnings),
        warnings=[w.model_dump(mode="json", exclude_none=True) for w in score.warnings],
        per_bar=per_bar_diagnostics,
        pdf_timing_mapping=pdf_timing_mapping,
    )

    return score, diagnostics


def _synchronize_skipped_system_measures(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    skipped_systems: set[tuple[int, int]] | None = None,
) -> None:
    """Re-align remaining candidates to MusicXML measures if there is a system-skipping gap."""
    if not musicxml.parts or not tabraw.candidates:
        return

    skipped = skipped_systems or set()

    # 1. Group all candidates by system
    system_candidates = defaultdict(list)
    for c in tabraw.candidates:
        if c.page_index is not None and c.system_index is not None:
            system_candidates[(c.page_index, c.system_index)].append(c)

    if not system_candidates:
        return

    # 2. Sort all systems visually
    all_systems = sorted(system_candidates.keys() | skipped, key=lambda sys: (sys[0], sys[1]))
    active_systems = sorted(system_candidates.keys(), key=lambda sys: (sys[0], sys[1]))

    # 3. Precompute system attributes and local bars
    tuning = _standard_guitar_tuning()
    system_len_seq = []
    orig_min_bar_seq = []
    local_bars_seq = []

    for sys_key in active_systems:
        cands = system_candidates[sys_key]
        bar_indices = {c.bar_index for c in cands if c.bar_index is not None}
        if not bar_indices:
            orig_min_bar = 1
            system_len = 1
        else:
            orig_min_bar = min(bar_indices)
            orig_max_bar = max(bar_indices)
            system_len = orig_max_bar - orig_min_bar + 1

        orig_min_bar_seq.append(orig_min_bar)
        system_len_seq.append(system_len)

        # Group cands in system by local bar index relative to orig_min_bar
        local_bars = [[] for _ in range(system_len)]
        for c in cands:
            if c.bar_index is not None:
                idx = c.bar_index - orig_min_bar
                if 0 <= idx < system_len:
                    local_bars[idx].append(c)
        local_bars_seq.append(local_bars)

    # 4. Get MusicXML measures and their pitches
    part = musicxml.parts[0]
    xml_measures = part.measures
    total_xml_measures = len(xml_measures)

    xml_measure_notes = {}
    xml_measure_pitches = {}
    for measure in xml_measures:
        notes = [note for note in measure.notes if not note.is_rest and note.pitch is not None]
        xml_measure_notes[measure.index] = notes
        xml_measure_pitches[measure.index] = [note.pitch.midi for note in notes]

    # 5. Define BarScore and System-to-Measure Window Score
    from collections import Counter

    def get_bar_score(bar_cands: list, xml_notes: list) -> float:
        cand_pitches = []
        for c in bar_cands:
            if c.string is not None and c.parsed_fret is not None:
                open_pitch = tuning.pitch_for_string(c.string)
                if open_pitch is not None:
                    cand_pitches.append(open_pitch + c.parsed_fret)

        xml_pitches = [n.pitch.midi for n in xml_notes]
        if not cand_pitches and not xml_pitches:
            return 0.0

        cand_counter = Counter(cand_pitches)
        xml_sounding_1 = [p - 12 for p in xml_pitches]
        xml_sounding_2 = xml_pitches

        c_xml_1 = Counter(xml_sounding_1)
        c_xml_2 = Counter(xml_sounding_2)

        matches_transposed = sum((cand_counter & c_xml_1).values())
        matches_non_transposed = sum((cand_counter & c_xml_2).values())
        exact_midi_matches = max(matches_transposed, matches_non_transposed)

        cand_classes = [p % 12 for p in cand_pitches]
        xml_classes = [p % 12 for p in xml_pitches]
        pitch_class_matches = sum((Counter(cand_classes) & Counter(xml_classes)).values())

        event_count_match = 1.0 if len(cand_pitches) == len(xml_pitches) and len(cand_pitches) > 0 else 0.0
        unmatched_visual = max(0, len(cand_pitches) - exact_midi_matches)
        unmatched_xml = max(0, len(xml_pitches) - exact_midi_matches)

        return 2.0 * exact_midi_matches + 1.0 * pitch_class_matches + 1.0 * event_count_match - 1.0 * unmatched_visual - 1.0 * unmatched_xml

    N = len(active_systems)
    system_scores = [{} for _ in range(N)]
    for i in range(N):
        sys_len = system_len_seq[i]
        for m in range(1, total_xml_measures - sys_len + 2):
            score = 0.0
            for j in range(sys_len):
                score += get_bar_score(local_bars_seq[i][j], xml_measure_notes.get(m + j, []))
            system_scores[i][m] = score

    # 6. Global Dynamic Programming over system sequence
    dp = [[-float('inf')] * (total_xml_measures + 1) for _ in range(N)]
    backtrack = [[-1] * (total_xml_measures + 1) for _ in range(N)]
    gap_penalty = 3.0
    overlap_penalty = 100.0

    # Initialize DP for system 0
    sys_len_0 = system_len_seq[0]
    for m in range(1, total_xml_measures - sys_len_0 + 2):
        if m in system_scores[0]:
            dp[0][m] = system_scores[0][m] - (m - 1) * gap_penalty

    # DP transition
    for i in range(1, N):
        sys_len = system_len_seq[i]
        prev_len = system_len_seq[i - 1]
        for m in range(1, total_xml_measures - sys_len + 2):
            if m not in system_scores[i]:
                continue
            best_val = -float('inf')
            best_prev = -1
            for prev_m in range(1, total_xml_measures - prev_len + 2):
                if dp[i - 1][prev_m] == -float('inf'):
                    continue
                prev_end = prev_m + prev_len
                skipped_count = m - prev_end
                if skipped_count >= 0:
                    penalty = gap_penalty * skipped_count
                else:
                    penalty = overlap_penalty * (-skipped_count)
                val = dp[i - 1][prev_m] - penalty
                if val > best_val:
                    best_val = val
                    best_prev = prev_m
            if best_prev != -1:
                dp[i][m] = system_scores[i][m] + best_val
                backtrack[i][m] = best_prev

    # Find the optimal ending starting measure
    best_m = -1
    best_score = -float('inf')
    last_len = system_len_seq[N - 1]
    for m in range(1, total_xml_measures - last_len + 2):
        if dp[N - 1][m] > best_score:
            best_score = dp[N - 1][m]
            best_m = m

    # 7. Apply optimal sequence alignments if valid
    if best_m != -1 and best_score > -float('inf'):
        m_seq = [0] * N
        curr_m = best_m
        for i in range(N - 1, -1, -1):
            m_seq[i] = curr_m
            curr_m = backtrack[i][curr_m]

        for i in range(N):
            sys_key = active_systems[i]
            cands = system_candidates[sys_key]
            offset = m_seq[i] - orig_min_bar_seq[i]
            for c in cands:
                if c.bar_index is not None:
                    c.bar_index += offset

        # 8. Identify skipped measures as intentional alignment gaps
        aligned_measures = set()
        for i in range(N):
            start_m = m_seq[i]
            for offset_bar in range(system_len_seq[i]):
                aligned_measures.add(start_m + offset_bar)

        if aligned_measures:
            last_measure = max(aligned_measures)
            for m in range(1, last_measure + 1):
                if m not in aligned_measures:
                    tabraw.warnings.append({
                        "code": "pdf_system_alignment_gap",
                        "message": f"MusicXML measure {m} was skipped as an intentional alignment gap."
                    })
    else:
        # 9. Contiguous Greedy Alignment Fallback
        expected_next_measure = 1
        after_skipped_gap = False
        system_pitches = {}
        for sys_key in system_candidates:
            cands = system_candidates[sys_key]
            pitches = []
            for c in cands:
                if c.string is not None and c.parsed_fret is not None:
                    open_pitch = tuning.pitch_for_string(c.string)
                    if open_pitch is not None:
                        pitches.append(open_pitch + c.parsed_fret)
            system_pitches[sys_key] = pitches

        for sys_key in all_systems:
            if sys_key in skipped:
                after_skipped_gap = True
                continue

            cands = system_candidates[sys_key]
            bar_indices = {c.bar_index for c in cands if c.bar_index is not None}
            if not bar_indices:
                continue
            orig_min_bar = min(bar_indices)
            orig_max_bar = max(bar_indices)
            system_len = orig_max_bar - orig_min_bar + 1

            if expected_next_measure == 1:
                best_measure_start = 1
                after_skipped_gap = False
            elif not after_skipped_gap:
                best_measure_start = expected_next_measure
            else:
                cand_pitches = system_pitches[sys_key]
                best_measure_start = expected_next_measure
                best_score = -1.0
                max_start = total_xml_measures - system_len + 1
                if max_start >= expected_next_measure:
                    for m in range(expected_next_measure, max_start + 1):
                        block_pitches = []
                        for idx in range(m, m + system_len):
                            block_pitches.extend(xml_measure_pitches.get(idx, []))
                        matches = 0
                        if cand_pitches and block_pitches:
                            cand_classes = [p % 12 for p in cand_pitches]
                            block_classes = [p % 12 for p in block_pitches]
                            c_cand = Counter(cand_classes)
                            c_xml = Counter(block_classes)
                            matches = sum((c_cand & c_xml).values())
                        score = float(matches)
                        if score > best_score:
                            best_score = score
                            best_measure_start = m
                after_skipped_gap = False

            offset = best_measure_start - orig_min_bar
            for c in cands:
                if c.bar_index is not None:
                    c.bar_index += offset
            expected_next_measure = best_measure_start + system_len



def _find_host_note(grace_note: MusicXmlNote, notes: list[MusicXmlNote]) -> MusicXmlNote | None:
    try:
        idx = notes.index(grace_note)
    except ValueError:
        return None
    for i in range(idx + 1, len(notes)):
        n = notes[i]
        if n.voice == grace_note.voice and not n.grace and not n.is_rest and not n.is_suppressed:
            return n
    return None



def _measure_events(
    measure: MusicXmlMeasure,
    candidate_pools: "CandidatePools",
    warnings: list[WarningItem],
) -> list[Event]:
    events: list[Event] = []
    harmony_by_onset = _harmony_by_onset(measure)
    used_harmony_onsets: set[int] = set()

    for group_index, group in enumerate(_note_groups(measure.notes), start=1):
        first = group[0]
        if first.grace:
            host_note = _find_host_note(first, measure.notes)
            if host_note is None:
                warnings.append(_event_warning("musicxml-grace-skipped", first, "Grace note is skipped: no host note found in measure/voice context."))
                continue
            duration_ticks = 0
            onset_ticks, onset_exact = host_note.onset_ticks(measure.divisions)
            if not onset_exact:
                warnings.append(
                    _event_warning(
                        "musicxml-non-integer-onset",
                        first,
                        "MusicXML grace note onset did not map to an integer ScoreIR tick value and was truncated.",
                    )
                )
        else:
            duration_ticks, exact = first.duration_ticks(measure.divisions)
            if duration_ticks <= 0:
                warnings.append(_event_warning("musicxml-zero-duration-skipped", first, "Zero-duration note/rest is skipped."))
                continue
            if not exact:
                warnings.append(
                    _event_warning(
                        "musicxml-non-integer-duration",
                        first,
                        "MusicXML duration did not map to an integer ScoreIR tick value and was truncated.",
                    )
                )

            onset_ticks, onset_exact = first.onset_ticks(measure.divisions)
            if not onset_exact:
                warnings.append(
                    _event_warning(
                        "musicxml-non-integer-onset",
                        first,
                        "MusicXML onset did not map to an integer ScoreIR tick value and was truncated.",
                    )
                )

        timing = _timing(first, measure, duration_ticks, onset_ticks)
        event_id = f"mx-m{measure.index}-e{group_index}"
        chord_symbol = harmony_by_onset.get(first.onset_divisions)
        if chord_symbol is not None:
            used_harmony_onsets.add(first.onset_divisions)
        if first.is_rest:
            events.append(
                Event(
                    id=event_id,
                    track_id=TRACK_ID,
                    timing=timing,
                    is_rest=True,
                    chord_symbol=chord_symbol,
                    confidence=0.9,
                    provenance=[_musicxml_provenance(first, measure)],
                )
            )
            continue

        notes: list[Note] = []
        for xml_note in group:
            if xml_note.pitch is None:
                warnings.append(_event_warning("musicxml-pitch-missing", xml_note, "Pitched note is missing pitch data."))
                continue
            candidate = candidate_pools.pop(measure.index, event_id=event_id, musicxml_note_id=xml_note.id)
            if candidate is None:
                warnings.append(
                    _event_warning(
                        "tab-candidate-missing",
                        xml_note,
                        "No TabRaw fret/string candidate was available for this MusicXML note.",
                    )
                )
                continue
            note = _aligned_note(xml_note, candidate, measure, warnings)
            if note is not None:
                notes.append(note)

        if notes:
            events.append(
                Event(
                    id=event_id,
                    track_id=TRACK_ID,
                    timing=timing,
                    notes=notes,
                    chord_symbol=chord_symbol,
                    techniques=_event_techniques(group),
                    confidence=min(note.confidence for note in notes),
                    provenance=[_musicxml_provenance(first, measure), *[note.provenance[-1] for note in notes]],
                )
            )
        else:
            warnings.append(
                _event_warning(
                    "scoreir-event-skipped",
                    first,
                    "MusicXML note group could not produce a valid ScoreIR event without aligned tab evidence.",
                )
            )

    for harmony in measure.harmonies:
        if harmony.onset_divisions not in used_harmony_onsets:
            warnings.append(_harmony_warning(harmony, "MusicXML harmony could not be attached to a timed event."))

    return sorted(events, key=lambda event: (event.timing.onset_ticks, event.timing.voice, event.id))


def _aligned_note(
    xml_note: MusicXmlNote,
    candidate: TabCandidate,
    measure: MusicXmlMeasure,
    warnings: list[WarningItem],
) -> Note | None:
    if candidate.string is None or candidate.parsed_fret is None:
        warnings.append(
            _event_warning(
                "tab-candidate-incomplete",
                xml_note,
                f"TabRaw candidate '{candidate.id}' lacks a string or parsed fret value.",
                candidate,
            )
        )
        return None

    tuning = _standard_guitar_tuning()
    open_pitch = tuning.pitch_for_string(candidate.string)
    if open_pitch is None:
        warnings.append(
            _event_warning(
                "tab-candidate-invalid-string",
                xml_note,
                f"TabRaw candidate '{candidate.id}' uses string {candidate.string}, which is outside the default tuning.",
                candidate,
            )
        )
        return None

    candidate_pitch = open_pitch + candidate.parsed_fret
    confidence = min(0.9, candidate.confidence)
    if xml_note.pitch is not None and candidate_pitch != xml_note.pitch.midi:
        xml_pitch_val = xml_note.pitch.midi
        pitch_diff = xml_pitch_val - candidate_pitch
        if pitch_diff % 12 == 0:
            warnings.append(
                _event_warning(
                    "musicxml-transposition-corrected",
                    xml_note,
                    (
                        f"MusicXML written pitch {xml_note.pitch.name} ({xml_pitch_val}) was transposed "
                        f"by {-pitch_diff} semitones to align with sounding pitch ({candidate_pitch}) "
                        f"on string {candidate.string} fret {candidate.parsed_fret}."
                    ),
                    candidate,
                )
            )
        else:
            warnings.append(
                _event_warning(
                    "musicxml-tab-pitch-mismatch",
                    xml_note,
                    (
                        f"MusicXML pitch {xml_note.pitch.name} ({xml_note.pitch.midi}) does not match "
                        f"TabRaw string {candidate.string} fret {candidate.parsed_fret} ({candidate_pitch}); "
                        "ScoreIR keeps the tab-derived pitch so validation remains strict."
                    ),
                    candidate,
                )
            )
            confidence = min(confidence, 0.5)

    tab_provenance = candidate.to_provenance()
    tab_provenance.raw["alignment_strategy"] = candidate.raw.get("alignment_strategy", "bar-x-order")
    tab_provenance.raw["candidate_pitch"] = candidate_pitch
    tab_provenance.raw["musicxml_pitch"] = xml_note.pitch.midi if xml_note.pitch is not None else None
    tab_provenance.raw["pitch_matched"] = xml_note.pitch is None or candidate_pitch == xml_note.pitch.midi

    provenance = [_musicxml_provenance(xml_note, measure)]
    if xml_note.dedup_tab_note_id is not None:
        from .musicxml import MusicXmlNote
        temp_note = MusicXmlNote(
            id=xml_note.dedup_tab_note_id,
            part_id=xml_note.part_id,
            measure_index=xml_note.measure_index,
            measure_number=xml_note.measure_number,
            note_index=xml_note.note_index,
            onset_divisions=xml_note.onset_divisions,
            duration_divisions=xml_note.duration_divisions,
            voice=xml_note.dedup_tab_note_voice or 5,
            staff=xml_note.dedup_tab_note_staff,
            techniques=xml_note.dedup_tab_note_techniques or [],
            source_path=xml_note.dedup_tab_note_source_path or xml_note.source_path,
            grace=xml_note.grace,
            grace_slash=getattr(xml_note, "grace_slash", False),
        )
        provenance.append(_musicxml_provenance(temp_note, measure))
    provenance.append(tab_provenance)

    techniques = _note_techniques(xml_note)
    if xml_note.grace:
        grace_timing = GraceTiming(
            position="before",
            slash=getattr(xml_note, "grace_slash", False),
            duration_ticks=0,
            duration=xml_note.notated_type,
        )
        techniques.append(
            GraceTechnique(
                kind="grace",
                slash=getattr(xml_note, "grace_slash", False),
                timing=grace_timing,
            )
        )

    return Note(
        string=candidate.string,
        fret=candidate.parsed_fret,
        pitch=candidate_pitch,
        techniques=techniques,
        confidence=confidence,
        provenance=provenance,
    )


def _note_groups(notes: Iterable[MusicXmlNote]) -> list[list[MusicXmlNote]]:
    groups: dict[tuple[int, int, int, bool], list[MusicXmlNote]] = defaultdict(list)
    for note in notes:
        key = (note.onset_divisions, note.voice, note.duration_divisions, note.is_rest)
        groups[key].append(note)
    return [
        group
        for _, group in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1], item[0][2], item[1][0].note_index))
    ]


@dataclass
class CandidateUse:
    candidate: TabCandidate
    requested_bar_index: int
    source_pool_bar_index: int | None
    event_id: str
    musicxml_note_id: str


@dataclass
class CandidatePools:
    pools: dict[int | None, list[TabCandidate]]
    consumed: list[CandidateUse] = field(default_factory=list)

    @classmethod
    def from_tabraw(cls, tabraw: TabRaw) -> "CandidatePools":
        pools: dict[int | None, list[TabCandidate]] = defaultdict(list)
        for candidate in tabraw.candidates:
            if candidate.parsed_fret is not None:
                pools[candidate.bar_index].append(candidate)
        for pool in pools.values():
            pool.sort(key=_candidate_pool_sort_key)
        return cls(pools=dict(pools))

    def pop(self, bar_index: int, *, event_id: str, musicxml_note_id: str) -> TabCandidate | None:
        pool = self.pools.get(bar_index)
        if pool:
            candidate = pool.pop(0)
            self.consumed.append(
                CandidateUse(
                    candidate=candidate,
                    requested_bar_index=bar_index,
                    source_pool_bar_index=bar_index,
                    event_id=event_id,
                    musicxml_note_id=musicxml_note_id,
                )
            )
            return candidate
        return None

    def unused(self) -> list[TabCandidate]:
        return [candidate for pool in self.pools.values() for candidate in pool]

    def consumed_in_bar(self, bar_index: int) -> list[CandidateUse]:
        return [use for use in self.consumed if use.requested_bar_index == bar_index]


def _candidate_pool_sort_key(candidate: TabCandidate) -> tuple[float, str]:
    ascii_onset = _raw_float(candidate.raw.get("aligned_musicxml_onset_ticks")) if isinstance(candidate.raw, dict) else None
    if ascii_onset is not None:
        return ascii_onset, candidate.id
    return float("inf") if candidate.x is None else candidate.x, candidate.id


def _timing(note: MusicXmlNote, measure: MusicXmlMeasure, duration_ticks: int, onset_ticks: int) -> Timing:
    grace_timing = None
    if note.grace:
        grace_timing = GraceTiming(
            position="before",
            slash=getattr(note, "grace_slash", False),
            duration_ticks=0,
            duration=note.notated_type,
        )
    return Timing(
        bar_index=measure.index,
        onset_ticks=onset_ticks,
        duration_ticks=duration_ticks,
        ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
        voice=note.voice,
        notated_duration=_notated_duration(note),
        tuplet=Tuplet(actual_notes=note.tuplet.actual_notes, normal_notes=note.tuplet.normal_notes)
        if note.tuplet is not None
        else None,
        grace=grace_timing,
    )


def _notated_duration(note: MusicXmlNote) -> NotatedDuration | None:
    if note.notated_type is None:
        return None
    mapping = {
        "whole": "whole",
        "half": "half",
        "quarter": "quarter",
        "eighth": "eighth",
        "16th": "16th",
        "32nd": "32nd",
        "64th": "64th",
        "128th": "128th",
    }
    value = mapping.get(note.notated_type)
    if value is None:
        return None
    return NotatedDuration(value=value, dots=note.dots)


def _harmony_by_onset(measure: MusicXmlMeasure) -> dict[int, str]:
    return {harmony.onset_divisions: harmony.text for harmony in measure.harmonies}


def _event_techniques(group: list[MusicXmlNote]) -> list[Technique]:
    # The current ScoreIR writer handles common guitar markings on notes. Keep
    # event-level techniques empty until we need an event-wide construct.
    return []


def _note_techniques(note: MusicXmlNote) -> list[Technique]:
    techniques = _tie_techniques(note)
    for technique in note.techniques:
        converted = _scoreir_technique(technique)
        if converted is not None:
            techniques.append(converted)
    return techniques


def _tie_techniques(note: MusicXmlNote) -> list[Technique]:
    if "start" in note.ties and "stop" in note.ties:
        return [{"kind": "tie", "state": "continue"}]  # type: ignore[return-value]
    if "start" in note.ties:
        return [{"kind": "tie", "state": "start"}]  # type: ignore[return-value]
    if "stop" in note.ties:
        return [{"kind": "tie", "state": "stop"}]  # type: ignore[return-value]
    return []


def _scoreir_technique(technique: MusicXmlTechnique) -> Technique | None:
    state = technique.state if technique.state in {"start", "stop", "continue"} else "start"
    if technique.kind == "slide":
        return {"kind": "slide", "style": "unknown", "direction": "unknown"}  # type: ignore[return-value]
    if technique.kind == "bend":
        return {
            "kind": "bend",
            "semitones": technique.semitones,
            "text": technique.text,
        }  # type: ignore[return-value]
    if technique.kind == "vibrato":
        return {"kind": "vibrato", "width": "unknown", "speed": "unknown"}  # type: ignore[return-value]
    if technique.kind == "hammer-on":
        return {"kind": "hammer-on"}  # type: ignore[return-value]
    if technique.kind == "pull-off":
        return {"kind": "pull-off"}  # type: ignore[return-value]
    if technique.kind == "slur":
        return {"kind": "slur", "state": state}  # type: ignore[return-value]
    if technique.kind == "unsupported":
        return {
            "kind": "unsupported",
            "label": technique.text or "MusicXML technical notation",
            "reason": "MusicXML importer preserved this notation but build-ir does not map it yet.",
            "raw": {"source_path": technique.source_path},
        }  # type: ignore[return-value]
    return None


def _musicxml_warnings(musicxml: MusicXmlImport) -> list[WarningItem]:
    return [
        WarningItem(
            code=warning.code,
            message=warning.message,
            severity=warning.severity,
            provenance=[
                Provenance(
                    source_stage=SourceStage.MUSICXML,
                    raw={"source_path": warning.source_path} if warning.source_path else {},
                    confidence=1.0,
                )
            ],
        )
        for warning in musicxml.warnings
    ]


def _musicxml_timing_issue_warnings(issues: list[MusicXmlTimingIssue]) -> list[WarningItem]:
    return [
        WarningItem(
            code=issue.code,
            message=issue.message,
            severity=issue.severity,
            provenance=[
                Provenance(
                    source_stage=SourceStage.MUSICXML,
                    bar_index=issue.measure_index,
                    raw_token_id=issue.musicxml_note_id,
                    raw={
                        "source_path": issue.source_path,
                        "measure_number": issue.measure_number,
                        "voice": issue.voice,
                        "expected_duration_divisions": issue.expected_duration_divisions,
                        "onset_divisions": issue.onset_divisions,
                        "duration_divisions": issue.duration_divisions,
                        "end_divisions": issue.end_divisions,
                    },
                    confidence=1.0,
                )
            ],
        )
        for issue in issues
    ]


def _tabraw_warnings(tabraw: TabRaw) -> list[WarningItem]:
    warnings: list[WarningItem] = []
    for raw_warning in tabraw.warnings:
        warnings.append(
            WarningItem(
                code=str(raw_warning.get("code", "tabraw-warning")),
                message=str(raw_warning.get("message", "TabRaw warning without message.")),
                severity=raw_warning.get("severity", "warning")
                if raw_warning.get("severity") in {"info", "warning", "error"}
                else "warning",
            )
        )

    for candidate in tabraw.candidates:
        if candidate.parsed_fret is None:
            warnings.append(
                WarningItem(
                    code=f"tabraw-{candidate.kind}-not-aligned",
                    message=(
                        f"TabRaw candidate '{candidate.id}' ({candidate.kind}) is preserved "
                        "but not aligned by this build-ir phase."
                    ),
                    severity="info",
                    provenance=[candidate.to_provenance()],
                )
            )
    return warnings


def _unused_candidate_warnings(candidate_pools: CandidatePools) -> list[WarningItem]:
    return [
        WarningItem(
            code="tab-candidate-unused",
            message=f"TabRaw candidate '{candidate.id}' was not consumed by MusicXML alignment.",
            severity="warning",
            provenance=[candidate.to_provenance()],
        )
        for candidate in candidate_pools.unused()
    ]


def _build_diagnostics(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    score: ScoreIR,
    candidate_pools: CandidatePools,
    *,
    ascii_gate_details: dict[str, object] | None = None,
) -> BuildIrDiagnostics:
    per_bar = []
    first_part = musicxml.parts[0] if musicxml.parts else None
    warnings = score.warnings
    warning_codes = [warning.code for warning in warnings]
    for bar in score.bars:
        measure = _measure_for_bar(first_part, bar.index)
        musicxml_groups = _diagnostic_groups(measure.notes) if measure is not None else []
        bar_warnings = [warning for warning in warnings if _warning_bar_index(warning) == bar.index]
        event_confidences = [event.confidence for event in bar.events]
        ambiguity_flags = _bar_ambiguity_flags(bar.index, candidate_pools)
        x_to_onset = _bar_x_to_onset_diagnostics(bar.index, measure, musicxml_groups, tabraw)
        per_bar.append(
            BarAlignmentDiagnostics(
                bar_index=bar.index,
                system_index=x_to_onset["system_index"],
                musicxml_event_count=len(musicxml_groups),
                musicxml_pitched_event_count=sum(1 for group in musicxml_groups if not group[0].is_rest),
                musicxml_rest_event_count=sum(1 for group in musicxml_groups if group[0].is_rest),
                scoreir_event_count=len(bar.events),
                matched_candidate_count=len(candidate_pools.consumed_in_bar(bar.index)),
                unmatched_musicxml_event_count=sum(1 for warning in bar_warnings if warning.code == "scoreir-event-skipped"),
                unmatched_musicxml_note_count=sum(1 for warning in bar_warnings if warning.code == "tab-candidate-missing"),
                unmatched_tabraw_candidate_count=sum(1 for candidate in candidate_pools.unused() if candidate.bar_index == bar.index),
                chord_event_count=sum(1 for group in musicxml_groups if len(group) > 1),
                playable_candidate_count=x_to_onset["playable_candidate_count"],
                playable_candidate_onset_group_count=x_to_onset["playable_candidate_onset_group_count"],
                musicxml_pitched_onset_group_count=x_to_onset["musicxml_pitched_onset_group_count"],
                bar_x_min=x_to_onset["bar_x_min"],
                bar_x_max=x_to_onset["bar_x_max"],
                x_span=x_to_onset["x_span"],
                onset_tick_min=x_to_onset["onset_tick_min"],
                onset_tick_max=x_to_onset["onset_tick_max"],
                candidate_x_positions=x_to_onset["candidate_x_positions"],
                candidate_x_groups=x_to_onset["candidate_x_groups"],
                musicxml_onsets=x_to_onset["musicxml_onsets"],
                musicxml_onset_groups=x_to_onset["musicxml_onset_groups"],
                relative_x_positions=x_to_onset["relative_x_positions"],
                relative_onsets=x_to_onset["relative_onsets"],
                mean_absolute_relative_error=x_to_onset["mean_absolute_relative_error"],
                max_relative_error=x_to_onset["max_relative_error"],
                monotonic_x=x_to_onset["monotonic_x"],
                has_chord_stack=x_to_onset["has_chord_stack"],
                ambiguous_x_group_count=x_to_onset["ambiguous_x_group_count"],
                quality=x_to_onset["quality"],
                x_to_onset_warnings=x_to_onset["x_to_onset_warnings"],
                average_event_confidence=round(sum(event_confidences) / len(event_confidences), 3) if event_confidences else None,
                ambiguity_flags=ambiguity_flags + x_to_onset["x_to_onset_warnings"],
            )
        )

    totals = _diagnostic_totals(per_bar)
    confidence_flags = [
        {
            "event_id": event.id,
            "bar_index": event.timing.bar_index,
            "confidence": event.confidence,
            "reason": "event confidence below 0.75",
        }
        for bar in score.bars
        for event in bar.events
        if event.confidence < 0.75
    ]

    chord_cands = [c for c in tabraw.candidates if c.kind == "chord-symbol"]
    tech_cands = [c for c in tabraw.candidates if c.kind == "technique-text"]

    attached_chord_ids = set()
    for bar in score.bars:
        for event in bar.events:
            for prov in event.provenance:
                if prov.raw_token_id:
                    attached_chord_ids.add(prov.raw_token_id)

    attached_tech_ids = set()
    for bar in score.bars:
        for event in bar.events:
            for note in event.notes:
                for prov in note.provenance:
                    if prov.raw_token_id:
                        attached_tech_ids.add(prov.raw_token_id)

    chord_found = len(chord_cands)
    chord_attached = sum(1 for c in chord_cands if c.id in attached_chord_ids)
    chord_unattached = chord_found - chord_attached

    tech_found = len(tech_cands)
    tech_attached = sum(1 for c in tech_cands if c.id in attached_tech_ids)
    tech_unattached = tech_found - tech_attached

    # Computations for pdf_timing_mapping
    matched_x_onset_group_count = 0
    unmatched_x_group_count = 0
    unmatched_onset_group_count = 0
    total_bar_relative_errors = []
    max_relative_error = None
    all_monotonic = True
    total_ambiguity_count = 0
    refusal_reason_codes = []
    has_chord_stack = False

    per_bar_mapping = []
    for diag in per_bar:
        x_len = len(diag.candidate_x_groups)
        onset_len = len(diag.musicxml_onset_groups)
        matched = min(x_len, onset_len)
        matched_x_onset_group_count += matched
        unmatched_x_group_count += max(0, x_len - onset_len)
        unmatched_onset_group_count += max(0, onset_len - x_len)

        if diag.mean_absolute_relative_error is not None:
            total_bar_relative_errors.append(diag.mean_absolute_relative_error)
        if diag.max_relative_error is not None:
            if max_relative_error is None or diag.max_relative_error > max_relative_error:
                max_relative_error = diag.max_relative_error

        if diag.monotonic_x is False:
            all_monotonic = False

        total_ambiguity_count += diag.ambiguous_x_group_count
        if diag.has_chord_stack:
            has_chord_stack = True

        per_bar_mapping.append({
            "bar_index": diag.bar_index,
            "playable_candidate_count": diag.playable_candidate_count,
            "musicxml_pitched_onset_group_count": diag.musicxml_pitched_onset_group_count,
            "candidate_x_groups": [g.model_dump() if hasattr(g, "model_dump") else g for g in diag.candidate_x_groups],
            "musicxml_onset_groups": [g.model_dump() if hasattr(g, "model_dump") else g for g in diag.musicxml_onset_groups],
            "mean_absolute_relative_error": diag.mean_absolute_relative_error,
            "max_relative_error": diag.max_relative_error,
            "monotonic": diag.monotonic_x,
            "ambiguity_count": diag.ambiguous_x_group_count,
            "warnings": diag.x_to_onset_warnings,
            "quality": diag.quality,
        })

    total_playable_count = sum(diag.playable_candidate_count for diag in per_bar)

    overall_quality = "good"
    if total_playable_count == 0:
        overall_quality = "unknown"
        refusal_reason_codes.append("pdf_timing_mapping_quality_unknown")
    else:
        if unmatched_x_group_count > 0:
            refusal_reason_codes.append("pdf_timing_mapping_x_group_unmatched")
            overall_quality = "warning"
        if unmatched_onset_group_count > 0:
            refusal_reason_codes.append("pdf_timing_mapping_onset_group_unmatched")
            overall_quality = "warning"
        if matched_x_onset_group_count == 0:
            overall_quality = "poor"
            refusal_reason_codes.append("pdf_timing_mapping_not_enough_for_build_ir")
        if all_monotonic is False:
            overall_quality = "poor"
            refusal_reason_codes.append("pdf_timing_mapping_non_monotonic")
        if max_relative_error is not None:
            if max_relative_error > 0.3:
                overall_quality = "poor"
                refusal_reason_codes.append("pdf_timing_mapping_quality_poor")
            elif max_relative_error > 0.15:
                if overall_quality != "poor":
                    overall_quality = "warning"
                refusal_reason_codes.append("pdf_timing_mapping_quality_warning")
        if total_ambiguity_count > 0:
            if overall_quality != "poor":
                overall_quality = "warning"
            refusal_reason_codes.append("pdf_timing_mapping_ambiguous_x_group")
        if has_chord_stack:
            refusal_reason_codes.append("pdf_timing_mapping_chord_stack_requires_review")

        if overall_quality == "good":
            refusal_reason_codes.append("pdf_timing_mapping_quality_good")
        elif overall_quality == "poor":
            refusal_reason_codes.append("pdf_timing_mapping_refused")

    whether_mapping_refused = (overall_quality == "poor" or all_monotonic is False)
    mapping_quality_classification, refinement_reason_codes = _pdf_timing_refinement_classification(
        total_playable_count=total_playable_count,
        matched_x_onset_group_count=matched_x_onset_group_count,
        unmatched_x_group_count=unmatched_x_group_count,
        unmatched_onset_group_count=unmatched_onset_group_count,
        total_ambiguity_count=total_ambiguity_count,
        overall_quality=overall_quality,
        all_monotonic=all_monotonic,
    )

    tabraw_warning_codes = {str(w.get("code", "")) for w in tabraw.warnings} if hasattr(tabraw, "warnings") and tabraw.warnings else set()
    fallback_used_codes = {
        "pdf_bar_box_inferred_edge_boundary",
        "pdf_bar_box_inferred_left_boundary",
        "pdf_bar_box_inferred_right_boundary",
        "pdf_bar_box_edge_boundary_fallback_used",
    }
    grouping_status = "recovered" if tabraw_warning_codes.intersection(fallback_used_codes) else "grouped"

    pdf_timing_mapping_dict = {
        "contract_version": "pdf-timing-mapping.v0.7",
        "refinement_contract_version": PDF_TIMING_REFINEMENT_VERSION,
        "input_class": getattr(tabraw, "input_class", "drawn_tab_candidate"),
        "grouping_status": grouping_status,
        "grouping_safe": True,
        "timing_source_safe": True,
        "musicxml_timing_preflight_status": "safe",
        "whether_mapping_attempted": True,
        "whether_mapping_refused": whether_mapping_refused,
        "refusal_reason_codes": sorted(list(set(refusal_reason_codes))),
        "mapping_quality_classification": mapping_quality_classification,
        "refinement_reason_codes": sorted(list(set(refinement_reason_codes))),
        "safe_layout_evidence": mapping_quality_classification == "safe",
        "partial_layout_evidence": mapping_quality_classification == "partial",
        "ambiguous_layout_evidence": mapping_quality_classification == "ambiguous",
        "incompatible_layout_evidence": mapping_quality_classification == "incompatible",
        "quality": overall_quality,
        "whether_scoreir_written": not whether_mapping_refused,
        "remediation_hint": "Timing mapping is diagnostic evidence only; do not repair or infer missing timing from PDF x positions.",
        "per_bar": per_bar_mapping,
        "matched_x_onset_group_count": matched_x_onset_group_count,
        "unmatched_x_group_count": unmatched_x_group_count,
        "unmatched_onset_group_count": unmatched_onset_group_count,
        "mean_absolute_relative_error": round(sum(total_bar_relative_errors) / len(total_bar_relative_errors), 3) if total_bar_relative_errors else None,
        "max_relative_error": max_relative_error,
        "monotonic": all_monotonic if per_bar else None,
        "ambiguity_count": total_ambiguity_count,
    }

    return BuildIrDiagnostics(
        musicxml_source=musicxml.source_path,
        tabraw_source=tabraw.source_pdf,
        musicxml_events_imported=totals["musicxml_event_count"],
        musicxml_pitched_events_imported=totals["musicxml_pitched_event_count"],
        musicxml_rest_events_imported=totals["musicxml_rest_event_count"],
        tabraw_candidates_loaded=len(tabraw.candidates),
        tabraw_fret_candidate_count=sum(1 for candidate in tabraw.candidates if candidate.parsed_fret is not None),
        tabraw_non_fret_candidate_count=sum(1 for candidate in tabraw.candidates if candidate.parsed_fret is None),
        tabraw_chord_symbol_candidate_count=_candidate_kind_count(tabraw, "chord-symbol"),
        tabraw_technique_text_candidate_count=_candidate_kind_count(tabraw, "technique-text"),
        tabraw_unknown_candidate_count=_candidate_kind_count(tabraw, "candidate-text"),
        tabraw_candidates_with_bbox=sum(1 for candidate in tabraw.candidates if candidate.bbox is not None),
        tabraw_candidates_with_x=sum(1 for candidate in tabraw.candidates if candidate.x is not None),
        tabraw_candidates_with_y=sum(1 for candidate in tabraw.candidates if candidate.y is not None),
        tabraw_candidates_with_system=sum(1 for candidate in tabraw.candidates if candidate.system_index is not None),
        tabraw_candidates_with_string=sum(1 for candidate in tabraw.candidates if candidate.string is not None),
        tabraw_candidates_with_bar=sum(1 for candidate in tabraw.candidates if candidate.bar_index is not None),
        tabraw_source_stage_counts=_tabraw_source_stage_counts(tabraw),
        matched_candidate_count=len(candidate_pools.consumed),
        unmatched_musicxml_event_count=totals["unmatched_musicxml_event_count"],
        unmatched_musicxml_note_count=totals["unmatched_musicxml_note_count"],
        unmatched_tabraw_candidate_count=len(candidate_pools.unused()),
        ignored_non_playable_candidate_count=sum(1 for candidate in tabraw.candidates if candidate.parsed_fret is None),
        symbol_attachment_chord_candidates_found=chord_found,
        symbol_attachment_chord_candidates_attached=chord_attached,
        symbol_attachment_chord_candidates_unattached=chord_unattached,
        symbol_attachment_technique_candidates_found=tech_found,
        symbol_attachment_technique_candidates_attached=tech_attached,
        symbol_attachment_technique_candidates_unattached=tech_unattached,
        unsupported_construct_warnings=[
            code
            for code in warning_codes
            if code.startswith("unsupported-") or code in {"musicxml-grace-skipped", "musicxml-harmony-unattached"}
        ],
        warning_count=len(warnings),
        confidence_flags=confidence_flags,
        extraction_quality_flags=_tabraw_extraction_quality_flags(tabraw) + _alignment_quality_flags(per_bar),
        ascii_scoreir_gate_status=_ascii_gate_detail_string(ascii_gate_details, "ascii_scoreir_gate_status", "not-applicable"),
        ascii_scoreir_gate_reason_codes=_ascii_gate_reason_codes(ascii_gate_details),
        ascii_scoreir_gate_primary_reason_code=_ascii_gate_detail_optional_string(ascii_gate_details, "primary_reason_code"),
        ascii_scoreir_gate_candidate_count=_ascii_gate_detail_int(ascii_gate_details, "candidate_count"),
        ascii_scoreir_gate_aligned_candidate_count=_ascii_gate_detail_int(ascii_gate_details, "aligned_candidate_count"),
        ascii_scoreir_gate_rejected_candidate_count=_ascii_gate_detail_int(ascii_gate_details, "rejected_candidate_count"),
        ascii_scoreir_gate_output_event_count=sum(len(bar.events) for bar in score.bars) if ascii_gate_details is not None else 0,
        ascii_scoreir_gate_scoreir_written=bool(ascii_gate_details.get("scoreir_written")) if ascii_gate_details else False,
        ascii_scoreir_gate_alignment_sidecar_present=_ascii_gate_detail_bool(ascii_gate_details, "alignment_sidecar_present"),
        ascii_scoreir_gate_alignment_status=_ascii_gate_detail_optional_string(ascii_gate_details, "alignment_status"),
        ascii_scoreir_gate_musicxml_timing_safe=_ascii_gate_detail_optional_bool(ascii_gate_details, "musicxml_timing_safe"),
        ascii_scoreir_gate_expected_next_remediation=_ascii_gate_detail_optional_string(ascii_gate_details, "expected_next_remediation"),
        per_system=_system_diagnostics(tabraw, candidate_pools),
        per_bar=per_bar,
        warnings=[warning.model_dump(mode="json", exclude_none=True) for warning in warnings],
        pdf_timing_mapping=pdf_timing_mapping_dict,
    )


def _ascii_gate_detail_string(details: dict[str, object] | None, key: str, default: str) -> str:
    if details is None:
        return default
    value = details.get(key)
    return value if isinstance(value, str) else default


def _ascii_gate_detail_int(details: dict[str, object] | None, key: str) -> int:
    if details is None:
        return 0
    value = details.get(key)
    return value if isinstance(value, int) else 0


def _ascii_gate_detail_bool(details: dict[str, object] | None, key: str) -> bool:
    if details is None:
        return False
    value = details.get(key)
    return value if isinstance(value, bool) else False


def _ascii_gate_detail_optional_bool(details: dict[str, object] | None, key: str) -> bool | None:
    if details is None:
        return None
    value = details.get(key)
    return value if isinstance(value, bool) else None


def _ascii_gate_detail_optional_string(details: dict[str, object] | None, key: str) -> str | None:
    if details is None:
        return None
    value = details.get(key)
    return value if isinstance(value, str) else None


def _ascii_gate_reason_codes(details: dict[str, object] | None) -> list[str]:
    if details is None:
        return []
    value = details.get("reason_codes")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _measure_for_bar(part: MusicXmlPart | None, bar_index: int) -> MusicXmlMeasure | None:
    if part is None:
        return None
    for measure in part.measures:
        if measure.index == bar_index:
            return measure
    return None


def _diagnostic_groups(notes: Iterable[MusicXmlNote]) -> list[list[MusicXmlNote]]:
    notes_list = list(notes)
    groups = []
    for group in _note_groups(notes_list):
        first = group[0]
        if first.grace:
            if _find_host_note(first, notes_list) is None:
                continue
        elif first.duration_divisions <= 0:
            continue
        groups.append(group)
    return groups


def _diagnostic_totals(per_bar: list[BarAlignmentDiagnostics]) -> dict[str, int]:
    return {
        "musicxml_event_count": sum(item.musicxml_event_count for item in per_bar),
        "musicxml_pitched_event_count": sum(item.musicxml_pitched_event_count for item in per_bar),
        "musicxml_rest_event_count": sum(item.musicxml_rest_event_count for item in per_bar),
        "unmatched_musicxml_event_count": sum(item.unmatched_musicxml_event_count for item in per_bar),
        "unmatched_musicxml_note_count": sum(item.unmatched_musicxml_note_count for item in per_bar),
    }


def _tabraw_source_stage_counts(tabraw: TabRaw) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in tabraw.candidates:
        key = str(candidate.source_stage)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _candidate_kind_count(tabraw: TabRaw, kind: str) -> int:
    return sum(1 for candidate in tabraw.candidates if candidate.kind == kind)


def _bar_x_to_onset_diagnostics(
    bar_index: int,
    measure: MusicXmlMeasure | None,
    musicxml_groups: list[list[MusicXmlNote]],
    tabraw: TabRaw,
) -> dict[str, object]:
    playable = sorted(
        (candidate for candidate in tabraw.candidates if candidate.parsed_fret is not None and candidate.bar_index == bar_index),
        key=lambda candidate: (float("inf") if candidate.x is None else candidate.x, candidate.id),
    )
    candidates_with_x = [candidate for candidate in playable if candidate.x is not None]
    x_groups = _candidate_x_groups(candidates_with_x)
    onset_groups = _musicxml_onset_groups(musicxml_groups, measure)
    candidate_x_positions = [round(float(candidate.x), 3) for candidate in candidates_with_x if candidate.x is not None]
    musicxml_onsets = [
        onset_tick
        for group in onset_groups
        for onset_tick in [group.onset_ticks] * group.event_count
    ]
    x_values = [group.x for group in x_groups]
    onset_values = [group.onset_ticks for group in onset_groups]
    relative_x_positions = _relative_values(x_values)
    relative_onsets = _relative_values(onset_values)
    relative_errors = _relative_errors(relative_x_positions, relative_onsets)
    bar_x_min, bar_x_max = _bar_x_bounds(candidates_with_x)
    ambiguous_x_group_count = _ambiguous_x_group_count(x_values)
    warnings = _x_to_onset_warnings(
        playable=playable,
        candidates_with_x=candidates_with_x,
        x_groups=x_groups,
        onset_groups=onset_groups,
        relative_errors=relative_errors,
        ambiguous_x_group_count=ambiguous_x_group_count,
    )
    quality = _x_to_onset_quality(
        x_groups=x_groups,
        onset_groups=onset_groups,
        relative_errors=relative_errors,
        ambiguous_x_group_count=ambiguous_x_group_count,
        warnings=warnings,
    )

    return {
        "system_index": _single_system_index(playable),
        "playable_candidate_count": len(playable),
        "playable_candidate_onset_group_count": len(x_groups),
        "musicxml_pitched_onset_group_count": len(onset_groups),
        "bar_x_min": bar_x_min,
        "bar_x_max": bar_x_max,
        "x_span": round(bar_x_max - bar_x_min, 3) if bar_x_min is not None and bar_x_max is not None else None,
        "onset_tick_min": min(onset_values) if onset_values else None,
        "onset_tick_max": max(onset_values) if onset_values else None,
        "candidate_x_positions": candidate_x_positions,
        "candidate_x_groups": x_groups,
        "musicxml_onsets": musicxml_onsets,
        "musicxml_onset_groups": onset_groups,
        "relative_x_positions": relative_x_positions,
        "relative_onsets": relative_onsets,
        "mean_absolute_relative_error": round(sum(relative_errors) / len(relative_errors), 3) if relative_errors else None,
        "max_relative_error": round(max(relative_errors), 3) if relative_errors else None,
        "monotonic_x": _is_monotonic(x_values) if x_values else None,
        "has_chord_stack": any(group.is_chord_stack for group in x_groups),
        "ambiguous_x_group_count": ambiguous_x_group_count,
        "quality": quality,
        "x_to_onset_warnings": warnings,
    }


def _candidate_x_groups(candidates: list[TabCandidate], tolerance: float = 1.5) -> list[CandidateXGroupDiagnostics]:
    groups: list[list[TabCandidate]] = []
    for candidate in sorted(candidates, key=lambda item: (float("inf") if item.x is None else item.x, item.id)):
        if candidate.x is None:
            continue
        if groups and abs(float(candidate.x) - _mean_x(groups[-1])) <= tolerance:
            groups[-1].append(candidate)
        else:
            groups.append([candidate])

    diagnostics = []
    for group in groups:
        xs = [float(candidate.x) for candidate in group if candidate.x is not None]
        strings = sorted({candidate.string for candidate in group if candidate.string is not None})
        diagnostics.append(
            CandidateXGroupDiagnostics(
                x=round(sum(xs) / len(xs), 3),
                x_min=round(min(xs), 3),
                x_max=round(max(xs), 3),
                candidate_count=len(group),
                candidate_ids=[candidate.id for candidate in group],
                strings=strings,
                is_chord_stack=len(group) > 1 and len(strings) > 1,
            )
        )
    return diagnostics


def _musicxml_onset_groups(
    musicxml_groups: list[list[MusicXmlNote]],
    measure: MusicXmlMeasure | None,
) -> list[MusicXmlOnsetGroupDiagnostics]:
    divisions = measure.divisions if measure is not None else 1
    by_onset: dict[int, list[str]] = defaultdict(list)
    for group in musicxml_groups:
        first = group[0]
        if first.is_rest:
            continue
        if first.grace:
            host_note = _find_host_note(first, measure.notes if measure is not None else [])
            if host_note is not None:
                onset_ticks, _ = host_note.onset_ticks(divisions)
            else:
                onset_ticks, _ = first.onset_ticks(divisions)
        else:
            onset_ticks, _ = first.onset_ticks(divisions)
        by_onset[onset_ticks].extend(note.id for note in group)
    return [
        MusicXmlOnsetGroupDiagnostics(
            onset_ticks=onset_ticks,
            event_count=len(note_ids),
            musicxml_note_ids=note_ids,
        )
        for onset_ticks, note_ids in sorted(by_onset.items())
    ]


def _x_to_onset_warnings(
    *,
    playable: list[TabCandidate],
    candidates_with_x: list[TabCandidate],
    x_groups: list[CandidateXGroupDiagnostics],
    onset_groups: list[MusicXmlOnsetGroupDiagnostics],
    relative_errors: list[float],
    ambiguous_x_group_count: int,
) -> list[str]:
    warnings = []
    if not playable:
        warnings.append("no playable TabRaw candidates in bar")
    if playable and len(candidates_with_x) != len(playable):
        warnings.append("one or more playable candidates lack x-position evidence")
    if not onset_groups:
        warnings.append("no MusicXML pitched onset evidence in bar")
    if x_groups and onset_groups and len(x_groups) != len(onset_groups):
        warnings.append("playable x-group count differs from MusicXML pitched onset group count")
    if x_groups and not _is_monotonic([group.x for group in x_groups]):
        warnings.append("playable x groups are not monotonic")
    if ambiguous_x_group_count:
        warnings.append("one or more playable x groups are too close to distinguish confidently")
    if relative_errors and max(relative_errors) > 0.3:
        warnings.append("visual x positions drift strongly from MusicXML onset spacing")
    elif relative_errors and max(relative_errors) > 0.15:
        warnings.append("visual x positions drift from MusicXML onset spacing")
    if len(x_groups) == 1 and len(onset_groups) == 1:
        warnings.append("single onset group cannot calibrate x-to-onset spacing")
    return warnings


def _tabraw_grouping_risk(tabraw: TabRaw) -> dict[str, object] | None:
    playable = [candidate for candidate in tabraw.candidates if candidate.parsed_fret is not None]
    unsafe_codes = _tabraw_unsafe_grouping_warning_codes(tabraw)
    if not playable and not unsafe_codes:
        return None
    warning_codes = [
        str(warning.get("code"))
        for warning in tabraw.warnings
        if warning.get("code")
    ]
    partial_ascii_grouping = "partial_ascii_tab_grouping" in warning_codes
    ascii_timing_unavailable = "ascii_tab_timing_unavailable" in warning_codes
    partial_ascii_timing = "partial_ascii_tab_timing" in warning_codes
    ambiguous_ascii_timing = "ambiguous_ascii_tab_timing" in warning_codes
    ascii_measure_boundary_missing = "ascii_tab_measure_boundary_missing" in warning_codes

    counts: dict[str, object] = {
        "total_candidate_count": len(tabraw.candidates),
        "playable_candidate_count": len(playable),
        "playable_fret_candidate_count": len(playable),
        "playable_candidates_with_system": sum(1 for candidate in playable if candidate.system_index is not None),
        "playable_candidates_with_bar": sum(1 for candidate in playable if candidate.bar_index is not None),
        "playable_candidates_with_string": sum(1 for candidate in playable if candidate.string is not None),
    }
    if partial_ascii_grouping:
        counts["category"] = "partial_ascii_tab_grouping"
        counts["grouping_status"] = "partial_ascii_tab_grouping"
        counts["warning_codes"] = warning_codes
        counts["missing_grouping_dimensions"] = [
            dimension
            for dimension, count_key in (
                ("system", "playable_candidates_with_system"),
                ("bar", "playable_candidates_with_bar"),
                ("string", "playable_candidates_with_string"),
            )
            if int(counts[count_key]) < len(playable)
        ]
        return counts
    if ambiguous_ascii_timing:
        counts["category"] = "ambiguous_ascii_tab_timing"
        counts["grouping_status"] = "ascii_grouped"
        counts["warning_codes"] = warning_codes
        counts["missing_grouping_dimensions"] = ["bar"]
        counts["ascii_timing_status_counts"] = _ascii_timing_status_counts(playable)
        return counts
    if partial_ascii_timing:
        counts["category"] = "partial_ascii_tab_timing"
        counts["grouping_status"] = "ascii_grouped"
        counts["warning_codes"] = warning_codes
        counts["missing_grouping_dimensions"] = ["bar"]
        counts["ascii_timing_status_counts"] = _ascii_timing_status_counts(playable)
        return counts
    if ascii_timing_unavailable or ascii_measure_boundary_missing:
        counts["category"] = "ascii_tab_timing_unavailable"
        counts["grouping_status"] = "ascii_grouped"
        counts["warning_codes"] = warning_codes
        counts["missing_grouping_dimensions"] = ["bar"]
        counts["ascii_timing_status_counts"] = _ascii_timing_status_counts(playable)
        return counts
    missing = []
    if counts["playable_candidates_with_system"] < len(playable):
        missing.append("system")
    if counts["playable_candidates_with_bar"] < len(playable):
        missing.append("bar")
    if counts["playable_candidates_with_string"] < len(playable):
        missing.append("string")
    if not missing:
        unsafe_codes = _tabraw_unsafe_grouping_warning_codes(tabraw)
        if not unsafe_codes:
            return None
        counts["missing_grouping_dimensions"] = []
        counts["unsafe_grouping_warning_codes"] = unsafe_codes
        counts["grouping_status"] = "missing" if len(playable) == 0 else "partial"
        counts["category"] = "missing_pdf_grouping" if len(playable) == 0 else "partial_pdf_grouping"
        counts["warning_codes"] = unsafe_codes
        counts["tabraw_warning_codes"] = unsafe_codes
        return counts
    counts["missing_grouping_dimensions"] = missing
    unsafe_codes = _tabraw_unsafe_grouping_warning_codes(tabraw)
    if unsafe_codes:
        counts["unsafe_grouping_warning_codes"] = unsafe_codes
    system_count = int(counts["playable_candidates_with_system"])
    bar_count = int(counts["playable_candidates_with_bar"])
    string_count = int(counts["playable_candidates_with_string"])
    counts["grouping_status"] = "missing" if system_count == 0 and bar_count == 0 and string_count == 0 else "partial"
    counts["category"] = "missing_pdf_grouping" if counts["grouping_status"] == "missing" else "partial_pdf_grouping"
    counts["warning_codes"] = [
        str(warning.get("code"))
        for warning in tabraw.warnings
        if warning.get("code")
        in {
            "missing_pdf_grouping",
            "partial_pdf_grouping",
            "pdf-tab-system-not-detected",
            "missing_pdf_barlines",
            "incomplete_tab_staff",
            "ambiguous_string_assignment",
            "ambiguous_bar_assignment",
            "pdf_no_systems_detected",
            "pdf_partial_system_detection",
            "pdf_tab_staff_missing",
            "pdf_tab_staff_incomplete",
            "pdf_tab_staff_ambiguous",
            "pdf_barlines_missing",
            "pdf_barlines_ambiguous",
            "pdf_bar_boxes_missing",
            "pdf_string_lines_missing",
            "pdf_string_assignment_missing",
            "pdf_string_assignment_ambiguous",
            "pdf_candidate_outside_system",
            "pdf_candidate_outside_bar",
            "pdf_candidate_between_strings",
            "pdf_multi_system_order_ambiguous",
            "pdf_page_layout_unsupported",
            "pdf_text_candidate_without_geometry",
            "pdf_ascii_and_drawn_layout_conflict",
            "pdf_grouping_not_safe_for_build_ir",

            # New Phase 4/8 Codes
            "pdf_text_geometry_present_but_no_safe_system",
            "pdf_tab_candidates_present_but_system_not_detected",
            "pdf_drawn_geometry_present_but_staff_unresolved",
            "pdf_tab_staff_lines_fragmented",
            "pdf_tab_staff_lines_overlapping",
            "pdf_tab_staff_spacing_inconsistent",
            "pdf_system_bbox_ambiguous",
            "pdf_system_order_ambiguous",
            "pdf_candidates_unassigned_to_system",
            "pdf_candidates_unassigned_to_bar",
            "pdf_candidates_unassigned_to_string",
            "pdf_partial_grouping_with_playable_candidates",
            "pdf_grouping_confidence_below_threshold",
            "pdf_missing_pdf_grouping_blocks_build_ir",
            "pdf_layout_detection_requires_manual_review",

            # Refined system-detection and bar-detection codes
            "pdf_drawn_system_not_detected",
            "pdf_drawn_system_ambiguous",
            "pdf_drawn_staff_lines_unresolved",
            "pdf_ascii_system_detected",
            "pdf_ascii_system_measure_boundaries_missing",
            "pdf_ascii_system_timing_unavailable",
            "pdf_system_detected_bar_detection_missing",
            "pdf_system_detection_succeeded_but_grouping_incomplete",
            "pdf_input_class_ascii_tab_requires_alignment",
            "pdf_input_class_drawn_tab_requires_barlines",
            "pdf_system_detection_not_enough_for_build_ir",
            "pdf_barlines_not_detected_in_system",
            "pdf_barline_candidates_present_but_invalid",
            "pdf_barline_does_not_cross_staff",
            "pdf_barline_too_short",
            "pdf_barline_outside_system_bounds",
            "pdf_barline_ambiguous",
            "pdf_bar_boxes_not_constructible",
            "pdf_bar_detection_succeeded_string_assignment_pending",
            "pdf_bar_detection_not_enough_for_build_ir",

            # Refined barline-validation taxonomy blocker codes
            "pdf_barline_too_short_absolute",
            "pdf_barline_too_short_relative_to_staff",
            "pdf_barline_crosses_insufficient_string_gaps",
            "pdf_barline_partial_staff_crossing",
            "pdf_barline_outside_staff_region",
            "pdf_barline_rejected_relative_height",
            "pdf_barline_validation_threshold_boundary",
            "pdf_barline_validation_not_enough_for_build_ir",

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
            "pdf_candidate_boundary_ambiguous",
            "pdf_candidate_unassigned_to_bar",
            "pdf_partial_grouping_one_system_unboxed",
            "pdf_grouping_complete",
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

            # New PDF String Assignment Codes
            "pdf_string_assignment_nearest_line",
            "pdf_string_assignment_outside_staff",
            "pdf_string_assignment_between_lines",
            "pdf_string_assignment_too_far_from_line",
            "pdf_string_assignment_overlaps_multiple_bands",
            "pdf_string_assignment_confidence_below_threshold",
            "pdf_string_assignment_compact_staff_ambiguous",
            "pdf_playable_candidate_requires_string_assignment",
            "pdf_non_playable_text_not_string_assigned",
            "pdf_multidigit_fret_string_assigned",
            "pdf_string_assignment_not_enough_for_build_ir",
            "pdf_string_assignment_succeeded_upstream_grouping_still_blocks",
        }
    ]
    counts["tabraw_warning_codes"] = counts["warning_codes"]
    return counts


def _tabraw_unsafe_grouping_warning_codes(tabraw: TabRaw) -> list[str]:
    unsafe = {
        "partial_pdf_grouping",
        "missing_pdf_barlines",
        "incomplete_tab_staff",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
        "ascii_tab_timing_unavailable",
        "partial_ascii_tab_grouping",
        "partial_ascii_tab_timing",
        "ambiguous_ascii_tab_timing",
        "unsupported_ascii_tab_rhythm",
        "ascii_tab_measure_boundary_missing",

        "pdf_no_systems_detected",
        "pdf_partial_system_detection",
        "pdf_tab_staff_missing",
        "pdf_tab_staff_incomplete",
        "pdf_tab_staff_ambiguous",
        "pdf_barlines_missing",
        "pdf_barlines_ambiguous",
        "pdf_bar_boxes_missing",
        "pdf_string_lines_missing",
        "pdf_string_assignment_missing",
        "pdf_string_assignment_ambiguous",
        "pdf_candidate_outside_system",
        "pdf_candidate_outside_bar",
        "pdf_candidate_between_strings",
        "pdf_multi_system_order_ambiguous",
        "pdf_page_layout_unsupported",
        "pdf_text_candidate_without_geometry",
        "pdf_ascii_and_drawn_layout_conflict",
        "pdf_grouping_not_safe_for_build_ir",

        # New Phase 4/8 Codes
        "pdf_text_geometry_present_but_no_safe_system",
        "pdf_tab_candidates_present_but_system_not_detected",
        "pdf_drawn_geometry_present_but_staff_unresolved",
        "pdf_tab_staff_lines_fragmented",
        "pdf_tab_staff_lines_overlapping",
        "pdf_tab_staff_spacing_inconsistent",
        "pdf_system_bbox_ambiguous",
        "pdf_system_order_ambiguous",
        "pdf_candidates_unassigned_to_system",
        "pdf_candidates_unassigned_to_bar",
        "pdf_candidates_unassigned_to_string",
        "pdf_partial_grouping_with_playable_candidates",
        "pdf_grouping_confidence_below_threshold",
        "pdf_missing_pdf_grouping_blocks_build_ir",
        "pdf_layout_detection_requires_manual_review",

        # Refined system-detection and bar-detection codes
        "pdf_drawn_system_not_detected",
        "pdf_drawn_system_ambiguous",
        "pdf_drawn_staff_lines_unresolved",
        "pdf_ascii_system_detected",
        "pdf_ascii_system_measure_boundaries_missing",
        "pdf_ascii_system_timing_unavailable",
        "pdf_system_detected_bar_detection_missing",
        "pdf_system_detection_succeeded_but_grouping_incomplete",
        "pdf_input_class_ascii_tab_requires_alignment",
        "pdf_input_class_drawn_tab_requires_barlines",
        "pdf_system_detection_not_enough_for_build_ir",
        "pdf_barlines_not_detected_in_system",
        "pdf_barline_candidates_present_but_invalid",
        "pdf_barline_does_not_cross_staff",
        "pdf_barline_too_short",
        "pdf_barline_outside_system_bounds",
        "pdf_barline_ambiguous",
        "pdf_bar_boxes_not_constructible",
        "pdf_bar_detection_succeeded_string_assignment_pending",
        "pdf_bar_detection_not_enough_for_build_ir",

        # Refined barline-validation taxonomy blocker codes
        "pdf_barline_too_short_absolute",
        "pdf_barline_too_short_relative_to_staff",
        "pdf_barline_crosses_insufficient_string_gaps",
        "pdf_barline_partial_staff_crossing",
        "pdf_barline_outside_staff_region",
        "pdf_barline_rejected_relative_height",
        "pdf_barline_validation_threshold_boundary",
        "pdf_barline_validation_not_enough_for_build_ir",

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
        "pdf_candidate_boundary_ambiguous",
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
        "pdf_bar_box_edge_boundary_fallback_rejected",
        "pdf_bar_box_edge_boundary_ambiguous",
        "pdf_bar_box_inferred_boundary_too_narrow",
        "pdf_bar_box_inferred_boundary_candidate_ambiguous",
        "pdf_bar_box_inferred_boundary_requires_clear_system_edge",
        "pdf_bar_box_inferred_boundary_not_enough_for_build_ir",

        # New PDF String Assignment Codes
        "pdf_string_assignment_outside_staff",
        "pdf_string_assignment_between_lines",
        "pdf_string_assignment_too_far_from_line",
        "pdf_string_assignment_overlaps_multiple_bands",
        "pdf_string_assignment_confidence_below_threshold",
        "pdf_string_assignment_compact_staff_ambiguous",
        "pdf_playable_candidate_requires_string_assignment",
        "pdf_string_assignment_not_enough_for_build_ir",

        # New Fret Refinement Blocker Codes
        "pdf_fret_digits_not_merged_gap_too_large",
        "pdf_fret_digits_not_merged_vertical_misalignment",
        "pdf_fret_digits_overlap_ambiguous",
        "pdf_fret_digit_symbol_overlap_ambiguous",
        "pdf_fret_bbox_too_tall",
        "pdf_fret_bbox_too_wide",
        "pdf_fret_bbox_too_small",
        "pdf_fret_outside_valid_range",
        "pdf_fret_non_digit_rejected",
        "pdf_fret_optical_bounds_confidence_below_threshold",
        "pdf_fret_refinement_not_enough_for_build_ir",

        # New Pitch / Tuning Blocker Codes
        "pdf_tuning_conflict_detected",
        "pdf_tuning_label_ambiguous",
        "pdf_tuning_label_malformed",
        "pdf_tuning_format_unsupported",
        "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",

        # New PDF Spacing & Timing Mapping Blocker Codes
        "pdf_timing_mapping_refused",
        "pdf_timing_mapping_not_enough_for_build_ir",
        "pdf_timing_mapping_group_count_mismatch",
        "pdf_timing_mapping_non_monotonic",
    }
    return sorted({str(warning.get("code")) for warning in tabraw.warnings if warning.get("code") in unsafe})


def _ascii_timing_status_counts(candidates: list[TabCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        status = str(candidate.raw.get("ascii_timing_status", "")) if isinstance(candidate.raw, dict) else ""
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _x_to_onset_quality(
    *,
    x_groups: list[CandidateXGroupDiagnostics],
    onset_groups: list[MusicXmlOnsetGroupDiagnostics],
    relative_errors: list[float],
    ambiguous_x_group_count: int,
    warnings: list[str],
) -> Literal["good", "warning", "poor", "unknown"]:
    if not x_groups or not onset_groups:
        return "unknown"
    if len(x_groups) == 1 and len(onset_groups) == 1:
        return "unknown"
    if len(x_groups) != len(onset_groups):
        return "poor"
    if not relative_errors:
        return "unknown"
    if max(relative_errors) > 0.3:
        return "poor"
    if max(relative_errors) > 0.15 or ambiguous_x_group_count or warnings:
        return "warning"
    return "good"


def _bar_x_bounds(candidates: list[TabCandidate]) -> tuple[float | None, float | None]:
    raw_mins = [_raw_float(candidate.raw.get("bar_x_min")) for candidate in candidates if isinstance(candidate.raw, dict)]
    raw_maxs = [_raw_float(candidate.raw.get("bar_x_max")) for candidate in candidates if isinstance(candidate.raw, dict)]
    raw_mins = [value for value in raw_mins if value is not None]
    raw_maxs = [value for value in raw_maxs if value is not None]
    if raw_mins and raw_maxs:
        return round(min(raw_mins), 3), round(max(raw_maxs), 3)
    xs = [float(candidate.x) for candidate in candidates if candidate.x is not None]
    if not xs:
        return None, None
    return round(min(xs), 3), round(max(xs), 3)


def _relative_values(values: list[float | int]) -> list[float]:
    if not values:
        return []
    minimum = float(min(values))
    maximum = float(max(values))
    if maximum == minimum:
        return [0.0 for _ in values]
    return [round((float(value) - minimum) / (maximum - minimum), 3) for value in values]


def _relative_errors(left: list[float], right: list[float]) -> list[float]:
    if len(left) != len(right) or len(left) < 2:
        return []
    return [abs(left_value - right_value) for left_value, right_value in zip(left, right)]


def _mean_x(candidates: list[TabCandidate]) -> float:
    values = [float(candidate.x) for candidate in candidates if candidate.x is not None]
    return sum(values) / len(values)


def _single_system_index(candidates: list[TabCandidate]) -> int | None:
    system_indexes = {candidate.system_index for candidate in candidates if candidate.system_index is not None}
    if len(system_indexes) == 1:
        return next(iter(system_indexes))
    return None


def _ambiguous_x_group_count(values: list[float], tolerance: float = 8.0) -> int:
    return sum(1 for left, right in zip(values, values[1:]) if 1.5 < abs(right - left) <= tolerance)


def _is_monotonic(values: list[float]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))


def _raw_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _alignment_quality_flags(per_bar: list[BarAlignmentDiagnostics]) -> list[str]:
    flags = []
    qualities = {bar.quality for bar in per_bar}
    if "poor" in qualities:
        flags.append("one or more bars have poor x-to-onset quality")
    if "warning" in qualities:
        flags.append("one or more bars have warning x-to-onset quality")
    if "unknown" in qualities:
        flags.append("one or more bars have unknown x-to-onset quality")
    return flags


def _system_diagnostics(tabraw: TabRaw, candidate_pools: CandidatePools) -> list[SystemAlignmentDiagnostics]:
    grouped: dict[tuple[int, int], list[TabCandidate]] = defaultdict(list)
    for candidate in tabraw.candidates:
        if candidate.page_index is not None and candidate.system_index is not None:
            grouped[(candidate.page_index, candidate.system_index)].append(candidate)

    consumed_ids = {use.candidate.id for use in candidate_pools.consumed}
    unused_ids = {candidate.id for candidate in candidate_pools.unused()}
    diagnostics = []
    for (page_index, system_index), candidates in sorted(grouped.items()):
        diagnostics.append(
            SystemAlignmentDiagnostics(
                page_index=page_index,
                system_index=system_index,
                tabraw_candidate_count=len(candidates),
                fret_candidate_count=sum(1 for candidate in candidates if candidate.parsed_fret is not None),
                non_fret_candidate_count=sum(1 for candidate in candidates if candidate.parsed_fret is None),
                matched_playable_candidate_count=sum(1 for candidate in candidates if candidate.id in consumed_ids),
                unmatched_playable_candidate_count=sum(1 for candidate in candidates if candidate.id in unused_ids),
                ignored_non_playable_candidate_count=sum(1 for candidate in candidates if candidate.parsed_fret is None),
                candidates_with_string=sum(1 for candidate in candidates if candidate.string is not None),
                candidates_with_bar=sum(1 for candidate in candidates if candidate.bar_index is not None),
            )
        )
    return diagnostics


def _tabraw_extraction_quality_flags(tabraw: TabRaw) -> list[str]:
    flags = []
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.parsed_fret is not None]
    if not tabraw.candidates:
        flags.append("TabRaw contains no candidates")
    if fret_candidates and any(candidate.x is None for candidate in fret_candidates):
        flags.append("fret candidate missing x-position")
    if fret_candidates and any(candidate.bbox is None for candidate in fret_candidates):
        flags.append("fret candidate missing bounding box")
    if fret_candidates and any(candidate.string is None for candidate in fret_candidates):
        flags.append("fret candidate missing inferred string")
    if fret_candidates and any(candidate.bar_index is None for candidate in fret_candidates):
        flags.append("fret candidate missing inferred bar")
    if fret_candidates and len({candidate.system_index for candidate in fret_candidates if candidate.system_index is not None}) > 1:
        flags.append("multiple inferred tab systems present")
    if any(candidate.confidence < 0.6 for candidate in tabraw.candidates):
        flags.append("one or more TabRaw candidates have low confidence")
    return flags


def _bar_ambiguity_flags(bar_index: int, candidate_pools: CandidatePools) -> list[str]:
    flags = []
    uses = candidate_pools.consumed_in_bar(bar_index)
    if any(use.candidate.x is None for use in uses):
        flags.append("matched candidate missing x-position")
    if any(use.source_pool_bar_index is None for use in uses):
        flags.append("used unscoped TabRaw candidate for bar")
    if _has_repeated_x([use.candidate for use in uses]):
        flags.append("repeated x-position candidates treated as a chord or stacked notes")
    return flags


def _has_repeated_x(candidates: list[TabCandidate], tolerance: float = 1.5) -> bool:
    values = sorted(candidate.x for candidate in candidates if candidate.x is not None)
    return any(abs(left - right) <= tolerance for left, right in zip(values, values[1:]))


def _warning_bar_index(warning: WarningItem) -> int | None:
    for provenance in warning.provenance:
        if provenance.bar_index is not None:
            return provenance.bar_index
    return None


def _event_warning(
    code: str,
    note: MusicXmlNote,
    message: str,
    candidate: TabCandidate | None = None,
) -> WarningItem:
    provenance = [
        Provenance(
            source_stage=SourceStage.MUSICXML,
            bar_index=note.measure_index,
            raw_token_id=note.id,
            raw={
                "source_path": note.source_path,
                "onset_divisions": note.onset_divisions,
                "duration_divisions": note.duration_divisions,
            },
            confidence=0.9,
        )
    ]
    if candidate is not None:
        provenance.append(candidate.to_provenance())
    return WarningItem(code=code, message=message, severity="warning", provenance=provenance)


def _harmony_warning(harmony: MusicXmlHarmony, message: str) -> WarningItem:
    return WarningItem(
        code="musicxml-harmony-unattached",
        message=message,
        severity="warning",
        provenance=[
            Provenance(
                source_stage=SourceStage.MUSICXML,
                bar_index=harmony.measure_index,
                raw_token_id=harmony.id,
                raw={
                    "source_path": harmony.source_path,
                    "text": harmony.text,
                    "onset_divisions": harmony.onset_divisions,
                },
                confidence=0.9,
            )
        ],
    )


def _musicxml_provenance(note: MusicXmlNote, measure: MusicXmlMeasure) -> Provenance:
    return Provenance(
        source_stage=SourceStage.MUSICXML,
        bar_index=measure.index,
        raw_token_id=note.id,
        raw={
            "source_path": note.source_path,
            "measure_number": note.measure_number,
            "onset_divisions": note.onset_divisions,
            "duration_divisions": note.duration_divisions,
            "measure_divisions": measure.divisions,
            "notated_type": note.notated_type,
            "dots": note.dots,
            "tuplet": note.tuplet.model_dump() if note.tuplet is not None else None,
            "techniques": [technique.model_dump(exclude_none=True) for technique in note.techniques],
        },
        confidence=0.9,
    )


def _standard_guitar_track() -> Track:
    return Track(
        id=TRACK_ID,
        name="Guitar",
        instrument="guitar",
        tuning=_standard_guitar_tuning(),
        tablature_enabled=True,
        staff_count=1,
    )


def _standard_guitar_tuning() -> Tuning:
    return Tuning(
        name="Standard guitar",
        strings=[
            TuningString(number=1, pitch=64, name="E4"),
            TuningString(number=2, pitch=59, name="B3"),
            TuningString(number=3, pitch=55, name="G3"),
            TuningString(number=4, pitch=50, name="D3"),
            TuningString(number=5, pitch=45, name="A2"),
            TuningString(number=6, pitch=40, name="E2"),
        ],
    )


def _classify_technique(text: str) -> str | None:
    t = text.strip().lower()
    if t in ("slide", "sl.", "sl"):
        return "slide"
    if t in ("bend", "b"):
        return "bend"
    if t in ("vibrato", "vib", "v"):
        return "vibrato"
    if t in ("hammer-on", "h", "hammer"):
        return "hammer-on"
    if t in ("pull-off", "p", "pull"):
        return "pull-off"
    if t in ("palm-mute", "p.m.", "p.m", "pm", "palm mute"):
        return "palm-mute"
    if t in ("let-ring", "l.r.", "l.r", "lr", "let ring"):
        return "let-ring"
    return None


TECHNIQUE_ATTACHMENT_AMBIGUITY_EPSILON = 2.0


def _get_note_x(note: Note) -> float | None:
    for prov in note.provenance:
        if prov.raw and prov.raw.get("x") is not None:
            try:
                return float(prov.raw["x"])
            except (ValueError, TypeError):
                pass
    return None


def _remove_not_aligned_warning(score: ScoreIR, candidate: TabCandidate) -> None:
    score.warnings = [
        w for w in score.warnings
        if not (w.code == f"tabraw-{candidate.kind}-not-aligned" and w.provenance and w.provenance[0].raw_token_id == candidate.id)
    ]


def _attach_symbols_and_techniques(score: ScoreIR, tabraw: TabRaw) -> None:
    bars_by_index = {bar.index: bar for bar in score.bars}

    for candidate in tabraw.candidates:
        if candidate.kind not in ("chord-symbol", "technique-text"):
            continue

        bar_idx = candidate.bar_index
        # If candidate lacks a bar index, or the target bar does not exist:
        if bar_idx is None or bar_idx not in bars_by_index:
            if candidate.kind == "chord-symbol":
                score.warnings.append(
                    WarningItem(
                        code="symbol_attachment_requires_timing" if bar_idx is None else "unattached_chord_symbol",
                        message=f"Chord symbol '{candidate.raw_text}' has no valid timed bar/event target.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
            else:
                score.warnings.append(
                    WarningItem(
                        code="technique_attachment_requires_note_target" if bar_idx is None else "unattached_technique_text",
                        message=f"Technique text '{candidate.raw_text}' has no valid timed bar target.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
            continue

        bar = bars_by_index[bar_idx]

        if candidate.kind == "chord-symbol":
            # Chord symbol attachment
            if not bar.events:
                score.warnings.append(
                    WarningItem(
                        code="symbol_attachment_requires_timing",
                        message=f"Chord symbol '{candidate.raw_text}' requires a timed event target in bar {bar_idx}.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
                continue

            # Fallback to the first event of the bar if candidate.x is None
            if candidate.x is None:
                event = bar.events[0]
                event.chord_symbol = candidate.raw_text
                event.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)
                continue

            # Visual proximity logic
            # Let's extract visual coordinate x for each event in the bar
            events_with_x = []
            for event in bar.events:
                x_coords = []
                for note in event.notes:
                    for prov in note.provenance:
                        if prov.raw and prov.raw.get("x") is not None:
                            try:
                                x_val = float(prov.raw["x"])
                                x_coords.append(x_val)
                            except (ValueError, TypeError):
                                pass
                if x_coords:
                    events_with_x.append((sum(x_coords) / len(x_coords), event))
                else:
                    events_with_x.append((None, event))

            # If all events have no visual coordinates, fallback to first event
            valid_events_with_x = [(x, ev) for x, ev in events_with_x if x is not None]
            if not valid_events_with_x:
                event = bar.events[0]
                event.chord_symbol = candidate.raw_text
                event.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)
                continue

            # Sort valid events by their x-coordinate
            valid_events_with_x.sort(key=lambda item: item[0])
            first_event_x = valid_events_with_x[0][0]

            # If candidate.x is at or before the first event's x position, map to first event
            if candidate.x <= first_event_x:
                event = bar.events[0]
                event.chord_symbol = candidate.raw_text
                event.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)
                continue

            # Find closest event by absolute visual distance
            dists = []
            for ev_x, ev in valid_events_with_x:
                dists.append((abs(ev_x - candidate.x), ev))
            dists.sort(key=lambda item: item[0])

            best_dist, best_event = dists[0]

            # Ambiguity check: if there's a tie or a second event within a tight range (e.g. 2.0 units), refuse attachment
            if len(dists) > 1 and abs(dists[0][0] - dists[1][0]) < 2.0:
                score.warnings.append(
                    WarningItem(
                        code="ambiguous_chord_symbol_attachment",
                        message=f"Chord symbol '{candidate.raw_text}' has ambiguous visual targets in bar {bar_idx}.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
            else:
                best_event.chord_symbol = candidate.raw_text
                best_event.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)

        elif candidate.kind == "technique-text":
            # Technique text attachment
            kind = _classify_technique(candidate.raw_text)
            if kind is None:
                score.warnings.append(
                    WarningItem(
                        code="unsupported_technique_text",
                        message=f"Technique text '{candidate.raw_text}' is unsupported in v0.1 vocabulary.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
                continue

            notes = [note for event in bar.events for note in event.notes]
            if not notes:
                score.warnings.append(
                    WarningItem(
                        code="technique_attachment_requires_note_target",
                        message=f"Technique text '{candidate.raw_text}' requires a note target in bar {bar_idx}.",
                        severity="warning",
                        provenance=[candidate.to_provenance()],
                    )
                )
                continue

            # Differentiate by kind
            if kind in ("hammer-on", "pull-off"):
                attached = False
                if candidate.x is not None:
                    # Collect candidate pairs of notes that:
                    # - Belong to the same bar, same track, same voice, and same string
                    # - Are chronologically adjacent on that string/voice/track within the bar
                    # - Are both playable (non-rest)
                    # - Both have valid visual x-coordinates (via _get_note_x)
                    notes_by_group = defaultdict(list)
                    for event in bar.events:
                        if event.is_rest:
                            continue
                        for note in event.notes:
                            x_val = _get_note_x(note)
                            if x_val is not None:
                                notes_by_group[(event.track_id, event.timing.voice, note.string)].append((event, note, x_val))

                    candidate_pairs = []
                    for group_key, group_notes in notes_by_group.items():
                        group_notes.sort(key=lambda item: item[0].timing.onset_ticks)
                        for i in range(len(group_notes) - 1):
                            ev1, note1, x1 = group_notes[i]
                            ev2, note2, x2 = group_notes[i+1]
                            if ev1.timing.onset_ticks < ev2.timing.onset_ticks:
                                mid_x = (x1 + x2) / 2.0
                                dist = abs(mid_x - candidate.x)
                                candidate_pairs.append((dist, ev1, note1, ev2, note2))

                    if candidate_pairs:
                        candidate_pairs.sort(key=lambda item: item[0])
                        if len(candidate_pairs) > 1 and abs(candidate_pairs[0][0] - candidate_pairs[1][0]) < TECHNIQUE_ATTACHMENT_AMBIGUITY_EPSILON:
                            score.warnings.append(
                                WarningItem(
                                    code="ambiguous_technique_attachment",
                                    message=f"Span technique '{candidate.raw_text}' has ambiguous visual targets in bar {bar_idx}.",
                                    severity="warning",
                                    provenance=[candidate.to_provenance()],
                                )
                            )
                        else:
                            best_dist, ev1, note1, ev2, note2 = candidate_pairs[0]
                            if kind == "hammer-on":
                                tech = HammerOnTechnique(kind="hammer-on", target_event_id=ev2.id)
                            else:
                                tech = PullOffTechnique(kind="pull-off", target_event_id=ev2.id)
                            note1.techniques.append(tech)
                            note1.provenance.append(candidate.to_provenance())
                            _remove_not_aligned_warning(score, candidate)
                        attached = True

                if not attached:
                    # Fallback to the original exact-count logic:
                    if len(notes) != 2:
                        score.warnings.append(
                            WarningItem(
                                code="ambiguous_technique_attachment",
                                message=f"Span technique '{candidate.raw_text}' requires exactly two notes in bar {bar_idx}.",
                                severity="warning",
                                provenance=[candidate.to_provenance()],
                            )
                        )
                        continue

                    note1, note2 = notes
                    event1 = next((ev for ev in bar.events if note1 in ev.notes), None)
                    event2 = next((ev for ev in bar.events if note2 in ev.notes), None)

                    if not event1 or not event2 or event1.timing.onset_ticks >= event2.timing.onset_ticks:
                        score.warnings.append(
                            WarningItem(
                                code="ambiguous_technique_attachment",
                                message=f"Span technique '{candidate.raw_text}' endpoints are not sequential in bar {bar_idx}.",
                                severity="warning",
                                provenance=[candidate.to_provenance()],
                            )
                        )
                        continue

                    if kind == "hammer-on":
                        tech = HammerOnTechnique(kind="hammer-on", target_event_id=event2.id)
                    else:
                        tech = PullOffTechnique(kind="pull-off", target_event_id=event2.id)

                    note1.techniques.append(tech)
                    note1.provenance.append(candidate.to_provenance())
                    _remove_not_aligned_warning(score, candidate)

            elif kind in ("slide", "palm-mute", "let-ring"):
                attached = False
                if candidate.x is not None:
                    notes_with_x = []
                    for event in bar.events:
                        if event.is_rest:
                            continue
                        for note in event.notes:
                            x_val = _get_note_x(note)
                            if x_val is not None:
                                notes_with_x.append((abs(x_val - candidate.x), note))

                    if notes_with_x:
                        notes_with_x.sort(key=lambda item: item[0])
                        if len(notes_with_x) > 1 and abs(notes_with_x[0][0] - notes_with_x[1][0]) < TECHNIQUE_ATTACHMENT_AMBIGUITY_EPSILON:
                            score.warnings.append(
                                WarningItem(
                                    code="ambiguous_technique_attachment",
                                    message=f"Technique '{candidate.raw_text}' has ambiguous visual targets in bar {bar_idx}.",
                                    severity="warning",
                                    provenance=[candidate.to_provenance()],
                                )
                            )
                        else:
                            best_dist, target_note = notes_with_x[0]
                            if kind == "slide":
                                tech = SlideTechnique(kind="slide", style="unknown", direction="unknown", target_event_id=None)
                            elif kind == "palm-mute":
                                tech = PalmMuteTechnique()
                            else:
                                tech = LetRingTechnique()
                            target_note.techniques.append(tech)
                            target_note.provenance.append(candidate.to_provenance())
                            _remove_not_aligned_warning(score, candidate)
                        attached = True

                if not attached:
                    if len(notes) != 1:
                        score.warnings.append(
                            WarningItem(
                                code="ambiguous_technique_attachment",
                                message=f"Technique '{candidate.raw_text}' requires exactly one note target in bar {bar_idx}.",
                                severity="warning",
                                provenance=[candidate.to_provenance()],
                            )
                        )
                        continue

                    target_note = notes[0]
                    if kind == "slide":
                        tech = SlideTechnique(kind="slide", style="unknown", direction="unknown", target_event_id=None)
                    elif kind == "palm-mute":
                        tech = PalmMuteTechnique()
                    else:
                        tech = LetRingTechnique()
                    target_note.techniques.append(tech)
                    target_note.provenance.append(candidate.to_provenance())
                    _remove_not_aligned_warning(score, candidate)

            else:
                # Bend, Vibrato (original logic)
                if len(notes) != 1:
                    score.warnings.append(
                        WarningItem(
                            code="ambiguous_technique_attachment",
                            message=f"Technique '{candidate.raw_text}' requires exactly one note target in bar {bar_idx}.",
                            severity="warning",
                            provenance=[candidate.to_provenance()],
                        )
                    )
                    continue

                target_note = notes[0]
                if kind == "bend":
                    tech = BendTechnique(kind="bend", semitones=None, points=[], text=None)
                else:
                    tech = VibratoTechnique(kind="vibrato", width="unknown", speed="unknown")

                target_note.techniques.append(tech)
                target_note.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)


def optimize_fret_snapping(score: ScoreIR) -> None:
    """
    Optimizes left-hand fingering execution positions using a localized dynamic programming costing solver.
    Filters out spans that breach biomechanical boundaries, clamps unplayable fret combinations,
    penalizes shifts and radical jumps, and prefers original candidates if ergonomic.
    """
    import itertools

    for track in score.tracks:
        events_to_optimize = []
        for bar in score.bars:
            for event in bar.events:
                if event.track_id == track.id and not event.is_rest and event.notes:
                    events_to_optimize.append(event)

        if not events_to_optimize:
            continue

        tuning = track.tuning

        # Step 1: Pre-generate valid states for each event
        event_states = []
        for event in events_to_optimize:
            pitches = [note.pitch for note in event.notes]
            suggestions = [(note.string, note.fret) for note in event.notes]

            # Generate valid states for these pitches
            valid_states = []
            possibilities = []
            for pitch in pitches:
                opts = []
                for string in tuning.strings:
                    fret = pitch - string.pitch
                    if 0 <= fret <= 24:
                        opts.append((string.number, fret))
                possibilities.append(opts)

            for state in itertools.product(*possibilities):
                strings = [s for s, f in state]
                if len(strings) != len(set(strings)):
                    continue

                non_open = [f for s, f in state if f > 0]
                if non_open:
                    span = max(non_open) - min(non_open)
                    if span > 5:  # Breach absolute biomechanical boundary
                        continue

                valid_states.append(list(state))

            if not valid_states:
                # Fallback to the original suggestion
                valid_states = [suggestions]

            event_states.append((event, valid_states, suggestions))

        # Step 2: Run dynamic programming cost minimization
        # dp[i] will store list of (min_total_cost, centroid_value, path_state_indexes) for each state at step i
        dp = []

        # Step 0 initialization
        step_0_states = event_states[0][1]
        step_0_suggestions = event_states[0][2]
        step_0_dp = []
        for j, state in enumerate(step_0_states):
            non_open = [f for s, f in state if f > 0]
            centroid = sum(non_open) / len(non_open) if non_open else 5.0

            cost = 0.0
            if non_open:
                # stretch
                span = max(non_open) - min(non_open)
                if span > 4:
                    cost += 15.0
                for f in non_open:
                    dist = abs(f - centroid)
                    if dist <= 4:
                        cost += 1.0 * dist
                    else:
                        cost += 4.0 + 20.0 * (dist - 4.0)

            if step_0_suggestions:
                for idx, (s, f) in enumerate(state):
                    if idx < len(step_0_suggestions):
                        s_sug, f_sug = step_0_suggestions[idx]
                        if s != s_sug or f != f_sug:
                            cost += 5.0

            step_0_dp.append((cost, centroid, [j]))
        dp.append(step_0_dp)

        # Loop for remaining events
        for i in range(1, len(event_states)):
            curr_states = event_states[i][1]
            curr_suggestions = event_states[i][2]
            prev_dp = dp[-1]

            curr_dp = []
            for j, state in enumerate(curr_states):
                non_open = [f for s, f in state if f > 0]
                has_non_open = len(non_open) > 0
                state_centroid = sum(non_open) / len(non_open) if has_non_open else None

                best_cost = float("inf")
                best_centroid = 5.0
                best_path = []

                for prev_cost, prev_centroid, prev_path in prev_dp:
                    curr_centroid = state_centroid if has_non_open else prev_centroid

                    state_cost = 0.0
                    if has_non_open:
                        span = max(non_open) - min(non_open)
                        if span > 4:
                            state_cost += 15.0
                        for f in non_open:
                            dist = abs(f - curr_centroid)
                            if dist <= 4:
                                state_cost += 1.0 * dist
                            else:
                                state_cost += 4.0 + 20.0 * (dist - 4.0)

                    if curr_suggestions:
                        for idx, (s, f) in enumerate(state):
                            if idx < len(curr_suggestions):
                                s_sug, f_sug = curr_suggestions[idx]
                                if s != s_sug or f != f_sug:
                                    state_cost += 5.0

                    # transition cost
                    dist = abs(curr_centroid - prev_centroid)
                    trans_cost = 2.0 * dist
                    if dist > 4:
                        trans_cost += 50.0

                    total_cost = prev_cost + trans_cost + state_cost
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_centroid = curr_centroid
                        best_path = prev_path + [j]

                curr_dp.append((best_cost, best_centroid, best_path))
            dp.append(curr_dp)

        # Step 3: Backtrack and update score objects in place
        final_dp = dp[-1]
        best_idx = 0
        min_final_cost = float("inf")
        for j, (cost, _, _) in enumerate(final_dp):
            if cost < min_final_cost:
                min_final_cost = cost
                best_idx = j

        optimal_path = final_dp[best_idx][2]

        for i, (event, states, _) in enumerate(event_states):
            opt_state = states[optimal_path[i]]
            for idx, note in enumerate(event.notes):
                if idx < len(opt_state):
                    s, f = opt_state[idx]
                    note.string = s
                    note.fret = f
                    # Update pitch to match optimized string and fret
                    open_pitch = tuning.pitch_for_string(s)
                    if open_pitch is not None:
                        note.pitch = open_pitch + f
