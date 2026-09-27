from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
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



def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


support = _load("pdf_tab_route_support", "test_pdf_tab_route_support.py")
route = _load("dur_02_route", "test_dur_02_note_type_route.py")
note, rest, digit, records = support.note, support.rest, support.digit, support.records


@pytest.fixture
def private_dir():
    """A directory whose path does not contain "test": extract_tab treats a PDF under such a path
    differently (see tests/test_dur_02_note_type_route.py), and these conversions must not."""
    path = Path(tempfile.mkdtemp(prefix="dur02-pdfonly-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _build(tmp_path, digits, pages, **kwargs):
    tabraw_file = tmp_path / "tabraw.json"
    TabRaw(candidates=digits).to_json_file(tabraw_file)
    return build_ir_from_tabraw_only(tabraw_file, note_durations=records(pages), **kwargs)


def _convert(pdf: Path, workdir: Path, out_gp: Path, *extra: str):
    return CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out_gp),
                                    "--work-dir", str(workdir), *extra])


def test_pdf_only_tab_rhythm_inference_policy(tmp_path) -> None:
    """Replaced (DUR-02): four TAB columns take the note types above them, not four eighths and a half rest."""
    specs = [note(10.0), note(30.0, "eighth"), note(50.0, "eighth", heads=2), note(70.0, "half")]
    digits = [digit("c-1", 0, 10.0, 1, 5), digit("c-2", 0, 30.0, 2, 7), digit("c-3", 0, 50.0, 3, 6),
              digit("c-4", 0, 50.1, 4, 7), digit("c-5", 0, 70.0, 5, 5)]
    score, diagnostics = _build(tmp_path, digits, [[specs]])
    events = score.bars[0].events
    assert [(e.timing.onset_ticks, e.timing.duration_ticks, e.timing.notated_duration.value) for e in events] == [
        (0, 960, "quarter"), (960, 480, "eighth"), (1440, 480, "eighth"), (1920, 1920, "half")]
    assert len(events[2].notes) == 2
    assert not any(e.is_rest for e in events)
    codes = [w.code for w in score.warnings]
    assert "pdf_only_tab_note_type_timing" in codes and "pdf_only_tab_inferred_timing" not in codes
    assert diagnostics.pdf_timing_mapping["quality"] == "note_type"


def test_pdf_only_tab_succeeds_and_generates_valid_gp(private_dir) -> None:
    """Replaced (DUR-02): a notation-and-TAB page converts to a valid GP; the TAB-only fixture is refused."""
    out_gp = private_dir / "output.gp"
    result = _convert(route.clean_pdf(private_dir / "clean.pdf"), private_dir / "workdir", out_gp)
    assert result.exit_code == 0, result.output
    assert not validate_gp(out_gp)["errors"]
    refused = _convert(SIMPLE_PDF, private_dir / "workdir_tab_only", private_dir / "tab_only.gp")
    assert refused.exit_code != 0 and not (private_dir / "tab_only.gp").exists()


def test_pdf_only_tab_json_report_fields(private_dir) -> None:
    json_report = private_dir / "report.json"
    result = _convert(route.clean_pdf(private_dir / "clean.pdf"), private_dir / "workdir", private_dir / "output.gp",
                      "--json-report", str(json_report), "--ref-gp", str(TEMPLATE_GP))
    assert result.exit_code == 0, result.output
    diagnostics = json.loads(json_report.read_text(encoding="utf-8"))["pdf_only_diagnostics"]
    assert diagnostics["pdf_grouping_status"] == "safe"
    assert diagnostics["inferred_rhythm_status"] == "note_type"
    assert diagnostics["gp_package_written"] is True
    assert "matches" in diagnostics["semantic_comparison"] and "differences" in diagnostics["semantic_comparison"]


def test_pdf_only_preserves_page_system_bar_order(tmp_path) -> None:
    """Three pages, one bar each, a digit at the same x on every page: three bars in page order."""
    digits = [digit(f"c-{p}", 0, 20.0, 1, p + 1, page=p) for p in range(3)]
    score, _ = _build(tmp_path, digits, [[[note(20.0, "whole")]] for _ in range(3)])
    assert [bar.index for bar in score.bars] == [1, 2, 3]
    assert [[n.fret for e in bar.events for n in e.notes] for bar in score.bars] == [[1], [2], [3]]
    for bar, page in zip(score.bars, (1, 2, 3)):
        assert {p.page for e in bar.events for p in e.provenance} == {page}


