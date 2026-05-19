from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

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
from .musicxml import MusicXmlImport, MusicXmlMeasure, MusicXmlNote, parse_musicxml
from .tabraw import TabCandidate, TabRaw

TRACK_ID = "gtr-1"


def build_ir_from_files(musicxml_path: str | Path, tabraw_path: str | Path, out_path: str | Path | None = None) -> ScoreIR:
    musicxml = parse_musicxml(musicxml_path)
    tabraw = TabRaw.from_json_file(tabraw_path)
    score = build_ir_from_imports(musicxml, tabraw)
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        score.to_json_file(out)
    return score


def build_ir_from_imports(musicxml: MusicXmlImport, tabraw: TabRaw) -> ScoreIR:
    warnings = _musicxml_warnings(musicxml)
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

    candidate_map = _candidate_map(tabraw)
    bars: list[Bar] = []
    if part is not None:
        for measure in part.measures:
            bar_warnings: list[WarningItem] = []
            events = _measure_events(measure, candidate_map, bar_warnings)
            warnings.extend(bar_warnings)
            bars.append(
                Bar(
                    index=measure.index,
                    time_signature=measure.time_signature,
                    key_signature=KeySignature(fifths=measure.key_fifths) if measure.key_fifths is not None else None,
                    events=events,
                )
            )

    return ScoreIR(
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


def _measure_events(
    measure: MusicXmlMeasure,
    candidate_map: dict[int | None, list[TabCandidate]],
    warnings: list[WarningItem],
) -> list[Event]:
    events: list[Event] = []
    candidate_pool = candidate_map.get(measure.index)
    if not candidate_pool:
        candidate_pool = candidate_map.get(None, [])

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

        timing = _timing(first, measure, duration_ticks)
        event_id = f"mx-m{measure.index}-e{group_index}"
        if first.is_rest:
            events.append(
                Event(
                    id=event_id,
                    track_id=TRACK_ID,
                    timing=timing,
                    is_rest=True,
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
            candidate = _pop_candidate(candidate_pool)
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

    return Note(
        string=candidate.string,
        fret=candidate.parsed_fret,
        pitch=candidate_pitch,
        techniques=_tie_techniques(xml_note),
        confidence=confidence,
        provenance=[_musicxml_provenance(xml_note, measure), candidate.to_provenance()],
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


def _candidate_map(tabraw: TabRaw) -> dict[int | None, list[TabCandidate]]:
    candidates: dict[int | None, list[TabCandidate]] = defaultdict(list)
    for candidate in tabraw.candidates:
        if candidate.parsed_fret is not None:
            candidates[candidate.bar_index].append(candidate)
    for pool in candidates.values():
        pool.sort(key=lambda candidate: (float("inf") if candidate.x is None else candidate.x, candidate.id))
    return candidates


def _pop_candidate(pool: list[TabCandidate]) -> TabCandidate | None:
    return pool.pop(0) if pool else None


def _timing(note: MusicXmlNote, measure: MusicXmlMeasure, duration_ticks: int) -> Timing:
    onset_ticks = int(note.onset_divisions * DEFAULT_TICKS_PER_QUARTER / measure.divisions)
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


def _tie_techniques(note: MusicXmlNote) -> list[Technique]:
    if "start" in note.ties and "stop" in note.ties:
        return [{"kind": "tie", "state": "continue"}]  # type: ignore[return-value]
    if "start" in note.ties:
        return [{"kind": "tie", "state": "start"}]  # type: ignore[return-value]
    if "stop" in note.ties:
        return [{"kind": "tie", "state": "stop"}]  # type: ignore[return-value]
    return []


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
