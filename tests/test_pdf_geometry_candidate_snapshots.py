import json
from pathlib import Path
import fitz
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates

def test_geometry_candidates_snapshots() -> None:
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster"
    ]

    for f in fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
        expected_path = Path(f"fixtures/public/expected_geometry_candidates_{f}.json")

        assert pdf_path.exists(), f"PDF missing: {pdf_path}"
        assert expected_path.exists(), f"Snapshot missing: {expected_path}"

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags_dict = extract_notation_diagnostics_dict(page, 1)

        diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)

        all_candidates = []
        for staff_diag in diags_model.staves:
            candidates = extract_geometry_candidates(staff_diag)
            all_candidates.append(candidates.model_dump(mode="json"))

        cand_dict = {"staves": all_candidates}

        with open(expected_path, "r", encoding="utf-8") as file:
            expected = json.load(file)

        # Ensure semantic fields do not appear in generated JSON
        diags_str = json.dumps(cand_dict).lower()
        for forbidden in ["pitch", "duration", "clef", "voice", "key signature", "notehead", "beat", "rhythm"]:
            assert forbidden not in diags_str, f"Forbidden semantic field '{forbidden}' found in candidates for {f}!"

        assert cand_dict == expected, f"Candidates snapshot mismatch for {f}"
