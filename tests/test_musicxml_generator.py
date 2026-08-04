import pytest
from src.score2gp.notation_omr.musicxml_generator import generate_musicxml_from_omr
from src.score2gp.musicxml import parse_musicxml, analyze_musicxml_timing
import xml.etree.ElementTree as ET

def test_generate_monophonic_musicxml():
    # Setup outcomes for 3 notes in sequence (C5, E5, G5)
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 2, "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 4, "x0": 50.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "E5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 6, "x0": 90.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "G5"}
    ]
    
    # 1 barline candidate to define a bar ending
    outcomes.append({"symbol_type": "barline_candidate", "x0": 150.0, "page_index": 1, "system_index": 1, "staff_index": 1})
    
    xml_str = generate_musicxml_from_omr(outcomes)
    assert xml_str != ""
    assert "<step>C</step>" in xml_str
    assert "<step>E</step>" in xml_str
    assert "<step>G</step>" in xml_str
    assert "<backup>" not in xml_str


def test_generate_polyphonic_musicxml():
    # Setup outcomes for Voice 1 (stems up, e.g. G5 at x=10) and Voice 2 (stems down, e.g. C4 at x=10)
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 6, "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "G5", "stem_direction": "up"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -4, "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C4", "stem_direction": "down"}
    ]
    outcomes.append({"symbol_type": "barline_candidate", "x0": 150.0, "page_index": 1, "system_index": 1, "staff_index": 1})
    
    xml_str = generate_musicxml_from_omr(outcomes)
    assert xml_str != ""
    assert "<backup>" in xml_str
    assert "<voice>1</voice>" in xml_str
    assert "<voice>2</voice>" in xml_str


def test_generate_chord_musicxml():
    # Setup outcomes for 2 notes at the exact same horizontal coordinate (C5 and E5 at x=10)
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 2, "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 4, "x0": 10.1, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "E5"}
    ]
    outcomes.append({"symbol_type": "barline_candidate", "x0": 150.0, "page_index": 1, "system_index": 1, "staff_index": 1})
    
    xml_str = generate_musicxml_from_omr(outcomes)
    assert xml_str != ""
    assert "<chord/>" in xml_str


def test_musicxml_generator_roundtrip(tmp_path):
    # Setup standard 4/4 measure outcomes (4 quarter notes to fill 3840 ticks)
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 2, "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 4, "x0": 40.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "E5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 6, "x0": 70.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "G5"},
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 8, "x0": 100.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C6"}
    ]
    outcomes.append({"symbol_type": "barline_candidate", "x0": 150.0, "page_index": 1, "system_index": 1, "staff_index": 1})
    
    xml_str = generate_musicxml_from_omr(outcomes)
    
    # Write to a temp file and load back with score2gp parser
    xml_file = tmp_path / "roundtrip.musicxml"
    xml_file.write_text(xml_str, encoding="utf-8")
    
    imported = parse_musicxml(xml_file)
    issues = analyze_musicxml_timing(imported)
    
    # Assert no timing or overlap errors were introduced
    assert not any(issue.severity == "error" for issue in issues)
    
    # Check that parts and notes parsed back correctly
    assert len(imported.parts) == 1
    measure = imported.parts[0].measures[0]
    assert len(measure.notes) == 4
    assert [n.pitch.step for n in measure.notes] == ["C", "E", "G", "C"]
