from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from score2gp.recognition.schemas import (
    OBSERVATIONS_SCHEMA_VERSION,
    TOPOLOGY_SCHEMA_VERSION,
    GRAPH_SCHEMA_VERSION,
    RESOLUTION_SCHEMA_VERSION,
    MUSICAL_DOCUMENT_SCHEMA_VERSION,
    BoundingBox2D,
    ConstraintViolation,
    DocumentObservations,
    DocumentTopology,
    FingeringProvenance,
    GraphNode,
    GraphNodeKind,
    GraphRelation,
    GraphRelationKind,
    MusicalDocument,
    MusicalEvent,
    MusicalKeySignature,
    MusicalMeasure,
    MusicalMetadata,
    MusicalNote,
    MusicalTechnique,
    MusicalTempo,
    MusicalTimeSignature,
    MusicalTiming,
    MusicalTrack,
    ObservationProvenance,
    PageTopology,
    PhysicalDivision,
    Point2D,
    RasterObservation,
    RecognitionGraph,
    ResolutionOutcome,
    ResolutionResult,
    ResolutionScope,
    ScaleEstimate,
    ScopedResolution,
    SourceModality,
    StaffKind,
    StaffLine,
    StaffPairing,
    StaffRegion,
    SystemTopology,
    TextObservation,
    TuningDefinition,
    VectorPathObservation,
    export_recognition_schemas,
    validate_recognition_payload,
)


# ---------------------------------------------------------------------------
# Fixture Builders
# ---------------------------------------------------------------------------

def sample_bbox(page: int = 1, x0: float = 10.0, y0: float = 20.0, x1: float = 100.0, y1: float = 200.0) -> BoundingBox2D:
    return BoundingBox2D(page_index=page, x0=x0, y0=y0, x1=x1, y1=y1)


def sample_provenance(page: int = 1, prim_id: str = "prim-1") -> ObservationProvenance:
    return ObservationProvenance(
        source_file="test_sample.pdf",
        source_hash="sha256:abc12345",
        page_index=page,
        raw_primitive_id=prim_id,
        acquisition_adapter="vector_extractor_v1",
    )


def sample_observations() -> DocumentObservations:
    prov = sample_provenance()
    return DocumentObservations(
        document_id="doc-test-01",
        source_file="test_sample.pdf",
        page_count=2,
        vectors=[
            VectorPathObservation(
                id="vec-1",
                provenance=prov,
                bbox=sample_bbox(1, 10, 10, 500, 12),
                path_type="line",
                points=[Point2D(x=10, y=10), Point2D(x=500, y=10)],
                stroke_width=1.0,
                stroke_color="#000000",
            ),
            VectorPathObservation(
                id="vec-2",
                provenance=prov,
                bbox=sample_bbox(1, 50, 10, 52, 60),
                path_type="rect",
                stroke_width=1.5,
            ),
        ],
        texts=[
            TextObservation(
                id="txt-1",
                provenance=prov,
                bbox=sample_bbox(1, 100, 20, 110, 30),
                raw_text="12",
                font_name="Helvetica-Bold",
                font_size=10.0,
            ),
        ],
        rasters=[
            RasterObservation(
                id="rast-1",
                provenance=prov,
                bbox=sample_bbox(1, 0, 0, 600, 800),
                resolution_dpi=300.0,
                pixel_width=2500,
                pixel_height=3300,
                feature_type="page_crop",
                raster_ref="sha256:rasterref123",
            ),
        ],
        scale_estimates={
            "page-1": ScaleEstimate(
                notation_staff_space=7.5,
                tab_string_space=9.0,
                stroke_thickness=0.8,
                glyph_scale=1.0,
                dpi=300.0,
            ),
        },
        metadata={"extraction_source": "digital_pdf"},
    )


