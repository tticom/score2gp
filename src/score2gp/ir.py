from __future__ import annotations

from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Technique(StrEnum):
    SLIDE = "slide"
    BEND = "bend"
    VIBRATO = "vibrato"
    HAMMER_ON = "hammer-on"
    PULL_OFF = "pull-off"
    LET_RING = "let-ring"
    GRACE = "grace"
    TUPLET = "tuplet"
    TIE = "tie"
    SLUR = "slur"


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
            raise ValueError("bounding box coordinates must be ordered")
        return self


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Untitled"
    artist: str | None = None
    copyright: str | None = None


class Tempo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bpm: int = Field(gt=0, le=400)
    text: str | None = None


class TimeSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int = Field(gt=0, le=64)
    denominator: int = Field(gt=0, le=64)

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


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    instrument: str = "guitar"
    tuning: Tuning


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")

    string: int = Field(ge=1, le=12)
    fret: int = Field(ge=0, le=36)
    pitch: int = Field(ge=0, le=127)
    duration: str | None = None
    voice: int | None = Field(default=None, ge=1, le=8)
    tie: str | None = Field(default=None, pattern="^(start|stop|continue)$")
    slur: str | None = Field(default=None, pattern="^(start|stop|continue)$")
    techniques: list[Technique] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: SourceRef | None = None


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    track_id: str
    voice: int = Field(default=1, ge=1, le=8)
    position: str
    duration: str
    notes: list[Note] = Field(default_factory=list)
    is_rest: bool = False
    chord_symbol: str | None = None
    techniques: list[Technique] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: SourceRef | None = None

    @field_validator("position", "duration")
    @classmethod
    def fraction_string(cls, value: str) -> str:
        Fraction(value)
        return value

    @model_validator(mode="after")
    def event_has_content(self) -> "Event":
        if not self.is_rest and not self.notes:
            raise ValueError("non-rest events must contain at least one note")
        return self


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    time_signature: TimeSignature
    key_signature: KeySignature | None = None
    events: list[Event] = Field(default_factory=list)


class WarningItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: str = Field(default="warning", pattern="^(info|warning|error)$")
    source: SourceRef | None = None


class ScoreIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1.0"
    metadata: Metadata = Field(default_factory=Metadata)
    tempo: Tempo
    tracks: list[Track] = Field(min_length=1)
    bars: list[Bar] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def events_reference_tracks(self) -> "ScoreIR":
        track_ids = {track.id for track in self.tracks}
        missing = {
            event.track_id
            for bar in self.bars
            for event in bar.events
            if event.track_id not in track_ids
        }
        if missing:
            raise ValueError(f"events reference unknown tracks: {sorted(missing)}")
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ScoreIR":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
