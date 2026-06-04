from __future__ import annotations

from pathlib import Path
import pytest

from score2gp.musicxml import parse_musicxml, analyze_musicxml_timing
from score2gp.build_ir import build_ir_from_files, BuildIrInputRiskError

FIXTURES = Path("tests/fixtures/musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")


def test_vc_valid_two_voice(tmp_path) -> None:
    # 1. Valid two-voice MusicXML using backup to start voice 2 after voice 1
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_two_voice.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Timing is valid, but it has cross-voice overlap which is unsupported polyphony
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_two_voice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_valid_two_voice.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_vc_valid_chord_stack(tmp_path) -> None:
    # 2. Valid chord stack using <chord/>
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_chord_stack.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Legit chord stack classified as valid timeline, not same-voice overlap (no error)
    assert any(issue.code == "musicxml_chord_stack_detected" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_chord_stack.ir.json"
    score = build_ir_from_files(FIXTURES / "timing_vc_valid_chord_stack.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_vc_invalid_same_voice(tmp_path) -> None:
    # 3. Invalid same-voice overlap caused by backup without voice separation
    imported = parse_musicxml(FIXTURES / "timing_vc_invalid_same_voice.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml-voice-overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "invalid_same_voice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_invalid_same_voice.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_backup_before_start(tmp_path) -> None:
    # 4. Invalid backup before measure start
    imported = parse_musicxml(FIXTURES / "timing_vc_backup_before_start.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_backup_rewinds_before_measure_start" and issue.severity == "warning" for issue in issues)


def test_vc_forward_past_end(tmp_path) -> None:
    # 5. Invalid forward past measure end
    imported = parse_musicxml(FIXTURES / "timing_vc_forward_past_end.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_forward_exceeds_measure_end" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "forward_past_end.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_forward_past_end.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_valid_two_voice_uneven(tmp_path) -> None:
    # 6. Valid voice 1 and voice 2 with different internal durations but both inside measure
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_two_voice_uneven.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_two_voice_uneven.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_valid_two_voice_uneven.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_vc_rest_overlap(tmp_path) -> None:
    # 7. Rest overlap in same voice
    imported = parse_musicxml(FIXTURES / "timing_vc_rest_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_rest_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "rest_overlap.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_rest_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_ambiguous_bf(tmp_path) -> None:
    # 8. Ambiguous backup/forward pattern where event ownership cannot be safely assigned
    imported = parse_musicxml(FIXTURES / "timing_vc_ambiguous_bf.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "ambiguous_bf.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_ambiguous_bf.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_audiveris_unsupported(tmp_path) -> None:
    # 9. Audiveris-like synthetic two-voice backup/forward pattern that is valid MusicXML timing but unsupported by ScoreIR
    imported = parse_musicxml(FIXTURES / "timing_vc_audiveris_unsupported.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Valid multivoice timing but unsupported polyphony
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "audiveris_unsupported.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_audiveris_unsupported.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_vc_underfull_backup_forward_remediation(tmp_path) -> None:
    # 1. allow_remediation=True downgrades underfull-only backup/forward drift to warnings
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>30</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <backup>
        <duration>30</duration>
      </backup>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>30</duration>
        <voice>5</voice>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "underfull_bf.musicxml"
    xml_file.write_text(xml_content, encoding="utf-8")

    # With allow_remediation=True, it should be a warning
    imported_remed = parse_musicxml(xml_file, allow_remediation=True)
    issues_remed = analyze_musicxml_timing(imported_remed)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "warning" for issue in issues_remed)
    assert not any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues_remed)

    # With allow_remediation=False, it should be an error
    imported_fatal = parse_musicxml(xml_file, allow_remediation=False)
    issues_fatal = analyze_musicxml_timing(imported_fatal)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues_fatal)


def test_vc_remediation_bounds_and_overlaps(tmp_path) -> None:
    # 2. Overfull measure with backup/forward remains fatal
    xml_overfull = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>34</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <backup>
        <duration>34</duration>
      </backup>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>34</duration>
        <voice>5</voice>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "overfull_bf.musicxml"
    xml_file.write_text(xml_overfull, encoding="utf-8")
    imported = parse_musicxml(xml_file, allow_remediation=False)
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    # 3. Same-voice overlap with backup/forward remains fatal
    xml_overlap = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>16</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <backup>
        <duration>8</duration>
      </backup>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>16</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <backup>
        <duration>24</duration>
      </backup>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>24</duration>
        <voice>5</voice>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "overlap_bf.musicxml"
    xml_file.write_text(xml_overlap, encoding="utf-8")
    imported = parse_musicxml(xml_file, allow_remediation=True)
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    # 4. Backup rewinds before measure start remains fatal
    xml_backup_past_zero = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>30</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <backup>
        <duration>40</duration>
      </backup>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>30</duration>
        <voice>5</voice>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "backup_past_zero_bf.musicxml"
    xml_file.write_text(xml_backup_past_zero, encoding="utf-8")
    imported = parse_musicxml(xml_file, allow_remediation=True)
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    # 5. Forward exceeds measure end remains fatal
    xml_forward_past_end = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>20</duration>
        <voice>1</voice>
        <staff>1</staff>
      </note>
      <forward>
        <duration>15</duration>
      </forward>
      <backup>
        <duration>35</duration>
      </backup>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>30</duration>
        <voice>5</voice>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    xml_file = tmp_path / "forward_past_end_bf.musicxml"
    xml_file.write_text(xml_forward_past_end, encoding="utf-8")
    imported = parse_musicxml(xml_file, allow_remediation=True)
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)
