from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict

PrimitiveEvidenceKind = Literal[
    "text_span",
    "curve",
    "vertical_stroke",
    "horizontal_stroke",
    "diagonal_stroke",
    "rectangle"
]

PrimitiveEvidenceSource = Literal["left_margin", "x_aligned_cluster"]

class PrimitiveEvidenceCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    kind: PrimitiveEvidenceKind
    source: PrimitiveEvidenceSource
    font_name: Optional[str] = None
    font_size: Optional[float] = None

    @model_validator(mode="after")
    def validate_bounds_and_metadata(self) -> "PrimitiveEvidenceCandidate":
        if self.x0 > self.x1:
            raise ValueError("x0 must be <= x1")
        if self.y0 > self.y1:
            raise ValueError("y0 must be <= y1")
        if self.kind != "text_span":
            if self.font_name is not None or self.font_size is not None:
                raise ValueError("font metadata must be absent for non-text candidates")
        if self.font_size is not None and self.font_size < 0:
            raise ValueError("font_size must be non-negative")
        return self

class LeftMarginPrimitiveCandidate(PrimitiveEvidenceCandidate):
    @model_validator(mode="after")
    def validate_source(self) -> "LeftMarginPrimitiveCandidate":
        if self.source != "left_margin":
            raise ValueError("LeftMarginPrimitiveCandidate must have source 'left_margin'")
        return self

class XAlignedPrimitiveClusterCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    x1: float
    primitive_count: int = Field(ge=1)
    primitives: list[PrimitiveEvidenceCandidate]

    @model_validator(mode="after")
    def validate_cluster(self) -> "XAlignedPrimitiveClusterCandidate":
        if self.x0 > self.x1:
            raise ValueError("x0 must be <= x1")
        if self.primitive_count != len(self.primitives):
            raise ValueError("primitive_count must equal length of primitives")
        for p in self.primitives:
            if p.page_index != self.page_index or p.system_index != self.system_index or p.staff_index != self.staff_index:
                raise ValueError("mixed staff identity in cluster primitives")
            if p.source != "x_aligned_cluster":
                raise ValueError("cluster primitives must have source 'x_aligned_cluster'")
        return self

class GeometryCandidateSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    left_margin_primitives: list[LeftMarginPrimitiveCandidate] = Field(default_factory=list)
    x_aligned_clusters: list[XAlignedPrimitiveClusterCandidate] = Field(default_factory=list)
