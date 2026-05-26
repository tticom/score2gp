import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from score2gp.musicxml import parse_musicxml

musicxml_path = PROJECT_ROOT / "fixtures" / "private" / "Derek Trucks BB King.mxl"
xml = parse_musicxml(musicxml_path)
print("Part fields:", xml.parts[0].model_fields.keys())
for idx, part in enumerate(xml.parts):
    print(f"Part {idx+1}: measures={len(part.measures)}")
