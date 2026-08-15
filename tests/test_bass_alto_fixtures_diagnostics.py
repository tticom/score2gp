import fitz
import pytest
pytest.skip("Legacy tests need refactoring to use dynamic private fixtures", allow_module_level=True)
from pathlib import Path
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates

def test_bass_alto_fixtures_are_readable_by_diagnostics() -> None:
    fixtures = ["bass_clef", "alto_clef"]

    for name in fixtures:
        pdf_path = Path(f_get_dynamic_private_pdf())
        assert pdf_path.exists(), f"Generated PDF fixture missing: {pdf_path}"

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags_dict = extract_notation_diagnostics_dict(page, 1)

        assert diags_dict is not None
        diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)
        assert len(diags_model.staves) > 0

        staff_diag = diags_model.staves[0]
        assert staff_diag.left_margin is not None

        # Verify left margin contains at least one curve candidate
        assert staff_diag.left_margin.curve_candidate_count >= 1

        # Verify geometry candidate extraction runs cleanly
        geometry = extract_geometry_candidates(staff_diag)
        assert len(geometry.left_margin_primitives) >= 1
        assert any(p.kind == "curve" for p in geometry.left_margin_primitives)
