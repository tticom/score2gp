from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Schema version constants
OBSERVATIONS_SCHEMA_VERSION = "document_observations.v0.1"
TOPOLOGY_SCHEMA_VERSION = "document_topology.v0.1"
GRAPH_SCHEMA_VERSION = "recognition_graph.v0.1"
RESOLUTION_SCHEMA_VERSION = "resolution_result.v0.1"
MUSICAL_DOCUMENT_SCHEMA_VERSION = "musical_document.v0.1"


# ---------------------------------------------------------------------------
# Common Primitives and Provenance
# ---------------------------------------------------------------------------

class SourceModality(StrEnum):
    VECTOR = "vector"
    TEXT = "text"
    RASTER = "raster"
    HYBRID = "hybrid"


class Point2D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class BoundingBox2D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def coordinates_are_ordered(self) -> "BoundingBox2D":
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError(
                f"bbox must use ordered coordinates: x0 ({self.x0}) <= x1 ({self.x1}) "
                f"and y0 ({self.y0}) <= y1 ({self.y1})"
            )
        return self


class ScaleEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notation_staff_space: float | None = None
    tab_string_space: float | None = None
    stroke_thickness: float | None = None
    glyph_scale: float | None = None
    dpi: float | None = None


class ObservationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str | None = None
    source_hash: str | None = None
    page_index: int = Field(ge=1)
    raw_primitive_id: str | None = None
    acquisition_adapter: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 1: DocumentObservations
# Invariant: MUST NOT contain any musical assignments (pitch, duration, rhythm,
# clef, key, tempo) or staff associations (staff index, string number, bar/measure).
# ---------------------------------------------------------------------------

FORBIDDEN_OBSERVATION_SEMANTIC_KEYS = {
    "pitch",
    "duration",
    "duration_ticks",
    "rhythm",
    "clef",
    "key_signature",
    "time_signature",
    "tempo",
    "string",
    "string_number",
    "fret",
    "bar_index",
    "measure_index",
    "event_id",
    "staff_index",
    "staff_id",
}


def _assert_no_forbidden_semantics(data: dict[str, Any], context: str) -> None:
    found = FORBIDDEN_OBSERVATION_SEMANTIC_KEYS.intersection(data.keys())
    if found:
        raise ValueError(
            f"Observation semantic leakage rejected in {context}: "
            f"forbidden keys found {sorted(found)}. "
            f"Observations must describe raw physical facts only."
        )


class VectorPathObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provenance: ObservationProvenance
    bbox: BoundingBox2D
    path_type: Literal["line", "curve", "rect", "polygon", "path"]
    points: list[Point2D] = Field(default_factory=list)
    stroke_width: float | None = None
    stroke_color: str | None = None
    fill_color: str | None = None
    is_closed: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_semantic_leakage(self) -> "VectorPathObservation":
        _assert_no_forbidden_semantics(self.extra, f"VectorPathObservation(id='{self.id}') extra")
        return self


class TextObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provenance: ObservationProvenance
    bbox: BoundingBox2D
    raw_text: str
    font_name: str | None = None
    font_size: float | None = None
    character_bboxes: list[BoundingBox2D] = Field(default_factory=list)
    reading_direction: Literal["horizontal_lr", "horizontal_rl", "vertical_tb"] = "horizontal_lr"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_semantic_leakage(self) -> "TextObservation":
        _assert_no_forbidden_semantics(self.extra, f"TextObservation(id='{self.id}') extra")
        return self


class RasterObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provenance: ObservationProvenance
    bbox: BoundingBox2D
    resolution_dpi: float = Field(gt=0)
    pixel_width: int = Field(gt=0)
    pixel_height: int = Field(gt=0)
    color_channels: int = Field(default=1, ge=1, le=4)
    feature_type: Literal["page_crop", "staff_crop", "glyph_crop", "region"] = "region"
    raster_ref: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_semantic_leakage(self) -> "RasterObservation":
        _assert_no_forbidden_semantics(self.extra, f"RasterObservation(id='{self.id}') extra")
        return self


