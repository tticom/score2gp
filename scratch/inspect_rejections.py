import json
from pathlib import Path

tabraw_path = Path("work/derek_trucks_conversion/tab/tab_raw.json")
if tabraw_path.exists():
    data = json.loads(tabraw_path.read_text(encoding="utf-8"))
    
    # 1. Print all warnings in tab_raw.json
    print("=== All Warnings in tab_raw.json ===")
    for w in data.get("warnings", []):
        if w.get("severity") == "error" or "barline" in w.get("message", "").lower() or "bar" in w.get("message", "").lower():
            print(f"- [{w.get('code')}] {w.get('message')}")
            
    # 2. Inspect the candidate barline details if present in candidates or raw
    print("\n=== Candidate details ===")
    cands = data.get("candidates", [])
    print(f"Total candidates: {len(cands)}")
    
    # Let's see if there are other files with details or if we can run conversion with a diagnostic flag
else:
    print("tab_raw.json not found!")
