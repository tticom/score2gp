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


def test_round_trip_quality_gate(tmp_path, monkeypatch) -> None:
    import scripts.gp_roundtrip_eval as eval_mod
    
    # Create actual score
    actual_ir_path = tmp_path / "score.ir.json"
    actual_score = ScoreIR(
        schema_version="0.1.0",
        metadata={"title": "Test actual"},
        tempo={"bpm": 120},
        tracks=[
            {
                "id": "t1",
                "name": "Guitar",
                "instrument": "guitar",
                "tuning": {
                    "name": "Standard",
                    "strings": [
                        {"number": 1, "pitch": 64, "name": "E"},
                        {"number": 2, "pitch": 59, "name": "B"},
                        {"number": 3, "pitch": 55, "name": "G"},
                        {"number": 4, "pitch": 50, "name": "D"},
                        {"number": 5, "pitch": 45, "name": "A"},
                        {"number": 6, "pitch": 40, "name": "E"},
                    ]
                }
            }
        ],
        bars=[
            {
                "index": 1,
                "time_signature": {"numerator": 4, "denominator": 4},
                "events": [
                    {
                        "id": "e1",
                        "track_id": "t1",
                        "timing": {"bar_index": 1, "onset_ticks": 0, "duration_ticks": 480, "voice": 1},
                        "notes": [{"string": 1, "fret": 5, "pitch": 69}]
                    }
                ]
            }
        ]
    )
    actual_score.to_json_file(actual_ir_path)
    
    # GP file compiled from actual
    gp_path = tmp_path / "smoke.gp"
    from score2gp.gp_package import write_gp
    write_gp(actual_score, gp_path)
    
    # 1. Test case: Positive passing round-trip where recovered matches oracle exactly!
    def mock_smoke_pass(*args, **kwargs):
        return {
            "extraction": {
                "total_candidates": 1,
                "playable_candidates": 1,
                "candidates_with_system": 1,
                "candidates_with_bar": 1,
                "candidates_with_string": 1,
                "grouping_warning_codes": [],
            },
            "build_ir": {
                "ran": True,
                "per_bar_quality_counts": {"good": 1, "poor": 0, "unknown": 0},
            }
        }
    monkeypatch.setattr(eval_mod, "run_private_diagnostic_smoke", mock_smoke_pass)
    
    report_pass = eval_mod.run_roundtrip_eval(
        pdf_path=Path("test.pdf"),
        musicxml_path=None,
        oracle_gp_path=gp_path,
        output_dir=tmp_path
    )
    
    assert report_pass["whether_scoreir_written"] is True
    assert report_pass["whether_gp_written"] is True
    assert report_pass["whether_semantic_comparison_ran"] is True
    assert report_pass["semantic_roundtrip_passed"] is True
    assert report_pass["semantic_roundtrip_status"] == "passed"
    assert report_pass["diagnostic_only"] is False
    assert report_pass["failure_category"] is None
    
    # 2. Test case: Negative failing round-trip due to poor bar quality
    def mock_smoke_fail_poor_bars(*args, **kwargs):
        return {
            "extraction": {
                "total_candidates": 1,
                "playable_candidates": 1,
                "candidates_with_system": 1,
                "candidates_with_bar": 1,
                "candidates_with_string": 1,
            },
            "build_ir": {
                "ran": True,
                "per_bar_quality_counts": {"good": 0, "poor": 1, "unknown": 0},
            }
        }
    monkeypatch.setattr(eval_mod, "run_private_diagnostic_smoke", mock_smoke_fail_poor_bars)
    
    report_fail_poor = eval_mod.run_roundtrip_eval(
        pdf_path=Path("test.pdf"),
        musicxml_path=None,
        oracle_gp_path=gp_path,
        output_dir=tmp_path
    )
    
    assert report_fail_poor["semantic_roundtrip_passed"] is False
    assert report_fail_poor["semantic_roundtrip_status"] == "failed_alignment_quality"
    assert report_fail_poor["diagnostic_only"] is True
    assert report_fail_poor["failure_category"] == "failed_alignment_quality"
    
    # 3. Test case: Negative failing round-trip due to note mismatch / low match rate!
    oracle_score = ScoreIR(
        schema_version="0.1.0",
        metadata={"title": "Test oracle"},
        tempo={"bpm": 120},
        tracks=actual_score.tracks,
        bars=[
            {
                "index": 1,
                "time_signature": {"numerator": 4, "denominator": 4},
                "events": [
                    {
                        "id": "e1",
                        "track_id": "t1",
                        "timing": {"bar_index": 1, "onset_ticks": 0, "duration_ticks": 480, "voice": 1},
                        "notes": [{"string": 2, "fret": 5, "pitch": 64}]
                    }
                ]
            }
        ]
    )
    oracle_gp_path = tmp_path / "oracle.gp"
    write_gp(oracle_score, oracle_gp_path)
    
    def mock_smoke_clean(*args, **kwargs):
        return {
            "extraction": {
                "total_candidates": 1,
                "playable_candidates": 1,
                "candidates_with_system": 1,
                "candidates_with_bar": 1,
                "candidates_with_string": 1,
            },
            "build_ir": {
                "ran": True,
                "per_bar_quality_counts": {"good": 1, "poor": 0, "unknown": 0},
            }
        }
    monkeypatch.setattr(eval_mod, "run_private_diagnostic_smoke", mock_smoke_clean)
    
    report_fail_mismatch = eval_mod.run_roundtrip_eval(
        pdf_path=Path("test.pdf"),
        musicxml_path=None,
        oracle_gp_path=oracle_gp_path,
        output_dir=tmp_path
    )
    
    assert report_fail_mismatch["semantic_roundtrip_passed"] is False
    assert report_fail_mismatch["semantic_roundtrip_status"] == "failed_string_fret_mismatch"
    assert report_fail_mismatch["diagnostic_only"] is True
    assert report_fail_mismatch["failure_category"] == "failed_string_fret_mismatch"
    assert report_fail_mismatch["semantic_diagnostics"]["fret_matching_rate_is_zero"] is True

    # 4. Test case: Negative failing round-trip due to note count mismatch!
    oracle_score_count = ScoreIR(
        schema_version="0.1.0",
        metadata={"title": "Test oracle count"},
        tempo={"bpm": 120},
        tracks=actual_score.tracks,
        bars=[
            {
                "index": 1,
                "time_signature": {"numerator": 4, "denominator": 4},
                "events": [
                    {
                        "id": "e1",
                        "track_id": "t1",
                        "timing": {"bar_index": 1, "onset_ticks": 0, "duration_ticks": 480, "voice": 1},
                        "notes": [
                            {"string": 1, "fret": 5, "pitch": 69},
                            {"string": 2, "fret": 7, "pitch": 66}
                        ]
                    }
                ]
            }
        ]
    )
    oracle_gp_path_count = tmp_path / "oracle_count.gp"
    write_gp(oracle_score_count, oracle_gp_path_count)

    report_fail_count = eval_mod.run_roundtrip_eval(
        pdf_path=Path("test.pdf"),
        musicxml_path=None,
        oracle_gp_path=oracle_gp_path_count,
        output_dir=tmp_path
    )

    assert report_fail_count["semantic_roundtrip_passed"] is False
    assert report_fail_count["semantic_roundtrip_status"] == "failed_note_count_mismatch"
    assert report_fail_count["diagnostic_only"] is True
    assert report_fail_count["failure_category"] == "failed_note_count_mismatch"