def sample_topology() -> DocumentTopology:
    staff_not = StaffRegion(
        id="staff-not-1",
        page_index=1,
        system_id="sys-1",
        staff_kind=StaffKind.NOTATION,
        line_count=5,
        bbox=sample_bbox(1, 50, 100, 550, 140),
        lines=[
            StaffLine(index=i, y_position=100.0 + (i - 1) * 10.0, x_start=50.0, x_end=550.0, stroke_width=0.8)
            for i in range(1, 6)
        ],
        staff_space=10.0,
        observation_ids=["vec-1"],
    )
    staff_tab = StaffRegion(
        id="staff-tab-1",
        page_index=1,
        system_id="sys-1",
        staff_kind=StaffKind.TAB,
        line_count=6,
        bbox=sample_bbox(1, 50, 160, 550, 210),
        lines=[
            StaffLine(index=i, y_position=160.0 + (i - 1) * 10.0, x_start=50.0, x_end=550.0, stroke_width=0.8)
            for i in range(1, 7)
        ],
        staff_space=10.0,
    )
    pairing = StaffPairing(
        id="pair-1",
        system_id="sys-1",
        notation_staff_id="staff-not-1",
        tab_staff_id="staff-tab-1",
        pairing_kind="paired_notation_tab",
        vertical_gap=20.0,
    )
    division = PhysicalDivision(
        id="div-1",
        page_index=1,
        system_id="sys-1",
        staff_region_ids=["staff-not-1", "staff-tab-1"],
        x=250.0,
        y_top=100.0,
        y_bottom=210.0,
        division_style="single",
    )
    system = SystemTopology(
        id="sys-1",
        page_index=1,
        system_index=1,
        bbox=sample_bbox(1, 40, 90, 560, 220),
        staff_region_ids=["staff-not-1", "staff-tab-1"],
        pairing_ids=["pair-1"],
        division_ids=["div-1"],
    )
    page = PageTopology(
        page_index=1,
        width=612.0,
        height=792.0,
        content_bbox=sample_bbox(1, 40, 90, 560, 700),
        system_ids=["sys-1"],
        reading_order=["sys-1"],
    )
    return DocumentTopology(
        document_id="doc-test-01",
        pages=[page],
        systems=[system],
        staves=[staff_not, staff_tab],
        pairings=[pairing],
        divisions=[division],
    )


def sample_graph() -> RecognitionGraph:
    node1 = GraphNode(
        id="node-digit-1",
        kind=GraphNodeKind.TAB_DIGIT,
        bbox=sample_bbox(1, 100, 160, 110, 170),
        page_index=1,
        system_id="sys-1",
        staff_id="staff-tab-1",
        source_observation_ids=["txt-1"],
        raw_text="5",
        candidate_values=[5],
        status="active",
    )
    node2 = GraphNode(
        id="node-notehead-1",
        kind=GraphNodeKind.NOTEHEAD,
        bbox=sample_bbox(1, 100, 110, 108, 118),
        page_index=1,
        system_id="sys-1",
        staff_id="staff-not-1",
        status="active",
    )
    node3 = GraphNode(
        id="node-stem-1",
        kind=GraphNodeKind.STEM,
        bbox=sample_bbox(1, 107, 90, 108, 114),
        page_index=1,
        system_id="sys-1",
        staff_id="staff-not-1",
        status="active",
    )
    rel1 = GraphRelation(
        id="rel-1",
        source_id="node-notehead-1",
        target_id="node-stem-1",
        kind=GraphRelationKind.ATTACHED_TO_STEM,
    )
    rel2 = GraphRelation(
        id="rel-2",
        source_id="node-digit-1",
        target_id="node-notehead-1",
        kind=GraphRelationKind.ALIGNED_WITH,
    )
    return RecognitionGraph(
        document_id="doc-test-01",
        nodes=[node1, node2, node3],
        relations=[rel1, rel2],
        competing_clusters=[],
        metadata={"graph_version": 1},
    )


