import json
from pathlib import Path

tabraw_path = Path("work/verification/lesson_3/tab_raw.json")
with open(tabraw_path, "r", encoding="utf-8") as f:
    data = json.load(f)

candidates = data.get("candidates", [])
playables_all = [c for c in candidates if c.get("parsed_fret") is not None]
print(f"Total fret-like candidates: {len(playables_all)}")

refusals = {}
for c in playables_all:
    ref = c.get("raw", {}).get("refusal_reason")
    refusals[ref] = refusals.get(ref, 0) + 1

print("\nRefusal reasons:")
for k, v in refusals.items():
    print(f"  {k}: {v}")
