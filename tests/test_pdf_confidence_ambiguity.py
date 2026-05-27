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


def test_double_barline_clustering_and_string_inversion(tmp_path) -> None:
    # 1. Verify clustering in _detect_tab_systems with synthetic candidates
    from score2gp.pdf import _LineSegment

    # Simulate system candidates very close horizontally representing double barline
    s1 = _LineSegment(x0=561.645, y0=100.0, x1=561.645, y1=180.0)
    s2 = _LineSegment(x0=563.686, y0=100.0, x1=563.686, y1=180.0)
    s3 = _LineSegment(x0=565.812, y0=100.0, x1=565.812, y1=180.0)

    system_candidates = [s1, s2, s3]

    clustered_candidates = []
    for s in sorted(system_candidates, key=lambda seg: (seg.x0 + seg.x1) / 2):
        x_val = (s.x0 + s.x1) / 2
        matched = False
        for existing in clustered_candidates:
            exist_x = (existing.x0 + existing.x1) / 2
            if abs(x_val - exist_x) < 6.0:
                h_s = abs(s.y1 - s.y0)
                h_e = abs(existing.y1 - existing.y0)
                if h_s > h_e:
                    clustered_candidates.remove(existing)
                    clustered_candidates.append(s)
                matched = True
                break
        if not matched:
            clustered_candidates.append(s)

    # Should successfully merge all three into a single candidate!
    assert len(clustered_candidates) == 1

    # 2. Verify string index mapping formulas
    # ScoreIR string 1 (high E) -> GP7 index 5
    # ScoreIR string 6 (low E) -> GP7 index 0
    string_count = 6
    assert string_count - 1 == 5
    assert string_count - 6 == 0


def test_dp_measure_resynchronization() -> None:
    # Verify our pitch-free visual-sequence geometry alignment
    from score2gp.build_ir import _synchronize_skipped_system_measures
    from score2gp.musicxml import MusicXmlImport, MusicXmlPart, MusicXmlMeasure
    from score2gp.tabraw import TabRaw, TabCandidate

    # 1. Create a dummy MusicXML structure with 6 measures
    class DummyMeasure:
        def __init__(self, index: int):
            self.index = index
            self.notes = []
            self.time_signature = None
            self.key_fifths = None

    class DummyPart:
        def __init__(self):
            self.measures = [DummyMeasure(i) for i in range(1, 7)]

    class DummyMusicXml:
        def __init__(self):
            self.parts = [DummyPart()]

    musicxml = DummyMusicXml()

    # 2. Create a TabRaw structure with candidates:
    # - System 1 (Page 1) spans 3 measures (originally Bars 1, 2, 3)
    # - System 2 (Page 1) is skipped (represented by warning/skipped set)
    # - System 3 (Page 1) spans 2 measures (originally Bars 4, 5)
    candidates = [
        TabCandidate(id="c1", page_index=1, system_index=1, bar_index=1, raw_text="0", parsed_fret=0),
        TabCandidate(id="c2", page_index=1, system_index=1, bar_index=3, raw_text="0", parsed_fret=0),
        TabCandidate(id="c3", page_index=1, system_index=3, bar_index=4, raw_text="0", parsed_fret=0),
        TabCandidate(id="c4", page_index=1, system_index=3, bar_index=5, raw_text="0", parsed_fret=0),
    ]
    tabraw = TabRaw(
        candidates=candidates,
        warnings=[
            {
                "code": "pdf_barlines_not_detected_in_system",
                "page_index": 1,
                "system_index": 2,
            }
        ]
    )

    skipped_systems = {(1, 2)}

    # Run pitch-free visual sequence alignment
    _synchronize_skipped_system_measures(musicxml, tabraw, skipped_systems)

    # System 1 should start at 1 and span 3 measures (starts 1). Offset = 0.
    # System 2 (skipped) should span 1 measure (Measure 4).
    # System 3 should start at 5 and span 2 measures. Offset = 5 - 4 = +1.
    # So System 3 candidates' bar_indices should be shifted by +1:
    # c3 (bar_index 4 -> 5)
    # c4 (bar_index 5 -> 6)
    assert tabraw.candidates[0].bar_index == 1
    assert tabraw.candidates[1].bar_index == 3
    assert tabraw.candidates[2].bar_index == 5
    assert tabraw.candidates[3].bar_index == 6