def sample_resolution_result(outcome: ResolutionOutcome = ResolutionOutcome.RESOLVED) -> ResolutionResult:
    is_success = outcome == ResolutionOutcome.RESOLVED
    violations = []
    if not is_success:
        violations.append(
            ConstraintViolation(
                constraint_id="C_TIME_01",
                constraint_name="MeasureDurationIntegrity",
                is_hard_constraint=True,
                description="Total event ticks exceeds measure capacity",
                affected_node_ids=["node-digit-1"],
                affected_scope=ResolutionScope.MEASURE,
                scope_id="m-1",
            )
        )
    scoped = ScopedResolution(
        scope=ResolutionScope.DOCUMENT,
        scope_id="doc-test-01",
        outcome=outcome,
        accepted_node_ids=["node-digit-1", "node-notehead-1"] if is_success else [],
        rejected_node_ids=[] if is_success else ["node-digit-1"],
        violations=violations,
        abstention_reason=None if is_success else "Measure duration integrity violated",
    )
    return ResolutionResult(
        document_id="doc-test-01",
        overall_outcome=outcome,
        is_success=is_success,
        scoped_resolutions=[scoped],
        all_accepted_node_ids=["node-digit-1", "node-notehead-1"] if is_success else [],
        all_rejected_node_ids=[] if is_success else ["node-digit-1"],
        all_violations=violations,
        summary_diagnostics={"total_hypotheses": 3},
    )


def sample_musical_document() -> MusicalDocument:
    note = MusicalNote(
        id="note-1",
        string=1,
        fret=5,
        pitch=69,
        is_tie_destination=False,
        fingering_provenance=FingeringProvenance.OBSERVED,
        source_node_ids=["node-digit-1"],
    )
    event = MusicalEvent(
        id="ev-1",
        track_id="trk-1",
        measure_index=1,
        timing=MusicalTiming(onset_ticks=0, duration_ticks=960, ticks_per_quarter=960, voice=1),
        is_rest=False,
        notes=[note],
        techniques=[
            MusicalTechnique(kind="vibrato", details={"intensity": "wide"}, source_node_ids=["tech-1"])
        ],
    )
    measure = MusicalMeasure(
        index=1,
        time_signature=MusicalTimeSignature(numerator=4, denominator=4),
        key_signature=MusicalKeySignature(fifths=0, mode="major"),
        tempo=MusicalTempo(bpm=120, text="Allegro"),
        barline_type="regular",
        events=[event],
    )
    track = MusicalTrack(
        id="trk-1",
        name="Lead Guitar",
        instrument="Electric Guitar",
        tuning=TuningDefinition(name="Standard", strings=[64, 59, 55, 50, 45, 40]),
        capo=0,
        staff_count=2,
    )
    return MusicalDocument(
        document_id="doc-test-01",
        metadata=MusicalMetadata(title="Sample Solo", artist="Artist"),
        tracks=[track],
        measures=[measure],
        resolution_provenance={"resolver_engine": "constrained_v1"},
    )


# ---------------------------------------------------------------------------
# Schema Snapshots and Export Tests
# ---------------------------------------------------------------------------

def test_exported_recognition_schemas_match_committed(tmp_path: Path) -> None:
    """Verify that export_recognition_schemas outputs match committed schema files."""
    exported_files = export_recognition_schemas(tmp_path)
    assert len(exported_files) == 5

    committed_dir = Path("schemas")
    for exported_path in exported_files:
        filename = exported_path.name
        committed_path = committed_dir / filename
        assert committed_path.exists(), f"Committed schema {committed_path} is missing"

        exported_json = json.loads(exported_path.read_text(encoding="utf-8"))
        committed_json = json.loads(committed_path.read_text(encoding="utf-8"))
        assert exported_json == committed_json, f"Mismatch in schema {filename}"


def test_schema_metadata_conforms_to_draft_2020_12() -> None:
    """Verify JSON schema root metadata."""
    committed_dir = Path("schemas")
    schema_names = [
        "document_observations.v0.1.schema.json",
        "document_topology.v0.1.schema.json",
        "recognition_graph.v0.1.schema.json",
        "resolution_result.v0.1.schema.json",
        "musical_document.v0.1.schema.json",
    ]
    for name in schema_names:
        path = committed_dir / name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert data["$id"].startswith("https://github.com/tticom/score2gp/schemas/")
        assert "title" in data
        assert "properties" in data or "$defs" in data


# ---------------------------------------------------------------------------
# Round-Trip Serialization Tests
# ---------------------------------------------------------------------------

