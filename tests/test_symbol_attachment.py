from __future__ import annotations

import json
from pathlib import Path
import pytest

from score2gp.build_ir import build_ir_from_files, build_ir_with_diagnostics_from_files
from score2gp.ir import validate_score_ir_file

MUSICXML = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")


def test_chord_symbol_attachment_cases(tmp_path) -> None:
    # 1. Unambiguous chord symbol above safely timed bar (x is None) - attaches to first event
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "2",
                "parsed_fret": 2,
                "x": 180.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "chord-001",
                "kind": "chord-symbol",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "Cmaj7",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_chord_none.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    assert len(score.bars) == 1
    events = score.bars[0].events
    assert len(events) == 3  # Two playable notes and one rest

    # Cmaj7 attaches to first event
    assert events[0].chord_symbol == "Cmaj7"
    assert events[0].provenance[-1].raw_token_id == "chord-001"
    assert events[1].chord_symbol is None
    assert score.warnings == []

    # Check diagnostic counters
    assert diagnostics.symbol_attachment_chord_candidates_found == 1
    assert diagnostics.symbol_attachment_chord_candidates_attached == 1
    assert diagnostics.symbol_attachment_chord_candidates_unattached == 0

    # 2. Unambiguous chord symbol near second event (x = 175.0) - attaches to second event
    tabraw_data["candidates"][-1]["x"] = 175.0
    tabraw_file = tmp_path / "tabraw_chord_near.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    assert events[0].chord_symbol is None
    assert events[1].chord_symbol == "Cmaj7"
    assert events[1].provenance[-1].raw_token_id == "chord-001"
    assert score.warnings == []

    # 3. Ambiguous chord symbol between two events (x = 140.0) - tie/close range ambiguity
    tabraw_data["candidates"][-1]["x"] = 140.0
    tabraw_file = tmp_path / "tabraw_chord_ambiguous.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    assert events[0].chord_symbol is None
    assert events[1].chord_symbol is None
    
    # Ambiguous warning is emitted
    warning_codes = [w.code for w in score.warnings]
    assert "ambiguous_chord_symbol_attachment" in warning_codes
    assert diagnostics.symbol_attachment_chord_candidates_found == 1
    assert diagnostics.symbol_attachment_chord_candidates_attached == 0
    assert diagnostics.symbol_attachment_chord_candidates_unattached == 1


def test_technique_attachment_cases(tmp_path) -> None:
    # 1. Supported technique vibrato near exactly one note target (attached)
    # Let's keep only one fret candidate so there is exactly one note target
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "vib",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_vibrato.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    # The first event is playable (others skipped/rest)
    playable_events = [e for e in events if not e.is_rest]
    assert len(playable_events) == 1
    note = playable_events[0].notes[0]
    
    assert len(note.techniques) == 1
    assert note.techniques[0].kind == "vibrato"
    assert note.provenance[-1].raw_token_id == "tech-001"

    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 1
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 0

    # 2. Ambiguous technique near multiple note targets
    # Let's add back the second fret candidate so there are two note targets
    tabraw_data["candidates"].insert(1, {
        "id": "tab-002",
        "kind": "fret",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bar_index": 1,
        "line_index": 1,
        "string": 1,
        "raw_text": "2",
        "parsed_fret": 2,
        "x": 180.0,
        "y": 40.0,
        "confidence": 0.95,
    })
    tabraw_file = tmp_path / "tabraw_tech_ambiguous.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    
    # Both notes should not have vibrato technique
    events = score.bars[0].events
    for ev in events:
        if not ev.is_rest:
            for note in ev.notes:
                # Vibrato was not attached because there are two notes in the bar
                assert not any(t.kind == "vibrato" for t in note.techniques)

    warning_codes = [w.code for w in score.warnings]
    assert "ambiguous_technique_attachment" in warning_codes
    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 0
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 1


def test_unsupported_technique_text(tmp_path) -> None:
    # Technique text of unsupported notation emits warning
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "release",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_unsupported.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    warning_codes = [w.code for w in score.warnings]
    assert "unsupported_technique_text" in warning_codes


def test_span_technique_attachment_cases(tmp_path) -> None:
    # 1. Unambiguous hammer-on with exactly two sequential notes
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "2",
                "parsed_fret": 2,
                "x": 180.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tech-001",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "h",
                "confidence": 0.9,
            }
        ],
        "warnings": []
    }
    tabraw_file = tmp_path / "tabraw_tech_ho.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_with_diagnostics_from_files(MUSICXML, tabraw_file)
    events = score.bars[0].events
    note1 = events[0].notes[0]
    note2 = events[1].notes[0]

    assert len(note1.techniques) == 1
    assert note1.techniques[0].kind == "hammer-on"
    assert note1.techniques[0].target_event_id == events[1].id
    assert note1.provenance[-1].raw_token_id == "tech-001"
    assert score.warnings == []

    assert diagnostics.symbol_attachment_technique_candidates_found == 1
    assert diagnostics.symbol_attachment_technique_candidates_attached == 1
    assert diagnostics.symbol_attachment_technique_candidates_unattached == 0


