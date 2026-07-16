import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, validate_roundtrip


def test_system_breaks_and_scaling_xml(tmp_path) -> None:
    # 1. Load the system breaks and staff layout scaling synthetic test fixture
    fixture_path = Path("fixtures/public/test_system_breaks.ir.json")
    score = ScoreIR.from_json_file(fixture_path)

    # 2. Write the ScoreIR to a GP7 binary package
    out_gp = tmp_path / "system_breaks.gp"
    warnings = write_gp(score, out_gp)

    # Verify compile success with zero warnings
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)

    # 3. Unpack and extract Content/score.gpif to verify layout tags structurally
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve layouts under Score
        layout_node = root.find(".//Score/Layout")
        assert layout_node is not None

        # SystemLayout checks
        sys_lay = layout_node.find("SystemLayout")
        assert sys_lay is not None
        assert sys_lay.find("SystemSizePercent").text == "90.0"
        assert sys_lay.find("StaffDistancingCushion").text == "12.5"
        assert sys_lay.find("BarlineStyle").text == "Dashed"

        # StaffLayout checks
        staff_lay = layout_node.find("StaffLayout")
        assert staff_lay is not None
        assert staff_lay.find("StaffSpacingCushion").text == "8.0"
        assert staff_lay.find("StaffSize").text == "1.1"

        # Retrieve MasterBars
        master_bars = root.findall(".//MasterBars/MasterBar")
        mb_map = {int(mb.get("index")): mb for mb in master_bars}

        # Bar 1: Barline is Hidden, layout break is Line
        mb1 = mb_map[1]
        assert mb1.find("Barline").text == "Hidden"
        assert mb1.find("Break").text == "Line"

        # Bar 2: Barline is Dashed, layout break is Page
        mb2 = mb_map[2]
        assert mb2.find("Barline").text == "Dashed"
        assert mb2.find("Break").text == "Page"

        # Retrieve Bars
        bars = root.findall(".//Bars/Bar")
        b_map = {int(b.get("index")): b for b in bars}

        # Bar 1: LayoutBreak is System
        b1 = b_map[1]
        lb1 = b1.find("LayoutBreak")
        assert lb1 is not None
        assert lb1.find("Type").text == "System"

        # Bar 2: LayoutBreak is Page
        b2 = b_map[2]
        lb2 = b2.find("LayoutBreak")
        assert lb2 is not None
        assert lb2.find("Type").text == "Page"

    # 4. Validate round-trip extraction
    res = validate_roundtrip(out_gp, score)
    assert res["valid"], f"Round-trip validation failed: {res['errors']}"


def test_layout_and_title_propagation(tmp_path) -> None:
    from unittest.mock import patch

    from score2gp.build_ir import build_ir_with_diagnostics_from_imports
    from score2gp.deterministic_musicxml import generate_musicxml_sidecar
    from score2gp.musicxml import parse_musicxml
    from score2gp.tabraw import TabRaw

    pdf_path = tmp_path / "test_trace.pdf"
    pdf_path.write_text("fake pdf data that is longer than 10 bytes")
    synthetic_result = {
        "timeline_preview": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "measures": [
                    {
                        "measure_index": 0,
                        "events": [
                            {
                                "candidate_id": "note_1",
                                "symbol_type": "quarter_note_candidate",
                                "voice": 1,
                                "start_tick": 0,
                                "duration_ticks": 960,
                                "resolved_pitch": "C4",
                            }
                        ],
                    }
                ],
            },
            {
                "page_index": 1,
                "system_index": 2,
                "staff_index": 1,
                "measures": [
                    {
                        "measure_index": 1,
                        "section_name": "Exercise 1",
                        "events": [
                            {
                                "candidate_id": "note_2",
                                "symbol_type": "quarter_note_candidate",
                                "voice": 1,
                                "start_tick": 0,
                                "duration_ticks": 960,
                                "resolved_pitch": "E4",
                            }
                        ],
                    }
                ],
            },
        ]
    }

    out_xml = tmp_path / "test_trace.musicxml"
    with patch(
        "score2gp.deterministic_musicxml.run_recognition_on_file",
        return_value=synthetic_result,
    ):
        generate_musicxml_sidecar(pdf_path, out_xml)

    tree = ET.parse(out_xml)
    measures_xml = tree.getroot().findall(".//measure")
    assert len(measures_xml) == 2
    assert measures_xml[0].find("print") is None
    print_tag = measures_xml[1].find("print")
    assert print_tag is not None
    assert print_tag.get("new-system") == "yes"
    rehearsal_tag = measures_xml[1].find(".//direction-type/rehearsal")
    assert rehearsal_tag is not None
    assert rehearsal_tag.text == "Exercise 1"

    parsed_part = parse_musicxml(out_xml)
    tabraw = TabRaw(candidates=[], warnings=[], pdf_layout_class="standard_staff")
    score_ir, _ = build_ir_with_diagnostics_from_imports(parsed_part, tabraw)
    assert len(score_ir.bars) == 2
    assert score_ir.bars[0].layout_break in (None, "none")
    assert score_ir.bars[0].marker is None
    assert score_ir.bars[1].layout_break == "line"
    assert score_ir.bars[1].marker == "Exercise 1"

    out_gp = tmp_path / "test_trace.gp"
    assert write_gp(score_ir, out_gp) == []
    with zipfile.ZipFile(out_gp) as zf:
        gpif_root = ET.fromstring(zf.read("Content/score.gpif"))
    master_bars = gpif_root.findall(".//MasterBars/MasterBar")
    assert len(master_bars) == 2
    assert master_bars[0].find("Section") is None
    assert master_bars[1].find("Break").text == "Line"
    section = master_bars[1].find("Section")
    assert section is not None
    assert section.find("Name").text == "Exercise 1"
