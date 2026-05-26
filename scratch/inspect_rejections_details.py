import sys
from pathlib import Path
import json

# Add project src to path so we can import score2gp components
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import fitz
from score2gp.pdf import _detect_tab_systems

pdf_path = PROJECT_ROOT / "fixtures" / "private" / "Derek Trucks BB King.pdf"
if not pdf_path.exists():
    print("PDF not found!")
    sys.exit(1)

with fitz.open(pdf_path) as doc:
    for page_num, page in enumerate(doc, start=1):
        print(f"\n--- PAGE {page_num} ---")
        systems = _detect_tab_systems(
            page,
            page_num,
            min_barline_height_ratio=0.65,
            barline_dedup_gap=3.0
        )
        for sys in systems:
            print(f"System {sys.system_index}: Valid: {sys.valid_barline_count}, Rejected: {sys.rejected_barline_count}")
            print(f"  Valid Barlines: {sys.barlines}")
            if sys.barline_candidates_details:
                print("  Candidates details:")
                for d in sys.barline_candidates_details:
                    print(f"    x={d['x']:.2f}, y_min={d['y_min']:.2f}, y_max={d['y_max']:.2f}, height={d['height']:.2f}, staff_height={d['staff_height']:.2f}, coverage={d['coverage_ratio']:.2f}, gaps={d['gaps_crossed']}, decision={d['final_decision']}, reason={d['rejection_reason']}")
