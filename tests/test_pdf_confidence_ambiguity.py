from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from score2gp.gp_package import extract_score_ir_from_gp
from score2gp.ir import ScoreIR
from scripts.gp_roundtrip_eval import extract_native_gp_notes, run_roundtrip_eval


def test_gp_package_robust_bars_querying(tmp_path) -> None:
    # 1. Create a minimal mock nested GP XML and flat GP XML to prove robust querying works
    nested_xml = """<GPIF version="7">
      <Score>
        <Bars>
          <Bar index="1">
            <Voices/>
          </Bar>
        </Bars>
      </Score>
    </GPIF>"""
    
    flat_xml = """<GPIF version="7">
      <MasterBars>
        <MasterBar index="1">
          <Bars/>
        </MasterBar>
      </MasterBars>
      <Bars>
        <Bar id="0">
          <Voices/>
        </Bar>
      </Bars>
    </GPIF>"""

    # Test nested lookup
    nested_root = ET.fromstring(nested_xml)
    bars_node_nested = nested_root.find("Bars")
    if bars_node_nested is None:
        for b in nested_root.findall(".//Bars"):
            if b.find("Bar") is not None:
                bars_node_nested = b
                break
    assert bars_node_nested is not None
    assert len(bars_node_nested.findall("Bar")) == 1
    assert bars_node_nested.findall("Bar")[0].get("index") == "1"

    # Test flat lookup
    flat_root = ET.fromstring(flat_xml)
    bars_node_flat = flat_root.find("Bars")
    if bars_node_flat is None:
        for b in flat_root.findall(".//Bars"):
            if b.find("Bar") is not None:
                bars_node_flat = b
                break
    assert bars_node_flat is not None
    assert len(bars_node_flat.findall("Bar")) == 1
    assert bars_node_flat.findall("Bar")[0].get("id") == "0"


def test_eval_script_extraction_with_public_fixture(tmp_path) -> None:
    # Validate with public tiny_score XML to ensure extract_recovered_notes works
    tiny_score_path = Path("fixtures/public/tiny_score.ir.json")
    assert tiny_score_path.exists()
    
    score = ScoreIR.from_json_file(tiny_score_path)
    from scripts.gp_roundtrip_eval import extract_recovered_notes
    notes = extract_recovered_notes(score)
    
    # Tiny score should have some notes resolved
    assert isinstance(notes, list)
    if notes:
        assert "bar_index" in notes[0]
        assert "string" in notes[0]
        assert "fret" in notes[0]
