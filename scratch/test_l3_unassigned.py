import json
from pathlib import Path

tabraw_path = Path("work/verification/lesson_3/tab_raw.json")
with open(tabraw_path, "r", encoding="utf-8") as f:
    data = json.load(f)

candidates = data.get("candidates", [])
playables = [c for c in candidates if c.get("kind") == "fret"]

print("=== Unassigned Playable Candidates (No System) ===")
no_sys = [c for c in playables if c.get("system_index") is None]
print(f"Total: {len(no_sys)}")
for c in no_sys[:10]:
    print(f"  ID: {c.get('id')} | Raw Text: '{c.get('raw_text')}' | Page: {c.get('page_index')} | Bbox: {c.get('bbox')}")

print("\n=== Unassigned Playable Candidates (No String) ===")
no_str = [c for c in playables if c.get("system_index") is not None and c.get("string") is None]
print(f"Total: {len(no_str)}")
for c in no_str[:15]:
    warnings = c.get("raw", {}).get("assignment_warnings", [])
    print(f"  ID: {c.get('id')} | Raw Text: '{c.get('raw_text')}' | Page: {c.get('page_index')} | System: {c.get('system_index')} | Bbox: {c.get('bbox')} | Warnings: {warnings}")

print("\n=== Unassigned Playable Candidates (No Bar) ===")
no_bar = [c for c in playables if c.get("system_index") is not None and c.get("bar_index") is None]
print(f"Total: {len(no_bar)}")
for c in no_bar[:15]:
    warnings = c.get("raw", {}).get("assignment_warnings", [])
    bar_warnings = c.get("raw", {}).get("bar_assignment_warnings", [])
    print(f"  ID: {c.get('id')} | Raw Text: '{c.get('raw_text')}' | Page: {c.get('page_index')} | System: {c.get('system_index')} | Bbox: {c.get('bbox')} | Warnings: {warnings} | Bar Warnings: {bar_warnings}")
