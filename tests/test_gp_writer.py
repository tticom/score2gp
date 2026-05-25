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
