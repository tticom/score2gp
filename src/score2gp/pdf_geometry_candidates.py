from typing import Literal, Optional, Any
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

class MalformedStructuralCycle(ValueError):
    pass

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
    is_bold: bool = False

    @model_validator(mode="after")
    def validate_section(self) -> "StructuralSectionCandidate":
        if abs(self.y_offset) > 50.0:
            raise ValueError("Must not inject a Section if the Y-offset heuristic exceeds the configured sensible default threshold (50 points)")
        text_lower = self.text.lower()
        known = {"chorus", "verse", "intro", "outro", "bridge", "solo", "section", "interlude", "pre-chorus", "prechorus", "coda"}
        
        is_known = False
        for k in known:
            # Exact match, or starts with known label (e.g. "Chorus 1")
            if text_lower == k or text_lower.startswith(k + " "):
                is_known = True
                break

        if not is_known:
            if self.is_bold:
                raise ValueError("Unrecognized bold text above the staff must be classified as standard lyrics, not a structural section")
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

class GeometryCandidateSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    left_margin_primitives: list[LeftMarginPrimitiveCandidate] = Field(default_factory=list)
    x_aligned_clusters: list[XAlignedPrimitiveClusterCandidate] = Field(default_factory=list)
    sections: list[StructuralSectionCandidate] = Field(default_factory=list)
    repeats: list[RepeatCandidate] = Field(default_factory=list)
    lyrics: list[LyricCandidate] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def apply_lyric_fallback(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sections_raw = data.get("sections", [])
            lyrics_raw = data.get("lyrics", [])
            valid_sections = []
            
            for s in sections_raw:
                if isinstance(s, dict):
                    text_lower = s.get("text", "").lower()
                    y_offset = s.get("y_offset", 0.0)
                    is_bold = s.get("is_bold", False)
                    
                    if abs(y_offset) > 50.0:
                        continue # Drop entirely per rules
                        
                    known = {"chorus", "verse", "intro", "outro", "bridge", "solo", "section", "interlude", "pre-chorus", "prechorus", "coda"}
                    is_known = False
                    for k in known:
                        if text_lower == k or text_lower.startswith(k + " "):
                            is_known = True
                            break
                            
                    if not is_known and is_bold:
                        # Fallback to lyric
                        lyrics_raw.append({
                            "page_index": s["page_index"],
                            "system_index": s["system_index"],
                            "staff_index": s["staff_index"],
                            "x0": s["x0"], "y0": s["y0"], "x1": s["x1"], "y1": s["y1"],
                            "text": s["text"]
                        })
                    elif is_known:
                        valid_sections.append(s)
                else:
                    valid_sections.append(s)
            
            data["sections"] = valid_sections
            data["lyrics"] = lyrics_raw
        return data

    @model_validator(mode="after")
    def validate_cycles(self) -> "GeometryCandidateSet":
        open_repeats = 0
        sorted_repeats = sorted(self.repeats, key=lambda r: (r.page_index, r.system_index, r.staff_index, r.x0))
        for r in sorted_repeats:
            if r.direction == "start":
                if open_repeats > 0:
                    raise MalformedStructuralCycle("Malformed cycle: nested or consecutive repeat starts")
                open_repeats += 1
            elif r.direction == "end":
                if open_repeats == 0:
                    raise MalformedStructuralCycle("Malformed cycle: unmatched repeat end")
                open_repeats -= 1

        if open_repeats > 0:
            raise MalformedStructuralCycle("Malformed cycle: unmatched repeat start")

        return self
    sections: list[StructuralSectionCandidate] = Field(default_factory=list)
    repeats: list[RepeatCandidate] = Field(default_factory=list)
    lyrics: list[LyricCandidate] = Field(default_factory=list)
