from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List
from score2gp.pdf_geometry_candidates import GeometryCandidateSet, XAlignedPrimitiveClusterCandidate

class EighthRestCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    cluster: XAlignedPrimitiveClusterCandidate

class SixteenthRestCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    cluster: XAlignedPrimitiveClusterCandidate

def extract_eighth_sixteenth_rest_candidates(
    geometry: GeometryCandidateSet,
    staff_spacing: float,
    staff_center_y: float
) -> tuple[List[EighthRestCandidate], List[SixteenthRestCandidate]]:
    eighths = []
    sixteenths = []

    if staff_spacing <= 0.0:
        return eighths, sixteenths

    for cluster in geometry.x_aligned_clusters:
        # Eighth and sixteenth rests are often single complex paths/curves or characters
        if cluster.primitive_count != 1:
            continue

        prim = cluster.primitives[0]
        if prim.kind not in ("text_span", "curve"):
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

        # Eighth rests are typically ~1.5 to 2.5 staff spaces high
        # Sixteenth rests are typically ~2.5 to 3.5 staff spaces high

        # Quarter rests overlap heavily with these, but quarter rests are usually taller (2.0 to 4.0)
        # and thinner (aspect ratio > 1.5).
        # Let's use specific heuristics if they differ, but wait, if it's identical, it's hard.
        # Actually, let's just make a simple distinction based on height.
        if aspect_ratio > 1.5:
            # Probably a quarter rest
            continue

        if 1.0 <= height_ratio <= 2.2:
            eighths.append(
                EighthRestCandidate(
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
        elif 2.2 < height_ratio <= 3.8:
            sixteenths.append(
                SixteenthRestCandidate(
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

    return eighths, sixteenths
