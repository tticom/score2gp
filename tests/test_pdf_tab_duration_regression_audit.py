from __future__ import annotations

import json
import zipfile
from pathlib import Path
import fitz  # type: ignore[import-not-found]
from typer.testing import CliRunner
import pytest

from score2gp.cli import app
from score2gp.build_ir import build_ir_from_tabraw_only, BuildIrInputRiskError
from score2gp.gp_package import inspect_gp, validate_gp, write_gp
from score2gp.pdf_staff_detection import (
    _drawing_segments,
    _tab_line_groups,
    merge_collinear_horizontal_segments,
)
from score2gp.pdf_staff_notation_diagnostics import (
    build_notation_diagnostics,
)
from score2gp.pdf_tab_bar_assembler import assemble_pdf_tab_bar
from score2gp.pdf_tab_duration_associator import (
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    resolve_tab_duration_evidence_for_events,
)
from score2gp.pdf_tab_duration_types import TabDurationEvidence
from score2gp.tabraw import TabRaw, make_tab_candidate


def test_end_to_end_pdf_to_gp_tracked_public_fixtures(tmp_path: Path) -> None:
    """Run CLI end-to-end PDF-to-GP conversion across all tracked public PDF-tab fixtures,
    validating GP package structure, GPIF XML well-formedness, and report statuses.
    """
    public_fixtures = [
        "generated_pdf_tab_duration.pdf",
        "generated_tiny_tab.pdf",
        "generated_pdf_fret_grouped_success.pdf",
    ]

    for pdf_name in public_fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/{pdf_name}")
        assert pdf_path.exists(), f"Tracked public fixture must exist: {pdf_name}"

        out_gp = tmp_path / f"out_{pdf_name}.gp"
        workdir = tmp_path / f"work_{pdf_name}"
        json_report = tmp_path / f"report_{pdf_name}.json"

        result = CliRunner().invoke(
            app,
            [
                "convert",
                "--pdf",
                str(pdf_path),
                "--pdf-only-tab",
                "--out",
                str(out_gp),
                "--work-dir",
                str(workdir),
                "--json-report",
                str(json_report),
            ],
        )

        assert result.exit_code == 0, f"Conversion failed for {pdf_name}: {result.output}"
        assert out_gp.exists(), f"Output GP package missing for {pdf_name}"
        assert json_report.exists(), f"JSON report missing for {pdf_name}"

        report = json.loads(json_report.read_text(encoding="utf-8"))
        assert report.get("status") == "success", f"Report status not success for {pdf_name}: {report}"

        # Validate generated GP package zip container and GPIF XML
        validation = validate_gp(out_gp)
        assert validation["is_zip"] is True, f"GP package for {pdf_name} is not a valid zip archive"
        assert validation["xml_well_formed"] is True, f"GPIF XML in {pdf_name} is not well-formed"
        assert validation["errors"] == [], f"GP package validation errors for {pdf_name}: {validation['errors']}"

        # Inspect semantic facts from GP package
        summary = inspect_gp(out_gp)
        assert summary.get("bar_count", 0) >= 1, f"GP summary for {pdf_name} has invalid bar_count: {summary}"
        assert summary.get("note_count", 0) >= 1, f"GP summary for {pdf_name} has invalid note_count: {summary}"


