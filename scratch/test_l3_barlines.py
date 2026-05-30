import sys
from pathlib import Path
sys.path.insert(0, "src")
from score2gp.pdf import _detect_tab_systems
import fitz

pdf_path = Path("fixtures/private/Lesson-3.pdf")
doc = fitz.open(pdf_path)

for page_idx, page in enumerate(doc):
    print(f"\n--- Page {page_idx+1} ---")
    systems = _detect_tab_systems(page, page_idx)
    print(f"Detected {len(systems)} systems.")
    for idx, system in enumerate(systems):
        print(f"  System {idx+1}:")
        print(f"    Line spacing: {system.line_spacing:.3f}")
        print(f"    Barlines count: {len(system.barlines)} -> {system.barlines}")
        print(f"    Rejected barlines count: {system.rejected_barline_count}")
        for d in (system.barline_candidates_details or []):
            if d.get("final_decision") == "rejected":
                print(f"      Rejected barline at x={d['x']:.3f}: height={d['height']:.3f}, reason={d['rejection_reason']}")