def test_pdf_only_does_not_stack_same_x_across_pages(tmp_path) -> None:
    digits = [digit("p1", 0, 20.0, 1, 5, page=0), digit("p2", 0, 20.0, 2, 7, page=1)]
    score, _ = _build(tmp_path, digits, [[[note(20.0, "whole")]], [[note(20.0, "whole")]]])
    assert [[(n.string, n.fret) for e in bar.events for n in e.notes] for bar in score.bars] == [[(1, 5)], [(2, 7)]]


def test_pdf_only_duplicate_string_same_event_split_or_refused(tmp_path) -> None:
    """Replaced (DUR-02): two digits on one string in one column cannot be one chord: the bar is refused."""
    digits = [digit("a", 0, 20.0, 1, 5), digit("b", 0, 20.1, 1, 7)] + [digit(f"q{i}", 1, 20.0 + 40.0 * i, 1, 1) for i in range(4)]
    score, diagnostics = _build(tmp_path, digits, [[[note(20.0, "whole", heads=2)], [note(20.0 + 40.0 * i) for i in range(4)]]])
    assert score.bars[0].events == [] and len(score.bars[1].events) == 4
    assert diagnostics.note_type_route["bars"][0]["reason"] == "notehead_digit_count_mismatch"


def test_pdf_only_preserves_candidate_top_level_source_identity(tmp_path) -> None:
    cand = digit("c-1", 0, 20.0, 1, 5, page=2).model_copy(update={"system_index": 4, "bar_index": 2})
    score, _ = _build(tmp_path, [cand], [[[]], [[]], [[note(20.0, "whole")]]])
    (provenance,) = score.bars[2].events[0].notes[0].provenance
    assert (provenance.page, provenance.system_id, provenance.bar_index, provenance.raw_token_id) == (3, "system-4", 2, "c-1")


def test_pdf_only_groups_small_x_offsets_across_strings_as_chord(tmp_path) -> None:
    """A chord column is digits within three quarters of a staff space (the notation's own unit)."""
    digits = [digit("a", 0, 20.0, 1, 5), digit("b", 0, 20.0 + 0.7 * support.SPACE, 2, 7)]
    score, _ = _build(tmp_path, digits, [[[note(21.0, "whole", heads=2)]]])
    (event,) = score.bars[0].events
    assert sorted((n.string, n.fret) for n in event.notes) == [(1, 5), (2, 7)]


def test_pdf_only_keeps_sequential_notes_separate_when_x_gap_is_large(tmp_path) -> None:
    digits = [digit("a", 0, 20.0, 1, 5), digit("b", 0, 20.0 + 3 * support.SPACE, 2, 7)]
    score, _ = _build(tmp_path, digits, [[[note(20.0, "half"), note(20.0 + 3 * support.SPACE, "half")]]])
    assert [[(n.string, n.fret) for n in e.notes] for e in score.bars[0].events] == [[(1, 5)], [(2, 7)]]


def test_pdf_only_does_not_group_duplicate_string_candidates_as_chord(tmp_path) -> None:
    digits = [digit("a", 0, 20.0, 1, 5), digit("b", 0, 20.0 + 3 * support.SPACE, 1, 7)]
    score, _ = _build(tmp_path, digits, [[[note(20.0, "half"), note(20.0 + 3 * support.SPACE, "half")]]])
    assert [[(n.string, n.fret) for n in e.notes] for e in score.bars[0].events] == [[(1, 5)], [(1, 7)]]


def test_pdf_only_never_groups_chords_across_source_bar_identity(tmp_path) -> None:
    """Two digits either side of a notation barline, close in x, go to their own bars."""
    near_end = support.BAR_WIDTH - 1.0
    digits = [digit("a", 0, near_end, 1, 5), digit("b", 1, 1.0, 2, 7)]
    score, _ = _build(tmp_path, digits, [[[note(near_end, "whole")], [note(1.0, "whole")]]])
    assert [[(n.string, n.fret) for e in bar.events for n in e.notes] for bar in score.bars] == [[(1, 5)], [(2, 7)]]


def test_build_ir_from_tabraw_only_tempo_override(tmp_path) -> None:
    """The tempo is the caller's; the editable-draft annotation that echoed it is gone."""
    digits = [digit("a", 0, 20.0, 1, 5)]
    pages = [[[note(20.0, "whole")]]]
    for kwargs, bpm in (({"tempo_bpm": 70.0}, 70.0), ({"tempo_bpm": 120.0}, 120.0), ({}, 120.0)):
        score, _ = _build(tmp_path, digits, pages, **kwargs)
        assert score.tempo.bpm == bpm
        assert all(e.text is None for bar in score.bars for e in bar.events)


