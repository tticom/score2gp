from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator
from score2gp.pdf_geometry_candidates import GeometryCandidateSet
from score2gp.logical_clef_candidate_classifier import classify_logical_clef_candidate
from score2gp.pdf_candidate_quarter_rest import QuarterRestCandidate

LogicalClefKind = Literal["treble", "bass", "unknown"]
SemanticGateStatus = Literal["no_candidate", "ambiguous_candidate", "logical_clef_candidate"]

class LogicalClefCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: SemanticGateStatus
    reason: str = Field(min_length=1)
    clef_kind: Optional[LogicalClefKind] = None

    @model_validator(mode="after")
    def validate_clef_state(self) -> LogicalClefCandidate:
        if self.status == "logical_clef_candidate":
            assert self.clef_kind is not None, "clef_kind must be provided when status is 'logical_clef_candidate'"
        else:
            assert self.clef_kind is None, "clef_kind must be None when status is not 'logical_clef_candidate'"
        return self

# Backwards compatibility alias
SemanticGateResult = LogicalClefCandidate

class StaffSemanticCandidates(BaseModel):
    model_config = ConfigDict(frozen=True)
    page_index: Optional[int] = Field(None, ge=1)
    system_index: int = Field(ge=1)
    staff_index: int = Field(ge=1)
    logical_clef: LogicalClefCandidate
    quarter_rests: List[QuarterRestCandidate]

def evaluate_logical_clef_gate(
    geometry: GeometryCandidateSet,
    staff_spacing: float = 0.0,
    staff_height: float = 0.0,
    staff_x0: float = 0.0
) -> SemanticGateResult:
    """
    Evaluates page-level geometry candidates to determine if a logical clef is present.
    Uses proportional bounding box heuristics to classify the clef kind.
    """
    if not geometry.left_margin_primitives:
        return SemanticGateResult(
            status="no_candidate", 
            reason="no left margin primitives found"
        )
    
    text_spans = [p for p in geometry.left_margin_primitives if p.kind == "text_span"]
    curves = [p for p in geometry.left_margin_primitives if p.kind == "curve"]
    
    if not text_spans and not curves:
        return SemanticGateResult(
            status="ambiguous_candidate", 
            reason="left margin contains primitives but no text spans or curves to suggest a clef"
        )
    
    classification = classify_logical_clef_candidate(
        geometry.left_margin_primitives,
        staff_spacing=staff_spacing,
        staff_height=staff_height,
        staff_x0=staff_x0
    )

    if classification["label"] == "treble_clef_candidate":
        return SemanticGateResult(
            status="logical_clef_candidate",
            clef_kind="treble",
            reason=classification["reason"]
        )
    else:
        return SemanticGateResult(
            status="logical_clef_candidate",
            clef_kind="unknown",
            reason=classification["reason"]
        )
