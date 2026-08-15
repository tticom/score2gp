import json
from pathlib import Path
import fitz
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict

def test_standard_staff_diagnostics_snapshots() -> None:
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster",
        "negative_tab",
        "negative_blank",
        "negative_noise"
    ]

    for f in fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
        expected_path = Path(f"fixtures/public/expected_diagnostics_{f}.json")

        assert pdf_path.exists()
        assert expected_path.exists()

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags = extract_notation_diagnostics_dict(page, 1)

        with open(expected_path, "r", encoding="utf-8") as file:
            expected = json.load(file)

        # Ensure semantic fields do not appear in generated JSON
        diags_str = json.dumps(diags).lower()
        for forbidden in ["pitch", "duration", "clef", "voice", "key signature", "notehead"]:
            assert forbidden not in diags_str, f"Forbidden semantic field '{forbidden}' found in diagnostics for {f}!"

        # We compare the dictionary output to make sure it matches the snapshot exactly
        # Note: If unstable fields are present, they need to be filtered out here.
        # But according to Task 13: "stable expected diagnostics snapshots exist, tests compare current stable subset against snapshots"
        assert diags == expected, f"Diagnostics snapshot mismatch for {f}"
