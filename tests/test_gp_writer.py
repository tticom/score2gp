from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from score2gp.gp_package import compare_gp, inspect_gp, validate_gp, write_gp
from score2gp.ir import ScoreIR


def test_write_gp_creates_valid_zip(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    out = tmp_path / "tiny.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        assert "VERSION" in zf.namelist()
        assert "Content/score.gpif" in zf.namelist()
        ET.fromstring(zf.read("Content/score.gpif"))


def test_validate_and_inspect_generated_gp(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    out = tmp_path / "tiny.gp"
    write_gp(score, out)

    validation = validate_gp(out)
    assert validation["is_zip"] is True
    assert validation["xml_well_formed"] is True
    assert validation["errors"] == []

    summary = inspect_gp(out)
    assert summary["tracks"] == ["Guitar"]
    assert summary["tempo"] == "66"
    assert summary["time_signatures"] == ["12/8"]
    assert summary["bar_count"] == 1
    assert summary["note_count"] == 2
    assert summary["chord_symbols"] == ["E"]
    assert summary["techniques"] == ["slide"]


def test_compare_generated_gp_semantics(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    expected = tmp_path / "expected.gp"
    actual = tmp_path / "actual.gp"
    write_gp(score, expected)
    write_gp(score, actual)

    comparison = compare_gp(expected, actual)
    assert comparison["matches"] is True
    assert comparison["differences"] == {}


def test_write_gp_warns_for_unsupported_scoreir_fields(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    data = score.model_dump(mode="json")
    data["tracks"][0]["midi_program"] = 30
    data["bars"][0]["events"][0]["notes"][0]["techniques"] = [
        {"kind": "let-ring"}
    ]
    score_with_unsupported = ScoreIR.model_validate(data)

    out = tmp_path / "warnings.gp"
    warnings = write_gp(score_with_unsupported, out)

    assert any("MIDI" in warning for warning in warnings)
    assert any("technique 'let-ring'" in warning for warning in warnings)
    assert zipfile.is_zipfile(out)



def test_gpif_ties_and_tuplets(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_ties_tuplets.ir.json")
    out = tmp_path / "ties_tuplets.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check e1 (tie start)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        assert n1.get("tie") == "start"
        t1 = n1.find("Tie")
        assert t1 is not None
        assert t1.get("origin") == "true"
        assert t1.get("destination") == "false"

        # Check e2 (tie continue)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        assert n2.get("tie") == "continue"
        t2 = n2.find("Tie")
        assert t2 is not None
        assert t2.get("origin") == "true"
        assert t2.get("destination") == "true"

        # Check e3 (tie stop)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        assert n3.get("tie") == "stop"
        t3 = n3.find("Tie")
        assert t3 is not None
        assert t3.get("origin") == "false"
        assert t3.get("destination") == "true"

        # Check Rhythm for e1
        r1 = e1.find("Rhythm")
        assert r1 is not None
        nv1 = r1.find("NoteValue")
        assert nv1 is not None
        assert nv1.text == "Quarter"
        assert r1.find("PrimaryTuplet") is None

        # Check Rhythm for et1 (triplet)
        et1 = event_map["et1"]
        rt1 = et1.find("Rhythm")
        assert rt1 is not None
        nv_t1 = rt1.find("NoteValue")
        assert nv_t1 is not None
        assert nv_t1.text == "Eighth"
        pt1 = rt1.find("PrimaryTuplet")
        assert pt1 is not None
        assert pt1.get("num") == "3"
        assert pt1.get("den") == "2"


def test_gpif_core_techniques(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_core_techniques.ir.json")
    out = tmp_path / "techniques.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check e1 (slide origin)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        assert n1.find("Slide") is not None
        slide_flag = n1.find(".//Property[@name='Slide']/Flags")
        assert slide_flag is not None
        assert slide_flag.text == "2"

        # Check e2 (slide destination - has no slide tag or slide property by default)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        assert n2.find("Slide") is None

        # Check e3 (bend)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        assert n3.find("Bend") is not None
        bended = n3.find(".//Property[@name='Bended']/Enable")
        assert bended is not None
        bend_val = n3.find(".//Property[@name='BendDestinationValue']/Float")
        assert bend_val is not None
        assert float(bend_val.text) == 50.0

        # Check e4 (hammer-on origin)
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4 is not None
        assert n4.find("HO") is not None
        hopo_org = n4.find(".//Property[@name='HopoOrigin']/Enable")
        assert hopo_org is not None
        assert n4.find(".//Property[@name='HopoDestination']") is None

        # Check e5 (hammer-on destination)
        e5 = event_map["e5"]
        n5 = e5.find("Note")
        assert n5 is not None
        assert n5.find("HO") is None
        assert n5.find(".//Property[@name='HopoOrigin']") is None
        hopo_dst = n5.find(".//Property[@name='HopoDestination']/Enable")
        assert hopo_dst is not None

        # Check e6 (pull-off origin)
        e6 = event_map["e6"]
        n6 = e6.find("Note")
        assert n6 is not None
        assert n6.find("PO") is not None
        hopo_org2 = n6.find(".//Property[@name='HopoOrigin']/Enable")
        assert hopo_org2 is not None

        # Check e7 (pull-off destination)
        e7 = event_map["e7"]
        n7 = e7.find("Note")
        assert n7 is not None
        assert n7.find("PO") is None
        hopo_dst2 = n7.find(".//Property[@name='HopoDestination']/Enable")
        assert hopo_dst2 is not None