def test_document_observations_roundtrip() -> None:
    obs = sample_observations()
    raw = obs.model_dump()
    reloaded = DocumentObservations.model_validate(raw)
    assert reloaded == obs
    assert reloaded.schema_version == OBSERVATIONS_SCHEMA_VERSION


def test_document_topology_roundtrip() -> None:
    topo = sample_topology()
    raw = topo.model_dump()
    reloaded = DocumentTopology.model_validate(raw)
    assert reloaded == topo
    assert reloaded.schema_version == TOPOLOGY_SCHEMA_VERSION


def test_recognition_graph_roundtrip() -> None:
    graph = sample_graph()
    raw = graph.model_dump()
    reloaded = RecognitionGraph.model_validate(raw)
    assert reloaded == graph
    assert reloaded.schema_version == GRAPH_SCHEMA_VERSION


@pytest.mark.parametrize(
    "outcome",
    [
        ResolutionOutcome.RESOLVED,
        ResolutionOutcome.AMBIGUOUS,
        ResolutionOutcome.UNSUPPORTED,
        ResolutionOutcome.CONTRADICTORY,
    ],
)
def test_resolution_result_roundtrip_all_outcomes(outcome: ResolutionOutcome) -> None:
    res = sample_resolution_result(outcome)
    raw = res.model_dump()
    reloaded = ResolutionResult.model_validate(raw)
    assert reloaded == res
    assert reloaded.schema_version == RESOLUTION_SCHEMA_VERSION
    assert reloaded.overall_outcome == outcome
    assert reloaded.is_success == (outcome == ResolutionOutcome.RESOLVED)


def test_musical_document_roundtrip() -> None:
    doc = sample_musical_document()
    raw = doc.model_dump()
    reloaded = MusicalDocument.model_validate(raw)
    assert reloaded == doc
    assert reloaded.schema_version == MUSICAL_DOCUMENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Negative Tests: Semantic Leakage Prevention
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "forbidden_key",
    [
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
    ],
)
def test_observation_schemas_reject_semantic_assignments(forbidden_key: str) -> None:
    """Observations must strictly reject musical semantic assignments."""
    prov = sample_provenance()
    bbox = sample_bbox()

    # Vector observation extra
    with pytest.raises(ValidationError, match="Observation semantic leakage rejected"):
        VectorPathObservation(
            id="v-bad",
            provenance=prov,
            bbox=bbox,
            path_type="line",
            extra={forbidden_key: 42},
        )

    # Text observation extra
    with pytest.raises(ValidationError, match="Observation semantic leakage rejected"):
        TextObservation(
            id="t-bad",
            provenance=prov,
            bbox=bbox,
            raw_text="5",
            extra={forbidden_key: "semantic_val"},
        )

    # Raster observation extra
    with pytest.raises(ValidationError, match="Observation semantic leakage rejected"):
        RasterObservation(
            id="r-bad",
            provenance=prov,
            bbox=bbox,
            resolution_dpi=300.0,
            pixel_width=100,
            pixel_height=100,
            extra={forbidden_key: 123},
        )


def test_document_observations_rejects_duplicate_ids() -> None:
    prov = sample_provenance()
    bbox = sample_bbox()
    with pytest.raises(ValidationError, match="Duplicate observation id 'obs-dup'"):
        DocumentObservations(
            document_id="doc-dup",
            page_count=1,
            vectors=[
                VectorPathObservation(id="obs-dup", provenance=prov, bbox=bbox, path_type="line"),
            ],
            texts=[
                TextObservation(id="obs-dup", provenance=prov, bbox=bbox, raw_text="dup"),
            ],
        )


# ---------------------------------------------------------------------------
# Negative Tests: Structural & Reference Invariants
# ---------------------------------------------------------------------------

def test_bounding_box_rejects_inverted_coordinates() -> None:
    with pytest.raises(ValidationError, match="bbox must use ordered coordinates"):
        BoundingBox2D(page_index=1, x0=100.0, y0=20.0, x1=50.0, y1=200.0)

    with pytest.raises(ValidationError, match="bbox must use ordered coordinates"):
        BoundingBox2D(page_index=1, x0=10.0, y0=300.0, x1=50.0, y1=200.0)


