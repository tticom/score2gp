import json
from pathlib import Path
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics

schema_path = Path("fixtures/public/pdf_staff_geometry_diagnostics_schema.json")
schema = PdfStaffNotationGeometryDiagnostics.model_json_schema()
with open(schema_path, "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=2)
