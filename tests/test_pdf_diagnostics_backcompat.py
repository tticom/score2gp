import json
from pathlib import Path
from score2gp.pdf import inspect_pdf

def test_diagnostics_backcompat():
    import tempfile
    
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster"
    ]
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for f in fixtures:
            fixture = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
            expected_path = Path(f"fixtures/public/expected_diagnostics_{f}.json")
            
            assert fixture.exists(), f"Fixture missing: {fixture}"
            assert expected_path.exists(), f"Snapshot missing: {expected_path}"
            
            out_dir = tmp_path / f"inspect_{f}"
            summary = inspect_pdf(fixture, out_dir)
            
            assert "pages" in summary
            assert len(summary["pages"]) > 0
            
            diags_dict = summary["pages"][0]["pdf_staff_notation_diagnostics"]
            
            with open(expected_path, "r", encoding="utf-8") as file:
                expected = json.load(file)
                
            assert diags_dict == expected, f"Diagnostics output broke backwards compatibility for {f}!"
