from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from score2gp.pdf_geometry_candidates import GeometryCandidateSet
from score2gp.logical_clef_candidate_classifier import classify_logical_clef_candidate

LogicalClefKind = Literal["treble", "bass", "unknown"]
SemanticGateStatus = Literal["no_candidate", "ambiguous_candidate", "logical_clef_candidate"]

class SemanticGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: SemanticGateStatus
    reason: str
    clef_kind: Optional[LogicalClefKind] = None

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
