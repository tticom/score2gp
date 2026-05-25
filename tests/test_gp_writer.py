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
        {"kind": "unsupported", "label": "some-weird-technique"}
    ]
    score_with_unsupported = ScoreIR.model_validate(data)

    out = tmp_path / "warnings.gp"
    warnings = write_gp(score_with_unsupported, out)

    assert any("MIDI" in warning for warning in warnings)
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