class DocumentObservations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["document_observations.v0.1"] = OBSERVATIONS_SCHEMA_VERSION
    document_id: str
    source_file: str | None = None
    page_count: int = Field(ge=1)
    vectors: list[VectorPathObservation] = Field(default_factory=list)
    texts: list[TextObservation] = Field(default_factory=list)
    rasters: list[RasterObservation] = Field(default_factory=list)
    scale_estimates: dict[str, ScaleEstimate] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def observation_ids_are_unique(self) -> "DocumentObservations":
        ids: set[str] = set()
        for group, items in [
            ("vector", self.vectors),
            ("text", self.texts),
            ("raster", self.rasters),
        ]:
            for obs in items:
                if obs.id in ids:
                    raise ValueError(f"Duplicate observation id '{obs.id}' in {group} observations")
                ids.add(obs.id)
        _assert_no_forbidden_semantics(self.metadata, "DocumentObservations metadata")
        return self


# ---------------------------------------------------------------------------
# Stage 3 & 4: DocumentTopology
# Structured layout: Pages, Systems, Staff Regions, Staff Pairings, Physical Divisions.
# Invariant: Exposes no measure, duration, pitch, or final-event semantics.
# ---------------------------------------------------------------------------

class StaffKind(StrEnum):
    NOTATION = "notation"
    TAB = "tab"
    UNKNOWN = "unknown"


class StaffLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    y_position: float
    x_start: float
    x_end: float
    stroke_width: float | None = None


class StaffRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    system_id: str
    staff_kind: StaffKind
    line_count: int = Field(ge=1, le=12)
    bbox: BoundingBox2D
    lines: list[StaffLine] = Field(default_factory=list)
    staff_space: float | None = None
    observation_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class StaffPairing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    system_id: str
    notation_staff_id: str | None = None
    tab_staff_id: str | None = None
    pairing_kind: Literal["paired_notation_tab", "standalone_notation", "standalone_tab"]
    vertical_gap: float | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PhysicalDivision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    system_id: str
    staff_region_ids: list[str] = Field(default_factory=list)
    x: float
    y_top: float
    y_bottom: float
    division_style: Literal[
        "single", "double", "repeat_start", "repeat_end", "final", "dashed", "dotted", "floating"
    ] = "single"
    stroke_thickness: float | None = None
    observation_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SystemTopology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    bbox: BoundingBox2D
    staff_region_ids: list[str] = Field(default_factory=list)
    pairing_ids: list[str] = Field(default_factory=list)
    division_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PageTopology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    content_bbox: BoundingBox2D | None = None
    system_ids: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)


class DocumentTopology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["document_topology.v0.1"] = TOPOLOGY_SCHEMA_VERSION
    document_id: str
    pages: list[PageTopology] = Field(default_factory=list)
    systems: list[SystemTopology] = Field(default_factory=list)
    staves: list[StaffRegion] = Field(default_factory=list)
    pairings: list[StaffPairing] = Field(default_factory=list)
    divisions: list[PhysicalDivision] = Field(default_factory=list)
    competing_hypotheses: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_topology_references(self) -> "DocumentTopology":
        page_indices = {p.page_index for p in self.pages}
        system_ids = {s.id for s in self.systems}
        staff_ids = {st.id for st in self.staves}
        pairing_ids = {p.id for p in self.pairings}
        division_ids = {d.id for d in self.divisions}

        # Check unique IDs
        if len(system_ids) != len(self.systems):
            raise ValueError("System IDs in DocumentTopology must be unique")
        if len(staff_ids) != len(self.staves):
            raise ValueError("Staff IDs in DocumentTopology must be unique")
        if len(pairing_ids) != len(self.pairings):
            raise ValueError("Pairing IDs in DocumentTopology must be unique")
        if len(division_ids) != len(self.divisions):
            raise ValueError("Division IDs in DocumentTopology must be unique")

        # Validate Page references
        for p in self.pages:
            for s_id in p.system_ids:
                if s_id not in system_ids:
                    raise ValueError(f"Page {p.page_index} references missing system_id '{s_id}'")
            for ro_id in p.reading_order:
                if ro_id not in system_ids:
                    raise ValueError(f"Page {p.page_index} reading order references missing system_id '{ro_id}'")

        # Validate System references
        for s in self.systems:
            if s.page_index not in page_indices and self.pages:
                raise ValueError(f"System '{s.id}' references missing page_index {s.page_index}")
            for st_id in s.staff_region_ids:
                if st_id not in staff_ids:
                    raise ValueError(f"System '{s.id}' references missing staff_region_id '{st_id}'")
            for p_id in s.pairing_ids:
                if p_id not in pairing_ids:
                    raise ValueError(f"System '{s.id}' references missing pairing_id '{p_id}'")
            for d_id in s.division_ids:
                if d_id not in division_ids:
                    raise ValueError(f"System '{s.id}' references missing division_id '{d_id}'")

        # Validate Staff references
        for st in self.staves:
            if st.system_id not in system_ids and self.systems:
                raise ValueError(f"Staff '{st.id}' references missing system_id '{st.system_id}'")

        # Validate Pairing references
        for pr in self.pairings:
            if pr.system_id not in system_ids and self.systems:
                raise ValueError(f"Pairing '{pr.id}' references missing system_id '{pr.system_id}'")
            if pr.notation_staff_id and pr.notation_staff_id not in staff_ids:
                raise ValueError(f"Pairing '{pr.id}' references missing notation_staff_id '{pr.notation_staff_id}'")
            if pr.tab_staff_id and pr.tab_staff_id not in staff_ids:
                raise ValueError(f"Pairing '{pr.id}' references missing tab_staff_id '{pr.tab_staff_id}'")

        # Validate Division references
        for div in self.divisions:
            if div.system_id not in system_ids and self.systems:
                raise ValueError(f"Division '{div.id}' references missing system_id '{div.system_id}'")
            for st_id in div.staff_region_ids:
                if st_id not in staff_ids:
                    raise ValueError(f"Division '{div.id}' references missing staff_region_id '{st_id}'")

        return self


