import pytest
import json
from pathlib import Path
from unittest.mock import patch
from score2gp.build_ir import build_ir_from_files, BuildIrInputRiskError
from score2gp.tabraw import TabRaw
from score2gp.ir import validate_score_ir_file

# Helper templates for synthetic MusicXML files
CLEAN_ONE_BAR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work><work-title>Clean One Bar Spacing</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>3</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""

CLEAN_MULTIBAR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work><work-title>Clean Multi Bar Spacing</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
    <measure number="2">
      <note>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
      <note>
        <pitch><step>E</step><octave>5</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""

POLYPHONY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work><work-title>Polyphony Overlap Spacing</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>2</duration>
        <voice>1</voice>
        <type>half</type>
      </note>
      <backup><duration>2</duration></backup>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>2</duration>
        <voice>2</voice>
        <type>half</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""

OVERFULL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work><work-title>Overfull Bar Spacing</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>3</duration>
        <voice>1</voice>
        <type>half</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""

def make_tabraw(items, warnings=None):
    return {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic",
        "inspection_kind": "born-digital",
        "items": items,
        "warnings": warnings or []
    }

def test_clean_one_bar_mapping_good(tmp_path) -> None:
    # 1. Clean one-bar PDF matching MusicXML onsets -> good quality
    xml_path = tmp_path / "clean_one_bar.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "clean_one_bar.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 200.0, "y": 60.0, "bbox": [200, 58, 205, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 2, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "clean_one_bar.ir.json"
    diagnostics_path = tmp_path / "clean_one_bar.diagnostics.json"
    
    score = build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert diagnostics["pdf_timing_mapping"]["quality"] == "good"
    assert diagnostics["pdf_timing_mapping"]["grouping_safe"] is True
    assert diagnostics["pdf_timing_mapping"]["timing_source_safe"] is True
    assert diagnostics["pdf_timing_mapping"]["whether_mapping_attempted"] is True
    assert diagnostics["pdf_timing_mapping"]["whether_mapping_refused"] is False
    assert "pdf_timing_mapping_quality_good" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert len(diagnostics["pdf_timing_mapping"]["per_bar"]) == 1
    assert diagnostics["pdf_timing_mapping"]["per_bar"][0]["quality"] == "good"
    assert (tmp_path / "pdf-timing-mapping-diagnostics.html").exists()

def test_clean_multibar_mapping_good(tmp_path) -> None:
    # 2. Multi-bar PDF matching MusicXML onsets -> good quality per bar
    xml_path = tmp_path / "clean_multibar.musicxml"
    xml_path.write_text(CLEAN_MULTIBAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "clean_multibar.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 200.0, "y": 60.0, "bbox": [200, 58, 205, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 2, "system_index": 1, "bar_index": 2, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]},
        {"id": "c4", "text": "0", "parsed_fret": 0, "string": 4, "system_index": 1, "bar_index": 2, "page": 1, "x": 400.0, "y": 65.0, "bbox": [400, 63, 405, 67]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "clean_multibar.ir.json"
    diagnostics_path = tmp_path / "clean_multibar.diagnostics.json"
    
    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert diagnostics["pdf_timing_mapping"]["quality"] == "good"
    assert len(diagnostics["pdf_timing_mapping"]["per_bar"]) == 2
    assert diagnostics["pdf_timing_mapping"]["per_bar"][0]["quality"] == "good"
    assert diagnostics["pdf_timing_mapping"]["per_bar"][1]["quality"] == "good"

def test_extra_pdf_x_group_unmatched(tmp_path) -> None:
    # 3. Extra PDF x group with no MusicXML onset -> unmatched x group / warning
    xml_path = tmp_path / "extra_pdf.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML.replace("<duration>1</duration>", "<duration>1</duration>").replace(
        """<note>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>""", ""
    ), encoding="utf-8")
    
    tabraw_path = tmp_path / "extra_pdf.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 200.0, "y": 60.0, "bbox": [200, 58, 205, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 2, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "extra_pdf.ir.json"
    diagnostics_path = tmp_path / "extra_pdf.diagnostics.json"
    
    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert diagnostics["pdf_timing_mapping"]["quality"] == "warning"
    assert "pdf_timing_mapping_x_group_unmatched" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert diagnostics["pdf_timing_mapping"]["unmatched_x_group_count"] == 1

def test_missing_pdf_x_group_unmatched(tmp_path) -> None:
    # 4. Missing PDF x group for a MusicXML onset -> unmatched onset group / warning
    xml_path = tmp_path / "missing_pdf.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "missing_pdf.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 60.0, "bbox": [300, 58, 305, 62]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "missing_pdf.ir.json"
    diagnostics_path = tmp_path / "missing_pdf.diagnostics.json"
    
    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert diagnostics["pdf_timing_mapping"]["quality"] == "warning"
    assert "pdf_timing_mapping_onset_group_unmatched" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert diagnostics["pdf_timing_mapping"]["unmatched_onset_group_count"] == 1

def test_non_monotonic_pdf_x_ordering_refused(tmp_path) -> None:
    # 5. Non-monotonic PDF x ordering -> refused
    xml_path = tmp_path / "non_monotonic.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "non_monotonic.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 200.0, "y": 60.0, "bbox": [200, 58, 205, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 2, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "non_monotonic.ir.json"
    diagnostics_path = tmp_path / "non_monotonic.diagnostics.json"
    
    with patch("score2gp.build_ir._is_monotonic", return_value=False):
        with pytest.raises(BuildIrInputRiskError) as raised:
            build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
            
    assert raised.value.category == "pdf_timing_mapping_non_monotonic"
    assert (tmp_path / "pdf-timing-mapping-diagnostics.html").exists()

def test_ambiguous_close_x_groups_flagged(tmp_path) -> None:
    # 6. Ambiguous close x groups -> ambiguous_x_group warning/warning quality
    xml_path = tmp_path / "ambiguous_close.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "ambiguous_close.tabraw.json"
    # x values at 100.0 and 104.0 are close -> ambiguous
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 104.0, "y": 60.0, "bbox": [104, 58, 109, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 2, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "ambiguous_close.ir.json"
    diagnostics_path = tmp_path / "ambiguous_close.diagnostics.json"
    
    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert diagnostics["pdf_timing_mapping"]["quality"] in {"warning", "poor"}
    assert "pdf_timing_mapping_ambiguous_x_group" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert diagnostics["pdf_timing_mapping"]["ambiguity_count"] == 1

def test_chord_stack_review_flagged(tmp_path) -> None:
    # 7. Chord stack at one onset -> chord-stack review flag
    xml_path = tmp_path / "chord_stack.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "chord_stack.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "3", "parsed_fret": 3, "string": 2, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 60.0, "bbox": [100, 58, 105, 62]},
        {"id": "c3", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 300.0, "y": 55.0, "bbox": [300, 53, 305, 57]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "chord_stack.ir.json"
    diagnostics_path = tmp_path / "chord_stack.diagnostics.json"
    
    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    
    assert "pdf_timing_mapping_chord_stack_requires_review" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert diagnostics["pdf_timing_mapping"]["per_bar"][0]["candidate_x_groups"][0]["is_chord_stack"] is True

def test_unsupported_polyphony_refused(tmp_path) -> None:
    # 8. Valid MusicXML timing but unsupported polyphony -> mapping refused/unsupported
    xml_path = tmp_path / "polyphony.musicxml"
    xml_path.write_text(POLYPHONY_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "polyphony.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]},
        {"id": "c2", "text": "0", "parsed_fret": 0, "string": 3, "system_index": 1, "bar_index": 1, "page": 1, "x": 200.0, "y": 60.0, "bbox": [200, 58, 205, 62]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "polyphony.ir.json"
    diagnostics_path = tmp_path / "polyphony.diagnostics.json"
    
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
        
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["pdf_timing_mapping"]["quality"] == "refused"
    assert "pdf_timing_mapping_polyphony_not_supported" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert (tmp_path / "pdf-timing-mapping-diagnostics.html").exists()

def test_unsafe_musicxml_timing_prevents_mapping(tmp_path) -> None:
    # 9. Unsafe MusicXML timing -> mapping not attempted
    xml_path = tmp_path / "unsafe_timing.musicxml"
    xml_path.write_text(OVERFULL_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "unsafe_timing.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]}
    ])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "unsafe_timing.ir.json"
    diagnostics_path = tmp_path / "unsafe_timing.diagnostics.json"
    
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
        
    assert raised.value.category == "musicxml_timing_risk"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["pdf_timing_mapping"]["quality"] == "refused"
    assert "pdf_timing_mapping_not_attempted_musicxml_unsafe" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert (tmp_path / "pdf-timing-mapping-diagnostics.html").exists()

def test_unsafe_pdf_grouping_prevents_mapping(tmp_path) -> None:
    # 10. Unsafe PDF grouping -> mapping not attempted
    xml_path = tmp_path / "unsafe_grouping.musicxml"
    xml_path.write_text(CLEAN_ONE_BAR_XML, encoding="utf-8")
    
    tabraw_path = tmp_path / "unsafe_grouping.tabraw.json"
    tabraw_data = make_tabraw([
        {"id": "c1", "text": "0", "parsed_fret": 0, "string": 1, "system_index": 1, "bar_index": 1, "page": 1, "x": 100.0, "y": 50.0, "bbox": [100, 48, 105, 52]}
    ], warnings=[{"code": "pdf_no_systems_detected", "message": "No systems", "severity": "error"}])
    tabraw_path.write_text(json.dumps(tabraw_data), encoding="utf-8")
    
    ir_path = tmp_path / "unsafe_grouping.ir.json"
    diagnostics_path = tmp_path / "unsafe_grouping.diagnostics.json"
    
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
        
    assert raised.value.category in ("missing_pdf_grouping", "partial_pdf_grouping")
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["pdf_timing_mapping"]["quality"] == "refused"
    assert "pdf_timing_mapping_not_attempted_grouping_unsafe" in diagnostics["pdf_timing_mapping"]["refusal_reason_codes"]
    assert (tmp_path / "pdf-timing-mapping-diagnostics.html").exists()
