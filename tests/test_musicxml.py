from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from score2gp.musicxml import analyze_musicxml_timing, mxl_rootfile_path, parse_musicxml

FIXTURES = Path("tests/fixtures/musicxml")


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _container(rootfile: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{rootfile}" media-type="application/vnd.recordare.musicxml+xml"/>
  </rootfiles>
</container>
"""


def _write_mxl(tmp_path: Path, *, rootfile: str, musicxml: str, include_container: bool = True) -> Path:
    path = tmp_path / "score.mxl"
    with ZipFile(path, "w", ZIP_DEFLATED) as package:
        if include_container:
            package.writestr("META-INF/container.xml", _container(rootfile))
        package.writestr(rootfile, musicxml)
    return path


def test_musicxml_importer_parses_tiny_partwise_score() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_single_bar.musicxml")

    assert imported.metadata.title == "Tiny MusicXML Test"
    assert imported.metadata.composer == "Generated Fixture"
    assert imported.tempo_bpm == 96
    assert imported.parts[0].id == "P1"
    assert imported.parts[0].name == "Guitar"

    measure = imported.parts[0].measures[0]
    assert measure.divisions == 4
    assert measure.time_signature.numerator == 4
    assert measure.time_signature.denominator == 4
    assert [note.voice for note in measure.notes] == [1, 1, 1]
    assert measure.notes[0].pitch is not None
    assert measure.notes[0].pitch.midi == 64
    assert measure.notes[1].pitch is not None
    assert measure.notes[1].pitch.name == "F#4"
    assert measure.notes[1].ties == ["start"]
    assert measure.notes[2].is_rest is True


def test_musicxml_duration_normalizes_to_scoreir_ticks() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_single_bar.musicxml")
    measure = imported.parts[0].measures[0]

    first_ticks, exact = measure.notes[0].duration_ticks(measure.divisions)
    rest_ticks, rest_exact = measure.notes[2].duration_ticks(measure.divisions)

    assert (first_ticks, exact) == (960, True)
    assert (rest_ticks, rest_exact) == (1920, True)


def test_musicxml_importer_preserves_simple_voice_numbers() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_two_voice.musicxml")
    measure = imported.parts[0].measures[0]

    assert [note.voice for note in measure.notes] == [1, 2]
    assert measure.notes[1].is_rest is True


def test_musicxml_importer_warns_for_unsupported_repeat() -> None:
    imported = parse_musicxml(FIXTURES / "unsupported_repeat.musicxml")

    assert [warning.code for warning in imported.warnings] == ["unsupported-repeat"]


def test_musicxml_importer_preserves_harmony_tuplets_and_guitar_techniques() -> None:
    imported = parse_musicxml(FIXTURES / "rich_guitar_cases.musicxml")

    assert imported.metadata.title == "Rich Guitar Cases"
    assert imported.tempo_bpm == 72

    first_measure = imported.parts[0].measures[0]
    assert first_measure.divisions == 24
    assert first_measure.harmonies[0].text == "E7"
    assert first_measure.harmonies[0].onset_divisions == 0

    chord_note = first_measure.notes[1]
    assert chord_note.chord is True
    assert chord_note.onset_divisions == 0

    triplet_note = first_measure.notes[3]
    assert triplet_note.duration_ticks(first_measure.divisions) == (320, True)
    assert triplet_note.tuplet is not None
    assert triplet_note.tuplet.actual_notes == 3
    assert triplet_note.tuplet.normal_notes == 2

    technique_kinds = [technique.kind for note in first_measure.notes for technique in note.techniques]
    assert technique_kinds == ["slide", "hammer-on", "bend", "vibrato", "slur"]

    second_measure = imported.parts[0].measures[1]
    assert second_measure.harmonies[0].text == "Gmaj7"


def test_musicxml_importer_handles_multibar_onsets_and_divisions() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_multibar.musicxml")

    assert len(imported.parts[0].measures) == 2
    first, second = imported.parts[0].measures
    assert [note.onset_ticks(first.divisions)[0] for note in first.notes] == [0, 960, 1920]
    assert [note.onset_ticks(second.divisions)[0] for note in second.notes] == [0, 1920]


def test_musicxml_importer_handles_chord_without_advancing_onset() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_chords.musicxml")
    measure = imported.parts[0].measures[0]

    assert measure.harmonies[0].text == "Em"
    assert [note.onset_divisions for note in measure.notes] == [0, 0, 4]
    assert measure.notes[1].chord is True


def test_musicxml_importer_handles_backup_for_simple_voice_timing() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_rests_voices.musicxml")
    measure = imported.parts[0].measures[0]

    assert [(note.onset_divisions, note.voice, note.is_rest) for note in measure.notes] == [
        (0, 1, False),
        (8, 1, False),
        (0, 2, True),
    ]


def test_musicxml_timing_preflight_detects_audiveris_like_overfull_bar() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_overfull_bar.musicxml")

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("musicxml-overfull-bar", "error"),
        ("musicxml_alignment_not_attempted_due_to_timing_risk", "error"),
    ]
    assert issues[0].expected_duration_divisions == 16
    assert issues[0].end_divisions == 20


def test_musicxml_timing_preflight_flags_12_8_compound_meter_without_error() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_12_8_timing.musicxml")

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("musicxml-compound-meter-assumption", "info"),
        ("valid_compound_meter", "info"),
    ]
    assert issues[0].expected_duration_divisions == 36


def test_musicxml_timing_preflight_records_backup_forward_risk() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_backup_forward.musicxml")

    assert [warning.code for warning in imported.warnings] == [
        "musicxml-backup-encountered",
        "musicxml-forward-encountered",
    ]

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("musicxml_forward_exceeds_measure_end", "error"),
        ("musicxml_unbalanced_backup_forward", "error"),
        ("musicxml_backup_forward_alignment_ambiguous", "error"),
        ("musicxml-overfull-bar", "error"),
        ("musicxml_alignment_not_attempted_due_to_timing_risk", "error"),
    ]
    overfull_issue = next(issue for issue in issues if issue.code == "musicxml-overfull-bar")
    assert overfull_issue.voice == 2


def test_musicxml_importer_parses_valid_mxl_with_container(tmp_path) -> None:
    mxl = _write_mxl(tmp_path, rootfile="score.musicxml", musicxml=_fixture_text("tiny_single_bar.musicxml"))

    imported = parse_musicxml(mxl)

    assert mxl_rootfile_path(mxl) == "score.musicxml"
    assert imported.metadata.title == "Tiny MusicXML Test"
    assert imported.source_path == str(mxl)
    assert imported.parts[0].measures[0].notes[0].pitch is not None


def test_musicxml_importer_parses_nested_mxl_rootfile(tmp_path) -> None:
    mxl = _write_mxl(tmp_path, rootfile="scores/nested.musicxml", musicxml=_fixture_text("tiny_multibar.musicxml"))

    imported = parse_musicxml(mxl)

    assert mxl_rootfile_path(mxl) == "scores/nested.musicxml"
    assert imported.metadata.title == "Tiny Multibar"
    assert len(imported.parts[0].measures) == 2


def test_musicxml_importer_rejects_mxl_missing_container(tmp_path) -> None:
    mxl = _write_mxl(
        tmp_path,
        rootfile="score.musicxml",
        musicxml=_fixture_text("tiny_single_bar.musicxml"),
        include_container=False,
    )

    with pytest.raises(ValueError, match="META-INF/container.xml"):
        parse_musicxml(mxl)


def test_musicxml_importer_rejects_mxl_missing_declared_rootfile(tmp_path) -> None:
    mxl = tmp_path / "missing-rootfile.mxl"
    with ZipFile(mxl, "w", ZIP_DEFLATED) as package:
        package.writestr("META-INF/container.xml", _container("missing/score.musicxml"))

    with pytest.raises(ValueError, match="declared MusicXML rootfile"):
        parse_musicxml(mxl)


def test_musicxml_importer_rejects_malformed_mxl(tmp_path) -> None:
    mxl = tmp_path / "not-a-zip.mxl"
    mxl.write_bytes(b"not a zip package")

    with pytest.raises(ValueError, match="invalid compressed MusicXML package"):
        parse_musicxml(mxl)


def test_musicxml_importer_rejects_empty_mxl(tmp_path) -> None:
    mxl = tmp_path / "empty.mxl"
    with ZipFile(mxl, "w", ZIP_DEFLATED):
        pass

    with pytest.raises(ValueError, match="empty"):
        parse_musicxml(mxl)


def test_musicxml_importer_rejects_unsafe_mxl_rootfile_path(tmp_path) -> None:
    mxl = tmp_path / "unsafe.mxl"
    with ZipFile(mxl, "w", ZIP_DEFLATED) as package:
        package.writestr("META-INF/container.xml", _container("../score.musicxml"))
        package.writestr("score.musicxml", _fixture_text("tiny_single_bar.musicxml"))

    with pytest.raises(ValueError, match="unsafe"):
        parse_musicxml(mxl)


def test_musicxml_timing_preflight_detects_overfull_bar_inside_mxl(tmp_path) -> None:
    mxl = _write_mxl(tmp_path, rootfile="score.musicxml", musicxml=_fixture_text("audiveris_like_overfull_bar.musicxml"))

    imported = parse_musicxml(mxl)
    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("musicxml-overfull-bar", "error"),
        ("musicxml_alignment_not_attempted_due_to_timing_risk", "error"),
    ]
    assert issues[0].end_divisions == 20


def test_musicxml_inferred_time_signature_when_missing(tmp_path) -> None:
    # 1. Create a synthetic MusicXML file with NO <time> element but has 6 beats
    musicxml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <!-- Voice 1 has notes spanning 6 beats -->
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>3</duration>
        <voice>1</voice>
        <type>half</type>
        <dot/>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>3</duration>
        <voice>1</voice>
        <type>half</type>
        <dot/>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "missing_time.musicxml"
    xml_file.write_text(musicxml_content, encoding="utf-8")

    imported = parse_musicxml(xml_file)
    assert len(imported.parts[0].measures) == 1
    measure = imported.parts[0].measures[0]

    # It must dynamically infer 12/8 instead of 4/4
    assert measure.time_signature.numerator == 12
    assert measure.time_signature.denominator == 8


def test_musicxml_polyphony_diagnostics() -> None:
    # 1. Parse two-voice score
    imported = parse_musicxml(FIXTURES / "tiny_two_voice.musicxml")

    # 2. Timing check without diagnostics should be empty or contain only standard info/warning
    issues_default = analyze_musicxml_timing(imported)
    assert not any(issue.code.startswith("musicxml_polyphony_gate_") for issue in issues_default)

    # 3. Timing check with diagnostics enabled
    issues_diag = analyze_musicxml_timing(imported, include_polyphony_diagnostics=True)
    diag_codes = {issue.code for issue in issues_diag}
    assert "musicxml_polyphony_gate_measure_count" in diag_codes
    assert "musicxml_polyphony_gate_voice_count" in diag_codes


def test_musicxml_tuplets_support(tmp_path) -> None:
    # Create a synthetic MusicXML file containing triplet (3:2), quadruplet (4:3), quintuplet (5:3), and septuplet (7:4)
    musicxml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>24</divisions>
        <time>
          <beats>12</beats>
          <beat-type>8</beat-type>
        </time>
        <key><fifths>0</fifths></key>
      </attributes>
      <!-- Voice 1: Triplet 3:2 -->
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>8</duration>
        <voice>1</voice>
        <type>eighth</type>
        <time-modification>
          <actual-notes>3</actual-notes>
          <normal-notes>2</normal-notes>
        </time-modification>
      </note>
      <!-- Voice 1: Quadruplet 4:3 -->
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>9</duration>
        <voice>1</voice>
        <type>eighth</type>
        <time-modification>
          <actual-notes>4</actual-notes>
          <normal-notes>3</normal-notes>
        </time-modification>
      </note>
      <!-- Voice 1: Quintuplet 5:3 -->
      <note>
        <pitch><step>A</step><octave>4</octave></pitch>
        <duration>7</duration>
        <voice>1</voice>
        <type>eighth</type>
        <time-modification>
          <actual-notes>5</actual-notes>
          <normal-notes>3</normal-notes>
        </time-modification>
      </note>
    </measure>
    <measure number="2">
      <attributes>
        <divisions>24</divisions>
        <time>
          <beats>12</beats>
          <beat-type>8</beat-type>
        </time>
      </attributes>
      <!-- Voice 1: Septuplet 7:4 (Unsupported) -->
      <note>
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>6</duration>
        <voice>1</voice>
        <type>eighth</type>
        <time-modification>
          <actual-notes>7</actual-notes>
          <normal-notes>4</normal-notes>
        </time-modification>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "tuplets_test.musicxml"
    xml_file.write_text(musicxml_content, encoding="utf-8")

    imported = parse_musicxml(xml_file)
    assert len(imported.parts[0].measures) == 2

    measure1 = imported.parts[0].measures[0]
    # Check that triplet, quadruplet, quintuplet are NOT marked unsupported
    assert measure1.notes[0].tuplet is not None
    assert measure1.notes[0].tuplet_unsupported is False
    assert measure1.notes[1].tuplet is not None
    assert measure1.notes[1].tuplet_unsupported is False
    assert measure1.notes[2].tuplet is not None
    assert measure1.notes[2].tuplet_unsupported is False

    measure2 = imported.parts[0].measures[1]
    # Check that septuplet is marked unsupported
    assert measure2.notes[0].tuplet is not None
    assert measure2.notes[0].tuplet_unsupported is True

    # Run preflight timing analysis
    issues = analyze_musicxml_timing(imported)

    # Measure 1 should have NO tuplet errors. Measure 2 should have one tuplet error.
    tuplet_errors = [issue for issue in issues if issue.code == "musicxml_tuplet_unsupported"]
    assert len(tuplet_errors) == 1
    assert tuplet_errors[0].measure_number == "2"


def test_musicxml_grace_note_parsing_and_deduplication(tmp_path) -> None:
    # 1. Create a synthetic MusicXML with notation & TAB grace notes in voice 1 and voice 5
    musicxml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>2</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <!-- Voice 1: Grace Note -> Host Note -->
      <note>
        <grace slash="yes"/>
        <pitch><step>E</step><octave>4</octave></pitch>
        <voice>1</voice>
        <type>eighth</type>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>2</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <!-- Backup to Voice 5 (TAB representation) -->
      <backup><duration>2</duration></backup>
      <note>
        <grace slash="yes"/>
        <pitch><step>E</step><octave>4</octave></pitch>
        <voice>5</voice>
        <type>eighth</type>
        <notations>
          <technical>
            <string>1</string>
            <fret>0</fret>
          </technical>
        </notations>
      </note>
      <note>
        <voice>5</voice>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>2</duration>
        <type>quarter</type>
        <notations>
          <technical>
            <string>1</string>
            <fret>3</fret>
          </technical>
        </notations>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "grace_test.musicxml"
    xml_file.write_text(musicxml_content, encoding="utf-8")

    from score2gp.musicxml import parse_musicxml
    imported = parse_musicxml(xml_file)
    assert len(imported.parts[0].measures) == 1
    measure = imported.parts[0].measures[0]

    # We should have 4 notes parsed
    assert len(measure.notes) == 4
    n1, n2, n3, n4 = measure.notes
    assert n1.grace is True
    assert n1.grace_slash is True
    assert n3.grace is True
    assert n3.grace_slash is True

    # Run deduplication
    from score2gp.musicxml import deduplicate_suspected_staff_tab_voices
    dedup_imported = deduplicate_suspected_staff_tab_voices(imported)
    dedup_measure = dedup_imported.parts[0].measures[0]

    # The duplicate TAB grace note (n3) and duplicate TAB host note (n4) should be suppressed
    grace_notes = [n for n in dedup_measure.notes if n.grace]
    assert len(grace_notes) == 2
    # n3 should be suppressed
    assert grace_notes[0].is_suppressed is False  # Voice 1 grace note
    assert grace_notes[1].is_suppressed is True   # Voice 5 grace note

    # Voice 1 grace note should have merged fret/string metadata
    assert grace_notes[0].dedup_tab_note_id == grace_notes[1].id

    # Build IR should align and compile them successfully
    from score2gp.build_ir import build_ir_from_files
    from score2gp.tabraw import TabRaw, TabCandidate

    tabraw = TabRaw(
        candidates=[
            TabCandidate(
                id="cand1",
                page_index=1,
                system_index=1,
                bar_index=1,
                parsed_fret=0,
                string=1,
                raw_text="0",
                x=10.0,
                source_stage="pdf-text",
                confidence=0.9,
                raw={"x": 10.0, "y": 100.0},
            ),
            TabCandidate(
                id="cand2",
                page_index=1,
                system_index=1,
                bar_index=1,
                parsed_fret=3,
                string=1,
                raw_text="3",
                x=20.0,
                source_stage="pdf-text",
                confidence=0.9,
                raw={"x": 20.0, "y": 100.0},
            ),
        ]
    )
    tabraw_file = tmp_path / "tabraw.json"
    tabraw.to_json_file(tabraw_file)
    # Build IR
    score = build_ir_from_files(xml_file, tabraw_file, allow_remediation=True)
    assert len(score.bars) == 1
    bar = score.bars[0]
    # We should have 2 events: one grace note event (duration 0) and one host note event
    assert len(bar.events) == 2
    e1, e2 = bar.events
    assert e1.timing.duration_ticks == 0
    assert e1.timing.grace is not None
    assert e1.timing.grace.slash is True
    assert e1.timing.grace.duration == "eighth"
    assert e1.notes[0].fret == 0
    assert e1.notes[0].string == 1

    assert e2.timing.duration_ticks == 960
    assert e2.timing.grace is None
    assert e2.notes[0].fret == 3
    assert e2.notes[0].string == 1