def test_symbol_attachment_html_diagnostics(tmp_path) -> None:
    # Test all HTML diagnostic report requirements
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "chord-attached",
                "kind": "chord-symbol",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "Cmaj7",
                "confidence": 0.9,
            },
            {
                "id": "chord-unattached",
                "kind": "chord-symbol",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 99,  # No bar 99 exists!
                "raw_text": "D7",
                "confidence": 0.8,
            },
            {
                "id": "tech-attached",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "vib",
                "confidence": 0.85,
            },
            {
                "id": "tech-unsupported",
                "kind": "technique-text",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "raw_text": "release",
                "confidence": 0.75,
            }
        ],
        "warnings": []
    }

    tabraw_file = tmp_path / "tabraw_diagnostics.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    ir_path = tmp_path / "score.ir.json"
    diagnostics_path = tmp_path / "diagnostics.json"

    score = build_ir_from_files(
        MUSICXML,
        tabraw_file,
        out_path=ir_path,
        diagnostics_out_path=diagnostics_path
    )

    # 1. HTML diagnostics are written when chord/technique attachment diagnostics exist
    html_path = tmp_path / "symbol-attachment-diagnostics.html"
    assert html_path.exists()

    html_content = html_path.read_text(encoding="utf-8")

    # 2. HTML includes attached chord count
    assert "Chord Symbols Summary" in html_content
    # There is 1 attached chord
    assert "Successfully Attached:" in html_content

    # 3. HTML includes unattached chord count
    assert "Unattached / Refused:" in html_content

    # 4. HTML includes attached technique count
    assert "Technique Texts Summary" in html_content

    # 5. HTML includes unattached technique count

    # 6. HTML includes warning/reason codes for unsupported or ambiguous text
    assert "unsupported_technique_text" in html_content
    assert "unattached_chord_symbol" in html_content

    # 7. HTML includes provenance/candidate IDs
    assert "chord-attached" in html_content
    assert "chord-unattached" in html_content
    assert "tech-attached" in html_content
    assert "tech-unsupported" in html_content

    # 8. HTML states that GPIF rendering is not implemented
    assert "GPIF rendering is NOT implemented" in html_content

    # 9. HTML states that symbols did not create notes/events/timing
    assert "Symbols and techniques DID NOT create notes" in html_content


