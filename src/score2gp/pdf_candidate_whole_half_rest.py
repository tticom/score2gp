from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Tuple
from score2gp.pdf_geometry_candidates import GeometryCandidateSet, XAlignedPrimitiveClusterCandidate

class WholeRestCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    cluster: XAlignedPrimitiveClusterCandidate

    @model_validator(mode="after")
    def validate_bounds(self) -> WholeRestCandidate:
        if self.x0 > self.x1:
            raise ValueError(f"x0 ({self.x0}) must be <= x1 ({self.x1})")
        if self.y0 > self.y1:
            raise ValueError(f"y0 ({self.y0}) must be <= y1 ({self.y1})")
        return self

class HalfRestCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    cluster: XAlignedPrimitiveClusterCandidate

    @model_validator(mode="after")
    def validate_bounds(self) -> HalfRestCandidate:
        if self.x0 > self.x1:
            raise ValueError(f"x0 ({self.x0}) must be <= x1 ({self.x1})")
        if self.y0 > self.y1:
            raise ValueError(f"y0 ({self.y0}) must be <= y1 ({self.y1})")
        return self

def extract_whole_half_rest_candidates(
    geometry: GeometryCandidateSet,
    staff_spacing: float,
    staff_center_y: float
) -> Tuple[List[WholeRestCandidate], List[HalfRestCandidate]]:
    whole_rests = []
    half_rests = []

    if staff_spacing <= 0.0:
        return whole_rests, half_rests

    for cluster in geometry.x_aligned_clusters:
        if not (1 <= cluster.primitive_count <= 25):
            continue

        # Check that no primitive is of an illegal kind for a rest
        has_invalid_kind = False
        for p in cluster.primitives:
            if p.kind not in ("text_span", "curve", "vertical_stroke", "rectangle", "horizontal_stroke", "diagonal_stroke"):
                has_invalid_kind = True
                break
        if has_invalid_kind:
            continue

        c_x0 = min(p.x0 for p in cluster.primitives)
        c_x1 = max(p.x1 for p in cluster.primitives)
        c_y0 = min(p.y0 for p in cluster.primitives)
        c_y1 = max(p.y1 for p in cluster.primitives)

        c_height = c_y1 - c_y0
        c_width = c_x1 - c_x0

        if c_height <= 0.0 or c_width <= 0.0:
            continue

        height_ratio = c_height / staff_spacing
        width_ratio = c_width / staff_spacing
        aspect_ratio = c_height / c_width
        c_center_y = (c_y0 + c_y1) / 2.0

        # Heuristic 1: Height ratio (typically ~0.5 staff spacing)
        if not (0.25 <= height_ratio <= 0.75):
            continue

        # Heuristic 2: Width ratio (wider than it is tall, typically >= 0.8 staff spaces)
        if not (0.8 <= width_ratio <= 2.5):
            continue

        # Heuristic 3: Aspect ratio (height to width <= 0.8)
        if aspect_ratio > 0.8:
            continue

        # Heuristic 4: Vertical positioning relative to staff center
        # Whole rest: hangs below line 1 (center_y around staff_center_y - 0.75 * spacing)
        # Half rest: sits above line 2 (center_y around staff_center_y - 0.25 * spacing)
        if (staff_center_y - 1.6 * staff_spacing) <= c_center_y <= (staff_center_y - 0.4 * staff_spacing):
            whole_rests.append(
                WholeRestCandidate(
                    page_index=cluster.page_index,
                    system_index=cluster.system_index,
                    staff_index=cluster.staff_index,
                    x0=c_x0,
                    y0=c_y0,
                    x1=c_x1,
                    y1=c_y1,
                    cluster=cluster
                )
            )
        elif (staff_center_y - 0.4 * staff_spacing) < c_center_y <= (staff_center_y + 0.4 * staff_spacing):
            half_rests.append(
                HalfRestCandidate(
                    page_index=cluster.page_index,
                    system_index=cluster.system_index,
                    staff_index=cluster.staff_index,
                    x0=c_x0,
                    y0=c_y0,
                    x1=c_x1,
                    y1=c_y1,
                    cluster=cluster
                )
            )

    return whole_rests, half_rests
