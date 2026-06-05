from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.ascii_alignment import align_ascii_musicxml_files
from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.cli import app
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab

ASCII_GATE_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
ASCII_GATE_MUSICXML = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")
ASCII_BARRED_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_barred.pdf")
ASCII_NO_BARS_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_no_bars.pdf")
ASCII_UNEVEN_TIMING_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_uneven_timing.pdf")
COMPATIBLE_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_compatible.musicxml")
AMBIGUOUS_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_ambiguous.musicxml")
INCOMPATIBLE_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_incompatible.musicxml")
OVERFULL_MUSICXML = Path("tests/fixtures/musicxml/audiveris_like_overfull_bar.musicxml")


def _extract(pdf_path: Path, tmp_path: Path) -> Path:
    tabraw_path = tmp_path / f"{pdf_path.stem}.tabraw.json"
    extract_tab(pdf_path, tabraw_path)
    return tabraw_path


def _alignment_path(tabraw_path: Path, musicxml_path: Path, tmp_path: Path) -> Path:
    out_dir = tmp_path / f"{tabraw_path.stem}.alignment"
    align_ascii_musicxml_files(tabraw_path=tabraw_path, musicxml_path=musicxml_path, out_dir=out_dir)
    return out_dir / "ascii_musicxml_alignment.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ascii_fret_candidates(payload: dict) -> list[dict]:
    return [
        candidate
        for candidate in payload["candidates"]
        if candidate["raw"].get("parser_version") == "ascii-tab.v0.1"
        and candidate["kind"] == "fret"
    ]


def _assert_gate_refusal(
    error: BuildIrInputRiskError,
    expected_category: str,
    *,
    alignment_sidecar_present: bool = True,
    alignment_status: str | None = "compatible",
) -> None:
    details = error.details
    assert error.category == expected_category
    assert details["ascii_scoreir_gate_status"] == "refused"
    assert details["primary_reason_code"] == expected_category
    assert expected_category in details["reason_codes"]
    assert details["candidate_count"] >= 1
    assert details["rejected_candidate_count"] >= 0
    assert details["scoreir_written"] is False
    assert details["alignment_sidecar_present"] is alignment_sidecar_present
    assert details["alignment_status"] == alignment_status
    assert details["expected_next_remediation"]
    assert all(isinstance(candidate_id, str) for candidate_id in details["sample_candidate_ids"])


def test_tiny_compatible_ascii_gate_writes_valid_scoreir(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    ir_path = tmp_path / "ascii_gate.ir.json"
    diagnostics_path = tmp_path / "ascii_gate.diagnostics.json"

    score = build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, diagnostics_path, alignment_path)
    validated, errors = validate_score_ir_file(ir_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))

    assert errors == []
    assert validated is not None
    assert score.metadata.title == "ASCII ScoreIR Gate Simple"
    assert score.tempo.bpm == 84
    assert [[note.fret for event in bar.events for note in event.notes] for bar in score.bars] == [[0, 1, 2], [3]]
    assert [[note.string for event in bar.events for note in event.notes] for bar in score.bars] == [[1, 1, 1], [1]]
    assert [event.timing.duration_ticks for bar in score.bars for event in bar.events if event.notes] == [192, 384, 576, 768]
    assert [event.timing.onset_ticks for bar in score.bars for event in bar.events if event.notes] == [768, 1920, 3072, 768]
    assert all(
        note.provenance[-1].raw["alignment_strategy"] == "ascii-musicxml-alignment.v0.1"
        for bar in score.bars
        for event in bar.events
        for note in event.notes
    )
    assert diagnostics["ascii_scoreir_gate_status"] == "allowed"
    assert diagnostics["ascii_scoreir_gate_reason_codes"] == ["ascii_scoreir_gate_allowed"]
    assert diagnostics["ascii_scoreir_gate_primary_reason_code"] == "ascii_scoreir_gate_allowed"
    assert diagnostics["ascii_scoreir_gate_candidate_count"] == 4
    assert diagnostics["ascii_scoreir_gate_aligned_candidate_count"] == 4
    assert diagnostics["ascii_scoreir_gate_rejected_candidate_count"] == 0
    assert diagnostics["ascii_scoreir_gate_output_event_count"] == 6
    assert diagnostics["ascii_scoreir_gate_scoreir_written"] is True
    assert diagnostics["ascii_scoreir_gate_alignment_sidecar_present"] is True
    assert diagnostics["ascii_scoreir_gate_alignment_status"] == "compatible"
    assert diagnostics["ascii_scoreir_gate_musicxml_timing_safe"] is True
    assert diagnostics["ascii_scoreir_gate_expected_next_remediation"] == "none"


def test_ascii_gate_missing_alignment_sidecar_is_refused(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    ir_path = tmp_path / "ascii_gate_missing_alignment.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    _assert_gate_refusal(
        raised.value,
        "pdf_input_class_ascii_tab_requires_alignment",
        alignment_sidecar_present=False,
        alignment_status=None,
    )


