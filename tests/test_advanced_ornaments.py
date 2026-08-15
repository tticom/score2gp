import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp


def test_advanced_ornaments_xml(tmp_path) -> None:
    # 1. Load our synthetic test fixture for advanced ornaments
    fixture_path = Path("fixtures/public/test_advanced_ornaments.ir.json")
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "advanced_ornaments.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify no unexpected compile warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract the main Content/score.gpif file
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Retrieve all events inside the XML
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}
        
        # Test Event 1 (Vibrato: Wide)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        
        # Note element has Vibrato child tag
        vibrato_el = n1.find("Vibrato")
        assert vibrato_el is not None
        assert vibrato_el.text == "Wide"
        
        # Properties has Vibrato wave size
        vibrato_prop = n1.find(".//Property[@name='Vibrato']")
        assert vibrato_prop is not None
        wave_size = vibrato_prop.find("WaveSize")
        assert wave_size is not None
        assert wave_size.text == "Wide"
        
        # Test Event 2 (Rasgueado: Direction Up)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        
        # Note has Ornament -> Rasgueado -> Direction
        rasg_el = n2.find("./Ornament/Rasgueado/Direction")
        assert rasg_el is not None
        assert rasg_el.text == "Up"
        
        # Properties has Rasgueado direction
        rasg_prop = n2.find(".//Property[@name='Rasgueado']")
        assert rasg_prop is not None
        direction_prop = rasg_prop.find("Direction")
        assert direction_prop is not None
        assert direction_prop.text == "Up"
        
        # Test Event 3 (Grace: BeforeBeat, Slash True, Duration 16th)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        
        # Event has event-level GraceNotes
        grace_notes_el = e3.find("GraceNotes")
        assert grace_notes_el is not None
        assert grace_notes_el.text == "BeforeBeat"
        
        # Properties has Grace properties
        grace_prop = n3.find(".//Property[@name='Grace']")
        assert grace_prop is not None
        
        slash_prop = grace_prop.find("Slash")
        assert slash_prop is not None
        assert slash_prop.text == "true"
        
        dur_prop = grace_prop.find("Duration")
        assert dur_prop is not None
        assert dur_prop.text == "16th"
        
        pos_prop = grace_prop.find("Position")
        assert pos_prop is not None
        assert pos_prop.text == "BeforeBeat"
        
        # Test Event 4 (Tremolo Picking Speed / Trill Frequency)
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4 is not None
        
        # Tremolo Picking XML elements
        tremolo_picking_el = n4.find("TremoloPicking")
        assert tremolo_picking_el is not None
        assert tremolo_picking_el.get("duration") == "ThirtySecond"
        
        tremolo_prop = n4.find(".//Property[@name='TremoloPicking']")
        assert tremolo_prop is not None
        
        trem_dur = tremolo_prop.find("Duration")
        assert trem_dur is not None
        assert trem_dur.text == "ThirtySecond"
        
        trem_speed = tremolo_prop.find("Speed")
        assert trem_speed is not None
        assert trem_speed.text == "very-fast"
        
        # Trill technique and auxiliary frequency
        trill_el = n4.find("Trill")
        assert trill_el is not None
        
        trill_prop = n4.find(".//Property[@name='Trill']")
        assert trill_prop is not None
        
        trill_fret = trill_prop.find("Fret")
        assert trill_fret is not None
        assert trill_fret.text == "2"
        
        trill_interval = trill_prop.find("Interval")
        assert trill_interval is not None
        assert trill_interval.text == "2"
        
        trill_freq = trill_prop.find("Frequency")
        assert trill_freq is not None
        assert trill_freq.text == "6.500000"
