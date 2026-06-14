from typing import Any, Iterable

def shape_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    candidate_prefix: str,
    start_index: int = 1
) -> list[dict]:
    """
    Takes raw diagnostic candidates (objects or dicts) for a single page, sorts them
    geometrically, and shapes them into deterministic read-only candidate evidence
    with stable IDs.

    Returns the shaped candidates.
    """
    def get_bbox(c: Any) -> list[float]:
        return c["bbox"] if isinstance(c, dict) else c.bbox

    candidates = list(raw_candidates)
    # Sort geometrically: top, left, bottom, right
    candidates.sort(key=lambda c: (get_bbox(c)[1], get_bbox(c)[0], get_bbox(c)[3], get_bbox(c)[2]))

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"{candidate_prefix}_{start_index + i:03d}"
        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "bbox": get_bbox(cand)
        })
    return shaped

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
        outcomes.append({
            "symbol_type": "whole_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

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

def run_recognition_on_file(
    pdf_path,
    include_x_aligned_clusters: bool = False,
    include_left_margin_candidates: bool = False
) -> dict | None:
    import sys
    import fitz  # type: ignore
    from score2gp.pdf_staff_notation_diagnostics import (
        _extract_whole_note_candidates,
        _extract_half_note_candidates,
        _extract_quarter_note_candidates,
        extract_notation_diagnostics_dict
    )

    if not pdf_path.exists():
        print(f"Error: File {pdf_path} not found", file=sys.stderr)
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    whole_note_locations = []
    half_note_locations = []
    quarter_note_locations = []
    x_aligned_cluster_locations = []
    left_margin_locations = []

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1

        whole_cands = _extract_whole_note_candidates(page)
        shaped_whole = shape_whole_note_candidate_evidence(
            whole_cands,
            page_index=page_index,
            start_index=len(whole_note_locations) + 1
        )
        whole_note_locations.extend(shaped_whole)

        half_cands = _extract_half_note_candidates(page)
        shaped_half = shape_half_note_candidate_evidence(
            half_cands,
            page_index=page_index,
            start_index=len(half_note_locations) + 1
        )
        half_note_locations.extend(shaped_half)

        quarter_cands = _extract_quarter_note_candidates(page)
        shaped_quarter = shape_quarter_note_candidate_evidence(
            quarter_cands,
            page_index=page_index,
            start_index=len(quarter_note_locations) + 1
        )
        quarter_note_locations.extend(shaped_quarter)

        if include_x_aligned_clusters:
            page_diags = extract_notation_diagnostics_dict(page, page_index)
            x_aligned_cands = []
            for staff in page_diags.get("staves", []):
                if staff.get("x_aligned_cluster_candidates"):
                    x_aligned_cands.extend(staff["x_aligned_cluster_candidates"])

            shaped_x_aligned = shape_x_aligned_cluster_candidate_evidence(
                x_aligned_cands,
                page_index=page_index,
                start_index=len(x_aligned_cluster_locations) + 1
            )
            x_aligned_cluster_locations.extend(shaped_x_aligned)

        if include_left_margin_candidates:
            page_diags = extract_notation_diagnostics_dict(page, page_index)
            left_margin_cands = []
            for staff in page_diags.get("staves", []):
                if staff.get("left_margin_candidates"):
                    left_margin_cands.extend(staff["left_margin_candidates"])

            shaped_left_margin = shape_left_margin_candidate_evidence(
                left_margin_cands,
                page_index=page_index,
                start_index=len(left_margin_locations) + 1
            )
            left_margin_locations.extend(shaped_left_margin)

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)
    outcomes.extend(map_half_note_candidates_to_read_only_outcomes(half_note_locations))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(quarter_note_locations))

    if include_x_aligned_clusters:
        outcomes.extend(map_x_aligned_cluster_candidates_to_read_only_outcomes(x_aligned_cluster_locations))

    if include_left_margin_candidates:
        outcomes.extend(map_left_margin_candidates_to_read_only_outcomes(left_margin_locations))

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "read_only_recognition_outcomes": outcomes
    }
