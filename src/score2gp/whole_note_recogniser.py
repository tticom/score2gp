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

def run_recognition_on_file(pdf_path) -> dict | None:
    import sys
    import fitz  # type: ignore
    from score2gp.pdf_staff_notation_diagnostics import _extract_whole_note_candidates

    if not pdf_path.exists():
        print(f"Error: File {pdf_path} not found", file=sys.stderr)
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    whole_note_locations = []

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1
        candidates_objs = _extract_whole_note_candidates(page)

        # Sort geometrically: top, left, bottom, right
        candidates_objs.sort(key=lambda c: (c.bbox[1], c.bbox[0], c.bbox[3], c.bbox[2]))

        for cand in candidates_objs:
            candidate_id = f"whole_note_candidate_{len(whole_note_locations) + 1:03d}"
            whole_note_locations.append({
                "candidate_id": candidate_id,
                "page_index": page_index,
                "bbox": cand.bbox
            })

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "read_only_recognition_outcomes": outcomes
    }
