from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class BuildIrInputRiskError(ValueError):
    """Raised when input timing/grouping risk would produce invalid ScoreIR."""

    def __init__(
        self,
        *,
        category: str,
        stage: str,
        message: str,
        timing_issues: list[MusicXmlTimingIssue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.stage = stage
        self.timing_issues = timing_issues or []

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
    unsupported_construct_warnings: list[str] = Field(default_factory=list)
    warning_count: int
    confidence_flags: list[dict[str, object]] = Field(default_factory=list)
    extraction_quality_flags: list[str] = Field(default_factory=list)
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
) -> ScoreIR:
    score, diagnostics = build_ir_with_diagnostics_from_files(musicxml_path, tabraw_path, out_path)
    if diagnostics_out_path is not None:
        diagnostics.to_json_file(diagnostics_out_path)
    return score


def build_ir_with_diagnostics_from_files(
    musicxml_path: str | Path,
    tabraw_path: str | Path,
    out_path: str | Path | None = None,
) -> tuple[ScoreIR, BuildIrDiagnostics]:
    musicxml = parse_musicxml(musicxml_path)
    tabraw = TabRaw.from_json_file(tabraw_path)
    score, diagnostics = build_ir_with_diagnostics_from_imports(musicxml, tabraw)
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        score.to_json_file(out)
    return score, diagnostics


def build_ir_from_imports(musicxml: MusicXmlImport, tabraw: TabRaw) -> ScoreIR:
    score, _ = build_ir_with_diagnostics_from_imports(musicxml, tabraw)
    return score


def build_ir_with_diagnostics_from_imports(musicxml: MusicXmlImport, tabraw: TabRaw) -> tuple[ScoreIR, BuildIrDiagnostics]:
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
    diagnostics = _build_diagnostics(musicxml, tabraw, score, candidate_pools)
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
    tab_provenance.raw["alignment_strategy"] = "bar-x-order"
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
            pool.sort(key=lambda candidate: (float("inf") if candidate.x is None else candidate.x, candidate.id))
        return cls(pools=dict(pools))

    def pop(self, bar_index: int, *, event_id: str, musicxml_note_id: str) -> TabCandidate | None:
        for key in (bar_index, None):
            pool = self.pools.get(key)
            if pool:
                candidate = pool.pop(0)
                self.consumed.append(
                    CandidateUse(
                        candidate=candidate,
                        requested_bar_index=bar_index,
                        source_pool_bar_index=key,
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
        unsupported_construct_warnings=[
            code
            for code in warning_codes
            if code.startswith("unsupported-") or code in {"musicxml-grace-skipped", "musicxml-harmony-unattached"}
        ],
        warning_count=len(warnings),
        confidence_flags=confidence_flags,
        extraction_quality_flags=_tabraw_extraction_quality_flags(tabraw) + _alignment_quality_flags(per_bar),
        per_system=_system_diagnostics(tabraw, candidate_pools),
        per_bar=per_bar,
        warnings=[warning.model_dump(mode="json", exclude_none=True) for warning in warnings],
    )


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
