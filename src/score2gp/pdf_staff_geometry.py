from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

class NotationStaffGeometry(BaseModel):
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
    model_config = ConfigDict(frozen=True)

    line_count: int
    curve_count: int
    rect_count: int
    text_span_count_by_font: dict[str, int]

class NotationStaffMorphology(BaseModel):
    model_config = ConfigDict(frozen=True)

    staff_line_horizontal: int
    non_staff_horizontal: int
    vertical_stroke_candidate: int
    diagonal_stroke_candidate: int
    rectangle_candidate: int
    curve_candidate: int
    text_span_by_font: dict[str, int]

class ClusterPrimitiveCountSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    lines_total: int
    curves_total: int
    rects_total: int
    text_spans_total: int

class XAlignedClusterAggregateDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    x_aligned_cluster_count: int
    max_primitives_per_x_aligned_cluster: int
    clusters_with_vertical_stroke_candidate: int
    max_cluster_vertical_span_staff_spaces: float
    cluster_primitive_count_summary: ClusterPrimitiveCountSummary

class NotationStaffDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    staff: NotationStaffGeometry
    primitives: LocalPrimitivesSummary
    morphology: NotationStaffMorphology | None = None
    clustering: XAlignedClusterAggregateDiagnostics | None = None

class PdfStaffNotationGeometryDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    staves: list[NotationStaffDiagnostics]
    status: str | None = "success"
