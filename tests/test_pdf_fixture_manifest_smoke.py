import json
from pathlib import Path
from score2gp.pdf import inspect_pdf

def test_manifest_fixtures_smoke(tmp_path) -> None:
    manifest_path = Path("fixtures/public/standard_staff_fixture_manifest.json")
    assert manifest_path.exists(), "Fixture manifest not found"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    fixtures = manifest.get("fixtures", [])
    
    for fixture in fixtures:
        pdf_path = Path(fixture["pdf_path"])
        assert pdf_path.exists(), f"PDF fixture not found for {fixture['id']}"
        
        result = inspect_pdf(str(pdf_path), out_dir=str(tmp_path / fixture["id"]))
        
        assert not any("traceback" in w.get("message", "").lower() for w in result.get("warnings", [])), f"Crash in {fixture['id']}"
        
        pages = result.get("pages", [])
        assert len(pages) >= 1, f"No pages returned for {fixture['id']}"
        
        diags = pages[0].get("pdf_staff_notation_diagnostics", {})
        assert diags, f"No diagnostics produced for {fixture['id']}"
        assert diags.get("status") == "success", f"Diagnostics failed for {fixture['id']}"
        
        staves = diags.get("staves", [])
        assert len(staves) >= 1, f"Expected minimum staff count >= 1 for {fixture['id']}"