@pytest.mark.parametrize(
    ("pdf_path", "musicxml_path", "expected_category", "alignment_status"),
    [
        (ASCII_NO_BARS_PDF, COMPATIBLE_MUSICXML, "ascii_alignment_status_unavailable", "unavailable"),
        (ASCII_UNEVEN_TIMING_PDF, AMBIGUOUS_MUSICXML, "ascii_alignment_status_ambiguous", "ambiguous"),
        (ASCII_BARRED_PDF, INCOMPATIBLE_MUSICXML, "ascii_alignment_status_incompatible", "incompatible"),
    ],
)
def test_ascii_gate_refuses_unsafe_alignment_sidecars(
    tmp_path,
    pdf_path: Path,
    musicxml_path: Path,
    expected_category: str,
    alignment_status: str,
) -> None:
    tabraw_path = _extract(pdf_path, tmp_path)
    alignment_path = _alignment_path(tabraw_path, musicxml_path, tmp_path)
    ir_path = tmp_path / "unsafe_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(musicxml_path, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, expected_category, alignment_status=alignment_status)


def test_ascii_gate_refuses_partial_alignment_sidecar(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(alignment_path)
    payload["overall_status"] = "partial"
    _write_json(alignment_path, payload)
    ir_path = tmp_path / "partial_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_alignment_status_partial", alignment_status="partial")


def test_ascii_gate_refuses_compatible_sidecar_when_inline_technique_is_present(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(tabraw_path)
    payload["candidates"].append(
        {
            "id": "public-ascii-technique-marker",
            "kind": "technique-text",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bar_index": None,
            "line_index": 1,
            "string": None,
            "raw_text": "h",
            "parsed_fret": None,
            "x": 120.0,
            "y": 100.0,
            "bbox": {"page": 1, "x0": 118.0, "y0": 96.0, "x1": 122.0, "y1": 104.0},
            "confidence": 0.6,
            "source_stage": "pdf-text",
            "raw": {"parser_version": "ascii-tab.v0.1", "technique_context": "ascii-inline-marker"},
        }
    )
    _write_json(tabraw_path, payload)
    ir_path = tmp_path / "technique_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_unsupported_technique_required")


def test_ascii_gate_refuses_compatible_sidecar_when_chord_symbol_is_present(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(tabraw_path)
    payload["candidates"].append(
        {
            "id": "public-ascii-chord-symbol",
            "kind": "chord-symbol",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bar_index": None,
            "line_index": None,
            "string": None,
            "raw_text": "G7",
            "parsed_fret": None,
            "x": 120.0,
            "y": 80.0,
            "bbox": {"page": 1, "x0": 116.0, "y0": 76.0, "x1": 124.0, "y1": 84.0},
            "confidence": 0.7,
            "source_stage": "pdf-text",
            "raw": {"parser_version": "ascii-tab.v0.1"},
        }
    )
    _write_json(tabraw_path, payload)
    ir_path = tmp_path / "chord_symbol_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_unsupported_chord_symbol")


def test_ascii_gate_refuses_candidate_missing_from_alignment_sidecar(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(alignment_path)
    payload["candidate_mappings"] = payload["candidate_mappings"][1:]
    payload["summary_counts"]["compatible_mappings"] -= 1
    _write_json(alignment_path, payload)
    ir_path = tmp_path / "missing_alignment_candidate.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_alignment_candidate_missing")


def test_ascii_gate_refuses_non_one_to_one_candidate_mapping(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(alignment_path)
    payload["candidate_mappings"][0]["nearest_musicxml_note_ids"] = [
        payload["candidate_mappings"][0]["nearest_musicxml_note_ids"][0],
        payload["candidate_mappings"][1]["nearest_musicxml_note_ids"][0],
    ]
    _write_json(alignment_path, payload)
    ir_path = tmp_path / "not_one_to_one_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_alignment_not_one_to_one")


def test_ascii_gate_refuses_missing_string_evidence(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(tabraw_path)
    _ascii_fret_candidates(payload)[0]["string"] = None
    _write_json(tabraw_path, payload)
    ir_path = tmp_path / "missing_string_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_candidate_missing_string")


def test_ascii_gate_refuses_missing_fret_evidence(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(tabraw_path)
    _ascii_fret_candidates(payload)[0]["parsed_fret"] = None
    _write_json(tabraw_path, payload)
    ir_path = tmp_path / "missing_fret_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_candidate_missing_fret")


def test_ascii_gate_refuses_unmapped_measure(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(alignment_path)
    payload["candidate_mappings"][0]["musicxml_measure_index"] = None
    _write_json(alignment_path, payload)
    ir_path = tmp_path / "unmapped_measure_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_candidate_unmapped_measure")


