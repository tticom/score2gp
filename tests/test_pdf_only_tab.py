from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner
import pytest

from score2gp.cli import app
from score2gp.build_ir import build_ir_from_tabraw_only, BuildIrInputRiskError
from score2gp.tabraw import TabRaw, TabCandidate
from score2gp.gp_package import inspect_gp, validate_gp, write_gp

# Public fixtures
SIMPLE_PDF = Path("tests/fixtures/pdf/generated_pdf_fret_grouped_success.pdf")
TEMPLATE_GP = Path("fixtures/templates/minimal_gp7.gp")


def test_pdf_only_tab_refuses_unsafe_grouping(tmp_path) -> None:
    # 1. Mock a TabRaw with a layout warning (e.g. pdf_no_systems_detected)
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": ["pdf_no_systems_detected"],
        "candidates": [
            {
                "id": "c-0001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_unsafe.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    # Assert that direct build raises BuildIrInputRiskError with pdf_only_tab_grouping_unsafe
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc_info.value.category == "pdf_only_tab_grouping_unsafe"
    assert "pdf_no_systems_detected" in str(exc_info.value)

    # Assert CLI convert returns exit code 4
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    # We manually override the generated tab_raw in workdir by running convert command,
    # or we can mock extract_tab_file if we want, but actually running convert on
    # generated_unstructured_tab_text.pdf (which has no systems/barlines) will refuse.
    # Let's test using generated_unstructured_tab_text.pdf directly in the CLI!
    unstructured_pdf = Path("tests/fixtures/pdf/generated_unstructured_tab_text.pdf")
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(unstructured_pdf),
            "--pdf-only-tab",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    assert result.exit_code == 4
    assert json_report.exists()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "refused"
    assert report["exit_code"] == 4
    assert report["refusal_code"] == "pdf_only_tab_grouping_unsafe"
    assert report["pdf_only_diagnostics"]["pdf_grouping_status"] == "refused"


def test_pdf_only_tab_strict_precise_timing_mode_refuses_inference(tmp_path) -> None:
    # 1.5 Strict precise-timing mode must reject missing timing evidence
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-0001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_timing.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    # API validation
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file, require_precise_timing=True)
    assert exc_info.value.category == "pdf_only_tab_missing_timing_evidence"
    assert "Precise rhythm conversion requires MusicXML/sidecar or explicit reliable timing evidence" in str(exc_info.value)

    # CLI validation
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    # We use a simple pdf fixture
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--pdf-only-tab",
            "--require-precise-timing",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    # The exit code for this category falls under "pdf_" so _convert_exit_code_for_error maps it to 2.
    # We could assert exit code 2 or 1, but actually the category starts with "pdf_", so it returns 2
    assert result.exit_code == 2
    assert not out_gp.exists()  # Ensure no misleading GP file was produced
    assert json_report.exists()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "refused"
    assert report["refusal_code"] == "pdf_only_tab_missing_timing_evidence"
    assert "Provide MusicXML/sidecar timing evidence" in report["recommended_action"]



def test_pdf_only_tab_rhythm_inference_policy(tmp_path) -> None:
    # 2. Mock a TabRaw with a bar containing 4 x-groups to verify rhythm grid logic
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            # Event 1: x=10
            {
                "id": "c-0001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            # Event 2: x=30
            {
                "id": "c-0002",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 2,
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 30.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            # Event 3: x=50 (chord: 2 candidates sharing near-identical x-position)
            {
                "id": "c-0003",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 3,
                "string": 3,
                "raw_text": "6",
                "parsed_fret": 6,
                "x": 50.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-0004",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 4,
                "string": 4,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 50.1,  # within 10.0 tolerance
                "y": 20.0,
                "confidence": 0.9,
            },
            # Event 4: x=70
            {
                "id": "c-0005",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 5,
                "string": 5,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 70.0,
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_rhythm.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    # 4 x-groups should lead to eighth notes (grid_spacing = 480)
    assert len(score.bars) == 1
    bar = score.bars[0]
    # Onsets: 0, 480, 960, 1440 for notes; 1920 for rest
    # Note Durations: 480, 480, 480, 480; Rest Duration: 1920 (half note)
    events = bar.events
    assert len(events) == 5

    assert events[0].timing.onset_ticks == 0
    assert events[0].timing.duration_ticks == 480
    assert events[0].timing.notated_duration.value == "eighth"

    assert events[1].timing.onset_ticks == 480
    assert events[1].timing.duration_ticks == 480

    # Event 3 is a chord (contains 2 notes)
    assert events[2].timing.onset_ticks == 960
    assert events[2].timing.duration_ticks == 480
    assert len(events[2].notes) == 2

    assert events[3].timing.onset_ticks == 1440
    assert events[3].timing.duration_ticks == 480
    assert events[3].timing.notated_duration.value == "eighth"

    assert events[4].is_rest
    assert events[4].id == "bar-1-rest-1"
    assert events[4].timing.onset_ticks == 1920
    assert events[4].timing.duration_ticks == 1920
    assert events[4].timing.notated_duration.value == "half"

    # Provenance warning indicating Timing layout inference is present
    warning_codes = [w.code for w in score.warnings]
    assert "pdf_only_tab_inferred_timing" in warning_codes


def test_pdf_only_tab_succeeds_and_generates_valid_gp(tmp_path) -> None:
    # 3. Successful conversion of a safe public PDF fixture directly without MusicXML
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--pdf-only-tab",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_gp.exists()

    # Structurally validate GP file
    validation = validate_gp(out_gp)
    assert not validation["errors"]


def test_pdf_only_tab_json_report_fields(tmp_path) -> None:
    # 4. Verify presence of grouping status, rhythm status, and comparison metrics in report
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--pdf-only-tab",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
            "--ref-gp",
            str(TEMPLATE_GP),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json_report.exists()

    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert "pdf_only_diagnostics" in report
    diagnostics = report["pdf_only_diagnostics"]
    assert diagnostics["pdf_grouping_status"] == "safe"
    assert diagnostics["inferred_rhythm_status"] == "applied"
    assert diagnostics["gp_package_written"] is True
    assert "semantic_comparison" in diagnostics
    assert "matches" in diagnostics["semantic_comparison"]
    assert "differences" in diagnostics["semantic_comparison"]


def test_pdf_only_preserves_page_system_bar_order(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 2,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-3",
                "kind": "fret",
                "page_index": 2,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "9",
                "parsed_fret": 9,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_order.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 3
    for b in score.bars:
        for ev in b.events:
            pages = {prov.page for prov in ev.provenance if prov.page is not None}
            systems = {prov.system_id for prov in ev.provenance if prov.system_id is not None}
            bars_local = {prov.bar_index for prov in ev.provenance if prov.bar_index is not None}
            assert len(pages) <= 1
            assert len(systems) <= 1
            assert len(bars_local) <= 1


def test_pdf_only_does_not_stack_same_x_across_pages(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 2,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_x_pages.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 2
    assert len(score.bars[0].events) == 4
    assert len(score.bars[1].events) == 4


def test_pdf_only_duplicate_string_same_event_split_or_refused(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 10.1,
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_dup_strings.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 1
    assert len(score.bars[0].events) == 4
    assert score.bars[0].events[0].notes[0].fret == 5
    assert score.bars[0].events[1].notes[0].fret == 7


def test_pdf_only_preserves_candidate_top_level_source_identity(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 3,
                "system_index": 4,
                "staff_index": 1,
                "bar_index": 2,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_identity.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 1
    event = score.bars[0].events[0]
    provenance = event.provenance[0]
    assert provenance.page == 3
    assert provenance.system_id == "system-4"
    assert provenance.bar_index == 2


def test_pdf_only_groups_small_x_offsets_across_strings_as_chord(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 19.0,  # 9.0 pt delta, within 10.0 tolerance
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_chord_grouped.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 1
    # 2 candidates should group into a single chord event (plus remainder rest events)
    assert len(score.bars[0].events) == 4
    event = score.bars[0].events[0]
    assert len(event.notes) == 2
    notes_sorted = sorted(event.notes, key=lambda n: n.string)
    assert notes_sorted[0].string == 1 and notes_sorted[0].fret == 5
    assert notes_sorted[1].string == 2 and notes_sorted[1].fret == 7


def test_pdf_only_keeps_sequential_notes_separate_when_x_gap_is_large(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 21.0,  # 11.0 pt delta, exceeds 10.0 tolerance
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_arpeggio.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 1
    # 2 candidates should remain sequential (plus remainder rest events)
    assert len(score.bars[0].events) == 4
    assert score.bars[0].events[0].notes[0].fret == 5
    assert score.bars[0].events[1].notes[0].fret == 7


def test_pdf_only_does_not_group_duplicate_string_candidates_as_chord(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,  # Same string
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 15.0,  # 5.0 pt delta (within 10.0), but same string
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_dup_string_check.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    assert len(score.bars) == 1
    # Must be split into 2 sequential events (plus remainder rest events) to protect duplicate string safety
    assert len(score.bars[0].events) == 4
    assert score.bars[0].events[0].notes[0].fret == 5
    assert score.bars[0].events[1].notes[0].fret == 7


def test_pdf_only_never_groups_chords_across_source_bar_identity(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,  # Bar 1
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 2,  # Bar 2
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 12.0,  # 2.0 pt delta, but different bars
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_bar_boundary.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    # Must be 2 distinct bars
    assert len(score.bars) == 2
    assert len(score.bars[0].events) == 4
    assert score.bars[0].events[0].notes[0].fret == 5
    assert len(score.bars[1].events) == 4
    assert score.bars[1].events[0].notes[0].fret == 7


def test_build_ir_from_tabraw_only_tempo_override(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_tempo.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    # Explicit 70.0 BPM
    score_70, _ = build_ir_from_tabraw_only(tabraw_file, tempo_bpm=70.0, tempo_is_explicit=True, editable_draft=True)
    assert score_70.tempo is not None
    assert score_70.tempo.bpm == 70.0
    assert "Tempo set to 70 bpm." in score_70.bars[0].events[0].text

    # Explicit 120.0 BPM
    score_exp120, _ = build_ir_from_tabraw_only(tabraw_file, tempo_bpm=120.0, tempo_is_explicit=True, editable_draft=True)
    assert score_exp120.tempo is not None
    assert score_exp120.tempo.bpm == 120.0
    assert "Tempo set to 120 bpm." in score_exp120.bars[0].events[0].text
    assert "Tempo defaulted" not in score_exp120.bars[0].events[0].text

    # Default (omitted) -> 120.0 BPM
    score_default, _ = build_ir_from_tabraw_only(tabraw_file, editable_draft=True)
    assert score_default.tempo is not None
    assert score_default.tempo.bpm == 120.0
    assert "Tempo defaulted to 120 bpm." in score_default.bars[0].events[0].text


def test_build_ir_from_tabraw_only_rejects_invalid_tempo(tmp_path) -> None:
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_invalid_tempo.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    for bad_tempo in [0.0, -10.0, float("nan"), float("inf"), float("-inf")]:
        with pytest.raises(BuildIrInputRiskError) as exc_info:
            build_ir_from_tabraw_only(tabraw_file, tempo_bpm=bad_tempo)
        assert exc_info.value.category == "pdf_only_tab_invalid_tempo"


def test_cli_convert_tempo_bpm_option(tmp_path) -> None:
    out_gp = tmp_path / "out_70.gp"
    workdir = tmp_path / "workdir_70"
    json_report = tmp_path / "report_70.json"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--pdf-only-tab",
            "--tempo-bpm",
            "70",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_gp.exists()
    gp_summary = inspect_gp(out_gp)
    assert gp_summary["tempo"] is not None
    assert gp_summary["tempo"].startswith("70")

    ir_file = workdir / "score.ir.json"
    assert ir_file.exists()
    ir_data = json.loads(ir_file.read_text(encoding="utf-8"))
    assert ir_data["tempo"]["bpm"] == 70.0

    # Omitting --tempo-bpm preserves 120.0 BPM
    out_gp_def = tmp_path / "out_def.gp"
    workdir_def = tmp_path / "workdir_def"

    result_def = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--pdf-only-tab",
            "--out",
            str(out_gp_def),
            "--work-dir",
            str(workdir_def),
        ],
    )
    assert result_def.exit_code == 0, result_def.output
    ir_file_def = workdir_def / "score.ir.json"
    assert ir_file_def.exists()
    ir_data_def = json.loads(ir_file_def.read_text(encoding="utf-8"))
    assert ir_data_def["tempo"]["bpm"] == 120.0

    # CLI refuses --tempo-bpm outside --pdf-only-tab / --editable-draft
    out_gp_refuse = tmp_path / "out_refuse.gp"
    workdir_refuse = tmp_path / "workdir_refuse"

    result_refuse = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--tempo-bpm",
            "70",
            "--out",
            str(out_gp_refuse),
            "--work-dir",
            str(workdir_refuse),
        ],
    )
    assert result_refuse.exit_code != 0
    assert not out_gp_refuse.exists()


def test_cli_convert_editable_draft_tempo_bpm_option(tmp_path) -> None:
    out_gp = tmp_path / "out_draft.gp"
    workdir = tmp_path / "workdir_draft"
    json_report = tmp_path / "report_draft.json"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--editable-draft",
            "--tempo-bpm",
            "70",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_gp.exists()

    # Inspect ScoreIR tempo & text annotation
    ir_file = workdir / "score.ir.json"
    assert ir_file.exists()
    ir_data = json.loads(ir_file.read_text(encoding="utf-8"))
    assert ir_data["tempo"]["bpm"] == 70.0

    first_event = ir_data["bars"][0]["events"][0]
    annotation = first_event.get("text")
    assert annotation is not None
    assert "Tempo set to 70 bpm." in annotation
    assert "Tempo defaulted" not in annotation

    # Inspect GPIF tempo in generated .gp package
    gp_summary = inspect_gp(out_gp)
    assert gp_summary["tempo"] is not None
    assert gp_summary["tempo"].startswith("70")

    # Regression test for explicit --tempo-bpm 120
    out_gp_120 = tmp_path / "out_draft_120.gp"
    workdir_120 = tmp_path / "workdir_draft_120"
    result_120 = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(SIMPLE_PDF),
            "--editable-draft",
            "--tempo-bpm",
            "120",
            "--out",
            str(out_gp_120),
            "--work-dir",
            str(workdir_120),
        ],
    )
    assert result_120.exit_code == 0, result_120.output
    assert out_gp_120.exists()
    ir_file_120 = workdir_120 / "score.ir.json"
    ir_data_120 = json.loads(ir_file_120.read_text(encoding="utf-8"))
    assert ir_data_120["tempo"]["bpm"] == 120.0

    ann_120 = ir_data_120["bars"][0]["events"][0].get("text")
    assert ann_120 is not None
    assert "Tempo set to 120 bpm." in ann_120
    assert "Tempo defaulted" not in ann_120

    gp_summary_120 = inspect_gp(out_gp_120)
    assert gp_summary_120["tempo"] is not None
    assert gp_summary_120["tempo"].startswith("120")


def test_cr04c_final_event_duration_consistency_n4_single_rest(tmp_path) -> None:
    # 4 eighth notes (x=10, 30, 50, 70)
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": f"c-000{i+1}",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0 + i * 20.0,
                "y": 20.0,
                "confidence": 0.9,
            }
            for i in range(4)
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_n4.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, _ = build_ir_from_tabraw_only(tabraw_file)
    assert len(score.bars) == 1
    bar = score.bars[0]
    events = bar.events
    assert len(events) == 5

    for i in range(4):
        assert not events[i].is_rest
        assert events[i].timing.duration_ticks == 480
        assert events[i].timing.notated_duration.value == "eighth"
        assert events[i].timing.notated_duration.dots == 0
        assert events[i].timing.onset_ticks == i * 480

    rest_event = events[4]
    assert rest_event.is_rest
    assert rest_event.id == "bar-1-rest-1"
    assert rest_event.timing.onset_ticks == 1920
    assert rest_event.timing.duration_ticks == 1920
    assert rest_event.timing.notated_duration.value == "half"
    assert rest_event.timing.notated_duration.dots == 0

    gp_file = tmp_path / "n4.gp"
    write_gp(score, gp_file, template=TEMPLATE_GP)
    assert validate_gp(gp_file)["errors"] == []


def test_cr04c_final_event_duration_consistency_n3_remainder(tmp_path) -> None:
    # 3 eighth notes (x=10, 30, 50)
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": f"c-000{i+1}",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0 + i * 20.0,
                "y": 20.0,
                "confidence": 0.9,
            }
            for i in range(3)
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_n3.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, _ = build_ir_from_tabraw_only(tabraw_file)
    assert len(score.bars) == 1
    bar = score.bars[0]
    events = bar.events
    assert len(events) == 5  # 3 notes + 2 rests

    for i in range(3):
        assert not events[i].is_rest
        assert events[i].timing.duration_ticks == 480
        assert events[i].timing.notated_duration.value == "eighth"

    r1 = events[3]
    assert r1.is_rest
    assert r1.id == "bar-1-rest-1"
    assert r1.timing.onset_ticks == 1440
    assert r1.timing.duration_ticks == 1920
    assert r1.timing.notated_duration.value == "half"
    assert r1.timing.notated_duration.dots == 0

    r2 = events[4]
    assert r2.is_rest
    assert r2.id == "bar-1-rest-2"
    assert r2.timing.onset_ticks == 3360
    assert r2.timing.duration_ticks == 480
    assert r2.timing.notated_duration.value == "eighth"
    assert r2.timing.notated_duration.dots == 0

    gp_file = tmp_path / "n3.gp"
    write_gp(score, gp_file, template=TEMPLATE_GP)
    assert validate_gp(gp_file)["errors"] == []


def test_cr04c_final_event_duration_consistency_n1_remainder(tmp_path) -> None:
    # 1 eighth note (x=10)
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-0001",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            }
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_n1.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, _ = build_ir_from_tabraw_only(tabraw_file)
    assert len(score.bars) == 1
    bar = score.bars[0]
    events = bar.events
    assert len(events) == 4  # 1 note + 3 rests

    assert not events[0].is_rest
    assert events[0].timing.duration_ticks == 480
    assert events[0].timing.notated_duration.value == "eighth"

    # Rest 1: half 1920 at 480
    assert events[1].is_rest
    assert events[1].id == "bar-1-rest-1"
    assert events[1].timing.onset_ticks == 480
    assert events[1].timing.duration_ticks == 1920
    assert events[1].timing.notated_duration.value == "half"

    # Rest 2: quarter 960 at 2400
    assert events[2].is_rest
    assert events[2].id == "bar-1-rest-2"
    assert events[2].timing.onset_ticks == 2400
    assert events[2].timing.duration_ticks == 960
    assert events[2].timing.notated_duration.value == "quarter"

    # Rest 3: eighth 480 at 3360
    assert events[3].is_rest
    assert events[3].id == "bar-1-rest-3"
    assert events[3].timing.onset_ticks == 3360
    assert events[3].timing.duration_ticks == 480
    assert events[3].timing.notated_duration.value == "eighth"

    gp_file = tmp_path / "n1.gp"
    write_gp(score, gp_file, template=TEMPLATE_GP)
    assert validate_gp(gp_file)["errors"] == []


def test_cr04c_final_event_duration_consistency_overcapacity_refusal(tmp_path) -> None:
    # 5 candidates in --editable-draft mode (grid_spacing=960 -> 5*960=4800 > 3840)
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": f"c-000{i+1}",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0 + i * 20.0,
                "y": 20.0,
                "confidence": 0.9,
            }
            for i in range(5)
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_overcapacity.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file, editable_draft=True)

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"


def test_cr04c_final_event_duration_consistency_mixed_rest_overcapacity(tmp_path) -> None:
    # 5 eighth note candidates (5 * 480 = 2400) + 2 quarter_rest candidates (2 * 960 = 1920)
    # N = 7 candidates -> grid_spacing = 480 for notes.
    # Total ticks: 2400 + 1920 = 4320 > 3840 ticks.
    candidates = [
        {
            "id": f"c-000{i+1}",
            "kind": "fret",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bar_index": 1,
            "line_index": 1,
            "string": 1,
            "raw_text": "5",
            "parsed_fret": 5,
            "x": 10.0 + i * 20.0,
            "y": 20.0,
            "confidence": 0.9,
        }
        for i in range(5)
    ]
    candidates.extend(
        [
            {
                "id": f"c-rest-{i+1}",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,
                "line_index": 1,
                "string": 1,
                "raw_text": "quarter_rest",
                "parsed_fret": None,
                "x": 110.0 + i * 20.0,
                "y": 20.0,
                "confidence": 0.9,
            }
            for i in range(2)
        ]
    )
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": candidates,
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_mixed_overcapacity.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_file)

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"
    assert exc_info.value.details.get("accumulated_ticks") == "4320"
