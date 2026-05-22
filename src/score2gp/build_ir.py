from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .ascii_alignment import ALIGNMENT_SCHEMA_VERSION, AsciiMusicXmlAlignment
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
        return {
            "schema_version": "build-ir-failure-diagnostics.v0.1",
            "stage": self.stage,
            "category": self.category,
            "message": str(self),
            "timing_issue_count": len(self.timing_issues),
            "timing_issue_counts": dict(sorted(issue_counts.items())),
            "timing_issues": [issue.model_dump(mode="json", exclude_none=True) for issue in self.timing_issues],
            "details": self.details,
        }


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
) -> ScoreIR:
    try:
        score, diagnostics = build_ir_with_diagnostics_from_files(
            musicxml_path,
            tabraw_path,
            out_path,
            ascii_alignment_path=ascii_alignment_path,
        )
        if diagnostics_out_path is not None:
            diagnostics.to_json_file(diagnostics_out_path)
        return score
    except BuildIrInputRiskError as exc:
        if diagnostics_out_path is not None:
            import json
            payload = exc.to_diagnostics_payload()
            out_path_p = Path(diagnostics_out_path)
            out_path_p.parent.mkdir(parents=True, exist_ok=True)
            out_path_p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            if exc.stage == "ascii-scoreir-gate":
                from .report import write_ascii_gate_diagnostics_html
                html_path = out_path_p.parent / "ascii-scoreir-gate-diagnostics.html"
                write_ascii_gate_diagnostics_html(html_path, payload, json_path_ref=out_path_p.name)
        raise



def build_ir_with_diagnostics_from_files(
    musicxml_path: str | Path,
    tabraw_path: str | Path,
    out_path: str | Path | None = None,
    ascii_alignment_path: str | Path | None = None,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    musicxml = parse_musicxml(musicxml_path)
    tabraw = TabRaw.from_json_file(tabraw_path)
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
    score, diagnostics = build_ir_with_diagnostics_from_imports(musicxml, tabraw, ascii_gate_details=ascii_gate_details)
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
    mappings_by_candidate = {mapping.candidate_id: mapping for mapping in alignment.candidate_mappings}
    compatible_mappings = [mapping for mapping in alignment.candidate_mappings if mapping.result == "compatible"]
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
        reason_codes = ["missing_ascii_alignment_sidecar"]
        category = "missing_ascii_alignment_sidecar"
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
    details.update(
        {
            "ascii_scoreir_gate_status": "refused",
            "reason_codes": deduped or [primary],
            "primary_reason_code": primary,
            "secondary_reason_codes": deduped[1:],
            "rejected_candidate_count": candidate_count,
            "output_event_count": 0,
            "scoreir_written": False,
            "expected_next_remediation": _ascii_gate_remediation(primary),
        }
    )


def _ascii_alignment_status_reason(status: str) -> str:
    if status in {"unavailable", "partial", "ambiguous", "incompatible"}:
        return f"ascii_alignment_status_{status}"
    return "ascii_outside_tiny_gate_scope"


def _ascii_gate_remediation(reason_code: str) -> str:
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


def build_ir_from_imports(musicxml: MusicXmlImport, tabraw: TabRaw) -> ScoreIR:
    score, _ = build_ir_with_diagnostics_from_imports(musicxml, tabraw)
    return score


def build_ir_with_diagnostics_from_imports(
    musicxml: MusicXmlImport,
    tabraw: TabRaw,
    *,
    ascii_gate_details: dict[str, object] | None = None,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    warnings = _musicxml_warnings(musicxml)
    timing_issues = analyze_musicxml_timing(musicxml)
    warnings.extend(_musicxml_timing_issue_warnings(timing_issues))
    fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
    if fatal_timing_issues:
        raise BuildIrInputRiskError(
            category="musicxml_timing_risk",
            stage="musicxml-import",
            message=(
                "MusicXML timing risk prevents ScoreIR output: "
                f"{len(fatal_timing_issues)} overfull or overlapping event(s) would violate ScoreIR timing."
            ),
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
        for measure in part.measures:
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
    diagnostics = _build_diagnostics(musicxml, tabraw, score, candidate_pools, ascii_gate_details=ascii_gate_details)
    return score, diagnostics


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
            warnings.append(_event_warning("musicxml-grace-skipped", first, "Grace note is skipped in this phase."))
            continue

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

    return Note(
        string=candidate.string,
        fret=candidate.parsed_fret,
        pitch=candidate_pitch,
        techniques=_note_techniques(xml_note),
        confidence=confidence,
        provenance=[_musicxml_provenance(xml_note, measure), tab_provenance],
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
    groups = []
    for group in _note_groups(notes):
        first = group[0]
        if first.grace or first.duration_divisions <= 0:
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
    if not playable:
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
        counts["grouping_status"] = "partial"
        counts["category"] = "partial_pdf_grouping"
        counts["warning_codes"] = unsafe_codes
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
        }
    ]
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
                # Span/link technique requires exactly two notes in the bar
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

                # Ensure notes are in chronological order (which they are, because events are sorted)
                note1, note2 = notes
                event1 = next(ev for ev in bar.events if note1 in ev.notes)
                event2 = next(ev for ev in bar.events if note2 in ev.notes)

                # Ensure they are at different onset times
                if event1.timing.onset_ticks >= event2.timing.onset_ticks:
                    score.warnings.append(
                        WarningItem(
                            code="ambiguous_technique_attachment",
                            message=f"Span technique '{candidate.raw_text}' endpoints are not sequential in bar {bar_idx}.",
                            severity="warning",
                            provenance=[candidate.to_provenance()],
                        )
                    )
                    continue

                # Unambiguous: attach to note1 targeting event2.id
                if kind == "hammer-on":
                    tech = HammerOnTechnique(kind="hammer-on", target_event_id=event2.id)
                else:
                    tech = PullOffTechnique(kind="pull-off", target_event_id=event2.id)

                note1.techniques.append(tech)
                note1.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)

            else:
                # Slide, Bend, Vibrato require exactly one note in the bar
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

                # Unambiguous: attach to the single note
                target_note = notes[0]
                if kind == "slide":
                    tech = SlideTechnique(kind="slide", style="unknown", direction="unknown", target_event_id=None)
                elif kind == "bend":
                    tech = BendTechnique(kind="bend", semitones=None, points=[], text=None)
                else:
                    tech = VibratoTechnique(kind="vibrato", width="unknown", speed="unknown")

                target_note.techniques.append(tech)
                target_note.provenance.append(candidate.to_provenance())
                _remove_not_aligned_warning(score, candidate)
