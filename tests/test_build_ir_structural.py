import pytest
from pathlib import Path
from score2gp.pdf import extract_tab
import json

def test_integration_pdf_structural_signaling(tmp_path: Path):
    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "npg_04d_structural.pdf"

    # Run public production path
    raw = extract_tab(pdf_path, tmp_path)

    with open(tmp_path / "inspect" / "inspect_pdf.json") as f:
        diags = json.load(f)
        for cand in diags["pages"][0]["geometry_candidates"]:
            if cand.get("x_aligned_clusters"):
                print("CLUSTERS:", json.dumps(cand["x_aligned_clusters"], indent=2))
