import json
from pathlib import Path
import fitz
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
from score2gp.pdf_candidate_semantic_gate import evaluate_logical_clef_gate
from score2gp.pdf_candidate_quarter_rest import extract_quarter_rest_candidates
from score2gp.pdf_candidate_whole_half_rest import extract_whole_half_rest_candidates

def test_semantic_candidates_snapshots() -> None:
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster",
        "negative_tab",
        "negative_blank",
        "negative_noise",
        "bass_clef",
        "alto_clef"
    ]

    for f in fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
        expected_path = Path(f"fixtures/public/expected_semantic_candidates_{f}.json")

        assert pdf_path.exists(), f"PDF missing: {pdf_path}"

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags_dict = extract_notation_diagnostics_dict(page, 1)

        diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)

        staves_data = []
        for staff_diag in diags_model.staves:
            geometry = extract_geometry_candidates(staff_diag)

            line_y_coords = staff_diag.staff.line_y_coords
            staff_spacing = (line_y_coords[-1] - line_y_coords[0]) / 4.0 if len(line_y_coords) == 5 else 10.0
            staff_height = line_y_coords[-1] - line_y_coords[0] if len(line_y_coords) == 5 else (staff_diag.staff.y1 - staff_diag.staff.y0)
            staff_x0 = staff_diag.staff.x0
            staff_center_y = sum(line_y_coords) / len(line_y_coords) if line_y_coords else (staff_diag.staff.y0 + staff_diag.staff.y1) / 2.0

            clef_res = evaluate_logical_clef_gate(geometry, staff_spacing, staff_height, staff_x0)
            qr_cands = extract_quarter_rest_candidates(geometry, staff_spacing, staff_center_y)
            whole_cands, half_cands = extract_whole_half_rest_candidates(geometry, staff_spacing, staff_center_y)

            staves_data.append({
                "page_index": staff_diag.staff.page_index,
                "system_index": staff_diag.staff.system_index,
                "staff_index": staff_diag.staff.staff_index,
                "logical_clef": clef_res.model_dump(mode="json"),
                "quarter_rests": [qr.model_dump(mode="json") for qr in qr_cands],
                "whole_rests": [wr.model_dump(mode="json") for wr in whole_cands],
                "half_rests": [hr.model_dump(mode="json") for hr in half_cands]
            })

        cand_dict = {"staves": staves_data}

        # Ensure prohibited semantic terms (like pitch, scoreir, duration/rhythm timeline inference)
        # do not appear in the generated JSON. Note: "clef" and "rests" are fine here since they are candidate level.
        diags_str = json.dumps(cand_dict).lower()
        for forbidden in ["pitch", "timeline", "scoreir", "duration_inference"]:
            assert forbidden not in diags_str, f"Forbidden semantic field '{forbidden}' found in semantic candidates for {f}!"

        import os
        if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not expected_path.exists():
            with open(expected_path, "w", encoding="utf-8") as file:
                json.dump(cand_dict, file, indent=2)
                file.write("\n")

        with open(expected_path, "r", encoding="utf-8") as file:
            expected = json.load(file)

        assert cand_dict == expected, f"Semantic candidates snapshot mismatch for {f}"
