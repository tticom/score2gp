from __future__ import annotations

import xml.etree.ElementTree as ET
from score2gp.gp_package import _summarize_gpif
from scripts.private_gp_quality_audit import classify_gp_quality


def test_parser_ignores_automation_bar_tags() -> None:
    # Test 1: Parser ignores automation Bar tags for musical bar count
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Bars>
      <Bar />
      <Bar />
      <Bar />
      <Bar />
    </Bars>
    <Automation>
      <Bar />
      <Bar />
      <Bar />
      <Bar />
    </Automation>
  </Score>
</GPIF>
"""
    root = ET.fromstring(xml_content.encode("utf-8"))
    summary = _summarize_gpif(root)

    assert summary["raw_bar_tag_count"] == 8
    assert summary["musical_track_bar_count"] == 4
    assert summary["automation_bar_tag_count"] == 4
    assert summary["bar_count"] == 4
    assert summary["bar_count_source"] == "track_bars"
    assert summary["gpif_bar_count_fallback_used"] is False


def test_raw_plus_4_automation_overcount_no_suspect() -> None:
    # Test 2: Raw +4 automation overcount no longer creates alignment suspect
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 4,
        "raw_bar_tag_count": 8,
        "musical_track_bar_count": 4,
        "automation_bar_tag_count": 4,
        "template_prelude_bar_count": 0,
        "scoreir_note_count": 20,
        "gpif_note_count": 20,
        "playable_fret_candidate_count": 20,
        "matched_fret_candidate_count": 20,
    }
    
    classification = classify_gp_quality(metrics)
    assert metrics["bar_alignment_status"] == "aligned"
    assert classification != "gp_output_bar_alignment_suspect"
    assert classification == "gp_output_quality_pass_basic"


def test_raw_plus_4_mismatch_without_automation_is_suspect() -> None:
    # Test 3: Raw +4 mismatch without automation or template evidence remains suspect
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 4,
        "raw_bar_tag_count": 8,
        "musical_track_bar_count": 8,
        "automation_bar_tag_count": 0,
        "template_prelude_bar_count": 0,
        "scoreir_note_count": 20,
        "gpif_note_count": 20,
        "playable_fret_candidate_count": 20,
        "matched_fret_candidate_count": 20,
    }
    
    classification = classify_gp_quality(metrics)
    assert metrics["bar_alignment_status"] == "mismatch"
    assert classification == "gp_output_bar_alignment_suspect"


def test_explicit_template_prelude_track_bars_accounted() -> None:
    # Test 4: Explicit template prelude track bars are accounted for
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 24,
        "musical_track_bar_count": 28,
        "template_prelude_bar_count": 4,
        "gpif_note_count": 100,
        "scoreir_note_count": 100,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 100,
    }
    
    classification = classify_gp_quality(metrics)
    assert metrics["bar_alignment_status"] == "expected_template_bars_accounted"
    assert classification != "gp_output_bar_alignment_suspect"
    assert classification == "gp_output_expected_template_bars_accounted"


def test_claimed_template_bars_with_notes_remain_suspect() -> None:
    # Test 5: Claimed template bars with note content remain suspect
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 24,
        "musical_track_bar_count": 28,
        "template_prelude_bar_count": 4,
        "template_prelude_note_count": 1,
        "gpif_note_count": 100,
        "scoreir_note_count": 100,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 100,
    }
    
    classification = classify_gp_quality(metrics)
    assert classification == "gp_output_bar_alignment_suspect"


def test_fewer_musical_gpif_bars_than_scoreir_remains_suspect() -> None:
    # Test 6: Fewer musical GPIF bars than ScoreIR remains suspect
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 24,
        "musical_track_bar_count": 23,
        "template_prelude_bar_count": 0,
        "gpif_note_count": 100,
        "scoreir_note_count": 100,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 100,
    }
    
    classification = classify_gp_quality(metrics)
    assert classification == "gp_output_bar_alignment_suspect"


def test_technique_loss_reached_only_after_alignment_passes() -> None:
    # Test 7: Technique loss is only reached after bar alignment passes
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 24,
        "musical_track_bar_count": 24,
        "scoreir_note_count": 100,
        "gpif_note_count": 100,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 100,
        "non_playable_technique_text_candidate_count": 20,
    }
    
    classification = classify_gp_quality(metrics)
    assert classification == "gp_output_technique_loss_expected"


def test_low_serialized_note_coverage_beats_bar_success() -> None:
    # Test 8: Low serialized note coverage beats bar success
    metrics = {
        "whether_gp_package_produced": True,
        "scoreir_bar_count": 24,
        "musical_track_bar_count": 24,
        "scoreir_note_count": 100,
        "gpif_note_count": 30,
        "playable_fret_candidate_count": 100,
        "matched_fret_candidate_count": 100,
    }
    
    classification = classify_gp_quality(metrics)
    assert classification == "gp_output_note_coverage_low"
