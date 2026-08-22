import json
from pathlib import Path
from score2gp.build_ir import build_ir_from_files
from score2gp.ir import validate_score_ir_file

def test_dynamic_system_skipped_measure_alignment(tmp_path):
    # 1. Create a synthetic MusicXML file with 4 measures:
    # Measure 1 (number 21): pitch E4 (sounding MIDI 52)
    # Measure 2 (number 22): pitch F4 (sounding MIDI 53)
    # Measure 3 (number 23): pitch G4 (sounding MIDI 55)
    # Measure 4 (number 24): pitch A4 (sounding MIDI 57)
    musicxml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="21">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
    <measure number="22">
      <note>
        <pitch><step>F</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
    <measure number="23">
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
    <measure number="24">
      <note>
        <pitch><step>A</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    musicxml_path = tmp_path / "test_score.musicxml"
    musicxml_path.write_text(musicxml_content, encoding="utf-8")

    # 2. Create a synthetic TabRaw file with 3 visual bars:
    # Bar 1 (System 1, local_bar 1): pitch E3 (sounding MIDI 52) -> string 4, fret 2
    # Bar 2 (System 2, local_bar 1): pitch G3 (sounding MIDI 55) -> string 3, fret 0
    # Bar 3 (System 3, local_bar 1): pitch A3 (sounding MIDI 57) -> string 3, fret 2
    tabraw_data = {
      "schema_version": "tabraw.v0.1",
      "source_pdf": "synthetic skipped measure alignment test",
      "inspection_kind": "synthetic",
      "candidates": [
        {
          "id": "tab-001",
          "kind": "fret",
          "page_index": 1,
          "system_index": 1,
          "staff_index": 1,
          "bar_index": 1,
          "line_index": 1,
          "string": 4,
          "raw_text": "2",
          "parsed_fret": 2,
          "x": 100.0,
          "y": 40.0,
          "confidence": 0.95,
          "source_stage": "pdf-text",
          "raw": {
            "local_bar_index": 1,
            "system_first_bar_index": 1
          }
        },
        {
          "id": "tab-002",
          "kind": "fret",
          "page_index": 1,
          "system_index": 2,
          "staff_index": 1,
          "bar_index": 1,
          "line_index": 1,
          "string": 3,
          "raw_text": "0",
          "parsed_fret": 0,
          "x": 100.0,
          "y": 80.0,
          "confidence": 0.95,
          "source_stage": "pdf-text",
          "raw": {
            "local_bar_index": 1,
            "system_first_bar_index": 1
          }
        },
        {
          "id": "tab-003",
          "kind": "fret",
          "page_index": 1,
          "system_index": 3,
          "staff_index": 1,
          "bar_index": 1,
          "line_index": 1,
          "string": 3,
          "raw_text": "2",
          "parsed_fret": 2,
          "x": 100.0,
          "y": 120.0,
          "confidence": 0.95,
          "source_stage": "pdf-text",
          "raw": {
            "local_bar_index": 1,
            "system_first_bar_index": 1
          }
        }
      ],
      "warnings": []
    }
    tabraw_path = tmp_path / "test_tabraw.json"
    tabraw_path.write_text(json.dumps(tabraw_data, indent=2), encoding="utf-8")

    # 3. Build ScoreIR from files
    ir_path = tmp_path / "test_score.ir.json"
    score = build_ir_from_files(musicxml_path, tabraw_path, ir_path, allow_skip_unboxed=True)

    # 4. Verify validation success
    validated, errors = validate_score_ir_file(ir_path)
    assert errors == []
    assert validated is not None

    # 5. Assert correct mappings:
    # - Bar 1 -> Measure 21 (IR index 0)
    # - Bar 2 -> Measure 23 (IR index 2)
    # - Bar 3 -> Measure 24 (IR index 3)
    # Measure 22 (IR index 1) should remain a rest (empty of fret candidates)
    # 5. Assert correct mappings:
    assert len(score.bars) == 4
    
    # Check E (sounding 52) is in Bar 1 (index 0)
    bar1_events = score.bars[0].events
    assert len(bar1_events) == 1
    assert bar1_events[0].notes[0].pitch == 52
    
    # Check Bar 2 (index 1, Measure 22) is empty/rest (skipped event)
    bar2_events = score.bars[1].events
    assert len(bar2_events) == 0
    
    # Check G (sounding 55) is in Bar 3 (index 2, Measure 23)
    bar3_events = score.bars[2].events
    assert len(bar3_events) == 1
    assert bar3_events[0].notes[0].pitch == 55
    
    # Check A (sounding 57) is in Bar 4 (index 3, Measure 24)
    bar4_events = score.bars[3].events
    assert len(bar4_events) == 1
    assert bar4_events[0].notes[0].pitch == 57

    # 6. Verify that skipped Measure 2 (Measure index 2, number "22") is logged as a pdf_system_alignment_gap warning
    warnings = [w for w in score.warnings if w.code == "pdf_system_alignment_gap"]
    assert len(warnings) == 1
    assert "measure 2" in warnings[0].message.lower() or "measure index 2" in warnings[0].message.lower() or "measure 22" in warnings[0].message.lower()
