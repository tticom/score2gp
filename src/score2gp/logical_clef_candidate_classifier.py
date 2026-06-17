from __future__ import annotations

from typing import Any
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate

def classify_logical_clef_candidate(
    candidates: list[LeftMarginPrimitiveCandidate] | None,
    staff_spacing: float,
    staff_height: float,
    staff_x0: float
) -> dict[str, Any]:
    """
    Diagnostic-only read-only classifier to extract logical clef candidate
    evidence from existing left-margin primitive candidates.
    
    A conservative heuristic is used. If evidence is missing, weak, or 
    ambiguous, it fails closed and returns 'unknown'.
    """
    if not candidates:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Missing candidate evidence",
            "features": {}
        }
        
    if staff_spacing <= 0.0 or staff_height <= 0.0:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Invalid staff geometry",
            "features": {}
        }

    # Find the largest candidate by height (clefs are characteristically tall).
    # We restrict to text_span and curve.
    best_cand = None
    max_height = 0.0
    
    for cand in candidates:
        if cand.kind not in ("text_span", "curve"):
            continue
            
        c_height = cand.y1 - cand.y0
        if c_height > max_height:
            max_height = c_height
            best_cand = cand
            
    if not best_cand:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "No valid text_span or curve evidence present",
            "features": {}
        }
        
    c_height = best_cand.y1 - best_cand.y0
    c_width = best_cand.x1 - best_cand.x0
    
    if c_width <= 0.0:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Candidate width is invalid",
            "features": {}
        }
    
    height_to_spacing = float(c_height) / float(staff_spacing)
    width_to_spacing = float(c_width) / float(staff_spacing)
    height_to_staff_height = float(c_height) / float(staff_height)
    x0_offset = float(best_cand.x0) - float(staff_x0)

    features = {
        "candidate_kind": best_cand.kind,
        "height_to_spacing": round(height_to_spacing, 3),
        "width_to_spacing": round(width_to_spacing, 3),
        "height_to_staff_height": round(height_to_staff_height, 3),
        "x0_offset_from_staff_x0": round(x0_offset, 3)
    }

    # Conservative heuristic check for treble clef
    # A true treble clef must be significantly taller than the staff lines alone.
    if height_to_spacing >= 3.5 and width_to_spacing >= 1.5 and height_to_staff_height > 1.2:
        label = "treble_clef_candidate"
        reason = "Candidate matches proportional heuristics for a treble clef"
    else:
        label = "unknown"
        reason = "Evidence is ambiguous or does not strongly match treble clef heuristics"

    return {
        "kind": "logical_clef_candidate_classifier",
        "label": label,
        "reason": reason,
        "features": features
    }
