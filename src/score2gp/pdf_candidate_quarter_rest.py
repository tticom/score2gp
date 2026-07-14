from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List
from score2gp.pdf_geometry_candidates import GeometryCandidateSet, XAlignedPrimitiveClusterCandidate

class QuarterRestCandidate(BaseModel):
    """
    A semantic candidate representing a quarter rest identified from stable body geometry.
    """
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    # Link back to the original geometry cluster
    cluster: XAlignedPrimitiveClusterCandidate

    @model_validator(mode="after")
    def validate_bounds(self) -> QuarterRestCandidate:
        if self.x0 > self.x1:
            raise ValueError(f"x0 ({self.x0}) must be <= x1 ({self.x1})")
        if self.y0 > self.y1:
            raise ValueError(f"y0 ({self.y0}) must be <= y1 ({self.y1})")
        return self

def extract_quarter_rest_candidates(
    geometry: GeometryCandidateSet,
    staff_spacing: float,
    staff_center_y: float
) -> List[QuarterRestCandidate]:
    """
    Extracts quarter rest candidates from x_aligned_clusters based on isolation and bounding box proportion heuristics.
    """
    candidates = []

    if staff_spacing <= 0.0:
        return []

    for cluster in geometry.x_aligned_clusters:
        # Rule 1: Isolation (must be exactly 1 primitive, of kind text_span, curve, or vertical_stroke)
        if cluster.primitive_count != 1:
            continue
            
        prim = cluster.primitives[0]
        if prim.kind not in ("text_span", "curve", "vertical_stroke"):
            continue
        if prim.kind == "text_span":
            font = (getattr(prim, "font_name", "") or "").lower()
            if any(f in font for f in ("times", "arial", "helvetica", "calibri", "georgia", "courier", "verdana", "cambria")):
                continue

        c_height = prim.y1 - prim.y0
        c_width = prim.x1 - prim.x0

        if c_height <= 0.0 or c_width <= 0.0:
            continue

        height_ratio = c_height / staff_spacing
        aspect_ratio = c_height / c_width
        c_center_y = (prim.y0 + prim.y1) / 2.0

        # Rule 2: Height Ratio (between 2.0 and 4.0 staff spaces)
        if not (2.0 <= height_ratio <= 4.0):
            continue

        # Rule 3: Aspect Ratio (taller than wide, > 1.5)
        if aspect_ratio <= 1.5:
            continue

        # Rule 4: Vertical Centering (midpoint within 0.5 staff spaces of staff center)
        if abs(c_center_y - staff_center_y) > (0.5 * staff_spacing):
            continue

        candidates.append(
            QuarterRestCandidate(
                page_index=cluster.page_index,
                system_index=cluster.system_index,
                staff_index=cluster.staff_index,
                x0=prim.x0,
                y0=prim.y0,
                x1=prim.x1,
                y1=prim.y1,
                cluster=cluster
            )
        )

    return candidates
