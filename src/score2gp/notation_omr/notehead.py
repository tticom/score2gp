"""Notehead candidate evidence and read-only outcome mapping."""

from typing import Any, Iterable

from .evidence import shape_candidate_evidence


def shape_whole_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "whole_note_candidate", start_index)

def shape_half_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "half_note_candidate", start_index)

def shape_quarter_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "quarter_note_candidate", start_index)

def shape_x_aligned_cluster_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        return (c_dict.get("system_index", 0), c_dict.get("staff_index", 0), c_dict.get("x0", 0.0), c_dict.get("x1", 0.0))

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"x_aligned_cluster_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": c_dict.get("system_index"),
            "staff_index": c_dict.get("staff_index"),
            "x0": c_dict.get("x0"),
            "x1": c_dict.get("x1"),
            "primitive_count": c_dict.get("primitive_count"),
            "primitives": c_dict.get("primitives", [])
        })
    return shaped

def shape_left_margin_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        return (c_dict.get("system_index", 0), c_dict.get("staff_index", 0), c_dict.get("x0", 0.0), c_dict.get("y0", 0.0))

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"left_margin_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": c_dict.get("system_index"),
            "staff_index": c_dict.get("staff_index"),
            "x0": c_dict.get("x0"),
            "y0": c_dict.get("y0"),
            "x1": c_dict.get("x1"),
            "y1": c_dict.get("y1"),
            "kind": c_dict.get("kind"),
            "source": c_dict.get("source"),
            "font_name": c_dict.get("font_name"),
            "font_size": c_dict.get("font_size")
        })
    return shaped

def map_whole_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic whole-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    This acts as the first safe product seam from diagnostics to notation.
    """
    outcomes = []
    for cand in candidate_locations:
        outcome = {
            "symbol_type": "whole_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "association_status": cand.get("association_status"),
            "font_name": cand.get("font_name"),
            "glyph_ordinal": cand.get("glyph_ordinal"),
            "origin_x": cand.get("origin_x"),
            "origin_y": cand.get("origin_y"),
            "source_method": cand.get("source_method"),
            "duration": "whole",
            "source": "diagnostic_candidate_evidence"
        }
        if "association_reason" in cand:
            outcome["association_reason"] = cand.get("association_reason")
        outcomes.append(outcome)
    return outcomes

def map_whole_note_candidates_to_intermediate_notes(outcomes: list[dict]) -> list[dict]:
    """
    Consumes read-only recognition outcomes and emits whole-note intermediate representations
    for valid staff-associated whole note candidates.
    """
    intermediate_notes = []

    for cand in outcomes:
        if cand.get("symbol_type") != "whole_note_candidate":
            continue

        intermediate_note = {
            "source_candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "source": cand.get("source", "intermediate_representation")
        }

        # We need successful staff association
        if cand.get("association_status") != "success":
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = f"invalid_association_status: {cand.get('association_status')}"
            intermediate_notes.append(intermediate_note)
            continue

        page_index = cand.get("page_index")
        system_index = cand.get("system_index")
        staff_index = cand.get("staff_index")
        staff_position_index = cand.get("staff_position_index")
        bbox = cand.get("bbox")

        if page_index is None or system_index is None or staff_index is None:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_staff_indices"
            intermediate_notes.append(intermediate_note)
            continue

        if type(staff_position_index) is not int:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_or_invalid_staff_position_index"
            intermediate_notes.append(intermediate_note)
            continue

        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_or_malformed_bbox"
            intermediate_notes.append(intermediate_note)
            continue

        intermediate_note["symbol_type"] = "whole_note"
        intermediate_note["note_kind"] = "whole_note"
        intermediate_note["duration_kind"] = "whole"
        intermediate_note["page_index"] = page_index
        intermediate_note["system_index"] = system_index
        intermediate_note["staff_index"] = staff_index
        intermediate_note["staff_position_index"] = staff_position_index
        intermediate_note["mapping_status"] = "success"

        intermediate_notes.append(intermediate_note)

    return intermediate_notes

def map_half_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic half-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    """
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "half_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "duration": "half",
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_quarter_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic quarter-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    """
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "quarter_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "duration": "quarter",
            "stem_bbox": cand.get("stem_bbox"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_x_aligned_cluster_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "x_aligned_cluster_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "x0": cand.get("x0"),
            "x1": cand.get("x1"),
            "primitive_count": cand.get("primitive_count"),
            "primitives": cand.get("primitives"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_left_margin_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "left_margin_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "x0": cand.get("x0"),
            "y0": cand.get("y0"),
            "x1": cand.get("x1"),
            "y1": cand.get("y1"),
            "kind": cand.get("kind"),
            "source": "diagnostic_candidate_evidence",
            "font_name": cand.get("font_name"),
            "font_size": cand.get("font_size")
        })
    return outcomes
