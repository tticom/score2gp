import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp


def test_timeline_repeats_xml(tmp_path) -> None:
    # 1. Load the timeline repeats and voltas synthetic test fixture
    fixture_path = Path("fixtures/public/test_timeline_repeats.ir.json")
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "timeline_repeats.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all master bars
        master_bars = root.findall(".//MasterBars/MasterBar")
        mb_map = {int(mb.get("index")): mb for mb in master_bars}
        
        # MasterBar 3: alternate ending 1st pass (bitmask = 1)
        mb3 = mb_map[3]
        ae3 = mb3.find("AlternateEndings")
        assert ae3 is not None
        assert ae3.text == "1"
        
        # MasterBar 4: alternate ending 2nd pass (bitmask = 2)
        mb4 = mb_map[4]
        ae4 = mb4.find("AlternateEndings")
        assert ae4 is not None
        assert ae4.text == "2"
        
        # Retrieve all bars
        bars = root.findall(".//Bars/Bar")
        b_map = {int(b.get("index")): b for b in bars}
        
        # Bar 3: alternate endings and alternative ending blocks
        b3 = b_map[3]
        assert b3.find("AlternateEndings").text == "1"
        assert b3.find(".//AlternativeEnding/AlternateEndings").text == "1"
        
        # Bar 4: alternate endings and alternative ending blocks
        b4 = b_map[4]
        assert b4.find("AlternateEndings").text == "2"
        assert b4.find(".//AlternativeEnding/AlternateEndings").text == "2"

    # 4. Validate round-trip extraction
    from score2gp.gp_package import validate_roundtrip
    res = validate_roundtrip(out_gp, score)
    assert res["valid"], f"Round-trip validation failed: {res['errors']}"
