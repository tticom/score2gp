import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, extract_score_ir_from_gp


def test_measure_ranges_xml(tmp_path) -> None:
    # 1. Load the multi-measure rest and repeat count overlay synthetic test fixture
    fixture_path = Path("fixtures/public/test_measure_ranges.ir.json")
    assert fixture_path.exists()
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "measure_ranges.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all bars
        bars = root.findall(".//Bars/Bar")
        b_map = {int(b.get("index")): b for b in bars}
        
        # Bar 1: multi measure rest of 16 bars
        b1 = b_map[1]
        mmr1 = b1.find("MultiMeasureRest")
        assert mmr1 is not None
        assert mmr1.find("BarCount").text == "16"
        
        # Bar 17: repeat count overlay with style "Percent"
        b17 = b_map[17]
        rc17 = b17.find("RepeatCount")
        assert rc17 is not None
        assert rc17.find("Count").text == "4"
        assert rc17.find("Span").text == "1"
        assert rc17.find("Style").text == "Percent"
        
        # Bar 18: repeat count overlay with style "Numbered"
        b18 = b_map[18]
        rc18 = b18.find("RepeatCount")
        assert rc18 is not None
        assert rc18.find("Count").text == "4"
        assert rc18.find("Span").text == "1"
        assert rc18.find("Style").text == "Numbered"
        
        # Bar 19: repeat count overlay with style "Standard"
        b19 = b_map[19]
        rc19 = b19.find("RepeatCount")
        assert rc19 is not None
        assert rc19.find("Count").text == "4"
        assert rc19.find("Span").text == "1"
        assert rc19.find("Style").text == "Standard"
        
        # Bar 20: repeat count overlay with style "Default" and span 2
        b20 = b_map[20]
        rc20 = b20.find("RepeatCount")
        assert rc20 is not None
        assert rc20.find("Count").text == "4"
        assert rc20.find("Span").text == "2"
        assert rc20.find("Style").text == "Default"

    # 4. Symmetrically verify the reverse package parser
    recovered = extract_score_ir_from_gp(out_gp)
    assert isinstance(recovered, ScoreIR)
    
    rec_b1 = recovered.bars[0]
    assert rec_b1.multi_measure_rest_count == 16
    
    rec_b17 = recovered.bars[16]
    assert rec_b17.repeat_count_overlay is not None
    assert rec_b17.repeat_count_overlay.count == 4
    assert rec_b17.repeat_count_overlay.span == 1
    assert rec_b17.repeat_count_overlay.style == "percent"
    
    rec_b18 = recovered.bars[17]
    assert rec_b18.repeat_count_overlay is not None
    assert rec_b18.repeat_count_overlay.count == 4
    assert rec_b18.repeat_count_overlay.span == 1
    assert rec_b18.repeat_count_overlay.style == "numbered"
    
    rec_b19 = recovered.bars[18]
    assert rec_b19.repeat_count_overlay is not None
    assert rec_b19.repeat_count_overlay.count == 4
    assert rec_b19.repeat_count_overlay.span == 1
    assert rec_b19.repeat_count_overlay.style == "standard"
    
    rec_b20 = recovered.bars[19]
    assert rec_b20.repeat_count_overlay is not None
    assert rec_b20.repeat_count_overlay.count == 4
    assert rec_b20.repeat_count_overlay.span == 2
    assert rec_b20.repeat_count_overlay.style == "default"
