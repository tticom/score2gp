from __future__ import annotations
import sys
from pathlib import Path
import fitz  # type: ignore

try:
    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
    from score2gp.pdf_geometry_candidate_extractor import PdfGeometryCandidateExtractor
    from score2gp.pdf_staff_geometry import PrimitiveGeometryEvidence
    from score2gp.logical_clef_candidate_classifier import classify_logical_clef_candidate, _cluster_curves, _BBox
    from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate
except ImportError:
    print("Run with PYTHONPATH=src")
    sys.exit(1)

def diagnose_extraction_failure(
    cands: list[LeftMarginPrimitiveCandidate] | None,
    staff_spacing: float,
    staff_height: float,
    staff_x0: float,
    classifier_result: dict
) -> str:
    """
    Returns a specific failure category based on the candidates and the classifier result.
    Categories:
    - "no_left_margin"
    - "staff_association_missing_or_malformed"
    - "primitives_found_but_wrong_type"
    - "primitives_found_but_malformed"
    - "primitives_found_but_too_fragmented"
    - "primitives_found_but_outside_staff_region"
    - "primitives_found_but_ambiguous"
    - "primitives_found_but_failing_classifier_thresholds"
    - "treble_clef_candidate"
    """
    label = classifier_result.get("label", "unknown")
    reason = classifier_result.get("reason", "")

    if label == "treble_clef_candidate":
        return "treble_clef_candidate"
    
    if staff_spacing <= 0.0 or staff_height <= 0.0:
        return "staff_association_missing_or_malformed"

    if not cands:
        return "no_left_margin"

    if "Ambiguous: multiple" in reason:
        return "primitives_found_but_ambiguous"

    # Analyze candidates
    text_spans = [c for c in cands if c.kind == "text_span"]
    curves = [c for c in cands if c.kind == "curve"]
    rectangles = [c for c in cands if c.kind == "rectangle"]

    if not text_spans and not curves:
        return "primitives_found_but_wrong_type"

    # Check for fragmentation
    if len(curves) > 10:
        return "primitives_found_but_too_fragmented"
    
    candidate_groups = []
    for ts in text_spans:
        candidate_groups.append({"kind": "text_span", "bbox": _BBox(ts.x0, ts.y0, ts.x1, ts.y1)})
    for cb in _cluster_curves(curves, staff_spacing):
        candidate_groups.append({"kind": "curve_group", "bbox": cb})

    # Check if outside staff region (e.g. extremely far left or right)
    # The clef should be near staff_x0
    all_outside = True
    all_malformed = True
    all_failed_threshold = True

    for group in candidate_groups:
        bbox = group["bbox"]
        c_h = bbox.y1 - bbox.y0
        c_w = bbox.x1 - bbox.x0

        if c_h > 0 and c_w > 0:
            all_malformed = False
        else:
            continue

        # Check if it's within a reasonable horizontal distance from staff_x0
        x0_offset = bbox.x0 - staff_x0
        # A clef should start near the staff_x0. If it's more than 5 staff spaces away, it's far.
        if abs(x0_offset) < 5 * staff_spacing:
            all_outside = False
            
            # Since it's inside region and not malformed, if it still didn't pass, it failed thresholds
            # The exact thresholds in the classifier:
            # height_to_spacing >= 3.5 and width_to_spacing >= 1.5 and height_to_staff_height > 1.2
            h2s = c_h / staff_spacing
            w2s = c_w / staff_spacing
            h2staff = c_h / staff_height
            if h2s < 3.5 or w2s < 1.5 or h2staff <= 1.2:
                # specifically failing thresholds
                pass
            else:
                all_failed_threshold = False

    if all_malformed:
        return "primitives_found_but_malformed"
    if all_outside:
        return "primitives_found_but_outside_staff_region"
    
    return "primitives_found_but_failing_classifier_thresholds"


def run_diagnostic(pdfs_dir: Path) -> dict:
    pdfs = sorted(pdfs_dir.glob("generated_standard_staff_*.pdf"))
    extractor = PdfGeometryCandidateExtractor()

    counts = {
        "staves_total": 0,
        "no_left_margin": 0,
        "staff_association_missing_or_malformed": 0,
        "primitives_found_but_wrong_type": 0,
        "primitives_found_but_malformed": 0,
        "primitives_found_but_too_fragmented": 0,
        "primitives_found_but_outside_staff_region": 0,
        "primitives_found_but_ambiguous": 0,
        "primitives_found_but_failing_classifier_thresholds": 0,
        "treble_clef_candidate": 0,
        "total_curves": 0,
        "total_text_spans": 0,
        "total_rectangles": 0,
        "total_vertical_strokes": 0,
        "total_horizontal_strokes": 0
    }

    if not pdfs:
        return counts

    for pdf_path in pdfs:
        doc = fitz.open(pdf_path)
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_diags = extract_notation_diagnostics_dict(page, page_idx + 1)
            for staff_dict in page_diags.get("staves", []):
                counts["staves_total"] += 1
                
                staff_geom = staff_dict.get("staff")
                left_margin = staff_dict.get("left_margin")

                x0 = staff_geom.get("x0", 0.0)
                y0 = staff_geom.get("y0", 0.0)
                y1 = staff_geom.get("y1", 0.0)
                height = y1 - y0
                spacing = staff_geom.get("staff_space", 0.0)
                if spacing == 0.0:
                    spacing = height / 4.0 if height > 0 else 0.0

                if not left_margin:
                    res = diagnose_extraction_failure(None, spacing, height, x0, {})
                    counts[res] = counts.get(res, 0) + 1
                    continue

                evidence_dicts = left_margin.get("evidence", [])
                
                evidence = []
                for ed in evidence_dicts:
                    kind = ed["kind"]
                    counts[f"total_{kind}s"] = counts.get(f"total_{kind}s", 0) + 1
                    evidence.append(PrimitiveGeometryEvidence(
                        x0=ed.get("x0", 0), y0=ed.get("y0", 0), x1=ed.get("x1", 0), y1=ed.get("y1", 0),
                        kind=kind,
                        font_name=ed.get("font_name"),
                        font_size=ed.get("font_size")
                    ))

                sys_idx = staff_geom.get("system_index", 1)
                staff_idx = staff_geom.get("staff_index", 1)
                cands = extractor.extract_left_margin_candidates(page_idx + 1, sys_idx, staff_idx, evidence)

                clf_res = classify_logical_clef_candidate(cands, spacing, height, x0)
                cat = diagnose_extraction_failure(cands, spacing, height, x0, clf_res)
                counts[cat] = counts.get(cat, 0) + 1

    return counts

def main():
    repo_root = Path(__file__).parent.parent
    fixtures_dir = repo_root / "tests" / "fixtures" / "pdf"
    
    counts = run_diagnostic(fixtures_dir)

    print("=== Extraction Gap Diagnostic ===")
    for k, v in counts.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
