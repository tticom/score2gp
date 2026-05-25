from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_VERSION = "0.1.0"
DEFAULT_TICKS_PER_QUARTER = 960


class SourceStage(StrEnum):
    MUSICXML = "musicxml"
    PDF_TEXT = "pdf-text"
    OCR = "ocr"
    INFERRED = "inferred"
    MANUAL = "manual"
    GPIF = "gpif"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def coordinates_are_ordered(self) -> "BoundingBox":
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("bbox must use ordered PDF coordinates: x0 <= x1 and y0 <= y1")
        return self


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_stage: SourceStage = SourceStage.UNKNOWN
    page: int | None = Field(default=None, ge=1)
    system_id: str | None = None
    staff_id: str | None = None
    bar_index: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    raw_token_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Untitled"
    subtitle: str | None = None
    artist: str | None = None
    composer: str | None = None
    album: str | None = None
    transcriber: str | None = None
    copyright: str | None = None
    source: str | None = None


class ConversionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "score2gp"
    tool_version: str | None = None
    conversion_timestamp: str | None = None
    source_file_hash: str | None = None
    source_page_count: int | None = Field(default=None, ge=0)
    audiveris_version: str | None = None


class Tempo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bpm: int = Field(gt=0, le=400)
    text: str | None = None


class TimeSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int = Field(gt=0, le=64)
    denominator: int = Field(gt=0, le=64)

    @model_validator(mode="before")
    @classmethod
    def sanitize_time_signature(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field_name in ("numerator", "denominator"):
                if field_name in data:
                    try:
                        val = int(round(float(data[field_name])))
                        data[field_name] = max(1, min(64, val))
                    except (ValueError, TypeError):
                        pass
        return data

    @field_validator("denominator")
    @classmethod
    def denominator_is_power_of_two(cls, value: int) -> int:
        if value & (value - 1):
            raise ValueError("time signature denominator must be a power of two")
        return value


class KeySignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fifths: int = Field(ge=-7, le=7)
    mode: str = "major"


class TuningString(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=12)
    pitch: int = Field(ge=0, le=127)
    name: str
    volume_offset: float | None = None
    fine_tune: float | None = None


class Tuning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    strings: list[TuningString] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def string_numbers_are_unique(self) -> "Tuning":
        numbers = [string.number for string in self.strings]
        if len(numbers) != len(set(numbers)):
            raise ValueError("tuning string numbers must be unique")
        return self

    def pitch_for_string(self, number: int) -> int | None:
        for string in self.strings:
            if string.number == number:
                return string.pitch
        return None


class Mixer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    mute: bool = False
    solo: bool = False


class SoundConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    path: str | None = None
    midi_port: int = Field(default=1, ge=1)
    midi_channel: int | None = Field(default=None, ge=1, le=16)
    midi_program: int | None = Field(default=None, ge=0, le=127)


class TrackLayoutPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab_only: bool = False
    stem_direction: Literal["auto", "up", "down"] | None = None
    line_sizing: Literal["standard", "small", "large"] | None = None
    view_mode: Literal["page", "screen", "horizontal", "vertical"] | None = None


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    instrument: str = "guitar"
    tuning: Tuning
    capo: int = Field(default=0, ge=0, le=24)
    tablature_enabled: bool = True
    staff_count: int = Field(default=1, ge=1, le=4)
    midi_program: int | None = Field(default=None, ge=0, le=127)
    midi_channel: int | None = Field(default=None, ge=1, le=16)
    mixer: Mixer | None = None
    color: str | None = None
    systems_layout: int | None = Field(default=None, ge=1, le=3)
    sound: SoundConfig | None = None
    layout_preferences: TrackLayoutPreferences | None = None



class NotatedDuration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th", "128th"]
    dots: int = Field(default=0, ge=0, le=4)


class Tuplet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_notes: int = Field(gt=0, le=64)
    normal_notes: int = Field(gt=0, le=64)


class GraceTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Literal["before", "on-beat", "after"] = "before"
    slash: bool = False
    duration_ticks: int = Field(default=0, ge=0)


class Timing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bar_index: int = Field(ge=1)
    onset_ticks: int = Field(ge=0)
    duration_ticks: int = Field(ge=0)
    ticks_per_quarter: int = Field(default=DEFAULT_TICKS_PER_QUARTER, gt=0)
    voice: int = Field(default=1, ge=1, le=8)
    notated_duration: NotatedDuration | None = None
    tuplet: Tuplet | None = None
    grace: GraceTiming | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_timing_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field_name in ("onset_ticks", "duration_ticks", "ticks_per_quarter", "bar_index", "voice"):
                if field_name in data:
                    try:
                        val = int(round(float(data[field_name])))
                        if field_name in ("onset_ticks", "duration_ticks"):
                            data[field_name] = max(0, val)
                        elif field_name == "ticks_per_quarter":
                            data[field_name] = max(1, val)
                        elif field_name == "bar_index":
                            data[field_name] = max(1, val)
                        elif field_name == "voice":
                            data[field_name] = max(1, min(8, val))
                    except (ValueError, TypeError):
                        pass
        return data

    @model_validator(mode="after")
    def duration_is_positive_unless_grace(self) -> "Timing":
        if self.duration_ticks == 0 and self.grace is None:
            raise ValueError("duration_ticks must be positive unless grace timing is present")
        return self


class SlideTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["slide"] = "slide"
    style: Literal["shift", "legato", "slide-in", "slide-out", "glissando", "grace", "unknown"] = "unknown"
    direction: Literal["up", "down", "unknown"] = "unknown"
    target_event_id: str | None = None
    glissando: bool = False
    flags: int | None = None


class BendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset_ticks: int = Field(ge=0)
    semitones: float = Field(ge=-12.0, le=12.0)


class BendTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["bend"] = "bend"
    semitones: float | None = Field(default=None, ge=-12.0, le=12.0)
    points: list[BendPoint] = Field(default_factory=list)
    text: str | None = None


class VibratoCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: float = Field(ge=0.0, le=1.0)
    value: float = Field(ge=0.0, le=1.0)
    speed: Literal["slow", "medium", "fast", "unknown"] = "unknown"


class VibratoCurve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[VibratoCurvePoint] = Field(default_factory=list)


class VibratoTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["vibrato"] = "vibrato"
    width: Literal["narrow", "wide", "unknown"] = "unknown"
    speed: Literal["slow", "medium", "fast", "unknown"] = "unknown"
    curve: VibratoCurve | None = None


class HammerOnTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["hammer-on"] = "hammer-on"
    target_event_id: str | None = None
    style: str | None = None
    flags: int | None = None
    legato: bool | None = None


class PullOffTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["pull-off"] = "pull-off"
    target_event_id: str | None = None
    style: str | None = None
    flags: int | None = None
    legato: bool | None = None


class TieTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tie"] = "tie"
    state: Literal["start", "stop", "continue"]
    target_event_id: str | None = None


class SlurTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["slur"] = "slur"
    state: Literal["start", "stop", "continue"]
    target_event_id: str | None = None


class LetRingTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["let-ring"] = "let-ring"
    end_event_id: str | None = None


class PalmMuteTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["palm-mute"] = "palm-mute"
    end_event_id: str | None = None


class GraceTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["grace"] = "grace"
    slash: bool = False
    timing: GraceTiming | None = None


class TremoloBarPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: float = Field(ge=0.0, le=1.0)
    value: float = Field(ge=-12.0, le=12.0)


class TremoloBarTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tremolo-bar"] = "tremolo-bar"
    points: list[TremoloBarPoint] = Field(default_factory=list)


class TremoloPickingTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tremolo-picking"] = "tremolo-picking"
    duration: Literal["eighth", "16th", "32nd", "64th", "unknown"] = "16th"


class SlapTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["slap"] = "slap"


class PopTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["pop"] = "pop"


class TappingTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tapping"] = "tapping"


class TrillTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["trill"] = "trill"
    fret: int | None = Field(default=None, ge=0, le=36)
    interval: int | None = Field(default=None, ge=0, le=24)


class UnsupportedTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unsupported"] = "unsupported"
    label: str
    reason: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


Technique = Annotated[
    SlideTechnique
    | BendTechnique
    | VibratoTechnique
    | HammerOnTechnique
    | PullOffTechnique
    | TieTechnique
    | SlurTechnique
    | LetRingTechnique
    | PalmMuteTechnique
    | GraceTechnique
    | TremoloBarTechnique
    | TremoloPickingTechnique
    | SlapTechnique
    | PopTechnique
    | TappingTechnique
    | TrillTechnique
    | UnsupportedTechnique,
    Field(discriminator="kind"),
]


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")

    string: int = Field(ge=1, le=12)
    fret: int = Field(ge=0, le=36)
    pitch: int = Field(ge=0, le=127)
    is_dead: bool = False
    articulations: list[Literal["staccato", "accent", "marcato", "tenuto"]] = Field(default_factory=list)
    techniques: list[Technique] = Field(default_factory=list)
    left_hand_fingering: str | None = None
    right_hand_fingering: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[Provenance] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sanitize_note_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "string" in data:
                try:
                    val = int(round(float(data["string"])))
                    data["string"] = max(1, min(12, val))
                except (ValueError, TypeError):
                    pass
            if "fret" in data:
                try:
                    val = int(round(float(data["fret"])))
                    data["fret"] = max(0, min(36, val))
                except (ValueError, TypeError):
                    pass
            if "pitch" in data:
                try:
                    val = int(round(float(data["pitch"])))
                    data["pitch"] = max(0, min(127, val))
                except (ValueError, TypeError):
                    pass
        return data


class ChordFret(BaseModel):
    model_config = ConfigDict(extra="forbid")

    string: int = Field(ge=1, le=12)
    fret: int = Field(ge=0, le=36)


class ChordFinger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    string: int = Field(ge=1, le=12)
    fret: int = Field(ge=0, le=36)
    finger: Literal["None", "Index", "Middle", "Ring", "Little", "Thumb"] = "None"


class ChordDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    string_count: int = Field(default=6, ge=1, le=12)
    fret_count: int = Field(default=5, ge=1, le=24)
    base_fret: int = Field(default=0, ge=0, le=36)
    frets: list[ChordFret] = Field(default_factory=list)
    fingers: list[ChordFinger] = Field(default_factory=list)
    key_note_step: str = "C"
    key_note_accidental: str = "Natural"
    bass_note_step: str = "C"
    bass_note_accidental: str = "Natural"


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    track_id: str
    timing: Timing
    notes: list[Note] = Field(default_factory=list)
    is_rest: bool = False
    chord_symbol: str | None = None
    chord_diagram: ChordDiagram | None = None
    dynamic: str | None = None
    hairpin: Literal["crescendo", "decrescendo", "diminuendo", "stop", "none"] | None = None
    fermata: Literal["standard", "short", "long", "none"] | None = None
    arpeggio: Literal["up", "down", "none"] | None = None
    arpeggio_duration: Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th", "128th"] | None = None
    brush: Literal["up", "down", "none"] | None = None
    brush_duration: Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th", "128th"] | None = None
    text: str | None = None
    techniques: list[Technique] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[Provenance] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sanitize_event(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "notes" in data and not isinstance(data["notes"], list):
                raise ValueError("notes must be a valid JSON array")
            if "techniques" in data and not isinstance(data["techniques"], list):
                raise ValueError("techniques must be a valid JSON array")
        return data

    @model_validator(mode="after")
    def rest_note_consistency(self) -> "Event":
        if self.is_rest and self.notes:
            raise ValueError(f"event {self.id} is a rest and must not contain notes")
        if not self.is_rest and not self.notes:
            raise ValueError(f"event {self.id} is not a rest and must contain at least one note")
        return self


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    time_signature: TimeSignature
    key_signature: KeySignature | None = None
    events: list[Event] = Field(default_factory=list)
    tempo: Tempo | None = None
    layout_break: Literal["line", "page", "none"] | None = None
    anacrusis: bool = False
    barline: Literal["regular", "double", "end", "section", "repeat-start", "repeat-end"] | None = None
    repeat_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_bar(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "events" in data and not isinstance(data["events"], list):
                raise ValueError("events must be a valid JSON array")
        return data


class WarningItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    provenance: list[Provenance] = Field(default_factory=list)


class PageMargins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float = Field(default=15.0, ge=0.0)
    bottom: float = Field(default=15.0, ge=0.0)
    left: float = Field(default=15.0, ge=0.0)
    right: float = Field(default=15.0, ge=0.0)


class PageSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: float = Field(default=210.0, gt=0.0)
    height: float = Field(default=297.0, gt=0.0)
    margins: PageMargins = Field(default_factory=PageMargins)
    scale: float = Field(default=1.0, gt=0.0)


class ScoreViewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["page", "screen", "horizontal", "vertical"] = "page"
    scroll_speed: float | None = None


class ScorePrintSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    print_title: bool = True
    print_subtitle: bool = True
    print_artist: bool = True
    print_composer: bool = True
    print_transcriber: bool = True
    print_copyright: bool = True
    print_page_numbering: bool = True
    print_multi_track: bool = False


class SystemPageMargins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float = Field(default=10.0, ge=0.0)
    bottom: float = Field(default=10.0, ge=0.0)
    left: float = Field(default=10.0, ge=0.0)
    right: float = Field(default=10.0, ge=0.0)


class EngravingBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: float = Field(default=180.0, gt=0.0)
    height: float = Field(default=260.0, gt=0.0)


class EnsembleBracket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_ids: list[str] = Field(default_factory=list)
    style: Literal["brace", "bracket", "line", "none"] = "bracket"


class ScoreLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_setup: PageSetup = Field(default_factory=PageSetup)
    track_order: list[str] = Field(default_factory=list)
    score_systems_layout: int = Field(default=4, ge=1, le=4)
    view: ScoreViewConfig | None = None
    print_setup: ScorePrintSetup | None = None
    system_page_margins: SystemPageMargins | None = None
    engraving_boundaries: EngravingBoundaries | None = None
    ensemble_brackets: list[EnsembleBracket] | None = None


class ScoreIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    metadata: Metadata = Field(default_factory=Metadata)
    conversion: ConversionInfo = Field(default_factory=ConversionInfo)
    tempo: Tempo
    tracks: list[Track] = Field(min_length=1)
    bars: list[Bar] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
    layout: ScoreLayout = Field(default_factory=ScoreLayout)


    @model_validator(mode="before")
    @classmethod
    def sanitize_score_ir(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tracks" in data and not isinstance(data["tracks"], list):
                raise ValueError("tracks must be a valid JSON array")
            if "bars" in data and not isinstance(data["bars"], list):
                raise ValueError("bars must be a valid JSON array")
            if "warnings" in data and not isinstance(data["warnings"], list):
                raise ValueError("warnings must be a valid JSON array")
        return data

    @model_validator(mode="after")
    def semantic_contract_is_valid(self) -> "ScoreIR":
        errors = self.semantic_errors()
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ScoreIR":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def semantic_errors(self) -> list[str]:
        errors: list[str] = []
        track_map = {track.id: track for track in self.tracks}
        if len(track_map) != len(self.tracks):
            errors.append("track IDs must be unique")

        bar_map = {bar.index: bar for bar in self.bars}
        if len(bar_map) != len(self.bars):
            errors.append("bar indexes must be unique")

        all_events = [event for bar in self.bars for event in bar.events]
        event_ids = {event.id for event in all_events}
        if len(event_ids) != len(all_events):
            errors.append("event IDs must be unique")

        events_by_voice: dict[tuple[str, int, int], list[Event]] = {}
        for bar in self.bars:
            for event in bar.events:
                if event.track_id not in track_map:
                    errors.append(f"event '{event.id}' references unknown track '{event.track_id}'")
                    continue

                if event.timing.bar_index != bar.index:
                    errors.append(
                        f"event '{event.id}' is stored in bar {bar.index} but timing.bar_index is {event.timing.bar_index}"
                    )

                bar_length = _bar_length_ticks(bar.time_signature, event.timing.ticks_per_quarter)
                event_end = event.timing.onset_ticks + event.timing.duration_ticks
                if event.timing.grace is None and event_end > bar_length:
                    errors.append(
                        f"event '{event.id}' exceeds bar {bar.index}: ends at tick {event_end}, bar length is {bar_length}"
                    )

                track = track_map[event.track_id]
                for note in event.notes:
                    open_pitch = track.tuning.pitch_for_string(note.string)
                    if open_pitch is None:
                        errors.append(
                            f"event '{event.id}' uses string {note.string}, but track '{track.id}' tuning does not define it"
                        )
                        continue
                    expected_pitch = open_pitch + note.fret
                    if note.pitch != expected_pitch:
                        errors.append(
                            f"event '{event.id}' note string {note.string} fret {note.fret} has pitch {note.pitch}; "
                            f"expected {expected_pitch} from tuning"
                        )

                _validate_technique_links(event.id, event.techniques, event_ids, errors)
                for note in event.notes:
                    _validate_technique_links(event.id, note.techniques, event_ids, errors)

                if event.timing.duration_ticks > 0:
                    key = (event.track_id, bar.index, event.timing.voice)
                    events_by_voice.setdefault(key, []).append(event)

        for (track_id, bar_index, voice), events in events_by_voice.items():
            ordered = sorted(events, key=lambda item: (item.timing.onset_ticks, item.id))
            for previous, current in zip(ordered, ordered[1:]):
                previous_end = previous.timing.onset_ticks + previous.timing.duration_ticks
                if previous_end > current.timing.onset_ticks:
                    errors.append(
                        f"events '{previous.id}' and '{current.id}' overlap on track '{track_id}', "
                        f"bar {bar_index}, voice {voice}"
                    )

        return errors


def _bar_length_ticks(time_signature: TimeSignature, ticks_per_quarter: int) -> int:
    return int(time_signature.numerator * ticks_per_quarter * 4 / time_signature.denominator)


def _validate_technique_links(
    event_id: str,
    techniques: list[Technique],
    known_event_ids: set[str],
    errors: list[str],
) -> None:
    for technique in techniques:
        target = getattr(technique, "target_event_id", None) or getattr(technique, "end_event_id", None)
        if target is not None and target not in known_event_ids:
            errors.append(
                f"event '{event_id}' technique '{technique.kind}' references unknown event '{target}'"
            )


def format_validation_errors(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        prefix = f"{location}: " if location else ""
        message = str(error["msg"])
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        messages.append(f"{prefix}{message}")
    return messages


def validate_score_ir_file(path: str | Path) -> tuple[ScoreIR | None, list[str]]:
    try:
        return ScoreIR.from_json_file(path), []
    except ValidationError as exc:
        return None, format_validation_errors(exc)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    except OSError as exc:
        return None, [str(exc)]


def scoreir_schema() -> dict[str, Any]:
    schema = ScoreIR.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/scoreir.v0.1.schema.json"
    schema["title"] = "ScoreIR v0.1"
    return schema


def export_scoreir_schema(out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "scoreir.v0.1.schema.json"
    path.write_text(json.dumps(scoreir_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def semantic_scoreir_summary(score: ScoreIR) -> dict[str, Any]:
    return {
        "schema_version": score.schema_version,
        "metadata": score.metadata.model_dump(exclude_none=True),
        "tempo": score.tempo.model_dump(exclude_none=True),
        "layout": score.layout.model_dump() if getattr(score, "layout", None) else None,
        "tracks": [
            {
                "id": track.id,
                "name": track.name,
                "instrument": track.instrument,
                "tuning": track.tuning.model_dump(),
                "capo": track.capo,
                "tablature_enabled": track.tablature_enabled,
                "staff_count": track.staff_count,
                "midi_program": track.midi_program,
                "midi_channel": track.midi_channel,
                "mixer": track.mixer.model_dump() if track.mixer else None,
                "color": track.color,
                "systems_layout": getattr(track, "systems_layout", None),
            }
            for track in score.tracks
        ],
        "bars": [
            {
                "index": bar.index,
                "time_signature": bar.time_signature.model_dump(),
                "key_signature": bar.key_signature.model_dump() if bar.key_signature else None,
                "tempo": bar.tempo.model_dump() if bar.tempo else None,
                "layout_break": bar.layout_break,
                "anacrusis": bar.anacrusis,
                "barline": bar.barline,
                "repeat_count": bar.repeat_count,
                "events": [
                    {
                        "id": event.id,
                        "track_id": event.track_id,
                        "timing": event.timing.model_dump(exclude_none=True),
                        "is_rest": event.is_rest,
                        "chord_symbol": event.chord_symbol,
                        "dynamic": event.dynamic,
                        "hairpin": event.hairpin,
                        "fermata": getattr(event, "fermata", None),
                        "arpeggio": getattr(event, "arpeggio", None),
                        "arpeggio_duration": getattr(event, "arpeggio_duration", None),
                        "brush": getattr(event, "brush", None),
                        "brush_duration": getattr(event, "brush_duration", None),
                        "text": event.text,
                        "notes": [note.model_dump(exclude_none=True, exclude={"provenance"}) for note in event.notes],
                        "techniques": [technique.model_dump(exclude_none=True) for technique in event.techniques],
                    }
                    for event in sorted(bar.events, key=lambda item: (item.timing.onset_ticks, item.id))
                ],
            }
            for bar in sorted(score.bars, key=lambda item: item.index)
        ],
    }


def compare_score_ir(expected: str | Path, actual: str | Path) -> dict[str, Any]:
    expected_score, expected_errors = validate_score_ir_file(expected)
    actual_score, actual_errors = validate_score_ir_file(actual)
    if expected_errors or actual_errors:
        return {
            "expected": str(expected),
            "actual": str(actual),
            "matches": False,
            "errors": {"expected": expected_errors, "actual": actual_errors},
            "differences": {},
        }

    assert expected_score is not None
    assert actual_score is not None
    expected_summary = semantic_scoreir_summary(expected_score)
    actual_summary = semantic_scoreir_summary(actual_score)
    differences = {
        key: {"expected": expected_summary[key], "actual": actual_summary[key]}
        for key in expected_summary
        if expected_summary[key] != actual_summary.get(key)
    }
    return {
        "expected": str(expected),
        "actual": str(actual),
        "matches": not differences,
        "errors": {},
        "differences": differences,
    }
