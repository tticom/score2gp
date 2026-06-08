import json
from pathlib import Path
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics

schema_path = Path("fixtures/public/pdf_staff_geometry_diagnostics_schema.json")
schema = PdfStaffNotationGeometryDiagnostics.model_json_schema()
schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

# Fix missing newlines in the other fixtures
for file in Path("fixtures/public").glob("*.json"):
    text = file.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        file.write_text(text + "\n", encoding="utf-8")
