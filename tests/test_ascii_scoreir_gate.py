from __future__ import annotations

import json
from pathlib import Path

import pytest

from score2gp.ascii_alignment import align_ascii_musicxml_files
from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
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
    assert diagnostics["ascii_scoreir_gate_candidate_count"] == 4
    assert diagnostics["ascii_scoreir_gate_aligned_candidate_count"] == 4
    assert diagnostics["ascii_scoreir_gate_output_event_count"] == 6
    assert diagnostics["ascii_scoreir_gate_scoreir_written"] is True


def test_ascii_gate_missing_alignment_sidecar_is_refused(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    ir_path = tmp_path / "ascii_gate_missing_alignment.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "partial_ascii_tab_timing"


@pytest.mark.parametrize(
    ("pdf_path", "musicxml_path", "expected_category"),
    [
        (ASCII_NO_BARS_PDF, COMPATIBLE_MUSICXML, "ascii_musicxml_alignment_unavailable"),
        (ASCII_UNEVEN_TIMING_PDF, AMBIGUOUS_MUSICXML, "ascii_musicxml_alignment_ambiguous"),
        (ASCII_BARRED_PDF, INCOMPATIBLE_MUSICXML, "ascii_musicxml_alignment_incompatible"),
    ],
)
def test_ascii_gate_refuses_unsafe_alignment_sidecars(tmp_path, pdf_path: Path, musicxml_path: Path, expected_category: str) -> None:
    tabraw_path = _extract(pdf_path, tmp_path)
    alignment_path = _alignment_path(tabraw_path, musicxml_path, tmp_path)
    ir_path = tmp_path / "unsafe_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(musicxml_path, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == expected_category
    assert raised.value.details["ascii_scoreir_gate_status"] == "refused"


def test_ascii_gate_refuses_partial_alignment_sidecar(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = json.loads(alignment_path.read_text(encoding="utf-8"))
    payload["overall_status"] = "partial"
    alignment_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ir_path = tmp_path / "partial_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == "ascii_musicxml_alignment_partial"


def test_ascii_gate_refuses_compatible_sidecar_when_inline_technique_is_present(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = json.loads(tabraw_path.read_text(encoding="utf-8"))
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
    tabraw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ir_path = tmp_path / "technique_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == "ascii_scoreir_gate_unsupported_technique"


def test_ascii_gate_refuses_missing_string_evidence(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, ASCII_GATE_MUSICXML, tmp_path)
    payload = json.loads(tabraw_path.read_text(encoding="utf-8"))
    payload["candidates"][0]["string"] = None
    tabraw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ir_path = tmp_path / "missing_string_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(ASCII_GATE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == "ascii_scoreir_gate_candidate_missing_string"


def test_ascii_gate_refuses_musicxml_timing_risk_before_output(tmp_path) -> None:
    tabraw_path = _extract(ASCII_GATE_PDF, tmp_path)
    alignment_path = _alignment_path(tabraw_path, OVERFULL_MUSICXML, tmp_path)
    ir_path = tmp_path / "timing_risk_ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(OVERFULL_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == "musicxml_timing_risk"
