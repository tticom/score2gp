#!/usr/bin/env python3
import json
from pathlib import Path
import fitz
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict

def main() -> None:
    fixtures = [
        "dense_margin",
        "sparse",
        "wide_curves",
        "complex_cluster"
    ]
    
    # Run from anywhere, resolve paths relative to this script
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent.parent.parent
    
    for f in fixtures:
        pdf_path = repo_root / "tests" / "fixtures" / "pdf" / f"generated_standard_staff_{f}.pdf"
        out_path = repo_root / "fixtures" / "public" / f"expected_diagnostics_{f}.json"
        
        with fitz.open(pdf_path) as doc:
            page = doc[0]
            diags = extract_notation_diagnostics_dict(page, 1)
            
        with open(out_path, "w", encoding="utf-8") as out:
            json.dump(diags, out, indent=2)
            out.write("\n")
            
        print(f"Generated {out_path.name}")

if __name__ == "__main__":
    main()
