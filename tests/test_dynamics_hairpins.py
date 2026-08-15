import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp


def test_dynamics_hairpins_xml(tmp_path) -> None:
    # 1. Load the dynamics and hairpins synthetic test fixture
    fixture_path = Path("fixtures/public/test_dynamics_hairpins.ir.json")
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "dynamics_hairpins.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}
        
        # Event e1: dynamic P, crescendo hairpin visual wedge
        e1 = event_map["e1"]
        assert e1.find("Dynamic").text == "P"
        
        hp1 = e1.find("Hairpin")
        assert hp1 is not None
        assert hp1.get("type") == "Crescendo"
        assert hp1.find("Type").text == "Crescendo"
        assert hp1.find("StartBeat").text == "1"
        assert hp1.find("StopBeat").text == "3"
        assert hp1.find("Thickness").text == "2.500000"
        
        vp1 = hp1.find("ValuePath")
        assert vp1 is not None
        vals1 = [float(v.text) for v in vp1.findall("Value")]
        assert vals1 == [10.0, 30.0, 60.0]
        
        # Event e2: note staccatissimo
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        assert n2.find("Staccatissimo") is not None
        
        acc_prop2 = n2.find(".//Property[@name='Accentuation']/Value")
        assert acc_prop2 is not None
        assert acc_prop2.text == "Staccatissimo"
        
        # Event e3: note marcato (heavy accent)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        assert n3.find("Accent").text == "2"
        assert n3.find("HeavyAccent") is not None
        
        acc_prop3 = n3.find(".//Property[@name='Accentuation']/Value")
        assert acc_prop3 is not None
        assert acc_prop3.text == "Marcato"
        
        # Event e4: decrescendo hairpin visual wedge
        e4 = event_map["e4"]
        hp4 = e4.find("Hairpin")
        assert hp4 is not None
        assert hp4.get("type") == "Decrescendo"
        assert hp4.find("Type").text == "Decrescendo"
        assert hp4.find("StartBeat").text == "3"
        assert hp4.find("StopBeat").text == "4"
        assert hp4.find("Thickness").text == "1.500000"
        
        vp4 = hp4.find("ValuePath")
        assert vp4 is not None
        vals4 = [float(v.text) for v in vp4.findall("Value")]
        assert vals4 == [60.0, 20.0]
