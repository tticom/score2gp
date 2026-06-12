from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class NotationStaffGeometry(BaseModel):
    """
    Geometric bounding box and basic staff line coordinates for a single staff.
    """
    model_config = ConfigDict(frozen=True)

    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(default=1, ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    line_y_coords: list[float]

    @model_validator(mode="after")
    def validate_bounds(self) -> NotationStaffGeometry:
        assert self.x0 <= self.x1, f"x0 ({self.x0}) must be <= x1 ({self.x1})"
        assert self.y0 <= self.y1, f"y0 ({self.y0}) must be <= y1 ({self.y1})"
        return self

class LocalPrimitivesSummary(BaseModel):
    """
    Raw geometric primitive counts strictly within the staff bounding box.
    """
    model_config = ConfigDict(frozen=True)

    line_count: int
    curve_count: int
    rect_count: int
    text_span_count_by_font: dict[str, int]

class NotationStaffMorphology(BaseModel):
    """
    Initial morphological classification of primitives into shapes like strokes,
    rectangles, or curves, before any clustering occurs.
    """
    model_config = ConfigDict(frozen=True)

    staff_line_horizontal: int
    non_staff_horizontal: int
    vertical_stroke_candidate: int
    diagonal_stroke_candidate: int
    rectangle_candidate: int
    curve_candidate: int
    text_span_by_font: dict[str, int]

class ClusterPrimitiveCountSummary(BaseModel):
    """
    Summary of all primitives contained within any x-aligned cluster.
    Useful for asserting total geometric density of clusters.
    """
    model_config = ConfigDict(frozen=True)

    lines_total: int = Field(ge=0)
    curves_total: int = Field(ge=0)
    rects_total: int = Field(ge=0)
    text_spans_total: int = Field(ge=0)

class PrimitiveGeometryEvidence(BaseModel):
    """
    Evidence array item for a single geometric primitive.
    """
    model_config = ConfigDict(frozen=True)

    x0: float
    y0: float
    x1: float
    y1: float
    kind: Literal["text_span", "curve", "vertical_stroke", "horizontal_stroke", "rectangle", "diagonal_stroke"]
    font_name: str | None = None
    font_size: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> PrimitiveGeometryEvidence:
        assert self.x0 <= self.x1, f"x0 ({self.x0}) must be <= x1 ({self.x1})"
        assert self.y0 <= self.y1, f"y0 ({self.y0}) must be <= y1 ({self.y1})"
        return self

class XAlignedPrimitiveClusterEvidence(BaseModel):
    """
    Evidence array item for a cluster of horizontally-aligned primitives.
    """
    model_config = ConfigDict(frozen=True)

    x0: float
    x1: float
    primitive_count: int
    primitives: list[PrimitiveGeometryEvidence]

    @model_validator(mode="after")
    def validate_state(self) -> XAlignedPrimitiveClusterEvidence:
        assert self.x0 <= self.x1, f"x0 ({self.x0}) must be <= x1 ({self.x1})"
        assert self.primitive_count >= 0, "primitive_count must be non-negative"
        assert self.primitive_count == len(self.primitives), "primitive_count must match length of primitives array"
        return self

class XAlignedClusterAggregateDiagnostics(BaseModel):
    """
    Geometric statistics for x-aligned clusters of primitives (e.g. circular markers grouped with vertical strokes).
    This layer does not assign semantic meaning, only spatial grouping.
    """
    model_config = ConfigDict(frozen=True)

    x_aligned_cluster_count: int = Field(ge=0)
    max_primitives_per_x_aligned_cluster: int = Field(ge=0)
    clusters_with_vertical_stroke_candidate: int = Field(ge=0)
    max_cluster_vertical_span_staff_spaces: float = Field(ge=0.0)
    cluster_primitive_count_summary: ClusterPrimitiveCountSummary
    evidence: list[XAlignedPrimitiveClusterEvidence] | None = None

class StaffLeftMarginAggregateDiagnostics(BaseModel):
    """
    Diagnostics for primitives falling within the extreme left margin of the staff,
    typically used for marker-like geometric shapes near the staff start.
    """
    model_config = ConfigDict(frozen=True)

    margin_x_threshold_staff_spaces: float = Field(ge=0.0)
    text_span_count: int = Field(ge=0)
    distinct_font_count: int = Field(ge=0)
    max_text_spans_for_single_font: int = Field(ge=0)
    curve_candidate_count: int = Field(ge=0)
    vertical_stroke_candidate_count: int = Field(ge=0)
    rectangle_candidate_count: int = Field(ge=0)
    evidence: list[PrimitiveGeometryEvidence] | None = None

class NotationStaffDiagnostics(BaseModel):
    """
    Comprehensive geometric diagnostics for a single notation staff.
    """
    model_config = ConfigDict(frozen=True)

    contract_version: Literal["notation-diagnostics.v0.1"] = "notation-diagnostics.v0.1"
    staff: NotationStaffGeometry
    primitives: LocalPrimitivesSummary
    morphology: NotationStaffMorphology | None = None
    clustering: XAlignedClusterAggregateDiagnostics | None = None
    left_margin: StaffLeftMarginAggregateDiagnostics | None = None
    left_margin_candidates: list[LeftMarginPrimitiveCandidate] | None = None
    x_aligned_cluster_candidates: list[XAlignedPrimitiveClusterCandidate] | None = None

class SystemConnectorDiagnostics(BaseModel):
    """
    Geometry-only diagnostics for evidence connecting multiple staves into a system.
    """
    model_config = ConfigDict(frozen=True)

    connected_staff_indices: list[int]
    connector_kind: Literal["leading_barline", "bracket_curve", "brace_curve"]
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def validate_bounds(self) -> SystemConnectorDiagnostics:
        assert self.x0 <= self.x1, f"x0 ({self.x0}) must be <= x1 ({self.x1})"
        assert self.y0 <= self.y1, f"y0 ({self.y0}) must be <= y1 ({self.y1})"
        return self

class PdfStaffNotationGeometryDiagnostics(BaseModel):
    """
    Top-level payload containing diagnostic details for all identified staves.
    """
    model_config = ConfigDict(frozen=True)

    staves: list[NotationStaffDiagnostics]
    system_connectors: list[SystemConnectorDiagnostics] | None = None
    whole_note_candidates: list[WholeNoteCandidateDiagnostics] | None = None
    status: str | None = "success"

class WholeNoteCandidateDiagnostics(BaseModel):
    """
    Candidate whole-note bounding box extracted directly from vector shapes, independent of
    semantic staff processing. Follows proportional heuristics to exclude stems.
    """
    model_config = ConfigDict(frozen=True)

    bbox: list[float]
    width: float
    height: float
    aspect_ratio: float


# Resolve forward references for candidate types used in NotationStaffDiagnostics.
# This import is deferred to avoid any future circular-import risk.
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate, XAlignedPrimitiveClusterCandidate  # noqa: E402
NotationStaffDiagnostics.model_rebuild()

