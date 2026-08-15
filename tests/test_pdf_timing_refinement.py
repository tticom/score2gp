from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.musicxml import analyze_musicxml_timing, parse_musicxml


FIXTURES = Path("tests/fixtures/musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")

THREE_EVENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>3</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>B</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
    </measure>
  </part>
</score-partwise>
"""


def _tabraw(items: list[dict[str, object]], warnings: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "synthetic-timing-refinement.pdf",
        "inspection_kind": "born-digital",
        "items": items,
        "warnings": warnings or [],
    }


def _candidate(candidate_id: str, x: float, string: int = 1, fret: int = 0) -> dict[str, object]:
    return {
        "id": candidate_id,
        "text": str(fret),
        "parsed_fret": fret,
        "string": string,
        "system_index": 1,
        "bar_index": 1,
        "page": 1,
        "x": x,
        "y": 50.0 + string,
        "bbox": [x, 48.0 + string, x + 5.0, 52.0 + string],
    }


def _write_pair(tmp_path: Path, candidates: list[dict[str, object]]) -> tuple[Path, Path, Path, Path]:
    xml_path = tmp_path / "timing_refinement.musicxml"
    tabraw_path = tmp_path / "timing_refinement.tabraw.json"
    ir_path = tmp_path / "timing_refinement.ir.json"
    diagnostics_path = tmp_path / "timing_refinement.diagnostics.json"
    xml_path.write_text(THREE_EVENT_XML, encoding="utf-8")
    tabraw_path.write_text(json.dumps(_tabraw(candidates)), encoding="utf-8")
    return xml_path, tabraw_path, ir_path, diagnostics_path


def _failure_payload(tmp_path: Path, musicxml_name: str) -> dict[str, object]:
    diagnostics_path = tmp_path / f"{musicxml_name}.diagnostics.json"
    with pytest.raises(BuildIrInputRiskError):
        build_ir_from_files(FIXTURES / musicxml_name, TABRAW, tmp_path / f"{musicxml_name}.ir.json", diagnostics_path)
    return json.loads(diagnostics_path.read_text(encoding="utf-8"))


def test_timing_refinement_keeps_valid_chord_stack_out_of_overlap_bucket() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_chord_stack.musicxml")
    issues = analyze_musicxml_timing(imported)

    assert any(issue.code == "musicxml_chord_stack_detected" and issue.severity == "info" for issue in issues)
    assert any(issue.code == "musicxml_chord_stack_not_timing_overlap" for issue in issues)
    assert not any(issue.code in {"musicxml-voice-overlap", "musicxml_same_voice_tick_overlap"} for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("timing_vc_invalid_same_voice.musicxml", "musicxml-voice-overlap"),
        ("timing_vc_rest_overlap.musicxml", "musicxml_rest_overlap"),
        ("timing_overfull_measure.musicxml", "musicxml-overfull-bar"),
    ],
)
def test_invalid_timing_refinement_summary_refuses_without_repair(
    tmp_path: Path,
    fixture_name: str,
    expected_code: str,
) -> None:
    payload = _failure_payload(tmp_path, fixture_name)
    summary = payload["musicxml_timing_refinement"]

    assert payload["category"] == "musicxml_timing_risk"
    assert summary["contract_version"] == "pdf-timing-refinement.v1.0"
    assert summary["timing_classification"] == "invalid_timing_refused"
    assert summary["invalid_timing_issue_count"] > 0
    assert summary["automatic_repair_attempted"] is False
    assert expected_code in summary["issue_counts"]


def test_valid_multivoice_polyphony_refinement_summary_is_unsupported_not_invalid(tmp_path: Path) -> None:
    payload = _failure_payload(tmp_path, "timing_vc_valid_two_voice.musicxml")
    summary = payload["musicxml_timing_refinement"]

    assert payload["category"] == "musicxml_scoreir_polyphony_gate_refused"
    assert summary["timing_classification"] == "unsupported_polyphony_refused"
    assert summary["unsupported_polyphony_issue_count"] > 0
    assert summary["invalid_timing_issue_count"] == 0
    assert "musicxml_valid_multivoice_unsupported" in summary["issue_counts"]


def test_underfull_measure_remains_warning_only() -> None:
    imported = parse_musicxml(FIXTURES / "timing_underfull_measure.musicxml")
    issues = analyze_musicxml_timing(imported)

    assert any(issue.code == "musicxml-underfull-bar" and issue.severity == "warning" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)


def test_pdf_timing_refinement_classifies_safe_layout_evidence(tmp_path: Path) -> None:
    xml_path, tabraw_path, ir_path, diagnostics_path = _write_pair(
        tmp_path,
        [_candidate("c1", 100.0, 1), _candidate("c2", 200.0, 2), _candidate("c3", 300.0, 3)],
    )

    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    mapping = diagnostics["pdf_timing_mapping"]

    assert mapping["refinement_contract_version"] == "pdf-timing-refinement.v1.0"
    assert mapping["mapping_quality_classification"] == "safe"
    assert mapping["safe_layout_evidence"] is True
    assert "pdf_timing_refinement_safe_layout_evidence" in mapping["refinement_reason_codes"]


def test_pdf_timing_refinement_classifies_partial_layout_evidence(tmp_path: Path) -> None:
    xml_path, tabraw_path, ir_path, diagnostics_path = _write_pair(
        tmp_path,
        [
            _candidate("c1", 100.0, 1),
            _candidate("c2", 200.0, 2),
            _candidate("c3", 300.0, 3),
            _candidate("c4", 400.0, 4),
        ],
    )

    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    mapping = json.loads(diagnostics_path.read_text(encoding="utf-8"))["pdf_timing_mapping"]

    assert mapping["mapping_quality_classification"] == "partial"
    assert mapping["partial_layout_evidence"] is True
    assert mapping["unmatched_x_group_count"] == 1
    assert "pdf_timing_refinement_partial_layout_evidence" in mapping["refinement_reason_codes"]


def test_pdf_timing_refinement_classifies_ambiguous_layout_evidence(tmp_path: Path) -> None:
    xml_path, tabraw_path, ir_path, diagnostics_path = _write_pair(
        tmp_path,
        [_candidate("c1", 100.0, 1), _candidate("c2", 104.0, 2), _candidate("c3", 108.0, 3)],
    )

    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    mapping = json.loads(diagnostics_path.read_text(encoding="utf-8"))["pdf_timing_mapping"]

    assert mapping["mapping_quality_classification"] == "ambiguous"
    assert mapping["ambiguous_layout_evidence"] is True
    assert mapping["ambiguity_count"] > 0
    assert "pdf_timing_refinement_ambiguous_layout_evidence" in mapping["refinement_reason_codes"]


def test_pdf_timing_refinement_classifies_non_monotonic_layout_as_incompatible(tmp_path: Path) -> None:
    xml_path, tabraw_path, ir_path, diagnostics_path = _write_pair(
        tmp_path,
        [_candidate("c1", 100.0, 1), _candidate("c2", 200.0, 2), _candidate("c3", 300.0, 3)],
    )

    with patch("score2gp.build_ir._is_monotonic", return_value=False):
        with pytest.raises(BuildIrInputRiskError):
            build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)

    mapping = json.loads(diagnostics_path.read_text(encoding="utf-8"))["pdf_timing_mapping"]
    assert mapping["mapping_quality_classification"] == "incompatible"
    assert mapping["incompatible_layout_evidence"] is True
    assert mapping["whether_mapping_refused"] is True
    assert mapping["whether_scoreir_written"] is False
    assert "pdf_timing_refinement_incompatible_layout_evidence" in mapping["refinement_reason_codes"]


def test_pdf_timing_refinement_html_explains_classification(tmp_path: Path) -> None:
    xml_path, tabraw_path, ir_path, diagnostics_path = _write_pair(
        tmp_path,
        [_candidate("c1", 100.0, 1), _candidate("c2", 104.0, 2), _candidate("c3", 108.0, 3)],
    )

    build_ir_from_files(xml_path, tabraw_path, ir_path, diagnostics_path)
    html_path = tmp_path / "pdf-timing-mapping-diagnostics.html"
    html = html_path.read_text(encoding="utf-8")

    assert "pdf-timing-refinement.v1.0" in html
    assert "Timing Refinement Classification" in html
    assert "ambiguous" in html
    assert "pdf_timing_refinement_ambiguous_layout_evidence" in html
