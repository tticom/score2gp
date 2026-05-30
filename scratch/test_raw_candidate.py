import json
from pathlib import Path

tabraw_path = Path("work/verification/lesson_3/tab_raw.json")
with open(tabraw_path, "r", encoding="utf-8") as f:
    data = json.load(f)

candidates = data.get("candidates", [])
for c in candidates:
    if c.get("id") in ("pdf-p001-c0070", "pdf-p001-c0071", "pdf-p002-c0172"):
        print(f"\n--- Candidate {c.get('id')} ---")
        print(json.dumps(c, indent=2))