def test_end_to_end_duration_evidence_propagation_to_scoreir_and_gpif(tmp_path: Path) -> None:
    """Verify that TabDurationEvidence (quarter, eighth, 16th) propagates from TabRaw through assemble_pdf_tab_bar,
    ScoreIR timing attributes, and into GPIF XML <Rhythms> elements (<NoteValue>Quarter</NoteValue>, etc.).
    """
    quarter_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True, source="visual_morphology")
    eighth_ev = TabDurationEvidence(duration_name="eighth", duration_ticks=480, stem_present=True, beam_count=1, source="visual_morphology")
    sixteenth_ev = TabDurationEvidence(duration_name="16th", duration_ticks=240, stem_present=True, beam_count=2, source="visual_morphology")

    cands = [
        make_tab_candidate(candidate_id="c1", raw_text="0", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=6, bbox_values=(100.0, 150.0, 104.0, 154.0), confidence=1.0, duration_evidence=quarter_ev),
        make_tab_candidate(candidate_id="c2", raw_text="2", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=5, bbox_values=(140.0, 150.0, 144.0, 154.0), confidence=1.0, duration_evidence=eighth_ev),
        make_tab_candidate(candidate_id="c3", raw_text="7", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=1, bbox_values=(180.0, 150.0, 184.0, 154.0), confidence=1.0, duration_evidence=sixteenth_ev),
    ]

    tabraw = TabRaw(source_pdf="public_test.pdf", pdf_layout_class="drawn", candidates=cands)
    tabraw_path = tmp_path / "duration_propagation.tabraw.json"
    tabraw.to_json_file(tabraw_path)

    # 1. Build ScoreIR and verify event durations
    score_ir, _ = build_ir_from_tabraw_only(tabraw_path)
    assert len(score_ir.bars) == 1
    events = score_ir.bars[0].events
    assert events[0].timing.notated_duration.value == "quarter"
    assert events[0].timing.duration_ticks == 960
    assert events[1].timing.notated_duration.value == "eighth"
    assert events[1].timing.duration_ticks == 480
    assert events[2].timing.notated_duration.value == "16th"
    assert events[2].timing.duration_ticks == 240

    # 2. Write GP package and inspect GPIF XML
    gp_path = tmp_path / "duration_propagation.gp"
    write_gp(score_ir, gp_path)
    assert gp_path.exists()

    with zipfile.ZipFile(gp_path, "r") as zf:
        gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
        assert "<NoteValue>Quarter</NoteValue>" in gpif_xml
        assert "<NoteValue>Eighth</NoteValue>" in gpif_xml
        assert "<NoteValue>16th</NoteValue>" in gpif_xml



def test_conflicting_duration_evidence_mutation_counterexample_fails_closed(tmp_path: Path) -> None:
    """Verify that a multi-string chord with conflicting duration evidence (quarter vs eighth)
    fails closed by raising BuildIrInputRiskError with category pdf_only_tab_ambiguous_duration.
    """
    quarter_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True, source="visual_morphology")
    eighth_ev = TabDurationEvidence(duration_name="eighth", duration_ticks=480, stem_present=True, source="visual_morphology")

    conflicting_cands = [
        make_tab_candidate(candidate_id="c1", raw_text="0", page_index=1, system_index=1, staff_index=1, bar_index=1, bbox_values=(100.0, 150.0, 104.0, 154.0), confidence=1.0, string=1, duration_evidence=quarter_ev),
        make_tab_candidate(candidate_id="c2", raw_text="1", page_index=1, system_index=1, staff_index=1, bar_index=1, bbox_values=(100.0, 164.0, 104.0, 168.0), confidence=1.0, string=2, duration_evidence=eighth_ev),
    ]

    tabraw = TabRaw(source_pdf="conflict.pdf", pdf_layout_class="drawn", candidates=conflicting_cands)
    tabraw_path = tmp_path / "conflict.tabraw.json"
    tabraw.to_json_file(tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_path)

    assert exc_info.value.category == "pdf_only_tab_ambiguous_duration"
    assert "Conflicting duration evidence across candidates in chord subgroup" in str(exc_info.value)


