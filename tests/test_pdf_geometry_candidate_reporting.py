from pathlib import Path
from score2gp.pdf import inspect_pdf

def test_inspect_pdf_contains_geometry_candidates(tmp_path: Path):
    fixture = Path("tests/fixtures/pdf/generated_standard_staff_dense_margin.pdf")
    out_dir = tmp_path / "inspect"
    
    summary = inspect_pdf(fixture, out_dir)
    
    assert "pages" in summary
    assert len(summary["pages"]) > 0
    
    page_info = summary["pages"][0]
    assert "geometry_candidates" in page_info
    assert isinstance(page_info["geometry_candidates"], list)
