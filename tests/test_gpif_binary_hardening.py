import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from score2gp.ir import ScoreIR
from score2gp.gpif import build_gpif
from score2gp.gp_package import write_gp, extract_score_ir_from_gp, validate_gp

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "public" / "test_gpif_binary_hardening.ir.json"


def test_gpif_binary_hardening_sequencing():
    # 1. Load the comprehensive synthetic fixture
    assert FIXTURE_PATH.exists()
    score = ScoreIR.from_json_file(FIXTURE_PATH)

    # 2. Build raw GPIF bytes
    gpif_xml = build_gpif(score)
    root = ET.fromstring(gpif_xml)
    score_node = root.find("Score")
    assert score_node is not None

    # 3. Retrieve all child elements under <Score>
    child_tags = [child.tag for child in score_node]

    # Verify all expected elements exist and are strictly ordered
    TAG_ORDER = [
        "Metadata",
        "Tempo",
        "PageSetup",
        "ScoreSystemsDefaultLayout",
        "ScoreSystemsLayout",
        "View",
        "Print",
        "Layout",
        "MusicFont",
        "SymbolFont",
        "Fonts",
        "StyleCollections",
        "Styles",
        "MasterTrack",
        "Booklet",
        "Tracks",
        "MasterBars",
        "Bars"
    ]

    # Map actual child tags to their indexes in the strict sequence ordering
    indexes = [TAG_ORDER.index(tag) for tag in child_tags if tag in TAG_ORDER]
    
    # Assert that indexes are monotonically increasing, meaning the tags are sorted strictly
    assert indexes == sorted(indexes)

    # Ensure key elements actually exist in our fixture's generated XML
    assert "Metadata" in child_tags
    assert "Layout" in child_tags
    assert "MasterTrack" in child_tags
    assert "Tracks" in child_tags
    assert "MasterBars" in child_tags
    assert "Bars" in child_tags


def test_companion_files_and_roundtrip(tmp_path):
    assert FIXTURE_PATH.exists()
    score = ScoreIR.from_json_file(FIXTURE_PATH)

    output_gp = tmp_path / "hardened_test.gp"

    # Write binary GP7 package
    warnings = write_gp(score, output_gp, target_version="GP7")
    assert not warnings

    # Validate zip file integrity
    validation = validate_gp(output_gp)
    assert not validation["errors"]

    # Verify companion files inside the package
    with zipfile.ZipFile(output_gp, "r") as zf:
        namelist = zf.namelist()
        assert "Content/Preferences.json" in namelist
        assert "Content/LayoutConfiguration" in namelist

        # 1. Verify Content/Preferences.json populated contents
        pref_bytes = zf.read("Content/Preferences.json")
        pref_data = json.loads(pref_bytes.decode("utf-8"))
        assert pref_data["scoreViewMode"] == "Screen"
        assert pref_data["pageFormat"]["width"] == 210.0
        assert pref_data["pageFormat"]["height"] == 297.0
        assert pref_data["pageFormat"]["scale"] == 1.2
        assert pref_data["pageFormat"]["marginTop"] == 15.0
        assert pref_data["pageFormat"]["marginBottom"] == 15.0

        # 2. Verify Content/LayoutConfiguration populated contents
        layout_bytes = zf.read("Content/LayoutConfiguration")
        layout_root = ET.fromstring(layout_bytes)
        assert layout_root.tag == "LayoutConfiguration"
        assert layout_root.find("ActiveLayout").text == "Screen"
        assert layout_root.find("SystemLayout").text == "3"
        
        spm = layout_root.find("SystemPageMargins")
        assert spm is not None
        assert spm.find("Top").text == "12.0"
        assert spm.find("Bottom").text == "12.0"
        assert spm.find("Left").text == "12.0"
        assert spm.find("Right").text == "12.0"

    # 3. Verify E2E round-trip recovery integrity
    recovered = extract_score_ir_from_gp(output_gp)
    assert recovered.metadata.title == "Binary Hardened Synthetic Suite"
    assert recovered.metadata.artist == "Compiler Hardening Test Suite"
    assert recovered.tempo.bpm == 140
    assert len(recovered.tracks) == 1
    assert recovered.tracks[0].name == "Hardened Guitar"