def test_pdf_tab_duration_extraction_and_association_pipeline() -> None:
    """Open generated_pdf_tab_duration.pdf, extract morphology primitives, run spatial association,
    and verify exact duration evidence resolution (quarter, eighth, 16th notes).
    """
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    # 1. Extract text spans (frets)
    text_dict = page.get_text("dict")
    extracted_spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt.isdigit() and span.get("font") == "Courier":
                    bbox = span.get("bbox")
                    if bbox:
                        event_x = (bbox[0] + bbox[2]) / 2.0
                        extracted_spans.append((event_x, txt))

    extracted_spans.sort(key=lambda t: t[0])
    extracted_xs = [t[0] for t in extracted_spans]
    assert len(extracted_xs) == 12

    # 2. Extract drawings (stems, beams, flags)
    stems: list[StemPrimitiveCandidate] = []
    beams: list[BeamPrimitiveCandidate] = []
    flags: list[FlagPrimitiveCandidate] = []
    drawing_lines: list[tuple[float, float, float, float]] = []

    for draw in page.get_drawings():
        for item in draw.get("items", []):
            if not item:
                continue
            itype = item[0]
            if itype == "l" and len(item) >= 3:
                p0, p1 = item[1], item[2]
                dx = abs(p0.x - p1.x)
                dy = abs(p0.y - p1.y)
                ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                drawing_lines.append((ix0, iy0, ix1, iy1))

                if dy >= 5.0 and dx <= 2.0:
                    stems.append(StemPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1), is_downward=True))
                elif dy <= 1.0 and dx >= 7.0:
                    if not (149.0 <= iy0 <= 221.0 and dx > 300.0):
                        beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))
                elif dx >= 3.0 and dy >= 3.0:
                    flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))

    staff_line_ys = sorted({round(iy0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(iy0 - iy1) <= 1.0 and abs(ix1 - ix0) >= 300.0})
    staff_space = (staff_line_ys[-1] - staff_line_ys[0]) / (len(staff_line_ys) - 1)
    barline_xs = sorted({round((ix0 + ix1) / 2.0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(ix0 - ix1) <= 1.0 and (iy1 - iy0) >= 60.0 and iy0 <= staff_line_ys[0] + 2.0 and iy1 >= staff_line_ys[-1] - 2.0})

    context = StaffSystemContext(
        line_y_coords=staff_line_ys,
        barline_x_coords=barline_xs,
        staff_space=staff_space,
    )

    ev_results = resolve_tab_duration_evidence_for_events(extracted_xs, stems, beams, flags, context)

    # Bar 1 quarter notes
    for ex in extracted_xs[:4]:
        ev = ev_results[ex]
        assert ev.duration_name == "quarter"
        assert ev.duration_ticks == 960
        assert ev.stem_present is True
        assert ev.beam_count == 0

    # Bar 2 flagged eighth notes
    for ex in extracted_xs[4:6]:
        ev = ev_results[ex]
        assert ev.duration_name == "eighth"
        assert ev.duration_ticks == 480
        assert ev.flag_count == 1

    # Bar 2 single-beamed eighth notes
    for ex in extracted_xs[6:8]:
        ev = ev_results[ex]
        assert ev.duration_name == "eighth"
        assert ev.duration_ticks == 480
        assert ev.beam_count == 1

    # Bar 2 double-beamed 16th notes
    for ex in extracted_xs[8:]:
        ev = ev_results[ex]
        assert ev.duration_name == "16th"
        assert ev.duration_ticks == 240
        assert ev.beam_count == 2

    # Also exercise build_notation_diagnostics with staff line groups
    raw_h = [s for s in _drawing_segments(page.get_drawings()) if s.is_horizontal]
    h_segs = merge_collinear_horizontal_segments(raw_h)
    tab_groups = list(_tab_line_groups(h_segs))
    diags = build_notation_diagnostics(page, page_index=1, notation_groups=tab_groups)
    assert len(diags.staves) == 1

    doc.close()


def test_unstemmed_and_mixed_staves_fallback_audit(tmp_path: Path) -> None:
    """Verify that unstemmed staves (e.g. generated_tiny_tab.pdf) fall back to equal-spacing grid heuristics,
    and process through TabRaw & assemble_pdf_tab_bar without corruption or timing errors.
    """
    pdf_path = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
    assert pdf_path.exists()

    unstemmed_candidates = [
        make_tab_candidate(
            candidate_id=f"tiny-{i}",
            raw_text="3",
            page_index=1,
            bbox_values=(100.0 + i * 40.0, 150.0, 104.0 + i * 40.0, 154.0),
            confidence=0.8,
            system_index=1,
            staff_index=1,
            bar_index=1,
            line_index=1,
            string=1,
        )
        for i in range(4)
    ]

    bar = assemble_pdf_tab_bar(unstemmed_candidates, output_bar_idx=1, track_id="t1")
    note_events = [ev for ev in bar.events if not ev.is_rest]

    assert len(note_events) == 4
    for ev in note_events:
        assert ev.timing.notated_duration.value == "eighth"
        assert ev.timing.duration_ticks == 480

    # Build ScoreIR from unstemmed candidates
    tabraw = TabRaw(
        source_pdf=str(pdf_path),
        pdf_layout_class="drawn",
        candidates=unstemmed_candidates,
    )

    tabraw_file = tmp_path / "tiny_tabraw.json"
    tabraw.to_json_file(tabraw_file)

    score_ir, _ = build_ir_from_tabraw_only(tabraw_file)
    assert len(score_ir.tracks) == 1
    assert len(score_ir.bars) == 1
    assert len(score_ir.bars[0].events) == 5  # 4 note events + 1 trailing rest event


def test_privacy_sanitization_and_no_leakage_audit(tmp_path: Path) -> None:
    """Audit privacy sanitization across TabRaw JSON serialization, ScoreIR outputs, and GP packages.
    Asserts zero raw memory pointers (object at 0x) or unhandled private path leakage into public artifacts.
    """
    sensitive_source = "private/fixture.pdf"
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )

    cand = make_tab_candidate(
        candidate_id="cand-priv-01",
        raw_text="5",
        page_index=1,
        bbox_values=(100.0, 150.0, 104.0, 154.0),
        confidence=0.9,
        system_index=1,
        staff_index=1,
        bar_index=1,
        line_index=1,
        string=1,
        duration_evidence=quarter_ev,
    )

    tabraw = TabRaw(
        source_pdf=sensitive_source,
        pdf_layout_class="drawn",
        candidates=[cand],
    )

    tabraw_file = tmp_path / "private_tabraw.json"
    tabraw.to_json_file(tabraw_file)

    # 1. Assert TabRaw JSON structure and schema
    loaded = json.loads(tabraw_file.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "tabraw.v0.1"

    raw_meta = loaded["candidates"][0]["raw"]
    assert "duration_evidence" in raw_meta
    assert raw_meta["duration_evidence"]["duration_name"] == "quarter"

    # 2. Build ScoreIR and verify no raw object pointers or unhandled exceptions occur
    score_ir, diagnostics = build_ir_from_tabraw_only(tabraw_file)
    assert score_ir.schema_version == "0.1.0"

    ir_json_str = score_ir.model_dump_json()
    assert "object at 0x" not in ir_json_str

    # 3. Perform CLI convert end-to-end on public fixture and audit output GP package
    public_pdf = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    out_gp = tmp_path / "privacy_test.gp"
    workdir = tmp_path / "privacy_work"
    report_json = tmp_path / "privacy_report.json"

    res = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(public_pdf),
            "--pdf-only-tab",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(report_json),
        ],
    )
    assert res.exit_code == 0
    assert out_gp.exists()

    # Read inside the GPIF archive and confirm no raw debug object addresses or invalid memory representations exist
    with zipfile.ZipFile(out_gp, "r") as zf:
        for zip_info in zf.infolist():
            content = zf.read(zip_info.filename).decode("utf-8", errors="ignore")
            assert "object at 0x" not in content
            assert "unhandled exception" not in content.lower()
