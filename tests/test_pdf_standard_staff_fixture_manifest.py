import json
from pathlib import Path

def test_standard_staff_fixture_manifest_properties() -> None:
    manifest_path = Path("fixtures/public/standard_staff_fixture_manifest.json")
    assert manifest_path.exists(), "Fixture manifest not found"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    fixtures = manifest.get("fixtures", [])
    assert len(fixtures) == 4, "Expected exactly 4 standard staff fixtures in manifest"
    
    expected_ids = {"dense-margin", "sparse", "wide-curves", "complex-cluster"}
    actual_ids = set()
    
    for fixture in fixtures:
        actual_ids.add(fixture["id"])
        
        # Verify paths exist (relative to the repo root where pytest runs)
        json_path = Path(fixture["json_path"])
        pdf_path = Path(fixture["pdf_path"])
        script_path = Path(fixture["generator_script"])
        
        assert json_path.exists(), f"JSON path {json_path} does not exist for {fixture['id']}"
        assert pdf_path.exists(), f"PDF path {pdf_path} does not exist for {fixture['id']}"
        assert script_path.exists(), f"Generator script {script_path} does not exist for {fixture['id']}"
        
        # Safety asserts: must be synthetic, must NOT be private/scanned/ocr/semantic
        assert fixture["synthetic"] is True, f"Fixture {fixture['id']} must be marked synthetic"
        assert fixture["private"] is False, f"Fixture {fixture['id']} must NOT be private"
        assert fixture["scanned"] is False, f"Fixture {fixture['id']} must NOT be scanned"
        assert fixture["ocr"] is False, f"Fixture {fixture['id']} must NOT use OCR"
        assert fixture["semantic_inference"] is False, f"Fixture {fixture['id']} must NOT imply semantic inference"

    assert actual_ids == expected_ids, f"Manifest entries do not match expected IDs. Got {actual_ids}"
