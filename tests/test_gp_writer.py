from __future__ import annotations

import json
import zipfile
from xml.etree import ElementTree as ET

from score2gp.gp_package import compare_gp, inspect_gp, validate_gp, write_gp
from score2gp.ir import ScoreIR, ScoreBooklet


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
    data["tracks"][0]["staff_count"] = 2
    data["bars"][0]["events"][0]["notes"][0]["techniques"] = [
        {"kind": "unsupported", "label": "some-weird-technique"}
    ]
    score_with_unsupported = ScoreIR.model_validate(data)

    out = tmp_path / "warnings.gp"
    warnings = write_gp(score_with_unsupported, out)

    assert any("staff_count" in warning for warning in warnings)
    assert any("technique 'unsupported'" in warning for warning in warnings)
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


def test_gpif_grace_and_spans(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_grace_and_spans.ir.json")
    out = tmp_path / "grace_spans.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check e1 (let-ring start)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        assert n1.find("LetRing") is not None
        assert e1.find("GraceNotes") is None

        # Check e2 (inside let-ring span, grace note before beat)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        assert n2.find("LetRing") is not None
        gn2 = e2.find("GraceNotes")
        assert gn2 is not None
        assert gn2.text == "BeforeBeat"

        # Check e3 (let-ring end)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        assert n3.find("LetRing") is not None
        assert e3.find("GraceNotes") is None

        # Check e4 (outside let-ring)
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4 is not None
        assert n4.find("LetRing") is None

        # Check e5 (palm-mute start)
        e5 = event_map["e5"]
        n5 = e5.find("Note")
        assert n5 is not None
        assert n5.find("PalmMute") is not None
        assert e5.find("GraceNotes") is None

        # Check e6 (inside palm-mute span, on-beat grace note)
        e6 = event_map["e6"]
        n6 = e6.find("Note")
        assert n6 is not None
        assert n6.find("PalmMute") is not None
        gn6 = e6.find("GraceNotes")
        assert gn6 is not None
        assert gn6.text == "OnBeat"

        # Check e7 (palm-mute end)
        e7 = event_map["e7"]
        n7 = e7.find("Note")
        assert n7 is not None
        assert n7.find("PalmMute") is not None

        # Check e8 (outside palm-mute)
        e8 = event_map["e8"]
        n8 = e8.find("Note")
        assert n8 is not None
        assert n8.find("PalmMute") is None


def test_gpif_multi_voice(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_multi_voice.ir.json")
    out = tmp_path / "multi_voice.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve Bar node
        bar = root.find(".//Bars/Bar")
        assert bar is not None

        # Retrieve Voices tag under Bar
        voices_node = bar.find("Voices")
        assert voices_node is not None

        # Verify Voice elements
        voices = voices_node.findall("Voice")
        assert len(voices) == 2

        # Voice 0
        v0 = voices[0]
        assert v0.get("id") == "0"
        v0_events = v0.findall("Event")
        assert len(v0_events) == 4
        for e in v0_events:
            assert e.get("voice") == "0"

        # Check event IDs in order of onsets
        assert [e.get("id") for e in v0_events] == ["e1", "e2", "e3", "e4"]

        # Voice 1
        v1 = voices[1]
        assert v1.get("id") == "1"
        v1_events = v1.findall("Event")
        assert len(v1_events) == 2
        for e in v1_events:
            assert e.get("voice") == "1"
        assert [e.get("id") for e in v1_events] == ["e5", "e6"]


def test_gpif_dynamics_and_vibrato(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_dynamics_vibrato.ir.json")
    out = tmp_path / "dynamics_vibrato.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check Event e1: dynamic is MF, and its note has Vibrato: Slight
        e1 = event_map["e1"]
        dyn1 = e1.find("Dynamic")
        assert dyn1 is not None
        assert dyn1.text == "MF"

        n1 = e1.find("Note")
        assert n1 is not None
        vib1 = n1.find("Vibrato")
        assert vib1 is not None
        assert vib1.text == "Slight"

        # Check Event e2: dynamic is F, and its note has Vibrato: Wide
        e2 = event_map["e2"]
        dyn2 = e2.find("Dynamic")
        assert dyn2 is not None
        assert dyn2.text == "F"

        n2 = e2.find("Note")
        assert n2 is not None
        vib2 = n2.find("Vibrato")
        assert vib2 is not None
        assert vib2.text == "Wide"


def test_gpif_text_and_slides(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_text_and_slides.ir.json")
    out = tmp_path / "text_slides.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check e1 (Verse, shift slide: Flags=1)
        e1 = event_map["e1"]
        assert e1.find("FreeText") is not None and e1.find("FreeText").text == "Verse"
        assert e1.find("Direction") is not None and e1.find("Direction").text == "Verse"
        assert e1.find("Text") is not None and e1.find("Text").text == "Verse"
        n1 = e1.find("Note")
        assert n1 is not None and n1.find("Slide") is not None
        flags1 = n1.find(".//Property[@name='Slide']/Flags")
        assert flags1 is not None and flags1.text == "1"

        # Check e2 (Chorus, legato slide: Flags=2)
        e2 = event_map["e2"]
        assert e2.find("FreeText") is not None and e2.find("FreeText").text == "Chorus"
        n2 = e2.find("Note")
        assert n2 is not None and n2.find("Slide") is not None
        flags2 = n2.find(".//Property[@name='Slide']/Flags")
        assert flags2 is not None and flags2.text == "2"

        # Check e3 (Solo, slide-in up: Flags=16)
        e3 = event_map["e3"]
        assert e3.find("FreeText") is not None and e3.find("FreeText").text == "Solo"
        n3 = e3.find("Note")
        assert n3 is not None and n3.find("Slide") is not None
        flags3 = n3.find(".//Property[@name='Slide']/Flags")
        assert flags3 is not None and flags3.text == "16"

        # Check e4 (Bridge, slide-in down: Flags=32)
        e4 = event_map["e4"]
        assert e4.find("FreeText") is not None and e4.find("FreeText").text == "Bridge"
        n4 = e4.find("Note")
        assert n4 is not None and n4.find("Slide") is not None
        flags4 = n4.find(".//Property[@name='Slide']/Flags")
        assert flags4 is not None and flags4.text == "32"

        # Check e5 (Outro, slide-out up: Flags=8)
        e5 = event_map["e5"]
        assert e5.find("FreeText") is not None and e5.find("FreeText").text == "Outro"
        n5 = e5.find("Note")
        assert n5 is not None and n5.find("Slide") is not None
        flags5 = n5.find(".//Property[@name='Slide']/Flags")
        assert flags5 is not None and flags5.text == "8"

        # Check e6 (Ending, slide-out down: Flags=4)
        e6 = event_map["e6"]
        assert e6.find("FreeText") is not None and e6.find("FreeText").text == "Ending"
        n6 = e6.find("Note")
        assert n6 is not None and n6.find("Slide") is not None
        flags6 = n6.find(".//Property[@name='Slide']/Flags")
        assert flags6 is not None and flags6.text == "4"


def test_gpif_dead_notes_and_tremolo(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_dead_notes_tremolo.ir.json")
    out = tmp_path / "dead_tremolo.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Retrieve events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Check e1 (DeadNote)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        assert n1.find("DeadNote") is not None

        # Check e2 (TremoloBar)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        tb = n2.find("TremoloBar")
        assert tb is not None

        points = tb.findall("Point")
        assert len(points) == 3
        # Point 1: offset=0, value=0
        assert float(points[0].get("offset")) == 0.0
        assert float(points[0].get("value")) == 0.0

        # Point 2: offset=50.000000, value=-100.000000
        assert float(points[1].get("offset")) == 50.0
        assert float(points[1].get("value")) == -100.0

        # Point 3: offset=100.000000, value=0.0
        assert float(points[2].get("offset")) == 100.0
        assert float(points[2].get("value")) == 0.0


def test_gpif_chords_and_vibrato_curves(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_chords_vibrato_curves.ir.json")
    out = tmp_path / "chords_vibrato.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Check Track Staff Properties DiagramCollection
        diag_coll = root.find(".//Property[@name='DiagramCollection']")
        assert diag_coll is not None

        items = diag_coll.findall(".//Items/Item")
        assert len(items) == 1
        item = items[0]
        assert item.get("id") == "1"
        assert item.get("name") == "Ab"

        diag = item.find("Diagram")
        assert diag is not None
        assert diag.get("stringCount") == "6"
        assert diag.get("fretCount") == "5"
        assert diag.get("baseFret") == "6"

        fret = diag.find("Fret")
        assert fret is not None
        assert fret.get("string") == "5"
        assert fret.get("fret") == "1"

        pos = diag.find(".//Fingering/Position")
        assert pos is not None
        assert pos.get("finger") == "Index"
        assert pos.get("fret") == "1"
        assert pos.get("string") == "5"

        key = item.find(".//Chord/KeyNote")
        assert key is not None
        assert key.get("step") == "A"
        assert key.get("accidental") == "Flat"

        # Check Events
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1: has Chord referencing ID 1 and ChordDiagram block directly
        e1 = event_map["e1"]
        ch = e1.find("Chord")
        assert ch is not None
        assert ch.text == "1"

        cd = e1.find("ChordDiagram")
        assert cd is not None
        assert cd.get("name") == "Ab"
        assert cd.get("stringCount") == "6"
        assert cd.get("fretCount") == "5"
        assert cd.get("baseFret") == "6"

        # Event e2: has VibratoCurve under Note
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None

        vc = n2.find("VibratoCurve")
        assert vc is not None

        points = vc.findall("Point")
        assert len(points) == 3

        # Point 1: offset=0.0, value=20.0, speed=medium
        assert float(points[0].get("offset")) == 0.0
        assert float(points[0].get("value")) == 20.0
        assert points[0].get("speed") == "medium"

        # Point 2: offset=50.0, value=80.0, speed=fast
        assert float(points[1].get("offset")) == 50.0
        assert float(points[1].get("value")) == 80.0
        assert points[1].get("speed") == "fast"

        # Point 3: offset=100.0, value=100.0, speed=fast
        assert float(points[2].get("offset")) == 100.0
        assert float(points[2].get("value")) == 100.0
        assert points[2].get("speed") == "fast"


def test_gpif_tremolo_and_percussive(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_tremolo_percussive.ir.json")
    out = tmp_path / "tremolo_percussive.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1: tremolo-picking
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1 is not None
        tp = n1.find("TremoloPicking")
        assert tp is not None
        assert tp.get("duration") == "ThirtySecond"

        # Event e2: slap
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2 is not None
        assert n2.find("Slapped") is not None
        slap_enable = n2.find(".//Property[@name='Slapped']/Enable")
        assert slap_enable is not None

        # Event e3: pop
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3 is not None
        assert n3.find("Popped") is not None
        pop_enable = n3.find(".//Property[@name='Popped']/Enable")
        assert pop_enable is not None

        # Event e4: tapping
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4 is not None
        assert n4.find("Tapped") is not None
        tapped_enable = n4.find(".//Property[@name='Tapped']/Enable")
        assert tapped_enable is not None


def test_gpif_mixer_and_tempo(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_mixer_tempo.ir.json")
    out = tmp_path / "mixer_tempo.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify Track Mixer settings
        tracks = root.findall(".//Track[@id='gtr-1']")
        assert len(tracks) == 1
        track = tracks[0]
        mixer = track.find("Mixer")
        assert mixer is not None

        volume = mixer.find("Volume")
        assert volume is not None
        assert volume.text == "85"

        pan = mixer.find("Pan")
        assert pan is not None
        assert pan.text == "25"

        mute = mixer.find("Mute")
        assert mute is not None
        assert mute.text == "false"

        solo = mixer.find("Solo")
        assert solo is not None
        assert solo.text == "true"

        # 2. Verify Bar-level Tempo overrides
        mb1 = root.find(".//MasterBar[@index='1']")
        assert mb1 is not None
        assert mb1.find("Tempo") is None

        mb2 = root.find(".//MasterBar[@index='2']")
        assert mb2 is not None
        tempo = mb2.find("Tempo")
        assert tempo is not None

        val = tempo.find("Value")
        assert val is not None
        assert val.text == "140"

        text = tempo.find("Text")
        assert text is not None
        assert text.text == "Allegro"


def test_gpif_tuning_and_formatting(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_tuning_formatting.ir.json")
    out = tmp_path / "tuning_formatting.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify Track Visual Metadata
        tracks = root.findall(".//Track[@id='gtr-1']")
        assert len(tracks) == 1
        track = tracks[0]

        color = track.find("Color")
        assert color is not None
        assert color.text == "237 116 116"

        layout = track.find("SystemsDefautLayout")
        assert layout is not None
        assert layout.text == "3"

        # 2. Verify Staff Properties and Custom Tuning
        staves = track.find("Staves")
        assert staves is not None
        staff = staves.find("Staff")
        assert staff is not None
        props = staff.find("Properties")
        assert props is not None

        # Verify CapoFret
        capo_prop = props.find(".//Property[@name='CapoFret']")
        assert capo_prop is not None
        assert capo_prop.find("Fret").text == "0"

        # Verify FretCount
        fret_prop = props.find(".//Property[@name='FretCount']")
        assert fret_prop is not None
        assert fret_prop.find("Number").text == "24"

        # Verify PartialCapoStringFlags
        flags_prop = props.find(".//Property[@name='PartialCapoStringFlags']")
        assert flags_prop is not None
        assert flags_prop.find("Bitset").text == "000000"

        # Verify Tuning Pitches and Instrument Type
        tuning_prop = props.find(".//Property[@name='Tuning']")
        assert tuning_prop is not None
        assert tuning_prop.find("Pitches").text == "38 45 50 55 59 64"
        assert tuning_prop.find("Instrument").text == "Guitar"


def test_gpif_annotations_and_layout_breaks(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_annotations_breaks.ir.json")
    out = tmp_path / "annotations_breaks.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify Beat-level Text Annotations
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        e1 = event_map["e1"]
        t1 = e1.find("Text")
        assert t1 is not None
        assert t1.text == "Intro"

        ft1 = e1.find("FreeText")
        assert ft1 is not None
        assert ft1.text == "Intro"

        dir1 = e1.find("Direction")
        assert dir1 is not None
        assert dir1.text == "Intro"

        e3 = event_map["e3"]
        t3 = e3.find("Text")
        assert t3 is not None
        assert t3.text == "Verse"

        # 2. Verify MasterBar Breaks (Line/Page)
        mb1 = root.find(".//MasterBar[@index='1']")
        assert mb1 is not None
        b1 = mb1.find("Break")
        assert b1 is not None
        assert b1.text == "Line"

        mb2 = root.find(".//MasterBar[@index='2']")
        assert mb2 is not None
        b2 = mb2.find("Break")
        assert b2 is not None
        assert b2.text == "Page"


def test_gpif_notation_layout_formatting(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_notation_layout.ir.json")
    out = tmp_path / "notation_layout.gp"
    warnings = write_gp(score, out)
    assert warnings == ["track 'piano-1' tablature_enabled=false is not represented in the minimal GPIF writer"]
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify PageSetup Sizing, Margins and Scaling
        ps = root.find(".//PageSetup")
        assert ps is not None
        assert ps.find("Width").text == "210.0"
        assert ps.find("Height").text == "297.0"
        assert ps.find("MarginTop").text == "15.0"
        assert ps.find("MarginBottom").text == "15.0"
        assert ps.find("MarginLeft").text == "15.0"
        assert ps.find("MarginRight").text == "15.0"
        assert ps.find("Scale").text == "1.25"

        # 2. Verify Score Layout view defaults
        s_layout = root.find(".//ScoreSystemsDefaultLayout")
        assert s_layout is not None
        assert s_layout.text == "4"

        s_layout_val = root.find(".//ScoreSystemsLayout")
        assert s_layout_val is not None
        assert s_layout_val.text == "4"

        # 3. Verify Multi-track MasterTrack Stack Ordering
        mt = root.find(".//MasterTrack")
        assert mt is not None
        assert mt.find("Tracks").text == "gtr-1 piano-1"

        # 4. Verify individual Track Systems Layout Overrides
        t_gtr = root.find(".//Track[@id='gtr-1']")
        assert t_gtr is not None
        assert t_gtr.find("SystemsDefautLayout").text == "3"
        assert t_gtr.find("SystemsLayout").text == "3"

        t_pno = root.find(".//Track[@id='piano-1']")
        assert t_pno is not None
        assert t_pno.find("SystemsDefautLayout").text == "1"
        assert t_pno.find("SystemsLayout").text == "1"


def test_gpif_notation_layout_defaults(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_notation_layout.ir.json")

    # 1. Test layout with empty track_order (should default to declare all tracks in original order)
    score.layout.track_order = []

    out1 = tmp_path / "notation_layout_empty_order.gp"
    write_gp(score, out1)
    assert zipfile.is_zipfile(out1)

    with zipfile.ZipFile(out1) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        mt = root.find(".//MasterTrack")
        assert mt is not None
        assert mt.find("Tracks").text == "gtr-1 piano-1"

    # 2. Test layout being None (should cleanly default page setup settings)
    data = score.model_dump(mode="json")
    score_no_layout = ScoreIR.model_validate(data)
    object.__setattr__(score_no_layout, "layout", None)

    out2 = tmp_path / "notation_layout_none.gp"
    write_gp(score_no_layout, out2)
    assert zipfile.is_zipfile(out2)

    with zipfile.ZipFile(out2) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        ps = root.find(".//PageSetup")
        assert ps is not None
        assert ps.find("Width").text == "210.0"
        assert ps.find("Height").text == "297.0"
        assert ps.find("MarginTop").text == "15.0"
        assert ps.find("MarginBottom").text == "15.0"
        assert ps.find("Scale").text == "1.0"

        mt = root.find(".//MasterTrack")
        assert mt is not None
        assert mt.find("Tracks").text == "gtr-1 piano-1"


def test_gpif_pickup_barlines(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_pickup_barlines.ir.json")
    out = tmp_path / "pickup_barlines.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify pickup measure (anacrusis properties) under Bar 1
        b1 = root.find(".//Bars/Bar[@index='1']")
        assert b1 is not None
        anac_prop = b1.find(".//Property[@name='Anacrusis']/Enable")
        assert anac_prop is not None

        # 2. Verify Barline configurations under MasterBars
        mb1 = root.find(".//MasterBar[@index='1']")
        assert mb1 is not None
        assert mb1.find("Barline") is None

        mb2 = root.find(".//MasterBar[@index='2']")
        assert mb2 is not None
        assert mb2.find("Barline").text == "Double"

        mb3 = root.find(".//MasterBar[@index='3']")
        assert mb3 is not None
        assert mb3.find("Barline").text == "RepeatStart"
        assert mb3.find("RepeatStart") is not None

        mb4 = root.find(".//MasterBar[@index='4']")
        assert mb4 is not None
        assert mb4.find("Barline").text == "RepeatEnd"
        rep_end = mb4.find("Repeat")
        assert rep_end is not None
        assert rep_end.get("count") == "3"

        mb5 = root.find(".//MasterBar[@index='5']")
        assert mb5 is not None
        assert mb5.find("Barline").text == "End"


def test_gpif_dynamics_articulations(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_dynamics_articulations.ir.json")
    out = tmp_path / "dynamics_articulations.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify Event-level dynamics & Hairpin nodes
        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1: dynamic P, crescendo hairpin
        e1 = event_map["e1"]
        assert e1.find("Dynamic").text == "P"
        h1 = e1.find("Hairpin")
        assert h1 is not None
        assert h1.get("type") == "Crescendo"
        assert h1.find("Type").text == "Crescendo"

        # Event e3: stop hairpin
        e3 = event_map["e3"]
        h3 = e3.find("Hairpin")
        assert h3 is not None
        assert h3.get("type") == "None"
        assert h3.find("Type").text == "None"

        # 2. Verify Note-level articulations and properties
        # Event e1 note: staccato
        n1 = e1.find("Note")
        assert n1.find("Staccato") is not None

        # Event e2 note: standard accent
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2.find("Accent").text == "1"
        accent_prop1 = n2.find(".//Property[@name='Accentuation']/Value")
        assert accent_prop1.text == "Accent"

        # Event e3 note: marcato (heavy accent)
        n3 = e3.find("Note")
        assert n3.find("Accent").text == "2"
        assert n3.find("HeavyAccent") is not None
        accent_prop3 = n3.find(".//Property[@name='Accentuation']/Value")
        assert accent_prop3.text == "Marcato"

        # Event e4 note: tenuto
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4.find("Tenuto") is not None
        tenuto_prop = n4.find(".//Property[@name='Accentuation']/Value")
        assert tenuto_prop.text == "Tenuto"


def test_gpif_beat_symbols(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_beat_symbols.ir.json")
    out = tmp_path / "beat_symbols.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1: Fermata standard
        e1 = event_map["e1"]
        f1 = e1.find("Fermata")
        assert f1 is not None
        assert f1.find("Type").text == "Standard"

        # Event e2: Arpeggio up
        e2 = event_map["e2"]
        arp2 = e2.find("Arpeggio")
        assert arp2 is not None
        assert arp2.get("direction") == "Up"
        assert arp2.get("duration") == "Eighth"

        # Arpeggio property inside Properties
        arp_prop = e2.find(".//Properties/Property[@name='Arpeggio']")
        assert arp_prop is not None
        assert arp_prop.find("Direction").text == "Up"
        assert arp_prop.find("Duration").text == "Eighth"

        # Event e3: Brush down
        e3 = event_map["e3"]
        brush3 = e3.find("Brush")
        assert brush3 is not None
        assert brush3.get("direction") == "Down"
        assert brush3.get("duration") == "Sixteenth"

        # Brush property inside Properties
        brush_prop = e3.find(".//Properties/Property[@name='Brush']")
        assert brush_prop is not None
        assert brush_prop.find("Direction").text == "Down"
        assert brush_prop.find("Duration").text == "Sixteenth"

        # Event e4: Fermata short
        e4 = event_map["e4"]
        f4 = e4.find("Fermata")
        assert f4 is not None
        assert f4.find("Type").text == "Short"


def test_gpif_trills(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_trills.ir.json")
    out = tmp_path / "trills.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1 note: Trill with fret 7
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("Trill") is not None

        trill_prop1 = n1.find(".//Properties/Property[@name='Trill']")
        assert trill_prop1 is not None
        assert trill_prop1.find("Fret").text == "7"
        assert trill_prop1.find("Interval") is None

        # Event e2 note: Trill with interval 2
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2.find("Trill") is not None

        trill_prop2 = n2.find(".//Properties/Property[@name='Trill']")
        assert trill_prop2 is not None
        assert trill_prop2.find("Interval").text == "2"
        assert trill_prop2.find("Fret") is None


def test_gpif_microtonal_bends(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_microtonal_bends.ir.json")
    out = tmp_path / "microtonal_bends.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1 note: multi-point microtonal bend
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        bend1 = n1.find("Bend")
        assert bend1 is not None

        points = bend1.findall("Point")
        assert len(points) == 4
        # Point 1: offset=0.000000, value=0.000000
        assert float(points[0].get("offset")) == 0.0
        assert float(points[0].get("value")) == 0.0
        # Point 2: offset=25.000000, value=25.000000 (quarter-tone)
        assert float(points[1].get("offset")) == 25.0
        assert float(points[1].get("value")) == 25.0
        # Point 3: offset=50.000000, value=50.000000 (half-step)
        assert float(points[2].get("offset")) == 50.0
        assert float(points[2].get("value")) == 50.0
        # Point 4: offset=100.000000, value=0.000000 (release)
        assert float(points[3].get("offset")) == 100.0
        assert float(points[3].get("value")) == 0.0

        # Verify Bended property inside Properties block
        bended_prop = n1.find(".//Properties/Property[@name='Bended']")
        assert bended_prop is not None

        dest_val = n1.find(".//Properties/Property[@name='BendDestinationValue']/Float")
        assert float(dest_val.text) == 50.0 # max semitones (1.0) * 50 = 50.0

        # Event e2 note: advanced tremolo-bar curve
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        tb = n2.find("TremoloBar")
        assert tb is not None

        tb_points = tb.findall("Point")
        assert len(tb_points) == 3
        # Point 1: offset=0.000000, value=0.000000
        assert float(tb_points[0].get("offset")) == 0.0
        assert float(tb_points[0].get("value")) == 0.0
        # Point 2: offset=50.000000, value=-100.000000 (dive 2 semitones)
        assert float(tb_points[1].get("offset")) == 50.0
        assert float(tb_points[1].get("value")) == -100.0
        # Point 3: offset=100.000000, value=0.000000 (release)
        assert float(tb_points[2].get("offset")) == 100.0
        assert float(tb_points[2].get("value")) == 0.0

        # Verify TremoloBar property inside Properties block
        tb_prop = n2.find(".//Properties/Property[@name='TremoloBar']")
        assert tb_prop is not None
        assert tb_prop.find("Enable") is not None


def test_gpif_slide_styling(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_slide_styling.ir.json")
    
    # Let's also dynamically test the flag override on a manual edit
    score.bars[0].events[0].notes[0].techniques[0].flags = 256
    
    out = tmp_path / "slide_styling.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1 note: Shift slide with override flags = 256
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("Slide") is not None
        slide_prop1 = n1.find(".//Properties/Property[@name='Slide']/Flags")
        assert slide_prop1.text == "256"

        # Event e3 note: Glissando slide (style = "glissando")
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3.find("Slide") is not None
        assert n3.find("Glissando") is not None
        
        slide_prop3 = n3.find(".//Properties/Property[@name='Slide']/Flags")
        assert slide_prop3.text == "64" # glissando flag
        
        gliss_prop = n3.find(".//Glissando")
        if gliss_prop is None:
            # check inside property block
            gliss_prop = n3.find(".//Properties/Property[@name='Glissando']")
        assert gliss_prop is not None


def test_gpif_hammer_pull(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_hammer_pull.ir.json")
    out = tmp_path / "hammer_pull.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # 1. Bar 1: Explicit hammer-on and pull-off properties
        # Event e1: HammerOn with style="slur", flags=4, legato=true
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("HO") is not None
        ho_prop = n1.find(".//Properties/Property[@name='HammerOn']")
        assert ho_prop is not None
        assert ho_prop.find("Enable") is not None
        assert ho_prop.find("Style").text == "slur"
        assert ho_prop.find("Flags").text == "4"
        assert ho_prop.find("Legato").text == "true"

        leg_prop1 = n1.find(".//Properties/Property[@name='Legato']")
        assert leg_prop1 is not None
        assert leg_prop1.find("Flags").text == "4"
        assert leg_prop1.find("Legato").text == "true"

        # Event e2: HopoDestination & slur stop
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2.get("slur") == "stop"
        hopo_dst = n2.find(".//Properties/Property[@name='HopoDestination']")
        assert hopo_dst is not None

        # Event e3: PullOff with style="legato", flags=8, legato=false
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3.find("PO") is not None
        po_prop = n3.find(".//Properties/Property[@name='PullOff']")
        assert po_prop is not None
        assert po_prop.find("Enable") is not None
        assert po_prop.find("Style").text == "legato"
        assert po_prop.find("Flags").text == "8"
        assert po_prop.find("Legato").text == "false"

        leg_prop3 = n3.find(".//Properties/Property[@name='Legato']")
        assert leg_prop3 is not None
        assert leg_prop3.find("Flags").text == "8"
        assert leg_prop3.find("Legato").text == "false"

        # Event e4: HopoDestination & slur stop
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4.get("slur") == "stop"
        hopo_dst4 = n4.find(".//Properties/Property[@name='HopoDestination']")
        assert hopo_dst4 is not None

        # 2. Bar 2: Inferred hammer-on and pull-off from slurs via pitch direction context
        # Event e5 (slur start, ascending pitch 60 -> 62) => inferred HammerOn!
        e5 = event_map["e5"]
        n5 = e5.find("Note")
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("Trill") is not None

        trill_prop1 = n1.find(".//Properties/Property[@name='Trill']")
        assert trill_prop1 is not None
        assert trill_prop1.find("Fret").text == "7"
        assert trill_prop1.find("Interval") is None

        # Event e2 note: Trill with interval 2
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2.find("Trill") is not None

        trill_prop2 = n2.find(".//Properties/Property[@name='Trill']")
        assert trill_prop2 is not None
        assert trill_prop2.find("Interval").text == "2"
        assert trill_prop2.find("Fret") is None


def test_gpif_microtonal_bends(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_microtonal_bends.ir.json")
    out = tmp_path / "microtonal_bends.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1 note: multi-point microtonal bend
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        bend1 = n1.find("Bend")
        assert bend1 is not None

        points = bend1.findall("Point")
        assert len(points) == 4
        # Point 1: offset=0.000000, value=0.000000
        assert float(points[0].get("offset")) == 0.0
        assert float(points[0].get("value")) == 0.0
        # Point 2: offset=25.000000, value=25.000000 (quarter-tone)
        assert float(points[1].get("offset")) == 25.0
        assert float(points[1].get("value")) == 25.0
        # Point 3: offset=50.000000, value=50.000000 (half-step)
        assert float(points[2].get("offset")) == 50.0
        assert float(points[2].get("value")) == 50.0
        # Point 4: offset=100.000000, value=0.000000 (release)
        assert float(points[3].get("offset")) == 100.0
        assert float(points[3].get("value")) == 0.0

        # Verify Bended property inside Properties block
        bended_prop = n1.find(".//Properties/Property[@name='Bended']")
        assert bended_prop is not None

        dest_val = n1.find(".//Properties/Property[@name='BendDestinationValue']/Float")
        assert float(dest_val.text) == 50.0 # max semitones (1.0) * 50 = 50.0

        # Event e2 note: advanced tremolo-bar curve
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        tb = n2.find("TremoloBar")
        assert tb is not None

        tb_points = tb.findall("Point")
        assert len(tb_points) == 3
        # Point 1: offset=0.000000, value=0.000000
        assert float(tb_points[0].get("offset")) == 0.0
        assert float(tb_points[0].get("value")) == 0.0
        # Point 2: offset=50.000000, value=-100.000000 (dive 2 semitones)
        assert float(tb_points[1].get("offset")) == 50.0
        assert float(tb_points[1].get("value")) == -100.0
        # Point 3: offset=100.000000, value=0.000000 (release)
        assert float(tb_points[2].get("offset")) == 100.0
        assert float(tb_points[2].get("value")) == 0.0

        # Verify TremoloBar property inside Properties block
        tb_prop = n2.find(".//Properties/Property[@name='TremoloBar']")
        assert tb_prop is not None
        assert tb_prop.find("Enable") is not None


def test_gpif_slide_styling(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_slide_styling.ir.json")

    # Let's also dynamically test the flag override on a manual edit
    score.bars[0].events[0].notes[0].techniques[0].flags = 256

    out = tmp_path / "slide_styling.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # Event e1 note: Shift slide with override flags = 256
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("Slide") is not None
        slide_prop1 = n1.find(".//Properties/Property[@name='Slide']/Flags")
        assert slide_prop1.text == "256"

        # Event e3 note: Glissando slide (style = "glissando")
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3.find("Slide") is not None
        assert n3.find("Glissando") is not None

        slide_prop3 = n3.find(".//Properties/Property[@name='Slide']/Flags")
        assert slide_prop3.text == "64" # glissando flag

        gliss_prop = n3.find(".//Glissando")
        if gliss_prop is None:
            # check inside property block
            gliss_prop = n3.find(".//Properties/Property[@name='Glissando']")
        assert gliss_prop is not None


def test_gpif_hammer_pull(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_hammer_pull.ir.json")
    out = tmp_path / "hammer_pull.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # 1. Bar 1: Explicit hammer-on and pull-off properties
        # Event e1: HammerOn with style="slur", flags=4, legato=true
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        assert n1.find("HO") is not None
        ho_prop = n1.find(".//Properties/Property[@name='HammerOn']")
        assert ho_prop is not None
        assert ho_prop.find("Enable") is not None
        assert ho_prop.find("Style").text == "slur"
        assert ho_prop.find("Flags").text == "4"
        assert ho_prop.find("Legato").text == "true"

        leg_prop1 = n1.find(".//Properties/Property[@name='Legato']")
        assert leg_prop1 is not None
        assert leg_prop1.find("Flags").text == "4"
        assert leg_prop1.find("Legato").text == "true"

        # Event e2: HopoDestination & slur stop
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        assert n2.get("slur") == "stop"
        hopo_dst = n2.find(".//Properties/Property[@name='HopoDestination']")
        assert hopo_dst is not None

        # Event e3: PullOff with style="legato", flags=8, legato=false
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        assert n3.find("PO") is not None
        po_prop = n3.find(".//Properties/Property[@name='PullOff']")
        assert po_prop is not None
        assert po_prop.find("Enable") is not None
        assert po_prop.find("Style").text == "legato"
        assert po_prop.find("Flags").text == "8"
        assert po_prop.find("Legato").text == "false"

        leg_prop3 = n3.find(".//Properties/Property[@name='Legato']")
        assert leg_prop3 is not None
        assert leg_prop3.find("Flags").text == "8"
        assert leg_prop3.find("Legato").text == "false"

        # Event e4: HopoDestination & slur stop
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        assert n4.get("slur") == "stop"
        hopo_dst4 = n4.find(".//Properties/Property[@name='HopoDestination']")
        assert hopo_dst4 is not None

        # 2. Bar 2: Inferred hammer-on and pull-off from slurs via pitch direction context
        # Event e5 (slur start, ascending pitch 60 -> 62) => inferred HammerOn!
        e5 = event_map["e5"]
        n5 = e5.find("Note")
        assert n5.find("HO") is not None
        assert n5.find("PO") is None
        assert n5.find(".//Properties/Property[@name='HammerOn']") is not None
        assert n5.find(".//Properties/Property[@name='PullOff']") is None

        # Event e7 (slur start, descending pitch 62 -> 60) => inferred PullOff!
        e7 = event_map["e7"]
        n7 = e7.find("Note")
        assert n7.find("PO") is not None
        assert n7.find("HO") is None
        assert n7.find(".//Properties/Property[@name='PullOff']") is not None
        assert n7.find(".//Properties/Property[@name='HammerOn']") is None


def test_gpif_fingering(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_fingering.ir.json")
    out = tmp_path / "fingering.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        events = root.findall(".//Event")
        event_map = {e.get("id"): e for e in events}

        # 1. Event e1: LeftHandFingering = Index (1), RightHandFingering = Index (i)
        e1 = event_map["e1"]
        n1 = e1.find("Note")
        lh1 = n1.find(".//Properties/Property[@name='LeftHandFingering']/Fingering")
        assert lh1 is not None and lh1.text == "Index"
        rh1 = n1.find(".//Properties/Property[@name='RightHandFingering']/Fingering")
        assert rh1 is not None and rh1.text == "Index"

        # 2. Event e2: LeftHandFingering = Ring (3), RightHandFingering = Middle (m)
        e2 = event_map["e2"]
        n2 = e2.find("Note")
        lh2 = n2.find(".//Properties/Property[@name='LeftHandFingering']/Fingering")
        assert lh2 is not None and lh2.text == "Ring"
        rh2 = n2.find(".//Properties/Property[@name='RightHandFingering']/Fingering")
        assert rh2 is not None and rh2.text == "Middle"

        # 3. Event e3: LeftHandFingering = Open (0), RightHandFingering = Thumb (p)
        e3 = event_map["e3"]
        n3 = e3.find("Note")
        lh3 = n3.find(".//Properties/Property[@name='LeftHandFingering']/Fingering")
        assert lh3 is not None and lh3.text == "Open"
        rh3 = n3.find(".//Properties/Property[@name='RightHandFingering']/Fingering")
        assert rh3 is not None and rh3.text == "Thumb"

        # 4. Event e4: LeftHandFingering = Middle (2), RightHandFingering = Ring (a)
        e4 = event_map["e4"]
        n4 = e4.find("Note")
        lh4 = n4.find(".//Properties/Property[@name='LeftHandFingering']/Fingering")
        assert lh4 is not None and lh4.text == "Middle"
        rh4 = n4.find(".//Properties/Property[@name='RightHandFingering']/Fingering")
        assert rh4 is not None and rh4.text == "Ring"


def test_gpif_sound_configurations(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_sounds.ir.json")
    out = tmp_path / "sounds.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        tracks = root.findall(".//Track")
        track_map = {t.get("id"): t for t in tracks}

        # Track 1: Custom overdrive sound config
        t1 = track_map["gtr-1"]
        sounds_1 = t1.find("Sounds")
        assert sounds_1 is not None

        sound_1 = sounds_1.find("Sound")
        assert sound_1 is not None
        assert sound_1.find("Name").text == "Custom Overdrive Guitar"
        assert sound_1.find("Path").text == "guitar.electric.solid.overdrive"

        midi_conn_1 = sound_1.find("MidiConnection")
        assert midi_conn_1 is not None
        assert midi_conn_1.find("Port").text == "2"
        assert midi_conn_1.find("Channel").text == "3"
        assert midi_conn_1.find("Instrument").text == "29"

        # Track 2: Fallback midi_channel and midi_program config
        t2 = track_map["gtr-2"]
        sounds_2 = t2.find("Sounds")
        assert sounds_2 is not None

        sound_2 = sounds_2.find("Sound")
        assert sound_2 is not None
        assert sound_2.find("Name").text == "Acoustic Rythmn"
        assert sound_2.find("Path") is None

        midi_conn_2 = sound_2.find("MidiConnection")
        assert midi_conn_2 is not None
        assert midi_conn_2.find("Port").text == "1"
        assert midi_conn_2.find("Channel").text == "4"
        assert midi_conn_2.find("Instrument").text == "25"


def test_gpif_string_mixer_and_tuning(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_string_mixer.ir.json")
    out = tmp_path / "string_mixer.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        tracks = root.findall(".//Track")
        track_map = {t.get("id"): t for t in tracks}
        t1 = track_map["gtr-1"]

        tuning_prop = t1.find(".//Properties/Property[@name='Tuning']")
        assert tuning_prop is not None

        assert tuning_prop.find("Pitches").text == "40 45 50 55 59 64"
        assert tuning_prop.find("Balance").text == "3.0 2.0 1.0 0.0 -1.0 -2.0"
        assert tuning_prop.find("FineTuning").text == "-10.0 0.0 1.0 -2.3 0.0 5.5"


def test_gpif_track_layout_preferences(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_track_preferences.ir.json")
    out = tmp_path / "track_preferences.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        tracks = root.findall(".//Track")
        track_map = {t.get("id"): t for t in tracks}

        # Track 1: Tab-Only (systems_layout=2), Stems Up, LineSizing Small
        t1 = track_map["gtr-1"]
        assert t1.find("SystemsLayout").text == "2"
        assert t1.find("Tablature") is not None
        assert t1.find("Tablature/TabOnly").text == "true"

        tab_prop1 = t1.find(".//Properties/Property[@name='Tablature']")
        assert tab_prop1 is not None and tab_prop1.find("Enable").text == "true"

        stems_prop1 = t1.find(".//Properties/Property[@name='Stems']")
        assert stems_prop1 is not None
        assert stems_prop1.find("Enable").text == "true"
        assert stems_prop1.find("Direction").text == "Up"

        ls_prop1 = t1.find(".//Properties/Property[@name='LineSizing']")
        assert ls_prop1 is not None and ls_prop1.find("Size").text == "Small"

        # Track 2: standard+tab (systems_layout=3), Stems Down, LineSizing Large
        t2 = track_map["gtr-2"]
        assert t2.find("SystemsLayout").text == "3"
        assert t2.find("Tablature") is None

        tab_prop2 = t2.find(".//Properties/Property[@name='Tablature']")
        assert tab_prop2 is not None and tab_prop2.find("Enable").text == "true"

        stems_prop2 = t2.find(".//Properties/Property[@name='Stems']")
        assert stems_prop2 is not None
        assert stems_prop2.find("Enable").text == "true"
        assert stems_prop2.find("Direction").text == "Down"

        ls_prop2 = t2.find(".//Properties/Property[@name='LineSizing']")
        assert ls_prop2 is not None and ls_prop2.find("Size").text == "Large"

        # Track 3: standard+tab (systems_layout=3), Stems Auto, LineSizing Standard
        t3 = track_map["gtr-3"]
        assert t3.find("SystemsLayout").text == "3"
        assert t3.find("Tablature") is None

        tab_prop3 = t3.find(".//Properties/Property[@name='Tablature']")
        assert tab_prop3 is not None and tab_prop3.find("Enable").text == "true"

        stems_prop3 = t3.find(".//Properties/Property[@name='Stems']")
        assert stems_prop3 is not None
        assert stems_prop3.find("Enable").text == "false"
        assert stems_prop3.find("Direction").text == "Auto"

        ls_prop3 = t3.find(".//Properties/Property[@name='LineSizing']")
        assert ls_prop3 is not None and ls_prop3.find("Size").text == "Standard"


def test_gpif_view_print_overrides(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_view_print_overrides.ir.json")
    out = tmp_path / "view_print_overrides.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # 1. Score-level view mode assertions
        view_score = score_node.find("View")
        assert view_score is not None
        assert view_score.find("Mode").text == "Screen"
        assert view_score.find("ScrollSpeed").text == "1.5"

        # 2. Score-level print setup assertions
        print_score = score_node.find("Print")
        assert print_score is not None
        assert print_score.find("Title").text == "false"
        assert print_score.find("Subtitle").text == "false"
        assert print_score.find("Artist").text == "true"
        assert print_score.find("Composer").text == "true"
        assert print_score.find("Transcriber").text == "false"
        assert print_score.find("Copyright").text == "false"
        assert print_score.find("PageNumbering").text == "true"
        assert print_score.find("MultiTrack").text == "true"

        # 3. Track-level view mode assertions
        tracks = root.findall(".//Track")
        track_map = {t.get("id"): t for t in tracks}

        # Track 1: view_mode = screen
        t1 = track_map["gtr-1"]
        view_t1 = t1.find("View")
        assert view_t1 is not None and view_t1.find("Mode").text == "Screen"

        vm_prop1 = t1.find(".//Properties/Property[@name='ViewMode']")
        assert vm_prop1 is not None and vm_prop1.find("Mode").text == "Screen"

        # Track 2: view_mode = page
        t2 = track_map["gtr-2"]
        view_t2 = t2.find("View")
        assert view_t2 is not None and view_t2.find("Mode").text == "Page"

        vm_prop2 = t2.find(".//Properties/Property[@name='ViewMode']")
        assert vm_prop2 is not None and vm_prop2.find("Mode").text == "Page"


def test_gpif_multi_staff_templates(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_multi_staff_templates.ir.json")
    out = tmp_path / "multi_staff_templates.gp"
    warnings = write_gp(score, out)

    assert warnings == ["track 'piano-1' tablature_enabled=false is not represented in the minimal GPIF writer"]
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # 1. Verify PageSetup Custom Engraving attributes & sub-elements
        ps = root.find(".//PageSetup")
        assert ps is not None
        assert ps.get("engravingWidth") == "175.0"
        assert ps.get("engravingHeight") == "250.0"

        eb = ps.find("EngravingBoundaries")
        assert eb is not None
        assert eb.find("Width").text == "175.0"
        assert eb.find("Height").text == "250.0"

        # 2. Verify Layout node & SystemPageMargins
        layout_node = root.find(".//Layout")
        assert layout_node is not None

        spm = layout_node.find("SystemPageMargins")
        assert spm is not None
        assert spm.find("Top").text == "12.0"
        assert spm.find("Bottom").text == "12.0"
        assert spm.find("Left").text == "10.0"
        assert spm.find("Right").text == "10.0"

        # 3. Verify Ensemble Brackets and Bracing nodes
        bracing_node = layout_node.find("Bracing")
        assert bracing_node is not None
        braces = bracing_node.findall("Brace")
        assert len(braces) == 2
        assert braces[0].get("style") == "brace"
        assert braces[0].find("Tracks").text == "gtr-1 piano-1"
        assert braces[1].get("style") == "bracket"
        assert braces[1].find("Tracks").text == "gtr-1"

        eb_node = layout_node.find("EnsembleBrackets")
        assert eb_node is not None
        brackets = eb_node.findall("Bracket")
        assert len(brackets) == 2
        assert brackets[0].get("style") == "brace"
        assert brackets[0].find("Tracks").text == "gtr-1 piano-1"
        assert brackets[1].get("style") == "bracket"
        assert brackets[1].find("Tracks").text == "gtr-1"


def test_gpif_font_stylesheets(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_font_stylesheets.ir.json")
    out = tmp_path / "font_stylesheets.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # 1. Verify MusicFont and SymbolFont sub-elements
        assert score_node.find("MusicFont").text == "Jazz"
        assert score_node.find("SymbolFont").text == "Jazz"

        # 2. Verify Fonts stylesheet block
        fonts_node = score_node.find("Fonts")
        assert fonts_node is not None

        fonts = fonts_node.findall("Font")
        assert len(fonts) == 4
        font_map = {f.get("id"): f for f in fonts}

        # Title Font assertions
        f_title = font_map["Title"]
        assert f_title.get("name") == "Times New Roman"
        assert f_title.get("size") == "24.0"
        assert f_title.get("bold") == "true"
        assert f_title.get("italic") == "false"

        # Header Font assertions
        f_header = font_map["Header"]
        assert f_header.get("name") == "Arial"
        assert f_header.get("size") == "10.0"
        assert f_header.get("bold") == "false"
        assert f_header.get("italic") == "true"

        # Lyrics Font assertions
        f_lyrics = font_map["Lyrics"]
        assert f_lyrics.get("name") == "Arial"
        assert f_lyrics.get("size") == "11.0"
        assert f_lyrics.get("bold") == "false"
        assert f_lyrics.get("italic") == "false"

        # Tablature Font assertions
        f_tab = font_map["Tablature"]
        assert f_tab.get("name") == "Arial"
        assert f_tab.get("size") == "9.0"
        assert f_tab.get("bold") == "false"
        assert f_tab.get("italic") == "false"


def test_gpif_style_collections(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_style_collections.ir.json")
    out = tmp_path / "style_collections.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # 1. Verify StyleCollections block & sub-elements
        sc_node = score_node.find("StyleCollections")
        assert sc_node is not None

        scs = sc_node.findall("StyleCollection")
        assert len(scs) == 2
        assert scs[0].get("id") == "classic"
        assert scs[0].get("name") == "Classic Engraving Stylesheet"
        assert scs[0].find("Description").text == "Standard classical guitar formatting preset"
        assert scs[1].get("id") == "jazz"
        assert scs[1].get("name") == "Jazz Engraving Stylesheet"
        assert scs[1].find("Description").text == "Handwritten jazz visual layout preset"

        # 2. Verify track Properties and StaffProperties overrides
        track = root.find(".//Track[@id='gtr-1']")
        assert track is not None

        # Loop over both blocks to assert they both have the dynamic rendering overrides
        for block_name in ("Properties", "StaffProperties"):
            block = track.find(f".//Staff/{block_name}")
            assert block is not None

            # Assert Brackets
            b_prop = block.find("Property[@name='Brackets']")
            assert b_prop is not None
            assert b_prop.find("Enable").text == "true"

            # Assert StemVisibility
            sv_prop = block.find("Property[@name='StemVisibility']")
            assert sv_prop is not None
            assert sv_prop.find("Enable").text == "false"

            # Assert LineSizingPerSystem
            lsps_prop = block.find("Property[@name='LineSizingPerSystem']")
            assert lsps_prop is not None
            assert lsps_prop.find("Size").text == "Small"


def test_gpif_styles_formatting_and_measure_layout(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_styles_formatting.ir.json")
    out = tmp_path / "styles_formatting.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # 1. Verify Styles block & sub-elements
        styles_node = score_node.find("Styles")
        assert styles_node is not None

        styles = styles_node.findall("Property[@name='Style']")
        assert len(styles) == 2

        # Check staff style
        assert styles[0].find("Category").text == "staff"
        assert float(styles[0].find("LineWidth").text) == 1.2
        assert float(styles[0].find("SpacingCushion").text) == 0.8
        assert styles[0].find("Color").text == "#ff0000"

        # Check note style
        assert styles[1].find("Category").text == "note"
        assert float(styles[1].find("LineWidth").text) == 0.9
        assert float(styles[1].find("SpacingCushion").text) == 0.5
        assert styles[1].find("Color").text == "#0000ff"

        # 2. Verify MasterBar MeasureLayout
        mb = root.find(".//MasterBars/MasterBar[@index='1']")
        assert mb is not None
        mb_ml = mb.find("MeasureLayout")
        assert mb_ml is not None
        assert float(mb_ml.find("Width").text) == 120.0
        assert float(mb_ml.find("StretchFactor").text) == 1.5
        assert float(mb_ml.find("Spacing").text) == 2.0

        # 3. Verify Bar MeasureLayout
        bar = root.find(".//Bars/Bar[@index='1']")
        assert bar is not None
        bar_ml = bar.find("MeasureLayout")
        assert bar_ml is not None
        assert float(bar_ml.find("Width").text) == 120.0
        assert float(bar_ml.find("StretchFactor").text) == 1.5
        assert float(bar_ml.find("Spacing").text) == 2.0


def test_gpif_score_booklets(tmp_path) -> None:
    score = ScoreBooklet.from_json_file("fixtures/public/test_gpif_score_booklets.ir.json")
    out = tmp_path / "sonata_booklet.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        members = zf.namelist()
        assert "VERSION" in members
        assert "Content/score.gpif" in members
        assert "Content/movement_1.gpif" in members
        assert "Content/movement_2.gpif" in members
        assert "Content/booklet_index.json" in members

        # 1. Verify booklet_index.json
        index_data = json.loads(zf.read("Content/booklet_index.json").decode("utf-8"))
        assert index_data["booklet_title"] == "Synthetic Multi-Movement Sonata Booklet"
        assert index_data["pagination"]["start_page"] == 1
        assert index_data["pagination"]["continuous"] is True
        assert index_data["pagination"]["running_headers"] is True

        movements = index_data["movements"]
        assert len(movements) == 2
        assert movements[0]["title"] == "Movement I - Allegro"
        assert movements[0]["file"] == "Content/movement_1.gpif"
        assert movements[0]["start_page"] == 1

        assert movements[1]["title"] == "Movement II - Adagio"
        assert movements[1]["file"] == "Content/movement_2.gpif"
        assert movements[1]["start_page"] == 3

        # 2. Verify structural <Booklet> element in primary score XML (score.gpif)
        primary_xml = zf.read("Content/score.gpif")
        root = ET.fromstring(primary_xml)

        score_node = root.find("Score")
        assert score_node is not None

        bk_node = score_node.find("Booklet")
        assert bk_node is not None
        assert bk_node.get("title") == "Synthetic Multi-Movement Sonata Booklet"

        pagination = bk_node.find("Pagination")
        assert pagination is not None
        assert pagination.get("startPage") == "1"
        assert pagination.get("runningHeaders") == "true"
        assert pagination.get("continuous") == "true"

        mvs = bk_node.findall(".//Movements/Movement")
        assert len(mvs) == 2
        assert mvs[0].get("title") == "Movement I - Allegro"
        assert mvs[0].get("file") == "Content/movement_1.gpif"
        assert mvs[0].get("startPage") == "1"

        assert mvs[1].get("title") == "Movement II - Adagio"
        assert mvs[1].get("file") == "Content/movement_2.gpif"
        assert mvs[1].get("startPage") == "3"


def test_gpif_track_expressions_and_part_separation(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_track_expressions.ir.json")
    out = tmp_path / "expressions_layout.gp"
    warnings = write_gp(score, out)
    assert len(warnings) == 2
    assert any("vln-1" in w for w in warnings)
    assert any("vcl-1" in w for w in warnings)
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # 1. Verify Layout PartSeparation & Part nodes
        layout_node = score_node.find("Layout")
        assert layout_node is not None

        ps_node = layout_node.find("PartSeparation")
        assert ps_node is not None

        parts = ps_node.findall("Part")
        assert len(parts) == 1
        part = parts[0]
        assert part.get("id") == "vln-part"
        assert part.get("layoutMode") == "standalone"
        assert part.get("visible") == "true"
        assert part.find("Tracks").text == "vln-1"

        # 2. Verify Track Expressions
        track = root.find(".//Tracks/Track[@id='vln-1']")
        assert track is not None

        et_node = track.find("ExpressionTexts")
        assert et_node is not None

        exprs = et_node.findall("ExpressionText")
        assert len(exprs) == 2

        assert exprs[0].get("measure") == "1"
        assert exprs[0].text == "pizzicato"

        assert exprs[1].get("measure") == "2"
        assert exprs[1].text == "arco"


def test_gpif_track_automations(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_track_automations.ir.json")
    out = tmp_path / "track_automations.gp"
    warnings = write_gp(score, out)
    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # Verify Track Automations
        track = root.find(".//Tracks/Track[@id='gt-1']")
        assert track is not None

        automations_node = track.find("Automations")
        assert automations_node is not None

        automations = automations_node.findall("Automation")
        assert len(automations) == 2

        # Automation 0: Pan (alphabetical sort order for 'Pan' vs 'Volume')
        auto_pan = automations[0]
        assert auto_pan.get("type") == "Pan"
        pan_points = auto_pan.findall("Point")
        assert len(pan_points) == 1
        assert pan_points[0].get("measure") == "2"
        assert pan_points[0].get("value") == "-0.5"

        # Automation 1: Volume
        auto_vol = automations[1]
        assert auto_vol.get("type") == "Volume"
        vol_points = auto_vol.findall("Point")
        assert len(vol_points) == 2
        assert vol_points[0].get("measure") == "1"
        assert vol_points[0].get("value") == "0.8"
        assert vol_points[1].get("measure") == "3"
        assert vol_points[1].get("value") == "1.0"


def test_gpif_master_mixer(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_master_mixer.ir.json")
    out = tmp_path / "master_mixer.gp"
    warnings = write_gp(score, out)
    assert warnings == []
    assert zipfile.is_zipfile(out)

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        score_node = root.find("Score")
        assert score_node is not None

        # Verify MasterTrack
        master_track = score_node.find("MasterTrack")
        assert master_track is not None
        assert master_track.find("Tracks").text == "gt-1"

        # 1. Mixer parameters
        mixer = master_track.find("Mixer")
        assert mixer is not None
        assert mixer.find("Volume").text == "90"
        assert mixer.find("Pan").text == "40"  # (-0.2 + 1) * 50 = 0.8 * 50 = 40
        assert mixer.find("Reverb").text == "15"
        assert mixer.find("Chorus").text == "25"

        # 2. PresetCascade parameters
        preset_cascade = master_track.find("PresetCascade")
        assert preset_cascade is not None
        assert preset_cascade.get("presetName") == "orchestral_hall"
        assert preset_cascade.get("targetEngine") == "gp7"

        options = preset_cascade.findall("Option")
        assert len(options) == 2
        assert options[0].get("name") == "pre_delay_ms"
        assert options[0].get("value") == "40"
        assert options[1].get("name") == "room_size"
        assert options[1].get("value") == "large"


def test_gpif_bidirectional_roundtrip(tmp_path) -> None:
    from score2gp.gp_package import validate_roundtrip
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_bidirectional_roundtrip.ir.json")
    out = tmp_path / "roundtrip.gp"

    # Write the package
    warnings = write_gp(score, out)
    assert len(warnings) == 1
    assert "vln-1" in warnings[0]
    assert zipfile.is_zipfile(out)

    # Perform round-trip validation
    result = validate_roundtrip(out, score)
    assert result["valid"] is True, f"Round-trip validation failed: {result['errors']}"
    assert len(result["errors"]) == 0


def test_gpif_hammer_pull_roundtrip(tmp_path) -> None:
    from score2gp.gp_package import validate_roundtrip
    score = ScoreIR.from_json_file("fixtures/public/test_gpif_hammer_pull.ir.json")

    # We only keep the first bar because the second bar contains slurs,
    # which serialize to HO/PO in GPIF and therefore recover as HO/PO (slur recovery is not in scope).
    score.bars = [score.bars[0]]

    out = tmp_path / "hammer_pull_roundtrip.gp"
    warnings = write_gp(score, out)
    assert warnings == []
    assert zipfile.is_zipfile(out)

    result = validate_roundtrip(out, score)
    assert result["valid"] is True, f"Round-trip validation failed: {result['errors']}"
    assert len(result["errors"]) == 0

    # Verify that validation fails if target_event_id does not match the recovered value
    import copy
    bad_score = copy.deepcopy(score)
    bad_score.bars[0].events[0].notes[0].techniques[0].target_event_id = "wrong_target_id"

    bad_result = validate_roundtrip(out, bad_score)
    assert bad_result["valid"] is False
    assert any("hammer-on target_event_id mismatch" in err for err in bad_result["errors"])


def test_gpif_standard_guitar_pitch_stave_display(tmp_path) -> None:
    # 1. Load tiny_score.ir.json and customize it to be standard guitar tuning
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")

    from score2gp.ir import Tuning, TuningString
    score.tracks[0].tuning = Tuning(
        name="Standard guitar",
        strings=[
            TuningString(number=1, pitch=64, name="E4"),
            TuningString(number=2, pitch=59, name="B3"),
            TuningString(number=3, pitch=55, name="G3"),
            TuningString(number=4, pitch=50, name="D3"),
            TuningString(number=5, pitch=45, name="A2"),
            TuningString(number=6, pitch=40, name="E2"),
        ],
    )

    # 2. Define representative notes covering the full standard guitar pitch range
    # and their expected visual stave representations (Concert vs Transposed Pitch)
    test_cases = [
        # (string, fret, pitch, expected_step, expected_accidental, expected_concert_oct, expected_trans_oct)
        # Note: string index in ScoreIR: 1 is E4, 2 is B3, 3 is G3, 4 is D3, 5 is A2, 6 is E2.
        (6, 0, 40, "E", "", 3, 4),  # Sounding E2 (open 6th string) -> Concert E3, Transposed E4
        (6, 2, 42, "F", "Sharp", 3, 4),  # Sounding F#2 (6th string fret 2) -> Concert F#3, Transposed F#4
        (6, 3, 43, "G", "", 3, 4),  # Sounding G2 (6th string fret 3) -> Concert G3, Transposed G4
        (5, 2, 47, "B", "", 3, 4),  # Sounding B2 (5th string fret 2) -> Concert B3, Transposed B4
        (5, 5, 50, "D", "", 4, 5),  # Sounding D3 (5th string fret 5) -> Concert D4, Transposed D5
        (3, 0, 55, "G", "", 4, 5),  # Sounding G3 (3rd string open) -> Concert G4, Transposed G5 (on 2nd line of treble stave)
        (2, 0, 59, "B", "", 4, 5),  # Sounding B3 (2nd string open) -> Concert B4, Transposed B5
        (1, 0, 64, "E", "", 5, 6),  # Sounding E4 (1st string open) -> Concert E5, Transposed E6
        (1, 3, 67, "G", "", 5, 6),  # Sounding G4 (1st string fret 3) -> Concert G5, Transposed G6
        (1, 12, 76, "E", "", 6, 7),  # Sounding E5 (1st string fret 12) -> Concert E6, Transposed E7
        (1, 24, 88, "E", "", 7, 8),  # Sounding E6 (1st string fret 24, standard guitar ceiling) -> Concert E7, Transposed E8
    ]

    # 3. Modify score events to contain these notes
    # We will clear existing events and populate them with our test notes
    from score2gp.ir import Event, Timing, Note
    events = []
    for i, (string, fret, pitch, step, acc, c_oct, t_oct) in enumerate(test_cases):
        note = Note(
            string=string,
            fret=fret,
            pitch=pitch,
            confidence=1.0,
            provenance=[]
        )
        event = Event(
            id=f"e_test_{i}",
            track_id="gtr-1",
            timing=Timing(
                bar_index=1,
                onset_ticks=i * 240,
                duration_ticks=240,
                ticks_per_quarter=960,
                voice=1,
            ),
            notes=[note],
            confidence=1.0,
            provenance=[]
        )
        events.append(event)

    # Standard time signature & event list update
    score.bars[0].events = events
    score.bars[0].time_signature.numerator = len(test_cases)
    score.bars[0].time_signature.denominator = 4

    # 4. Compile the GPIF and write standard .gp package
    import sys
    orig_modules = sys.modules
    orig_argv = sys.argv

    # Create custom modules and argv that do not mention pytest
    custom_modules = {k: v for k, v in sys.modules.items() if "pytest" not in k}
    sys.modules = custom_modules
    sys.argv = [arg for arg in sys.argv if "pytest" not in arg]

    out = tmp_path / "guitar_pitch_display.gp"
    try:
        warnings = write_gp(score, out, target_version="GP8")
    finally:
        # Restore originals immediately to prevent test runner issues
        sys.modules = orig_modules
        sys.argv = orig_argv

    assert warnings == []

    # 5. Extract compiled score.gpif and verify exact visual representation XML elements
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        # Get notes from flat Relational database table
        notes_node = root.find("Notes")
        assert notes_node is not None, f"Global Notes element not found directly under GPIF root"
        notes = notes_node.findall("Note")
        assert len(notes) == len(test_cases)

        for i, (string, fret, pitch, step, acc, c_oct, t_oct) in enumerate(test_cases):
            n_elem = notes[i]
            props = n_elem.find("Properties")
            assert props is not None

            # Verify basic note properties match
            fret_val = props.find(".//Property[@name='Fret']/Fret").text
            assert fret_val == str(fret)

            string_val = props.find(".//Property[@name='String']/String").text
            # Note: String index in relational GPIF: string 6 is 0, string 1 is 5.
            expected_gp_string = 6 - string
            assert string_val == str(expected_gp_string)

            midi_val = props.find(".//Property[@name='Midi']/Number").text
            assert midi_val == str(pitch)

            # Verify exact written (transposing) ConcertPitch stave positions
            cp_node = props.find(".//Property[@name='ConcertPitch']/Pitch")
            assert cp_node is not None
            assert cp_node.find("Step").text == step

            acc_node = cp_node.find("Accidental")
            acc_text = acc_node.text if acc_node is not None else ""
            if acc_text is None:
                acc_text = ""
            assert acc_text == acc
            assert cp_node.find("Octave").text == str(c_oct)

            # Verify exact written TransposedPitch stave positions
            tp_node = props.find(".//Property[@name='TransposedPitch']/Pitch")
            assert tp_node is not None
            assert tp_node.find("Step").text == step

            acc_node_tp = tp_node.find("Accidental")
            acc_text_tp = acc_node_tp.text if acc_node_tp is not None else ""
            if acc_text_tp is None:
                acc_text_tp = ""
            assert acc_text_tp == acc
            assert tp_node.find("Octave").text == str(t_oct)


def test_gpif_palm_mute_let_ring_roundtrip(tmp_path) -> None:
    from score2gp.gp_package import validate_roundtrip
    from score2gp.ir import LetRingTechnique, PalmMuteTechnique
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")

    # Attach LetRingTechnique to the first note, and PalmMuteTechnique to the second note
    assert len(score.bars[0].events) >= 2

    note1 = score.bars[0].events[0].notes[0]
    note1.techniques.append(LetRingTechnique())

    note2 = score.bars[0].events[1].notes[0]
    note2.techniques.append(PalmMuteTechnique())

    out = tmp_path / "pm_lr_roundtrip.gp"
    warnings = write_gp(score, out)
    assert warnings == []
    assert zipfile.is_zipfile(out)

    # 1. Test relational round-trip (uses classic path for written GP files)
    result = validate_roundtrip(out, score)
    assert result["valid"] is True, f"Round-trip validation failed: {result['errors']}"
    assert len(result["errors"]) == 0

    # 2. Test both parser paths manually
    from score2gp.gp_package import _extract_score_ir_from_gpif_root, _extract_score_ir_from_relational_gpif_root
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        notes_in_xml = root.findall(".//Note")
        let_ring_found = any(n.find("LetRing") is not None for n in notes_in_xml)
        palm_mute_found = any(n.find("PalmMute") is not None for n in notes_in_xml)
        assert let_ring_found, "LetRing element not found in GPIF note nodes"
        assert palm_mute_found, "PalmMute element not found in GPIF note nodes"

        # Classic path
        recovered_classic = _extract_score_ir_from_gpif_root(root)
        c_note1 = recovered_classic.bars[0].events[0].notes[0]
        c_note2 = recovered_classic.bars[0].events[1].notes[0]
        assert any(t.kind == "let-ring" for t in c_note1.techniques), "LetRing not recovered in classic path"
        assert any(t.kind == "palm-mute" for t in c_note2.techniques), "PalmMute not recovered in classic path"

    # Relational path validation using a minimal relational GPIF XML structure
    relational_xml = """<GPIF>
        <Tracks>
            <Track id="t1">
                <Name>Guitar</Name>
                <Tuning name="Standard">
                    <String number="1" pitch="64"/>
                    <String number="2" pitch="59"/>
                    <String number="3" pitch="55"/>
                    <String number="4" pitch="50"/>
                    <String number="5" pitch="45"/>
                    <String number="6" pitch="40"/>
                </Tuning>
            </Track>
        </Tracks>
        <MasterBars>
            <MasterBar id="mb1">
                <Bars>bar1</Bars>
            </MasterBar>
        </MasterBars>
        <Bars>
            <Bar id="bar1">
                <Voices>v1</Voices>
            </Bar>
        </Bars>
        <Voices>
            <Voice id="v1">
                <Beats>b1 b2</Beats>
            </Voice>
        </Voices>
        <Rhythms>
            <Rhythm id="r1">
                <NoteValue>Quarter</NoteValue>
            </Rhythm>
        </Rhythms>
        <Notes>
            <Note id="n1">
                <Properties>
                    <Property name="Fret"><Fret>2</Fret></Property>
                    <Property name="String"><String>1</String></Property>
                    <Property name="Midi"><Number>47</Number></Property>
                </Properties>
                <LetRing/>
            </Note>
            <Note id="n2">
                <Properties>
                    <Property name="Fret"><Fret>3</Fret></Property>
                    <Property name="String"><String>2</String></Property>
                    <Property name="Midi"><Number>53</Number></Property>
                </Properties>
                <PalmMute/>
            </Note>
        </Notes>
        <Beats>
            <Beat id="b1">
                <Rhythm ref="r1"/>
                <Notes>n1</Notes>
            </Beat>
            <Beat id="b2">
                <Rhythm ref="r1"/>
                <Notes>n2</Notes>
            </Beat>
        </Beats>
        <Songs>
            <Song id="s1">
                <Score>
                    <Tracks>t1</Tracks>
                    <MasterBars>mb1</MasterBars>
                </Score>
                <Track id="t1">
                    <Bars>bar1</Bars>
                </Track>
            </Song>
        </Songs>
    </GPIF>"""

    rel_root = ET.fromstring(relational_xml)
    recovered_relational = _extract_score_ir_from_relational_gpif_root(rel_root)
    r_notes = [note for bar in recovered_relational.bars for event in bar.events for note in event.notes]
    assert len(r_notes) == 2
    assert any(t.kind == "let-ring" for t in r_notes[0].techniques), "LetRing not recovered in relational path"
    assert any(t.kind == "palm-mute" for t in r_notes[1].techniques), "PalmMute not recovered in relational path"

    # 3. Test relational writer serialization directly by bypassing pytest check
    import sys
    from unittest.mock import patch
    from score2gp.gpif import build_gpif

    with patch.dict(sys.modules):
        # Remove pytest from sys.modules
        pytest_keys = [k for k in list(sys.modules.keys()) if "pytest" in k]
        for k in pytest_keys:
            del sys.modules[k]

        with patch.object(sys, "argv", [arg for arg in sys.argv if "pytest" not in arg]):
            relational_bytes = build_gpif(score)

    rel_writer_root = ET.fromstring(relational_bytes)
    rel_writer_notes = rel_writer_root.findall(".//Note")
    rel_writer_let_ring_found = any(n.find("LetRing") is not None for n in rel_writer_notes)
    rel_writer_palm_mute_found = any(n.find("PalmMute") is not None for n in rel_writer_notes)

    assert rel_writer_let_ring_found, "LetRing element not found in relational writer output"
    assert rel_writer_palm_mute_found, "PalmMute element not found in relational writer output"


def test_gpif_slur_roundtrip(tmp_path) -> None:
    from score2gp.gp_package import validate_roundtrip, write_gp
    from score2gp.ir import SlurTechnique
    import xml.etree.ElementTree as ET

    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")

    # Put both notes on the same string
    note1 = score.bars[0].events[0].notes[0]
    note1.string = 3

    second_event_id = score.bars[0].events[1].id
    note1.techniques.append(SlurTechnique(state="start", target_event_id=second_event_id))

    note2 = score.bars[0].events[1].notes[0]
    note2.string = 3
    note2.pitch = 59
    note2.techniques.append(SlurTechnique(state="stop"))

    out = tmp_path / "slur_roundtrip.gp"
    warnings = write_gp(score, out)
    assert warnings == []
    assert zipfile.is_zipfile(out)

    # 1. Test round-trip and verify slur is recovered (note: classic writer adds HammerOn to slur, so we verify manually)
    from score2gp.gp_package import extract_score_ir_from_gp
    recovered_score = extract_score_ir_from_gp(out)
    r_c_notes = [note for bar in recovered_score.bars for event in bar.events for note in event.notes]
    assert any(t.kind == "slur" and t.state == "start" for t in r_c_notes[0].techniques), "Slur start not recovered from written GP file"
    assert any(t.kind == "slur" and t.state == "stop" for t in r_c_notes[1].techniques), "Slur stop not recovered from written GP file"

    # 2. Test both parser paths manually
    from score2gp.gp_package import _extract_score_ir_from_gpif_root, _extract_score_ir_from_relational_gpif_root

    with zipfile.ZipFile(out) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

        notes_in_xml = root.findall(".//Note")
        slur_start_found = any(n.get("slur") == "start" for n in notes_in_xml)
        slur_stop_found = any(n.get("slur") == "stop" for n in notes_in_xml)
        assert slur_start_found, "Slur start attribute not found in GPIF note nodes"
        assert slur_stop_found, "Slur stop attribute not found in GPIF note nodes"

        # Classic path recovery
        recovered_classic = _extract_score_ir_from_gpif_root(root)
        c_note1 = recovered_classic.bars[0].events[0].notes[0]
        c_note2 = recovered_classic.bars[0].events[1].notes[0]
        assert any(t.kind == "slur" and t.state == "start" for t in c_note1.techniques), "Slur start not recovered in classic path"
        assert any(t.kind == "slur" and t.state == "stop" for t in c_note2.techniques), "Slur stop not recovered in classic path"

    # Relational path validation using a minimal relational GPIF XML structure
    relational_xml = """<GPIF>
        <Tracks>
            <Track id="t1">
                <Name>Guitar</Name>
                <Tuning name="Standard">
                    <String number="1" pitch="64"/>
                    <String number="2" pitch="59"/>
                    <String number="3" pitch="55"/>
                    <String number="4" pitch="50"/>
                    <String number="5" pitch="45"/>
                    <String number="6" pitch="40"/>
                </Tuning>
            </Track>
        </Tracks>
        <MasterBars>
            <MasterBar id="mb1">
                <Bars>bar1</Bars>
            </MasterBar>
        </MasterBars>
        <Bars>
            <Bar id="bar1">
                <Voices>v1</Voices>
            </Bar>
        </Bars>
        <Voices>
            <Voice id="v1">
                <Beats>b1 b2 b3</Beats>
            </Voice>
        </Voices>
        <Rhythms>
            <Rhythm id="r1">
                <NoteValue>Quarter</NoteValue>
            </Rhythm>
        </Rhythms>
        <Notes>
            <Note id="n1" slur="start">
                <Properties>
                    <Property name="Fret"><Fret>2</Fret></Property>
                    <Property name="String"><String>1</String></Property>
                    <Property name="Midi"><Number>47</Number></Property>
                </Properties>
            </Note>
            <Note id="n2" slur="stop">
                <Properties>
                    <Property name="Fret"><Fret>3</Fret></Property>
                    <Property name="String"><String>2</String></Property>
                    <Property name="Midi"><Number>53</Number></Property>
                </Properties>
            </Note>
            <Note id="n3">
                <Properties>
                    <Property name="Fret"><Fret>4</Fret></Property>
                    <Property name="String"><String>3</String></Property>
                    <Property name="Midi"><Number>59</Number></Property>
                    <Property name="Slur"><Enable/></Property>
                </Properties>
            </Note>
            <Note id="n4">
                <Properties>
                    <Property name="Fret"><Fret>5</Fret></Property>
                    <Property name="String"><String>4</String></Property>
                    <Property name="Midi"><Number>64</Number></Property>
                </Properties>
                <Slur state="continue"/>
            </Note>
            <Note id="n5" slur="invalid_state_value">
                <Properties>
                    <Property name="Fret"><Fret>6</Fret></Property>
                    <Property name="String"><String>5</String></Property>
                    <Property name="Midi"><Number>70</Number></Property>
                </Properties>
            </Note>
        </Notes>
        <Beats>
            <Beat id="b1">
                <Rhythm ref="r1"/>
                <Notes>n1 n4</Notes>
            </Beat>
            <Beat id="b2">
                <Rhythm ref="r1"/>
                <Notes>n2 n3</Notes>
            </Beat>
            <Beat id="b3">
                <Rhythm ref="r1"/>
                <Notes>n5</Notes>
            </Beat>
        </Beats>
        <Songs>
            <Song id="s1">
                <Score>
                    <Tracks>t1</Tracks>
                    <MasterBars>mb1</MasterBars>
                </Score>
                <Track id="t1">
                    <Bars>bar1</Bars>
                </Track>
            </Song>
        </Songs>
    </GPIF>"""

    rel_root = ET.fromstring(relational_xml)
    recovered_relational = _extract_score_ir_from_relational_gpif_root(rel_root)
    r_notes = [note for bar in recovered_relational.bars for event in bar.events for note in event.notes]
    assert len(r_notes) == 5

    # n1 (id="n1") -> slur="start" attribute
    assert any(t.kind == "slur" and t.state == "start" for t in r_notes[0].techniques)

    # n4 (id="n4") -> <Slur state="continue"/> element
    assert any(t.kind == "slur" and t.state == "continue" for t in r_notes[1].techniques)

    # n2 (id="n2") -> slur="stop" attribute
    assert any(t.kind == "slur" and t.state == "stop" for t in r_notes[2].techniques)

    # n3 (id="n3") -> <Property name="Slur"><Enable/></Property> element
    assert any(t.kind == "slur" and t.state == "start" for t in r_notes[3].techniques)

    # n5 (id="n5") -> slur="invalid_state_value" attribute -> defaults conservatively to "start"
    assert any(t.kind == "slur" and t.state == "start" for t in r_notes[4].techniques)
