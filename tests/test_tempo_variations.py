import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, extract_score_ir_from_gp


def test_tempo_variations_xml(tmp_path) -> None:
    # 1. Load the tempo variations and staff text annotations synthetic test fixture
    fixture_path = Path("fixtures/public/test_tempo_variations.ir.json")
    assert fixture_path.exists()
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "tempo_variations.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Verify MasterBar TempoAutomations
        master_bars = root.findall(".//MasterBars/MasterBar")
        mb_map = {int(mb.get("index")): mb for mb in master_bars}
        
        # MasterBar 2: ritardando tempo automation
        mb2 = mb_map[2]
        ta2 = mb2.find("TempoAutomation")
        assert ta2 is not None
        assert ta2.find("Type").text == "Ritardando"
        assert ta2.find("Style").text == "Linear"
        assert ta2.find("TargetBPM").text == "80.0"
        
        # MasterBar 3: accelerando tempo automation
        mb3 = mb_map[3]
        ta3 = mb3.find("TempoAutomation")
        assert ta3 is not None
        assert ta3.find("Type").text == "Accelerando"
        assert ta3.find("Style").text == "Exponential"
        assert ta3.find("TargetBPM").text == "150.0"
        
        # Verify Staff Texts annotations
        staff = root.find(".//Tracks/Track/Staves/Staff")
        assert staff is not None
        texts_node = staff.find("Texts")
        assert texts_node is not None
        texts = [t.find("Value").text for t in texts_node.findall("Text")]
        assert texts == ["Rubato", "Open Jam"]

    # 4. Symmetrically verify the reverse package parser
    recovered = extract_score_ir_from_gp(out_gp)
    assert isinstance(recovered, ScoreIR)
    
    # Track annotations
    assert len(recovered.tracks) == 1
    assert recovered.tracks[0].text_annotations == ["Rubato", "Open Jam"]
    
    # Bar tempo automations
    assert recovered.bars[0].tempo_automation is None
    
    rec_b2 = recovered.bars[1]
    assert rec_b2.tempo_automation is not None
    assert rec_b2.tempo_automation.type == "ritardando"
    assert rec_b2.tempo_automation.style == "linear"
    assert rec_b2.tempo_automation.target_bpm == 80.0
    
    rec_b3 = recovered.bars[2]
    assert rec_b3.tempo_automation is not None
    assert rec_b3.tempo_automation.type == "accelerando"
    assert rec_b3.tempo_automation.style == "exponential"
    assert rec_b3.tempo_automation.target_bpm == 150.0