# ---------------------------------------------------------------------------
# Stage 6: RecognitionGraph
# Typed graph of nodes and bounded relations with explicit competing hypotheses.
# Invariant: Every relation MUST reference existing node IDs in the graph.
# ---------------------------------------------------------------------------

class GraphNodeKind(StrEnum):
    OBSERVATION_REF = "observation_ref"
    TAB_DIGIT = "tab_digit"
    NOTEHEAD = "notehead"
    STEM = "stem"
    BEAM = "beam"
    FLAG = "flag"
    REST = "rest"
    ACCIDENTAL = "accidental"
    AUGMENTATION_DOT = "augmentation_dot"
    TIE = "tie"
    SLUR = "slur"
    CLEF = "clef"
    TIME_SIGNATURE = "time_signature"
    KEY_SIGNATURE = "key_signature"
    CHORD_SYMBOL = "chord_symbol"
    TECHNIQUE_GLYPH = "technique_glyph"
    BARLINE = "barline"
    REPEAT_SIGN = "repeat_sign"
    SECTION_HEADER = "section_header"
    TEMPO_TEXT = "tempo_text"
    LYRIC_TEXT = "lyric_text"
    COMPETING_CLUSTER = "competing_cluster"


class GraphRelationKind(StrEnum):
    IN_STAFF = "in_staff"
    IN_SYSTEM = "in_system"
    ATTACHED_TO_STEM = "attached_to_stem"
    SAME_ONSET = "same_onset"
    CONFLICTS_WITH = "conflicts_with"
    CONTAINS = "contains"
    ALIGNED_WITH = "aligned_with"
    BEAMED_WITH = "beamed_with"
    TIED_TO = "tied_to"
    SLURRED_TO = "slurred_to"
    ATTACHED_TO_NOTE = "attached_to_note"
    PRECEDES = "precedes"
    BELONGS_TO_CLUSTER = "belongs_to_cluster"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: GraphNodeKind
    bbox: BoundingBox2D | None = None
    page_index: int | None = Field(default=None, ge=1)
    system_id: str | None = None
    staff_id: str | None = None
    source_observation_ids: list[str] = Field(default_factory=list)
    parent_hypothesis_ids: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    candidate_values: list[Any] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Literal["active", "rejected", "provisional"] = "provisional"


class GraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_id: str
    target_id: str
    kind: GraphRelationKind
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RecognitionGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["recognition_graph.v0.1"] = GRAPH_SCHEMA_VERSION
    document_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)
    competing_clusters: list[list[str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def graph_invariants(self) -> "RecognitionGraph":
        node_ids = {n.id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Graph node IDs must be unique")

        rel_ids = {r.id for r in self.relations}
        if len(rel_ids) != len(self.relations):
            raise ValueError("Graph relation IDs must be unique")

        # Invariant: Relations must reference existing nodes
        for rel in self.relations:
            if rel.source_id not in node_ids:
                raise ValueError(
                    f"Graph relation '{rel.id}' references non-existent source node '{rel.source_id}'"
                )
            if rel.target_id not in node_ids:
                raise ValueError(
                    f"Graph relation '{rel.id}' references non-existent target node '{rel.target_id}'"
                )

        # Invariant: Competing clusters must reference existing nodes
        for cluster in self.competing_clusters:
            for n_id in cluster:
                if n_id not in node_ids:
                    raise ValueError(
                        f"Competing cluster references non-existent node '{n_id}'"
                    )

        return self


# ---------------------------------------------------------------------------
# Stage 7: ResolutionResult
# The four explicit resolution outcomes: RESOLVED, AMBIGUOUS, UNSUPPORTED, CONTRADICTORY.
# ---------------------------------------------------------------------------

class ResolutionOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"


class ResolutionScope(StrEnum):
    DOCUMENT = "document"
    SYSTEM = "system"
    STAFF = "staff"
    MEASURE = "measure"
    VOICE = "voice"
    EVENT = "event"
    NODE = "node"


class ConstraintViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    constraint_name: str
    is_hard_constraint: bool = True
    description: str
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_scope: ResolutionScope = ResolutionScope.MEASURE
    scope_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ScopedResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: ResolutionScope
    scope_id: str
    outcome: ResolutionOutcome
    accepted_node_ids: list[str] = Field(default_factory=list)
    rejected_node_ids: list[str] = Field(default_factory=list)
    violations: list[ConstraintViolation] = Field(default_factory=list)
    abstention_reason: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["resolution_result.v0.1"] = RESOLUTION_SCHEMA_VERSION
    document_id: str
    overall_outcome: ResolutionOutcome
    is_success: bool
    scoped_resolutions: list[ScopedResolution] = Field(default_factory=list)
    all_accepted_node_ids: list[str] = Field(default_factory=list)
    all_rejected_node_ids: list[str] = Field(default_factory=list)
    all_violations: list[ConstraintViolation] = Field(default_factory=list)
    summary_diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def outcome_consistency(self) -> "ResolutionResult":
        expected_success = self.overall_outcome == ResolutionOutcome.RESOLVED
        if self.is_success != expected_success:
            raise ValueError(
                f"ResolutionResult.is_success ({self.is_success}) inconsistent with "
                f"overall_outcome ({self.overall_outcome}). Expected is_success={expected_success}."
            )
        return self


# ---------------------------------------------------------------------------
# Stage 8: MusicalDocument
# Typed domain output decoupled from geometry and layout, ready for ScoreIR compilation.
# ---------------------------------------------------------------------------

class FingeringProvenance(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"


class TuningDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "Standard"
    strings: list[int] = Field(default_factory=lambda: [64, 59, 55, 50, 45, 40])


class MusicalNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    string: int = Field(ge=1, le=12)
    fret: int = Field(ge=0, le=36)
    pitch: int = Field(ge=0, le=127)
    is_tie_destination: bool = False
    left_hand_finger: str | None = None
    right_hand_finger: str | None = None
    fingering_provenance: FingeringProvenance = FingeringProvenance.OBSERVED
    source_node_ids: list[str] = Field(default_factory=list)


class MusicalTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onset_ticks: int = Field(ge=0)
    duration_ticks: int = Field(gt=0)
    ticks_per_quarter: int = Field(default=960, gt=0)
    voice: int = Field(default=1, ge=1, le=8)
    is_triplet_or_tuplet: bool = False
    tuplet_ratio: str | None = None


class MusicalTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "slide",
        "bend",
        "vibrato",
        "hammer_on",
        "pull_off",
        "tap",
        "harmonic",
        "palm_mute",
        "let_ring",
    ]
    details: dict[str, Any] = Field(default_factory=dict)
    source_node_ids: list[str] = Field(default_factory=list)


class MusicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    track_id: str
    measure_index: int = Field(ge=1)
    timing: MusicalTiming
    is_rest: bool = False
    notes: list[MusicalNote] = Field(default_factory=list)
    chord_symbol: str | None = None
    techniques: list[MusicalTechnique] = Field(default_factory=list)
    dynamic: str | None = None
    text: str | None = None
    source_node_ids: list[str] = Field(default_factory=list)


class MusicalTimeSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int = Field(ge=1, le=64)
    denominator: int = Field(ge=1, le=64)


class MusicalKeySignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fifths: int = Field(ge=-7, le=7)
    mode: Literal["major", "minor"] = "major"


class MusicalTempo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bpm: int = Field(ge=20, le=400)
    text: str | None = None


class MusicalMeasure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    time_signature: MusicalTimeSignature
    key_signature: MusicalKeySignature | None = None
    tempo: MusicalTempo | None = None
    barline_type: Literal[
        "regular", "double", "repeat_start", "repeat_end", "final"
    ] = "regular"
    repeat_count: int | None = None
    alternate_ending: int | None = None
    section_header: str | None = None
    events: list[MusicalEvent] = Field(default_factory=list)
    source_division_ids: list[str] = Field(default_factory=list)


class MusicalTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = "Guitar"
    instrument: str = "Acoustic Guitar"
    tuning: TuningDefinition = Field(default_factory=TuningDefinition)
    capo: int = Field(default=0, ge=0, le=12)
    staff_count: int = Field(default=2, ge=1, le=4)
    has_tablature: bool = True
    has_standard_notation: bool = True
    midi_program: int = Field(default=25, ge=0, le=127)


class MusicalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Untitled"
    subtitle: str | None = None
    artist: str | None = None
    album: str | None = None
    composer: str | None = None
    transcriber: str | None = None
    copyright: str | None = None
    source_pdf: str | None = None


class MusicalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["musical_document.v0.1"] = MUSICAL_DOCUMENT_SCHEMA_VERSION
    document_id: str
    metadata: MusicalMetadata = Field(default_factory=MusicalMetadata)
    tracks: list[MusicalTrack] = Field(default_factory=list)
    measures: list[MusicalMeasure] = Field(default_factory=list)
    resolution_provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def musical_document_invariants(self) -> "MusicalDocument":
        track_ids = {t.id for t in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ValueError("Track IDs in MusicalDocument must be unique")

        measure_indices: set[int] = set()
        for measure in self.measures:
            if measure.index in measure_indices:
                raise ValueError(f"Duplicate measure index {measure.index} in MusicalDocument")
            measure_indices.add(measure.index)

            for event in measure.events:
                if event.track_id not in track_ids and self.tracks:
                    raise ValueError(
                        f"Event '{event.id}' in measure {measure.index} references unknown track '{event.track_id}'"
                    )
                if event.measure_index != measure.index:
                    raise ValueError(
                        f"Event '{event.id}' measure_index ({event.measure_index}) does not match "
                        f"containing measure index ({measure.index})"
                    )

        return self


# ---------------------------------------------------------------------------
# Schema Generation and Validation Utilities
# ---------------------------------------------------------------------------

def document_observations_schema() -> dict[str, Any]:
    schema = DocumentObservations.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/document_observations.v0.1.schema.json"
    schema["title"] = "DocumentObservations v0.1"
    return schema


def document_topology_schema() -> dict[str, Any]:
    schema = DocumentTopology.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/document_topology.v0.1.schema.json"
    schema["title"] = "DocumentTopology v0.1"
    return schema


def recognition_graph_schema() -> dict[str, Any]:
    schema = RecognitionGraph.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/recognition_graph.v0.1.schema.json"
    schema["title"] = "RecognitionGraph v0.1"
    return schema


def resolution_result_schema() -> dict[str, Any]:
    schema = ResolutionResult.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/resolution_result.v0.1.schema.json"
    schema["title"] = "ResolutionResult v0.1"
    return schema


def musical_document_schema() -> dict[str, Any]:
    schema = MusicalDocument.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/tticom/score2gp/schemas/musical_document.v0.1.schema.json"
    schema["title"] = "MusicalDocument v0.1"
    return schema


RECOGNITION_SCHEMA_FACTORIES = {
    "document_observations.v0.1.schema.json": document_observations_schema,
    "document_topology.v0.1.schema.json": document_topology_schema,
    "recognition_graph.v0.1.schema.json": recognition_graph_schema,
    "resolution_result.v0.1.schema.json": resolution_result_schema,
    "musical_document.v0.1.schema.json": musical_document_schema,
}


def export_recognition_schemas(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for filename, factory in RECOGNITION_SCHEMA_FACTORIES.items():
        path = out / filename
        path.write_text(
            json.dumps(factory(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exported.append(path)
    return exported


def validate_recognition_payload(
    data: dict[str, Any] | str | Path,
    contract_cls: type[BaseModel],
) -> tuple[BaseModel | None, list[str]]:
    try:
        if isinstance(data, (str, Path)):
            text = Path(data).read_text(encoding="utf-8")
            raw_data = json.loads(text)
        else:
            raw_data = data
        instance = contract_cls.model_validate(raw_data)
        return instance, []
    except ValidationError as exc:
        errors: list[str] = []
        for err in exc.errors():
            loc = " -> ".join(str(elem) for elem in err.get("loc", []))
            msg = err.get("msg", "validation error")
            errors.append(f"[{loc}]: {msg}")
        return None, errors
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"Payload loading failed: {exc}"]
