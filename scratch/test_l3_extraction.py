import sys
from pathlib import Path
sys.path.insert(0, "src")
from score2gp.cli import extract_tab_file
from score2gp.tabraw import TabRaw
import json

pdf_path = Path("fixtures/private/Lesson-3.pdf")
out_dir = Path("work/verification/lesson_3")
out_dir.mkdir(parents=True, exist_ok=True)
tabraw_path = out_dir / "tab_raw.json"

print("Running extract_tab_file on Lesson-3.pdf...")
extract_tab_file(pdf_path, tabraw_path)

with open(tabraw_path, "r", encoding="utf-8") as f:
    data = json.load(f)

raw = TabRaw.model_validate(data)
candidates = raw.candidates
playables = [c for c in candidates if c.kind == "fret"]

total_playables = len(playables)
with_system = sum(1 for c in playables if c.system_index is not None)
with_bar = sum(1 for c in playables if c.bar_index is not None)
with_string = sum(1 for c in playables if c.string is not None)

unassigned_to_bar = sum(1 for c in playables if c.bar_index is None)

print(f"\n--- Extraction Metrics for Lesson-3.pdf ---")
print(f"Total candidates: {len(candidates)}")
print(f"Playable fret candidates: {total_playables}")
print(f"  With system assigned: {with_system} / {total_playables}")
print(f"  With bar assigned: {with_bar} / {total_playables}")
print(f"  With string assigned: {with_string} / {total_playables}")
print(f"  Playables unassigned to bar: {unassigned_to_bar}")

# Print warnings
warnings = data.get("warnings", [])
print(f"\nTotal warnings: {len(warnings)}")
warning_codes = {}
for w in warnings:
    code = w.get("code")
    warning_codes[code] = warning_codes.get(code, 0) + 1
for k, v in warning_codes.items():
    print(f"  {k}: {v}")
