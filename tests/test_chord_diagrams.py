import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, extract_score_ir_from_gp, validate_roundtrip


def test_chord_diagrams_xml(tmp_path) -> None:
    # 1. Load the chord diagrams synthetic test fixture
    fixture_path = Path("fixtures/public/test_chord_diagrams.ir.json")
    assert fixture_path.exists()
    score = ScoreIR.from_json_file(fixture_path)
    
    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "test_chord_diagrams.gp"
    warnings = write_gp(score, out_gp)
    
    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    # 3. Unpack and extract Content/score.gpif
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Verify events
        events = root.findall(".//Voice/Event")
        assert len(events) == 3
        
        # Event 1: ChordDiagram Cmaj7
        e1 = events[0]
        chord_diagram_el = e1.find("ChordDiagram")
        assert chord_diagram_el is not None
        assert chord_diagram_el.get("name") == "Cmaj7"
        assert chord_diagram_el.get("stringCount") == "6"
        assert chord_diagram_el.get("fretCount") == "5"
        assert chord_diagram_el.get("baseFret") == "1"
        
        frets = chord_diagram_el.findall("Fret")
        assert len(frets) == 5
        
        # Verify note-level LeftHandFingering and RightHandFingering properties under Notes
        notes = e1.findall(".//Note")
        assert len(notes) == 3
        
        lh_fingering_count = 0
        rh_fingering_count = 0
        for note_el in notes:
            props = note_el.findall(".//Properties/Property")
            for prop in props:
                if prop.get("name") == "LeftHandFingering":
                    lh_fingering_count += 1
                elif prop.get("name") == "RightHandFingering":
                    rh_fingering_count += 1
        assert lh_fingering_count == 3
        assert rh_fingering_count == 3
        
        # Event 2: ChordDiagram G7
        e2 = events[1]
        chord_diagram_el2 = e2.find("ChordDiagram")
        assert chord_diagram_el2 is not None
        assert chord_diagram_el2.get("name") == "G7"
        
        # Event 3: Chord symbol Dm7 without diagram
        e3 = events[2]
        assert e3.find("ChordDiagram") is None
        assert e3.find("Chord").text == "Dm7"
        
    # 4. Symmetrically verify the reverse package parser & roundtrip function
    recovered = extract_score_ir_from_gp(out_gp)
    assert isinstance(recovered, ScoreIR)
    
    assert len(recovered.bars) == 1
    rev_events = recovered.bars[0].events
    assert len(rev_events) == 3
    
    # Event 1 round-trip chord diagram
    re1 = rev_events[0]
    assert re1.chord_symbol == "Cmaj7"
    assert re1.chord_diagram is not None
    assert re1.chord_diagram.name == "Cmaj7"
    assert re1.chord_diagram.base_fret == 1
    assert len(re1.chord_diagram.frets) == 5
    assert len(re1.chord_diagram.fingers) == 2
    assert re1.chord_diagram.fingers[0].finger == "Ring"
    
    # Note fingerings on Event 1
    rn1_0 = next(n for n in re1.notes if n.string == 5)
    assert rn1_0.left_hand_fingering == "ring"
    assert rn1_0.right_hand_fingering == "thumb"
    
    # Run the full validation roundtrip assertion
    rt_res = validate_roundtrip(out_gp, score)
    assert rt_res["valid"], f"Roundtrip validation failed: {rt_res['errors']}"