def test_topology_rejects_dangling_system_reference() -> None:
    topo = sample_topology()
    data = topo.model_dump()
    data["pages"][0]["system_ids"] = ["nonexistent-sys-id"]
    with pytest.raises(ValidationError, match="references missing system_id"):
        DocumentTopology.model_validate(data)


def test_topology_rejects_dangling_staff_reference() -> None:
    topo = sample_topology()
    data = topo.model_dump()
    data["systems"][0]["staff_region_ids"] = ["nonexistent-staff-id"]
    with pytest.raises(ValidationError, match="references missing staff_region_id"):
        DocumentTopology.model_validate(data)


def test_graph_rejects_dangling_relation_source() -> None:
    graph = sample_graph()
    data = graph.model_dump()
    data["relations"].append(
        {
            "id": "rel-dangling",
            "source_id": "nonexistent-node-1",
            "target_id": "node-notehead-1",
            "kind": "in_staff",
            "properties": {},
            "confidence": 1.0,
        }
    )
    with pytest.raises(ValidationError, match="references non-existent source node"):
        RecognitionGraph.model_validate(data)


def test_graph_rejects_dangling_relation_target() -> None:
    graph = sample_graph()
    data = graph.model_dump()
    data["relations"].append(
        {
            "id": "rel-dangling-tgt",
            "source_id": "node-notehead-1",
            "target_id": "nonexistent-node-target",
            "kind": "in_staff",
            "properties": {},
            "confidence": 1.0,
        }
    )
    with pytest.raises(ValidationError, match="references non-existent target node"):
        RecognitionGraph.model_validate(data)


def test_graph_rejects_dangling_competing_cluster_node() -> None:
    graph = sample_graph()
    data = graph.model_dump()
    data["competing_clusters"] = [["node-digit-1", "nonexistent-ghost-node"]]
    with pytest.raises(ValidationError, match="Competing cluster references non-existent node"):
        RecognitionGraph.model_validate(data)


def test_resolution_result_rejects_inconsistent_success_state() -> None:
    with pytest.raises(ValidationError, match="ResolutionResult.is_success"):
        ResolutionResult(
            document_id="doc-1",
            overall_outcome=ResolutionOutcome.AMBIGUOUS,
            is_success=True,  # Inconsistent!
        )

    with pytest.raises(ValidationError, match="ResolutionResult.is_success"):
        ResolutionResult(
            document_id="doc-1",
            overall_outcome=ResolutionOutcome.RESOLVED,
            is_success=False,  # Inconsistent!
        )


def test_musical_document_rejects_unknown_track_reference() -> None:
    doc = sample_musical_document()
    data = doc.model_dump()
    data["measures"][0]["events"][0]["track_id"] = "unknown-track-99"
    with pytest.raises(ValidationError, match="references unknown track 'unknown-track-99'"):
        MusicalDocument.model_validate(data)


def test_musical_document_rejects_event_measure_index_mismatch() -> None:
    doc = sample_musical_document()
    data = doc.model_dump()
    data["measures"][0]["events"][0]["measure_index"] = 2  # Inside measure 1!
    with pytest.raises(ValidationError, match="does not match containing measure index"):
        MusicalDocument.model_validate(data)


def test_musical_document_rejects_duplicate_measure_index() -> None:
    doc = sample_musical_document()
    data = doc.model_dump()
    data["measures"].append(data["measures"][0])
    with pytest.raises(ValidationError, match="Duplicate measure index 1"):
        MusicalDocument.model_validate(data)


# ---------------------------------------------------------------------------
# Payload Validation Helper Tests
# ---------------------------------------------------------------------------

def test_validate_recognition_payload_success() -> None:
    doc = sample_musical_document()
    instance, errors = validate_recognition_payload(doc.model_dump(), MusicalDocument)
    assert instance is not None
    assert not errors
    assert instance.document_id == "doc-test-01"


def test_validate_recognition_payload_failure_returns_readable_errors() -> None:
    bad_data = {"schema_version": "invalid.v999", "document_id": "test"}
    instance, errors = validate_recognition_payload(bad_data, MusicalDocument)
    assert instance is None
    assert len(errors) > 0
    assert any("schema_version" in e for e in errors)
