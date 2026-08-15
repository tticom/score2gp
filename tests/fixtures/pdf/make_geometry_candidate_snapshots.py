import json
from pathlib import Path
import fitz
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates

def generate_snapshots():
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster"
    ]

    for f in fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
        expected_path = Path(f"fixtures/public/expected_geometry_candidates_{f}.json")

        if not pdf_path.exists():
            print(f"Skipping {f}, PDF not found at {pdf_path}")
            continue

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags_dict = extract_notation_diagnostics_dict(page, 1)

        diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)

        # Collect candidates from all staves
        all_candidates = []
        for staff_diag in diags_model.staves:
            candidates = extract_geometry_candidates(staff_diag)
            all_candidates.append(candidates.model_dump(mode="json"))

        with open(expected_path, "w", encoding="utf-8") as file:
            json.dump({"staves": all_candidates}, file, indent=2)
            file.write("\n")

        print(f"Wrote snapshot: {expected_path}")

if __name__ == "__main__":
    generate_snapshots()
