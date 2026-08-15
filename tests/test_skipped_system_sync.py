from __future__ import annotations

import json
from pathlib import Path
import pytest

from score2gp.build_ir import build_ir_with_diagnostics_from_files
from score2gp.musicxml import parse_musicxml
from score2gp.tabraw import TabRaw

def test_skipped_system_sync_logic(tmp_path) -> None:
    # 1. Create a synthetic MusicXML file with 3 measures
    musicxml_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <!-- Measure 1 -->
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch>
          <step>E</step>
          <octave>4</octave>
        </pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
    <!-- Measure 2 -->
    <measure number="2">
      <note>
        <pitch>
          <step>F</step>
          <alter>1</alter>
          <octave>4</octave>
        </pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
    <!-- Measure 3 -->
    <measure number="3">
      <note>
        <pitch>
          <step>G</step>
          <octave>4</octave>
        </pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    musicxml_file = tmp_path / "sync_test.musicxml"
    musicxml_file.write_text(musicxml_content, encoding="utf-8")

    # 2. Create a TabRaw JSON file simulating:
    # - System 1 (Page 1): 1 candidate in Bar 1 (pitch E4 / string 1 fret 0)
    # - System 2 (Page 1): unboxed/skipped (warning present, no candidates)
    # - System 3 (Page 1): 1 candidate in Bar 2 (pitch G4 / string 1 fret 3)
    # Note that due to skipping System 2, System 3 got bar_index=2 in PDF.
    # Without synchronization, System 3 candidate would map to Measure 2 (pitch F#4),
    # causing a mismatch. With synchronization, it offsets to Measure 3.
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "sync_test.pdf",
        "candidates": [
            {
                "id": "c1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 500.0,
                "confidence": 0.95,
                "raw": {}
            },
            {
                "id": "c2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 3,
                "bar_index": 2,
                "string": 1,
                "raw_text": "3",
                "parsed_fret": 3,
                "x": 100.0,
                "y": 300.0,
                "confidence": 0.95,
                "raw": {}
            }
        ],
        "warnings": [
            # System 2 is skipped
            {
                "code": "pdf_barlines_not_detected_in_system",
                "message": "Barboxes are missing in system 2 on page 1.",
                "severity": "warning",
                "page_index": 1,
                "system_index": 2
            },
            {
                "code": "pdf_barline_too_short",
                "message": "Barline too short in system 2 on page 1.",
                "severity": "warning",
                "page_index": 1,
                "system_index": 2
            }
        ]
    }
    tabraw_file = tmp_path / "sync_test.tabraw.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    # 3. Compile using build_ir with allow_skip_unboxed=True
    score, diagnostics = build_ir_with_diagnostics_from_files(
        musicxml_file,
        tabraw_file,
        allow_skip_unboxed=True
    )

    # 4. Verify synchronization results
    # System 3 candidate (c2) should now be shifted to Bar index 3!
    assert score is not None
    assert len(score.bars) == 3

    # Bar 1 has the event from c1
    assert len(score.bars[0].events) == 1
    assert score.bars[0].events[0].notes[0].pitch == 64  # E4

    # Bar 2 has no events because Measure 2 was skipped
    assert len(score.bars[1].events) == 0

    # Bar 3 has the event from c2 (shifted from bar_index 2 to 3!)
    assert len(score.bars[2].events) == 1
    assert score.bars[2].events[0].notes[0].pitch == 67  # G4

    # The skipped warning should be clean
    warning_codes = [w.code for w in score.warnings]
    assert "pdf_unboxed_system_skipped" in warning_codes

def test_skipped_system_sync_fixtures() -> None:
    musicxml_file = Path("fixtures/public/skipped_system_sync.musicxml")
    tabraw_file = Path("fixtures/public/skipped_system_sync.tabraw.json")
    score, diagnostics = build_ir_with_diagnostics_from_files(
        musicxml_file,
        tabraw_file,
        allow_skip_unboxed=True
    )
    assert score is not None
    assert len(score.bars) == 3

    # Bar 1 has the event from c1
    assert len(score.bars[0].events) == 1
    assert score.bars[0].events[0].notes[0].pitch == 64  # E4

    # Bar 2 has no events because Measure 2 was skipped
    assert len(score.bars[1].events) == 0

    # Bar 3 has the event from c2 (shifted from bar_index 2 to 3!)
    assert len(score.bars[2].events) == 1
    assert score.bars[2].events[0].notes[0].pitch == 67  # G4

    # The skipped warning should be clean
    warning_codes = [w.code for w in score.warnings]
    assert "pdf_unboxed_system_skipped" in warning_codes

