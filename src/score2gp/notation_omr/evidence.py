"""Evidence extraction and candidate location shaping."""

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
        cand_dict = {
            "candidate_id": candidate_id,
            "page_index": page_index,
            "bbox": get_bbox(cand)
        }
        if isinstance(cand, dict):
            if "stem_bbox" in cand:
                cand_dict["stem_bbox"] = cand["stem_bbox"]
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if f in cand:
                    cand_dict[f] = cand[f]
        else:
            if hasattr(cand, "stem_bbox"):
                cand_dict["stem_bbox"] = cand.stem_bbox
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if hasattr(cand, f) and getattr(cand, f) is not None:
                    cand_dict[f] = getattr(cand, f)
        shaped.append(cand_dict)
    return shaped