def test_build_ir_from_tabraw_only_rejects_invalid_tempo(tmp_path) -> None:
    tabraw_file = tmp_path / "tabraw.json"
    TabRaw(candidates=[digit("a", 0, 20.0, 1, 5)]).to_json_file(tabraw_file)
    for bad in (0.0, -10.0, float("nan"), float("inf")):
        with pytest.raises(BuildIrInputRiskError) as exc_info:
            build_ir_from_tabraw_only(tabraw_file, note_durations=records([[[note(20.0, "whole")]]]), tempo_bpm=bad)
        assert exc_info.value.category == "pdf_only_tab_invalid_tempo"


def test_cli_convert_tempo_bpm_option(private_dir) -> None:
    pdf = route.clean_pdf(private_dir / "clean.pdf")
    out_gp = private_dir / "out_70.gp"
    result = _convert(pdf, private_dir / "workdir_70", out_gp, "--tempo-bpm", "70")
    assert result.exit_code == 0, result.output
    assert inspect_gp(out_gp)["tempo"].startswith("70")
    assert json.loads((private_dir / "workdir_70" / "score.ir.json").read_text(encoding="utf-8"))["tempo"]["bpm"] == 70.0

    result_def = _convert(pdf, private_dir / "workdir_def", private_dir / "out_def.gp")
    assert result_def.exit_code == 0, result_def.output
    assert json.loads((private_dir / "workdir_def" / "score.ir.json").read_text(encoding="utf-8"))["tempo"]["bpm"] == 120.0

    # CLI refuses --tempo-bpm outside --pdf-only-tab
    out_refuse = private_dir / "out_refuse.gp"
    refused = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--tempo-bpm", "70", "--out", str(out_refuse),
                                       "--work-dir", str(private_dir / "workdir_refuse")])
    assert refused.exit_code != 0 and not out_refuse.exists()


def test_cli_convert_editable_draft_tempo_bpm_option(private_dir) -> None:
    """Replaced (DUR-02): --editable-draft is gone; an explicit --tempo-bpm 120 with --pdf-only-tab is
    written as 120 with no annotation text."""
    pdf = route.clean_pdf(private_dir / "clean.pdf")
    gone = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--editable-draft", "--tempo-bpm", "70",
                                    "--out", str(private_dir / "x.gp"), "--work-dir", str(private_dir / "x")])
    assert gone.exit_code == 2 and "No such option" in gone.output
    out_gp = private_dir / "out_120.gp"
    result = _convert(pdf, private_dir / "workdir_120", out_gp, "--tempo-bpm", "120")
    assert result.exit_code == 0, result.output
    assert inspect_gp(out_gp)["tempo"].startswith("120")
    ir = json.loads((private_dir / "workdir_120" / "score.ir.json").read_text(encoding="utf-8"))
    assert ir["tempo"]["bpm"] == 120.0
    assert all(e.get("text") is None for bar in ir["bars"] for e in bar["events"])


@pytest.mark.parametrize(
    ("case", "specs", "detail"),
    [
        # four notes: the count rule made them eighths and added a half rest
        ("n4_single_rest", [note(10.0 + 20.0 * i, "eighth") for i in range(4)], "2 of 4 quarters"),
        # three notes: eighths plus half and eighth rests
        ("n3_remainder", [note(10.0 + 20.0 * i, "eighth") for i in range(3)], "3/2 of 4 quarters"),
        # one note: an eighth plus half, quarter and eighth rests
        ("n1_remainder", [note(10.0, "eighth")], "1/2 of 4 quarters"),
        # five quarters in 4/4 (the editable draft's overcapacity)
        ("overcapacity_refusal", [note(10.0 + 30.0 * i) for i in range(5)], "5 of 4 quarters"),
        # five eighths and two quarter rests
        ("mixed_rest_overcapacity", [note(10.0 + 20.0 * i, "eighth") for i in range(5)] + [rest(120.0), rest(160.0)],
         "9/2 of 4 quarters"),
    ],
)
def test_cr04c_final_event_duration_consistency(tmp_path, case, specs, detail) -> None:
    """Replaces the five test_cr04c_final_event_duration_consistency_* tests: a bar whose note types do
    not add up to its time signature is refused, never padded with rests and never truncated."""
    digits = [digit(f"c-{i}", 0, s["x"], 1, 5) for i, s in enumerate(specs) if s["kind"] != "rest"]
    digits += [digit(f"q-{i}", 1, 20.0 + 40.0 * i, 1, 1) for i in range(4)]
    score, diagnostics = _build(tmp_path, digits, [[specs, [note(20.0 + 40.0 * i) for i in range(4)]]])
    entry = diagnostics.note_type_route["bars"][0]
    assert (entry["status"], entry["reason"], entry["detail"]) == ("refused", "bar_total_mismatch", detail)
    assert score.bars[0].events == []
    assert [e.timing.duration_ticks for e in score.bars[1].events] == [960] * 4
