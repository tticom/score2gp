#!/usr/bin/env python3
"""
Regenerates the Pydantic JSON schema snapshot for PdfStaffNotationGeometryDiagnostics.
This snapshot acts as a strict guard against unintentional removal or renaming
of expected geometric diagnostic fields.
"""
import json
from pathlib import Path
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics

def main() -> None:
    schema = PdfStaffNotationGeometryDiagnostics.model_json_schema()
    
    # Path is relative to this script
    out_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "public" / "pdf_staff_geometry_diagnostics_schema.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    
    print(f"Successfully regenerated {out_path.name}")

if __name__ == "__main__":
    main()
