import json
from pathlib import Path

tabraw_path = Path("work/derek_trucks_conversion/tab/tab_raw.json")
if tabraw_path.exists():
    data = json.loads(tabraw_path.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    
    frets = [c for c in cands if c.get("kind") == "fret"]
    extracted = [f for f in frets if f.get("raw", {}).get("refusal_reason") in ("pdf_fret_single_digit_extracted", "pdf_fret_multidigit_extracted")]
    
    print(f"Successfully extracted frets count: {len(extracted)}")
    if extracted:
        # Let's count how many have system_index, string_index, bar_boxes
        system_indices = [f.get("raw", {}).get("system_index") for f in extracted]
        print("system_indices of extracted frets (unique):", set(system_indices))
        
        string_indices = [f.get("raw", {}).get("string_index") for f in extracted]
        print("string_indices of extracted frets (unique):", set(string_indices))
        
        bar_boxes_counts = [len(f.get("raw", {}).get("bar_boxes") or []) for f in extracted]
        print("bar_boxes count unique:", set(bar_boxes_counts))
        
        # Let's look at one example
        print("\nOne extracted fret candidate:")
        print(json.dumps(extracted[0], indent=2))
else:
    print("tab_raw.json not found!")
