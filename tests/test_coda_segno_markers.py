import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp


def test_coda_segno_markers_xml(tmp_path) -> None:
    # 1. Load our synthetic test fixture for repeat roadmaps and markers
    fixture_path = Path("fixtures/public/test_coda_segno_markers.ir.json")
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "coda_segno_markers.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify no unexpected compile warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract the main Content/score.gpif file
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all master bars inside MasterBars
        master_bars = root.findall(".//MasterBars/MasterBar")
        assert len(master_bars) == 5
        mb_map = {int(mb.get("index")): mb for mb in master_bars}
        
        # Bar 1: Intro Section Marker with color #FF0000
        mb1 = mb_map[1]
        marker1 = mb1.find("Marker")
        assert marker1 is not None
        assert marker1.find("Text").text == "Intro Section"
        assert marker1.find("Color").text == "#FF0000"
        
        # Bar 2: repeat-start barline & Segno direction glyph
        mb2 = mb_map[2]
        assert mb2.find("RepeatStart") is not None
        dirs2 = mb2.find("Directions")
        assert dirs2 is not None
        assert dirs2.find("Segno") is not None
        
        # Bar 3: To Coda direction jump instruction with TargetBarIndex = 5
        mb3 = mb_map[3]
        dirs3 = mb3.find("Directions")
        assert dirs3 is not None
        to_coda = dirs3.find("ToCoda")
        assert to_coda is not None
        assert to_coda.find("TargetBarIndex").text == "5"
        
        # Bar 4: repeat-end barline & Dal Segno al Coda jump to bar 2
        mb4 = mb_map[4]
        assert mb4.find("Repeat") is not None
        assert mb4.find("Repeat").get("count") == "2"
        dirs4 = mb4.find("Directions")
        assert dirs4 is not None
        ds_al_coda = dirs4.find("DalSegnoAlCoda")
        assert ds_al_coda is not None
        assert ds_al_coda.find("TargetBarIndex").text == "2"
        
        # Bar 5: Coda Outro section marker & Coda visual glyph
        mb5 = mb_map[5]
        marker5 = mb5.find("Marker")
        assert marker5 is not None
        assert marker5.find("Text").text == "Coda Outro"
        assert marker5.find("Color").text == "#00FF00"
        
        dirs5 = mb5.find("Directions")
        assert dirs5 is not None
        assert dirs5.find("Coda") is not None
