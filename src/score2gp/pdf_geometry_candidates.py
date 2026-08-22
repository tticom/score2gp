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


class LyricCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

class StructuralSectionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    y_offset: float
    is_bold: bool

    @model_validator(mode="after")
    def check_validity(self) -> "StructuralSectionCandidate":
        if abs(self.y_offset) > 50.0:
            raise ValueError("y_offset exceeds the configured sensible default threshold of 50.0")

        valid = ["Chorus", "Intro", "Verse", "Bridge", "Outro", "Coda", "Da Coda", "Da Capo", "D.S.", "D.C.", "Fine", "Segno", "A", "B", "C", "D", "E"]
        matched = False
        text = self.text.strip()
        for v in valid:
            if text == v or text.startswith(v + " ") or text.startswith(v + "."):
                matched = True
                break
        if not matched:
            if self.is_bold:
                raise ValueError("standard lyrics, not a structural section")
            else:
                raise ValueError("Unrecognized text must not be classified as a structural section")
        return self

class RepeatCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    direction: Literal["start", "end"]

class MalformedStructuralCycle(Exception):
    pass

class GeometryCandidateSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    left_margin_primitives: list[LeftMarginPrimitiveCandidate] = Field(default_factory=list)
    x_aligned_clusters: list[XAlignedPrimitiveClusterCandidate] = Field(default_factory=list)

    sections: list[StructuralSectionCandidate] = Field(default_factory=list)
    repeats: list[RepeatCandidate] = Field(default_factory=list)
    lyrics: list[LyricCandidate] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def fallback_unknown_bold(cls, data: dict) -> dict:
        if isinstance(data, dict):
            sections = data.get("sections", [])
            valid_sections = []
            lyrics = data.get("lyrics", [])
            for s in sections:
                if isinstance(s, dict):
                    # We can try to manually check if it fails the structural section rules
                    # But the requirement is to fallback unknown bold text to lyrics without raising exceptions.
                    # It's better to just check text here.
                    text = s.get("text", "").strip()
                    valid = ["Chorus", "Intro", "Verse", "Bridge", "Outro", "Coda", "Da Coda", "Da Capo", "D.S.", "D.C.", "Fine", "Segno", "A", "B", "C", "D", "E"]
                    matched = False
                    for v in valid:
                        if text == v or text.startswith(v + " ") or text.startswith(v + "."):
                            matched = True
                            break
                    if not matched:
                        if s.get("is_bold"):
                            lyrics.append({
                                "page_index": s["page_index"],
                                "system_index": s["system_index"],
                                "staff_index": s["staff_index"],
                                "x0": s["x0"],
                                "y0": s["y0"],
                                "x1": s["x1"],
                                "y1": s["y1"],
                                "text": s["text"]
                            })
                    else:
                        valid_sections.append(s)
                else:
                    valid_sections.append(s)
            data["sections"] = valid_sections
            data["lyrics"] = lyrics
        return data

    @model_validator(mode="after")
    def validate_cycles(self) -> "GeometryCandidateSet":
        reps = sorted(self.repeats, key=lambda r: (r.page_index, r.system_index, r.staff_index, r.x0))
        for i in range(len(reps)):
            if reps[i].direction == "end":
                if i == 0 or reps[i-1].direction == "end":
                    raise MalformedStructuralCycle("unmatched repeat end")
            elif reps[i].direction == "start":
                if i + 1 < len(reps) and reps[i+1].direction == "start":
                    raise MalformedStructuralCycle("nested repeat starts")
        return self
