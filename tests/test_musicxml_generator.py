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


def test_generate_sidecar_cli_plain_xml_and_zipped_mxl(tmp_path):
    import zipfile
    from pathlib import Path
    from typer.testing import CliRunner
    from score2gp.cli import app

    pdf_fixture = Path("fixtures/public/mutopia-bwv-anh-120-minuet-a-minor-a4.pdf")
    assert pdf_fixture.exists()

    # 1. Plain text MusicXML output
    out_xml = tmp_path / "sidecar.musicxml"
    runner = CliRunner()
    result_xml = runner.invoke(app, ["generate-sidecar", "--pdf", str(pdf_fixture), "--out", str(out_xml)])
    assert result_xml.exit_code == 0
    assert out_xml.exists()
    assert not zipfile.is_zipfile(out_xml)
    xml_text = out_xml.read_text(encoding="utf-8")
    assert "<score-partwise" in xml_text

    imported_xml = parse_musicxml(out_xml)
    assert imported_xml is not None
    assert len(imported_xml.parts) >= 1

    # 2. Zipped MXL package output
    out_mxl = tmp_path / "sidecar.mxl"
    result_mxl = runner.invoke(app, ["generate-sidecar", "--pdf", str(pdf_fixture), "--out", str(out_mxl)])
    assert result_mxl.exit_code == 0
    assert out_mxl.exists()
    assert zipfile.is_zipfile(out_mxl)

    with zipfile.ZipFile(out_mxl, "r") as zf:
        namelist = zf.namelist()
        assert "META-INF/container.xml" in namelist
        assert "score.xml" in namelist

    imported_mxl = parse_musicxml(out_mxl)
    assert imported_mxl is not None
    assert len(imported_mxl.parts) >= 1


def test_rest_chord_prevention():
    # Setup outcomes where a rest and note occur at the same start_tick
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C4"},
        {"symbol_type": "quarter_rest_candidate", "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": None},
    ]
    xml_str = generate_musicxml_from_omr(outcomes)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_str)
    notes = root.findall(".//note")
    for note in notes:
        if note.find("rest") is not None:
            assert note.find("chord") is None, "Rest note element must never contain <chord/>"


def test_timing_overlap_resolution_same_voice():
    # Setup two overlapping events on voice 1: quarter note at tick 0 (nominal 960) and eighth note at tick 480 (480 ticks)
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C4", "voice": 1, "start_tick": 0},
        {"symbol_type": "eighth_note_candidate", "x0": 20.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "E4", "voice": 1, "start_tick": 480},
    ]
    from score2gp.notation_omr.timeline import build_staff_timeline_preview
    previews = build_staff_timeline_preview(outcomes)
    v1_evts = [e for e in previews[0]["measures"][0]["events"] if e["voice"] == 1 and e["symbol_type"] != "padding_rest"]
    assert len(v1_evts) == 2
    # The first note's duration should be truncated from 960 to 480 to prevent overlap with the note at tick 480
    assert v1_evts[0]["start_tick"] == 0
    assert v1_evts[0]["duration_ticks"] == 480
    assert v1_evts[1]["start_tick"] == 480


def test_dynamic_time_signature_and_measure_capacity():
    outcomes = [
        {"symbol_type": "quarter_note_candidate", "x0": 10.0, "page_index": 1, "system_index": 1, "staff_index": 1, "clef_resolved_staff_pitch": "C4"},
    ]
    semantic_cands = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "time_signature": {"beats": 12, "beat_type": 8}
        }
    ]
    xml_str = generate_musicxml_from_omr(outcomes, semantic_candidates=semantic_cands)
    assert "<beats>12</beats>" in xml_str
    assert "<beat-type>8</beat-type>" in xml_str

    from score2gp.notation_omr.timeline import build_staff_timeline_preview
    previews = build_staff_timeline_preview(outcomes, semantic_candidates=semantic_cands)
    m1 = previews[0]["measures"][0]
    # D_measure should be 12 * 480 = 5760
    assert m1["voice_1_final_tick"] == 5760
