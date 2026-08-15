from tests.dynamic_fixtures import _get_dynamic_private_pdf, _get_dynamic_private_musicxml
from pathlib import Path
from score2gp.pdf import inspect_pdf

def test_inspect_pdf_contains_geometry_candidates(tmp_path: Path):
    fixture = _get_dynamic_private_pdf()
    out_dir = tmp_path / "inspect"

    summary = inspect_pdf(fixture, out_dir)

    assert "pages" in summary
    assert len(summary["pages"]) > 0

    page_info = summary["pages"][0]
    assert "geometry_candidates" in page_info
    assert isinstance(page_info["geometry_candidates"], list)