def test_ascii_gate_refuses_unmapped_onset(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(alignment_path)
    payload["candidate_mappings"][0]["nearest_musicxml_onset_ticks"] = None
    _write_json(alignment_path, payload)
    ir_path = tmp_path / "unmapped_onset_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_candidate_unmapped_onset")


def test_ascii_gate_refuses_missing_musicxml_duration_source(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    risky_musicxml = tmp_path / "missing-duration-source.musicxml"
    risky_musicxml.write_text(
        ASCII_GATE_MUSICXML.read_text(encoding="utf-8").replace("<duration>2</duration>", "<duration>0</duration>", 1),
        encoding="utf-8",
    )
    ir_path = tmp_path / "missing_duration_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(risky_musicxml, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_duration_source_missing")


def test_ascii_gate_refuses_musicxml_timing_risk_before_output(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, OVERFULL_MUSICXML, tmp_path)
    ir_path = tmp_path / "timing_risk_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(OVERFULL_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    _assert_gate_refusal(raised.value, "ascii_musicxml_timing_risk", alignment_status="unavailable")


def test_cli_failure_diagnostics_include_ascii_gate_refusal_taxonomy(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = _load_json(tabraw_path)
    payload["candidates"].append(
        {
            "id": "public-ascii-cli-technique-marker",
            "kind": "technique-text",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bar_index": None,
            "line_index": 1,
            "string": None,
            "raw_text": "/",
            "parsed_fret": None,
            "x": 130.0,
            "y": 100.0,
            "bbox": {"page": 1, "x0": 128.0, "y0": 96.0, "x1": 132.0, "y1": 104.0},
            "confidence": 0.6,
            "source_stage": "pdf-text",
            "raw": {"parser_version": "ascii-tab.v0.1", "technique_context": "ascii-inline-marker"},
        }
    )
    _write_json(tabraw_path, payload)
    ir_path = tmp_path / "cli_refusal.ir.json"
    diagnostics_path = tmp_path / "cli_refusal.diagnostics.json"

    result = CliRunner().invoke(
        app,
        [
            "build-ir",
            "--musicxml",
            str(ASCII_GATE_MUSICXML),
            "--tabraw",
            str(tabraw_path),
            "--ascii-alignment",
            str(alignment_path),
            "--out",
            str(ir_path),
            "--diagnostics-out",
            str(diagnostics_path),
        ],
    )

    diagnostics = _load_json(diagnostics_path)
    assert result.exit_code == 1
    assert not ir_path.exists()
    assert diagnostics["category"] == "ascii_unsupported_technique_required"
    assert diagnostics["details"]["primary_reason_code"] == "ascii_unsupported_technique_required"
    assert diagnostics["details"]["candidate_count"] == 4
    assert diagnostics["details"]["aligned_candidate_count"] == 4
    assert diagnostics["details"]["scoreir_written"] is False
    assert diagnostics["details"]["expected_next_remediation"]

    html_path = tmp_path / "ascii-scoreir-gate-diagnostics.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "ASCII ScoreIR Gate Refusal Diagnostics" in html_content
    assert "ascii_unsupported_technique_required" in html_content


def test_ascii_gate_refusal_writes_html_diagnostics_report(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    ir_path = tmp_path / "refusal_writes_html.ir.json"
    diagnostics_path = tmp_path / "refusal_writes_html.diagnostics.json"
    html_path = tmp_path / "ascii-scoreir-gate-diagnostics.html"

    with pytest.raises(BuildIrInputRiskError):
        build_ir_from_files(
            ASCII_GATE_MUSICXML,
            tabraw_path,
            ir_path,
            diagnostics_out_path=diagnostics_path,
        )

    assert not ir_path.exists()
    assert diagnostics_path.exists()
    assert html_path.exists()

    html_content = html_path.read_text(encoding="utf-8")

    # 1. Title identifying the failure as ASCII ScoreIR gate refusal
    assert "ASCII ScoreIR Gate Refusal Diagnostics" in html_content

    # 2. Gate status
    assert "Refused" in html_content

    # 3. Primary refusal reason
    assert "pdf_input_class_ascii_tab_requires_alignment" in html_content

    # 4. Secondary refusal reasons, or explicitly says none
    assert "None" in html_content or "secondary_reason_codes" in html_content

    # 5. Candidate/alignment/rejected counts
    assert "Total Candidates" in html_content
    assert "Aligned Candidates" in html_content
    assert "Rejected Candidates" in html_content

    # 6. Remediation hints
    assert "provide compatible ascii-musicxml-alignment.v0.1 evidence" in html_content

    # 7. States whether ScoreIR was written
    assert "ScoreIR Written" in html_content
    assert "False" in html_content

    # 8. Links or references the JSON diagnostics sidecar where practical
    assert "refusal_writes_html.diagnostics.json" in html_content

    # 9. Expected statement that refusal is expected for unsupported ASCII inputs
    assert "Refusal is expected behavior for unsupported ASCII inputs" in html_content
