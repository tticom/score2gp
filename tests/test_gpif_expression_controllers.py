from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from score2gp.gp_package import write_gp, extract_score_ir_from_gp, validate_roundtrip
from score2gp.ir import ScoreIR, ExpressionController, BendTechnique


def test_expression_controllers_and_bend_curves_roundtrip(tmp_path) -> None:
    # 1. Load the synthetic expression controllers fixture
    fixture_path = "fixtures/public/test_gpif_expression_controllers.ir.json"
    score = ScoreIR.from_json_file(fixture_path)

    # Validate models loaded correctly
    assert score.metadata.title == "Expressive Guitar Solo"
    
    # Event e1 notes & note-level expression controller & bend curve
    event1 = next(e for b in score.bars for e in b.events if e.id == "e1")
    note1 = event1.notes[0]
    
    assert note1.expression_controller is not None
    assert note1.expression_controller.type == "Expression"
    assert note1.expression_controller.duration_ticks == 1920
    assert len(note1.expression_controller.points) == 3
    assert note1.expression_controller.points[0].offset_ticks == 0
    assert note1.expression_controller.points[0].value == 40.0
    
    bend = next(t for t in note1.techniques if t.kind == "bend")
    assert bend.bend_type == "bend-release"
    assert bend.destination_value == 75.0
    assert bend.graphic_duration == 960
    assert len(bend.points) == 3
    assert bend.points[1].offset_ticks == 480
    assert bend.points[1].semitones == 1.0
    assert bend.points[1].v_x == 0.25
    assert bend.points[1].v_y == 0.5

    # Event e2 and event-level expression controller
    event2 = next(e for b in score.bars for e in b.events if e.id == "e2")
    assert event2.expression_controller is not None
    assert event2.expression_controller.type == "Volume"
    assert event2.expression_controller.duration_ticks == 1920
    assert len(event2.expression_controller.points) == 2
    assert event2.expression_controller.points[1].offset_ticks == 1920
    assert event2.expression_controller.points[1].value == 90.0

    # 2. Write the score to a GP package
    out_gp = tmp_path / "expressive_solo.gp"
    warnings = write_gp(score, out_gp)
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)

    # 3. Read & Verify Zip contents and XML layouts
    with zipfile.ZipFile(out_gp, "r") as zf:
        members = zf.namelist()
        assert "Content/score.gpif" in members

        score_xml = zf.read("Content/score.gpif")
        score_root = ET.fromstring(score_xml)

        # Verify beat-level <ExpressionController> on Event e2
        ev2_node = score_root.find(".//Bars/Bar/Voices/Voice/Event[@id='e2']")
        assert ev2_node is not None
        ec2_node = ev2_node.find("ExpressionController")
        assert ec2_node is not None
        assert ec2_node.get("type") == "Volume"
        assert ec2_node.find("Duration").text == "1920"
        points2 = ec2_node.findall("Point")
        assert len(points2) == 2
        assert points2[0].get("offset") == "0"
        assert float(points2[0].get("value")) == 50.0
        assert points2[1].get("offset") == "1920"
        assert float(points2[1].get("value")) == 90.0

        # Verify note-level <ExpressionController> on Note under Event e1
        ev1_node = score_root.find(".//Bars/Bar/Voices/Voice/Event[@id='e1']")
        assert ev1_node is not None
        note1_node = ev1_node.find("Note")
        assert note1_node is not None
        ec1_node = note1_node.find("ExpressionController")
        assert ec1_node is not None
        assert ec1_node.get("type") == "Expression"
        assert ec1_node.find("Duration").text == "1920"
        points1 = ec1_node.findall("Point")
        assert len(points1) == 3
        assert points1[0].get("offset") == "0"
        assert float(points1[0].get("value")) == 40.0

        # Verify note-level multi-point <Bend> properties
        bend_node = note1_node.find("Bend")
        assert bend_node is not None
        assert bend_node.get("type") == "bend-release"
        assert bend_node.find("DestinationValue").text == "75.0"
        assert bend_node.find("GraphicDuration").text == "960"

        bend_pts = bend_node.findall("Point")
        assert len(bend_pts) == 3
        assert float(bend_pts[0].get("offset")) == 0.0
        assert float(bend_pts[0].get("value")) == 0.0
        assert float(bend_pts[1].get("offset")) == 25.0 # (480 / 1920) * 100
        assert float(bend_pts[1].get("value")) == 50.0 # 1.0 * 50
        assert float(bend_pts[1].get("v_x")) == 0.25
        assert float(bend_pts[1].get("v_y")) == 0.5

        # Verify visual Properties block
        props_node = note1_node.find(".//Properties")
        assert props_node is not None
        bended_enable = props_node.find(".//Property[@name='Bended']/Enable")
        assert bended_enable is not None
        dest_val_prop = props_node.find(".//Property[@name='BendDestinationValue']/Float")
        assert dest_val_prop is not None
        assert float(dest_val_prop.text) == 75.0
        gd_prop = props_node.find(".//Property[@name='BendGraphicDuration']/Float")
        assert gd_prop is not None
        assert float(gd_prop.text) == 960.0

    # 4. Extract and check round-trip symmetric equality
    recovered = extract_score_ir_from_gp(out_gp)
    assert isinstance(recovered, ScoreIR)
    
    rec_event1 = next(e for b in recovered.bars for e in b.events if e.id == "e1")
    rec_note1 = rec_event1.notes[0]
    
    assert rec_note1.expression_controller is not None
    assert rec_note1.expression_controller.type == "Expression"
    assert rec_note1.expression_controller.duration_ticks == 1920
    assert len(rec_note1.expression_controller.points) == 3
    assert rec_note1.expression_controller.points[0].offset_ticks == 0
    assert rec_note1.expression_controller.points[0].value == 40.0
    
    rec_bend = next(t for t in rec_note1.techniques if t.kind == "bend")
    assert rec_bend.bend_type == "bend-release"
    assert rec_bend.destination_value == 75.0
    assert rec_bend.graphic_duration == 960
    assert len(rec_bend.points) == 3
    assert abs(rec_bend.points[1].offset_ticks - 480) <= 2
    assert rec_bend.points[1].semitones == 1.0
    assert rec_bend.points[1].v_x == 0.25
    assert rec_bend.points[1].v_y == 0.5

    rec_event2 = next(e for b in recovered.bars for e in b.events if e.id == "e2")
    assert rec_event2.expression_controller is not None
    assert rec_event2.expression_controller.type == "Volume"
    assert rec_event2.expression_controller.duration_ticks == 1920
    assert len(rec_event2.expression_controller.points) == 2
    assert rec_event2.expression_controller.points[1].offset_ticks == 1920
    assert rec_event2.expression_controller.points[1].value == 90.0

    # 5. Call validate_roundtrip and assert success
    rt_res = validate_roundtrip(out_gp, score)
    assert rt_res["valid"] is True
    assert rt_res["errors"] == []
