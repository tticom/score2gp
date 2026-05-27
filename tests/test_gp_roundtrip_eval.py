import sys
from pathlib import Path

# Add scripts directory to sys.path to allow importing gp_roundtrip_eval
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from gp_roundtrip_eval import extract_native_gp_notes


def test_extract_native_gp_notes_xml():
    gp_path = Path("tests/fixtures/mock_gp7_flat.xml")
    assert gp_path.exists()
    notes = extract_native_gp_notes(gp_path)
    assert len(notes) == 2
    assert notes[0] == {"bar_index": 1, "string": 6, "fret": 3}
    assert notes[1] == {"bar_index": 2, "string": 4, "fret": 5}