def test_proximity_technique_attachment_cases(tmp_path) -> None:
    # Set up a 3-note MusicXML file
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
        <divisions>4</divisions>
        <time>
          <beats>4</beats>
          <beat-type>4</beat-type>
        </time>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>F</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    musicxml_file = tmp_path / "three_notes.musicxml"
    musicxml_file.write_text(musicxml_content, encoding="utf-8")

    # Base tabraw template with three notes on string 1:
    # Note 1: x = 100.0
    # Note 2: x = 180.0
    # Note 3: x = 260.0
    # Total adjacent pairs are: (1, 2) midpoint 140.0, and (2, 3) midpoint 220.0.
    base_tabraw = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
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
                "string": 1,
                "raw_text": "0",
                "parsed_fret": 0,
                "x": 100.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "2",
                "parsed_fret": 2,
                "x": 180.0,
                "y": 40.0,
                "confidence": 0.95,
            },
            {
                "id": "tab-003",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "3",
                "parsed_fret": 3,
                "x": 260.0,
                "y": 40.0,
                "confidence": 0.95,
            },
        ],
        "warnings": []
    }

    # 1. Slide proximity test (unambiguous, matches Note 1)
    slide_candidate = {
        "id": "tech-slide",
        "kind": "technique-text",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bar_index": 1,
        "raw_text": "sl.",
        "x": 103.0,
        "confidence": 0.9,
    }
    tabraw_data = dict(base_tabraw)
    tabraw_data["candidates"] = base_tabraw["candidates"] + [slide_candidate]

    tabraw_file = tmp_path / "tabraw_slide_prox.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert len(events) == 3
    # slide should be on note 1 (events[0].notes[0])
    assert len(events[0].notes[0].techniques) == 1
    assert events[0].notes[0].techniques[0].kind == "slide"
    assert not events[1].notes[0].techniques
    assert not events[2].notes[0].techniques

    # 2. Slide proximity test (unambiguous, matches Note 2)
    slide_candidate["x"] = 182.0
    tabraw_file = tmp_path / "tabraw_slide_prox_2.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert len(events[1].notes[0].techniques) == 1
    assert events[1].notes[0].techniques[0].kind == "slide"
    assert not events[2].notes[0].techniques

    # 3. Slide ambiguity test (x is at midpoint 140.0, difference is 0.0 < 2.0)
    slide_candidate["x"] = 140.0
    tabraw_file = tmp_path / "tabraw_slide_ambig.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert not events[1].notes[0].techniques
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # 4. Slide ambiguity threshold (x = 140.5, dists: N1=40.5, N2=39.5, diff=1.0 < 2.0)
    slide_candidate["x"] = 140.5
    tabraw_file = tmp_path / "tabraw_slide_ambig_thresh.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert not events[1].notes[0].techniques
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # 5. Hammer-on proximity test (unambiguous, matches pair (1, 2) at mid_x=140.0)
    ho_candidate = {
        "id": "tech-ho",
        "kind": "technique-text",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bar_index": 1,
        "raw_text": "h",
        "x": 139.0,  # closer to mid_x 140.0 (dist 1.0) than mid_x 220.0 (dist 81.0)
        "confidence": 0.9,
    }
    tabraw_data = dict(base_tabraw)
    tabraw_data["candidates"] = base_tabraw["candidates"] + [ho_candidate]
    tabraw_file = tmp_path / "tabraw_ho_prox.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    # ho should be on note 1 targeting event 2
    assert len(events[0].notes[0].techniques) == 1
    assert events[0].notes[0].techniques[0].kind == "hammer-on"
    assert events[0].notes[0].techniques[0].target_event_id == events[1].id
    assert not events[1].notes[0].techniques

    # 6. Hammer-on proximity test (unambiguous, matches pair (2, 3) at mid_x=220.0)
    ho_candidate["x"] = 221.0
    tabraw_file = tmp_path / "tabraw_ho_prox_2.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert len(events[1].notes[0].techniques) == 1
    assert events[1].notes[0].techniques[0].kind == "hammer-on"
    assert events[1].notes[0].techniques[0].target_event_id == events[2].id

    # 7. Hammer-on ambiguity test (x = 180.0, midpoints 140.0 and 220.0 are equidistant at 40.0, diff 0.0 < 2.0)
    ho_candidate["x"] = 180.0
    tabraw_file = tmp_path / "tabraw_ho_ambig.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert not events[1].notes[0].techniques
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # 8. Hammer-on ambiguity threshold (x = 180.5, dists: (1,2)=40.5, (2,3)=39.5, diff 1.0 < 2.0)
    ho_candidate["x"] = 180.5
    tabraw_file = tmp_path / "tabraw_ho_ambig_thresh.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    events = score.bars[0].events
    assert not events[0].notes[0].techniques
    assert not events[1].notes[0].techniques
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # 9. Fallback preservation test (x is None, original count-based checks)
    # For slide, since we have 3 notes, fallback will fail and warn.
    slide_candidate["x"] = None
    tabraw_data = dict(base_tabraw)
    tabraw_data["candidates"] = base_tabraw["candidates"] + [slide_candidate]
    tabraw_file = tmp_path / "tabraw_slide_fallback_fail.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # For hammer-on, fallback will also fail and warn because we have 3 notes (not exactly 2).
    ho_candidate["x"] = None
    tabraw_data = dict(base_tabraw)
    tabraw_data["candidates"] = base_tabraw["candidates"] + [ho_candidate]
    tabraw_file = tmp_path / "tabraw_ho_fallback_fail.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file, tabraw_file)
    assert any(w.code == "ambiguous_technique_attachment" for w in score.warnings)

    # Now let's test fallback succeeds when notes count is correct:
    # 9a. Slide fallback succeeds on single note
    single_note_tabraw = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            base_tabraw["candidates"][0],
            slide_candidate
        ]
    }
    musicxml_content_1 = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    musicxml_file_1 = tmp_path / "one_note.musicxml"
    musicxml_file_1.write_text(musicxml_content_1, encoding="utf-8")
    tabraw_file = tmp_path / "tabraw_slide_fallback_pass.json"
    tabraw_file.write_text(json.dumps(single_note_tabraw), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file_1, tabraw_file)
    assert not any(w.code == "ambiguous_technique_attachment" for w in score.warnings)
    events = score.bars[0].events
    assert len(events[0].notes[0].techniques) == 1
    assert events[0].notes[0].techniques[0].kind == "slide"

    # 9b. HO fallback succeeds on exactly two notes
    two_note_tabraw = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "synthetic",
        "candidates": [
            base_tabraw["candidates"][0],
            base_tabraw["candidates"][1],
            ho_candidate
        ]
    }
    musicxml_content_2 = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>F</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    musicxml_file_2 = tmp_path / "two_notes.musicxml"
    musicxml_file_2.write_text(musicxml_content_2, encoding="utf-8")
    tabraw_file = tmp_path / "tabraw_ho_fallback_pass.json"
    tabraw_file.write_text(json.dumps(two_note_tabraw), encoding="utf-8")
    score, _ = build_ir_with_diagnostics_from_files(musicxml_file_2, tabraw_file)
    assert not any(w.code == "ambiguous_technique_attachment" for w in score.warnings)
    events = score.bars[0].events
    assert len(events[0].notes[0].techniques) == 1
    assert events[0].notes[0].techniques[0].kind == "hammer-on"
    assert events[0].notes[0].techniques[0].target_event_id == events[1].id
