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
from .musicxml import MusicXmlHarmony, MusicXmlImport, MusicXmlMeasure, MusicXmlNote, MusicXmlPart, MusicXmlTechnique, parse_musicxml
from .tabraw import TabCandidate, TabRaw

TRACK_ID = "gtr-1"
DIAGNOSTICS_SCHEMA_VERSION = "build-ir-diagnostics.v0.1"


class BarAlignmentDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bar_index: int
    musicxml_event_count: int
    musicxml_pitched_event_count: int
    musicxml_rest_event_count: int
    scoreir_event_count: int
    matched_candidate_count: int
    unmatched_musicxml_event_count: int
    unmatched_musicxml_note_count: int
    unmatched_tabraw_candidate_count: int
    chord_event_count: int
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
        per_bar.append(
            BarAlignmentDiagnostics(
                bar_index=bar.index,
                musicxml_event_count=len(musicxml_groups),
                musicxml_pitched_event_count=sum(1 for group in musicxml_groups if not group[0].is_rest),
                musicxml_rest_event_count=sum(1 for group in musicxml_groups if group[0].is_rest),
                scoreir_event_count=len(bar.events),
                matched_candidate_count=len(candidate_pools.consumed_in_bar(bar.index)),
                unmatched_musicxml_event_count=sum(1 for warning in bar_warnings if warning.code == "scoreir-event-skipped"),
                unmatched_musicxml_note_count=sum(1 for warning in bar_warnings if warning.code == "tab-candidate-missing"),
                unmatched_tabraw_candidate_count=sum(1 for candidate in candidate_pools.unused() if candidate.bar_index == bar.index),
                chord_event_count=sum(1 for group in musicxml_groups if len(group) > 1),
                average_event_confidence=round(sum(event_confidences) / len(event_confidences), 3) if event_confidences else None,
                ambiguity_flags=ambiguity_flags,
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
        extraction_quality_flags=_tabraw_extraction_quality_flags(tabraw),
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
