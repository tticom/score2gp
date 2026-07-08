from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from score2gp.pdf_geometry_candidates import GeometryCandidateSet

LogicalClefKind = Literal["treble", "bass", "unknown"]
SemanticGateStatus = Literal["no_candidate", "ambiguous_candidate", "logical_clef_candidate"]

class SemanticGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: SemanticGateStatus
    reason: str
    clef_kind: Optional[LogicalClefKind] = None

def evaluate_logical_clef_gate(geometry: GeometryCandidateSet) -> SemanticGateResult:
    """
    Evaluates page-level geometry candidates to determine if a logical clef is present.
    Because we only have bounding box and font metadata (no text characters),
    this gate fails closed to 'unknown' or 'ambiguous' when evidence is insufficient.
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
    
    return SemanticGateResult(
        status="logical_clef_candidate",
        clef_kind="unknown",
        reason="found text_span or curve in left margin suggesting a clef, but insufficient evidence to classify kind"
    )
