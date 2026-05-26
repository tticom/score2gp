import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, validate_roundtrip


def test_timeline_refinements_xml(tmp_path) -> None:
    # 1. Load the complex timeline refinements synthetic test fixture
    fixture_path = Path("fixtures/public/test_timeline_refinements.ir.json")
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "timeline_refinements.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif to verify layout tags structurally
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all master bars
        master_bars = root.findall(".//MasterBars/MasterBar")
        mb_map = {int(mb.get("index")): mb for mb in master_bars}
        
        # MasterBar 2: repeat-start
        mb2 = mb_map[2]
        assert mb2.find("Barline").text == "RepeatStart"
        assert mb2.find("RepeatStart") is not None
        
        # MasterBar 3: repeat-start
        mb3 = mb_map[3]
        assert mb3.find("Barline").text == "RepeatStart"
        assert mb3.find("RepeatStart") is not None
        
        # MasterBar 4: repeat-end (count = 2)
        mb4 = mb_map[4]
        assert mb4.find("Barline").text == "RepeatEnd"
        assert mb4.find("Repeat") is not None
        assert mb4.find("Repeat").get("count") == "2"
        
        # MasterBar 5: alternate ending passes [1, 3] (bitmask = 5)
        mb5 = mb_map[5]
        ae5 = mb5.find("AlternateEndings")
        assert ae5 is not None
        assert ae5.text == "5"
        
        # MasterBar 6: alternate ending passes [2, 4] (bitmask = 10), repeat-end (count = 4)
        mb6 = mb_map[6]
        ae6 = mb6.find("AlternateEndings")
        assert ae6 is not None
        assert ae6.text == "10"
        assert mb6.find("Barline").text == "RepeatEnd"
        assert mb6.find("Repeat") is not None
        assert mb6.find("Repeat").get("count") == "4"
        
        # Retrieve all bars
        bars = root.findall(".//Bars/Bar")
        b_map = {int(b.get("index")): b for b in bars}
        
        # Bar 5: Alternate endings and alternative ending blocks (bitmask = 5)
        b5 = b_map[5]
        assert b5.find("AlternateEndings").text == "5"
        assert b5.find(".//AlternativeEnding/AlternateEndings").text == "5"
        
        # Bar 6: Alternate endings and alternative ending blocks (bitmask = 10)
        b6 = b_map[6]
        assert b6.find("AlternateEndings").text == "10"
        assert b6.find(".//AlternativeEnding/AlternateEndings").text == "10"

    # 4. Validate round-trip extraction
    res = validate_roundtrip(out_gp, score)
    assert res["valid"], f"Round-trip validation failed: {res['errors']}"
