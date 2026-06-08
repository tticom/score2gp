from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

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

class XAlignedClusterAggregateDiagnostics(BaseModel):
    """
    Geometric statistics for x-aligned clusters of primitives (e.g. circles grouped with stems).
    This layer does not assign semantic meaning, only spatial grouping.
    """
    model_config = ConfigDict(frozen=True)

    x_aligned_cluster_count: int = Field(ge=0)
    max_primitives_per_x_aligned_cluster: int = Field(ge=0)
    clusters_with_vertical_stroke_candidate: int = Field(ge=0)
    max_cluster_vertical_span_staff_spaces: float = Field(ge=0.0)
    cluster_primitive_count_summary: ClusterPrimitiveCountSummary

class StaffLeftMarginAggregateDiagnostics(BaseModel):
    """
    Diagnostics for primitives falling within the extreme left margin of the staff,
    typically used for initial margin marker shapes.
    """
    model_config = ConfigDict(frozen=True)

    margin_x_threshold_staff_spaces: float = Field(ge=0.0)
    text_span_count: int = Field(ge=0)
    distinct_font_count: int = Field(ge=0)
    max_text_spans_for_single_font: int = Field(ge=0)
    curve_candidate_count: int = Field(ge=0)
    vertical_stroke_candidate_count: int = Field(ge=0)
    rectangle_candidate_count: int = Field(ge=0)

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

class PdfStaffNotationGeometryDiagnostics(BaseModel):
    """
    Top-level payload containing diagnostic details for all identified staves.
    """
    model_config = ConfigDict(frozen=True)

    staves: list[NotationStaffDiagnostics]
    status: str | None = "success"
