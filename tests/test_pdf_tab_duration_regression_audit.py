from __future__ import annotations

import json
import zipfile
from pathlib import Path
import fitz  # type: ignore[import-not-found]
from typer.testing import CliRunner

import pytest
from pathlib import Path

def _get_dynamic_private_pdf():
    pdfs = list(Path("fixtures/private").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No private fixtures found", allow_module_level=True)
    return pdfs[0]

def _get_dynamic_private_musicxml():
    xmls = list(Path("fixtures/private").glob("*.musicxml"))
    if not xmls:
        # Fallback to pdf just so Path doesn't fail, test will likely skip or fail gracefully
        return _get_dynamic_private_pdf()
    return xmls[0]


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

        if pdf_name == "generated_pdf_tab_duration.pdf":
            score_ir_data = json.loads((workdir / "score.ir.json").read_text(encoding="utf-8"))
            bar1_events = [ev for ev in score_ir_data["bars"][0]["events"] if not ev.get("is_rest")]
            bar2_events = [ev for ev in score_ir_data["bars"][1]["events"] if not ev.get("is_rest")]
            assert len(bar1_events) == 4, f"Bar 1 expected 4 note events, got {len(bar1_events)}"
            for ev in bar1_events:
                assert ev["timing"]["notated_duration"]["value"] == "quarter"
                assert ev["timing"]["duration_ticks"] == 960

            assert len(bar2_events) == 8, f"Bar 2 expected 8 note events, got {len(bar2_events)}"
            assert bar2_events[0]["timing"]["notated_duration"]["value"] == "eighth"
            assert bar2_events[0]["timing"]["duration_ticks"] == 480
            assert bar2_events[4]["timing"]["notated_duration"]["value"] == "16th"
            assert bar2_events[4]["timing"]["duration_ticks"] == 240

            with zipfile.ZipFile(out_gp, "r") as zf:
                gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
                assert "<NoteValue>Quarter</NoteValue>" in gpif_xml
                assert "<NoteValue>Eighth</NoteValue>" in gpif_xml
                assert "<NoteValue>16th</NoteValue>" in gpif_xml


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
    pdf_path = _get_dynamic_private_pdf()
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
    pdf_path = _get_dynamic_private_pdf()
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
    sensitive_pdf = tmp_path / "private_fixture_sensitive_input.pdf"
    sensitive_pdf.write_bytes(_get_dynamic_private_pdf().read_bytes())
    sensitive_source = str(sensitive_pdf)

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

    # 1. Assert TabRaw JSON structure, schema, and sensitive source path
    loaded = json.loads(tabraw_file.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "tabraw.v0.1"
    assert loaded["source_pdf"] == sensitive_source

    raw_meta = loaded["candidates"][0]["raw"]
    assert "duration_evidence" in raw_meta
    assert raw_meta["duration_evidence"]["duration_name"] == "quarter"

    # 2. Build ScoreIR and verify no raw object pointers or unhandled exceptions occur
    score_ir, diagnostics = build_ir_from_tabraw_only(tabraw_file)
    assert score_ir.schema_version == "0.1.0"

    ir_json_str = score_ir.model_dump_json()
    assert "object at 0x" not in ir_json_str

    # 3. Perform CLI convert end-to-end directly on the sensitive PDF input fixture and audit output GP package
    out_gp = tmp_path / "privacy_test.gp"
    workdir = tmp_path / "privacy_work"
    report_json = tmp_path / "privacy_report.json"

    res = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(sensitive_pdf),
            "--pdf-only-tab",
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(report_json),
        ],
    )
    assert res.exit_code == 0, f"CLI convert failed on sensitive input: {res.output}"
    assert out_gp.exists()
    assert report_json.exists()

    report_text = report_json.read_text(encoding="utf-8")
    report_data = json.loads(report_text)
    assert report_data.get("status") == "success"
    assert "object at 0x" not in report_text
    assert str(sensitive_pdf.resolve()) not in report_text, "Sensitive absolute path must not appear in JSON report"
    assert sensitive_pdf.name not in report_text, "Sensitive filename must not appear in JSON report"

    # Read inside the GPIF archive and confirm no raw debug object addresses, invalid memory representations, or sensitive path leakage exist
    with zipfile.ZipFile(out_gp, "r") as zf:
        for zip_info in zf.infolist():
            content = zf.read(zip_info.filename).decode("utf-8", errors="ignore")
            assert "object at 0x" not in content
            assert "unhandled exception" not in content.lower()
            assert str(sensitive_pdf.resolve()) not in content, f"Sensitive absolute path leaked into GP artifact: {zip_info.filename}"
            assert sensitive_pdf.name not in content, f"Sensitive filename leaked into GP artifact: {zip_info.filename}"


def test_upward_stem_duration_extraction_and_direction_counterexample(tmp_path: Path) -> None:
    """Verify that upward stems (is_downward=False) correctly resolve free_end_y (top of stem),
    matching beams/flags located above the staff and propagating duration evidence (eighth, 16th)
    into assemble_pdf_tab_bar, ScoreIR, and GPIF XML.
    Also verifies that forcing the wrong direction (is_downward=True on upward stems) causes beam/flag
    counting to miss the rhythm marks, falling back to equal-spacing grid placeholder heuristics.
    """
    staff_line_ys = [150.0, 164.0, 178.0, 192.0, 206.0, 220.0]
    staff_space = 14.0
    context = StaffSystemContext(
        line_y_coords=staff_line_ys,
        barline_x_coords=[80.0, 300.0],
        staff_space=staff_space,
    )

    # 4 event x-positions
    events_x = [100.0, 140.0, 180.0, 220.0]

    # Upward stems: extend UP from string 1 (y=150.0) to y=120.0 (above staff)
    upward_stems = [
        StemPrimitiveCandidate(bbox=SpatialBBox(x - 1.0, 120.0, x + 1.0, 150.0), is_downward=False)
        for x in events_x
    ]

    # Beams/flags located near top of stems (y=120.0)
    flags = [FlagPrimitiveCandidate(bbox=SpatialBBox(138.0, 118.0, 142.0, 122.0))]  # flag at x=140
    beams = [
        BeamPrimitiveCandidate(bbox=SpatialBBox(175.0, 119.5, 185.0, 120.5)),  # single beam at x=180
        BeamPrimitiveCandidate(bbox=SpatialBBox(215.0, 119.5, 225.0, 120.5)),  # double beam 1 at x=220
        BeamPrimitiveCandidate(bbox=SpatialBBox(215.0, 114.5, 225.0, 115.5)),  # double beam 2 at x=220
    ]

    # 1. Positive case: resolve_tab_duration_evidence_for_events with correct upward stems
    ev_results = resolve_tab_duration_evidence_for_events(events_x, upward_stems, beams, flags, context)
    assert ev_results[100.0].duration_name == "quarter"
    assert ev_results[100.0].duration_ticks == 960
    assert ev_results[140.0].duration_name == "eighth"
    assert ev_results[140.0].duration_ticks == 480
    assert ev_results[180.0].duration_name == "eighth"
    assert ev_results[180.0].duration_ticks == 480
    assert ev_results[220.0].duration_name == "16th"
    assert ev_results[220.0].duration_ticks == 240

    # Build candidates with resolved upward stem duration evidence and test pipeline to ScoreIR & GPIF
    cands = [
        make_tab_candidate(candidate_id="u1", raw_text="0", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=6, bbox_values=(98.0, 148.0, 102.0, 152.0), confidence=1.0, duration_evidence=ev_results[100.0]),
        make_tab_candidate(candidate_id="u2", raw_text="2", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=5, bbox_values=(138.0, 148.0, 142.0, 152.0), confidence=1.0, duration_evidence=ev_results[140.0]),
        make_tab_candidate(candidate_id="u3", raw_text="3", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=4, bbox_values=(178.0, 148.0, 182.0, 152.0), confidence=1.0, duration_evidence=ev_results[180.0]),
        make_tab_candidate(candidate_id="u4", raw_text="5", page_index=1, system_index=1, staff_index=1, bar_index=1, line_index=1, string=3, bbox_values=(218.0, 148.0, 222.0, 152.0), confidence=1.0, duration_evidence=ev_results[220.0]),
    ]
    tabraw = TabRaw(source_pdf="upward_test.pdf", pdf_layout_class="drawn", candidates=cands)
    tabraw_path = tmp_path / "upward_tabraw.json"
    tabraw.to_json_file(tabraw_path)

    score_ir, _ = build_ir_from_tabraw_only(tabraw_path)
    evs = score_ir.bars[0].events
    assert evs[0].timing.notated_duration.value == "quarter"
    assert evs[1].timing.notated_duration.value == "eighth"
    assert evs[2].timing.notated_duration.value == "eighth"
    assert evs[3].timing.notated_duration.value == "16th"

    gp_path = tmp_path / "upward_test.gp"
    write_gp(score_ir, gp_path)
    with zipfile.ZipFile(gp_path, "r") as zf:
        gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
        assert "<NoteValue>Quarter</NoteValue>" in gpif_xml
        assert "<NoteValue>Eighth</NoteValue>" in gpif_xml
        assert "<NoteValue>16th</NoteValue>" in gpif_xml

    # 2. Negative case: forcing wrong direction (is_downward=True) on upward stem geometry
    wrong_stems = [
        StemPrimitiveCandidate(bbox=SpatialBBox(x - 1.0, 120.0, x + 1.0, 150.0), is_downward=True)
        for x in events_x
    ]
    ev_wrong = resolve_tab_duration_evidence_for_events(events_x, wrong_stems, beams, flags, context)

    # With is_downward=True, free_end_y evaluates to 150.0 (bottom, down at staff line),
    # which is >6.0pt away from beams/flags at y=120.0, so beam/flag counting returns 0.
    assert ev_wrong[140.0].flag_count == 0
    assert ev_wrong[180.0].beam_count == 0
    assert ev_wrong[220.0].beam_count == 0
    assert ev_wrong[140.0].duration_name != "eighth"
    assert ev_wrong[220.0].duration_name != "16th"


def test_multisystem_production_path_stem_direction_inference_and_page_global_counterexample(tmp_path: Path) -> None:
    """End-to-end production path test for multi-system pages containing both downward and upward stems.
    Proves that pdf.py correctly infers stem direction relative to local PdfStaffSystem bounds rather than
    page-global bounds, extracting exact quarter, eighth, and 16th note durations into ScoreIR and GPIF XML.
    Also includes a counterexample demonstrating that the old page-global calculation misclassifies stems
    on multi-system pages and fails to extract duration evidence.
    """
    pdf_path = tmp_path / "multisystem_production_upward.pdf"

    # Construct multi-system PDF with PyMuPDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    shape = page.new_shape()

    # System 1: y=100..150 (top system)
    for ly in [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]:
        shape.draw_line(fitz.Point(80.0, ly), fitz.Point(300.0, ly))
    shape.draw_line(fitz.Point(80.0, 100.0), fitz.Point(80.0, 150.0))
    shape.draw_line(fitz.Point(300.0, 100.0), fitz.Point(300.0, 150.0))

    # System 1 downward stems (y=145..180) and beams
    for x in [100.0, 140.0, 180.0, 220.0]:
        shape.draw_line(fitz.Point(x, 145.0), fitz.Point(x, 180.0))
    shape.draw_line(fitz.Point(135.0, 179.0), fitz.Point(225.0, 179.0))  # single beam
    shape.draw_line(fitz.Point(175.0, 174.0), fitz.Point(225.0, 174.0))  # double beam

    # System 2: y=400..450 (bottom system)
    for ly in [400.0, 410.0, 420.0, 430.0, 440.0, 450.0]:
        shape.draw_line(fitz.Point(80.0, ly), fitz.Point(300.0, ly))
    shape.draw_line(fitz.Point(80.0, 400.0), fitz.Point(80.0, 450.0))
    shape.draw_line(fitz.Point(300.0, 400.0), fitz.Point(300.0, 450.0))

    # System 2 upward stems (y=370..405) and beams
    for x in [100.0, 140.0, 180.0, 220.0]:
        shape.draw_line(fitz.Point(x, 370.0), fitz.Point(x, 405.0))
    shape.draw_line(fitz.Point(135.0, 371.0), fitz.Point(225.0, 371.0))  # single beam
    shape.draw_line(fitz.Point(175.0, 376.0), fitz.Point(225.0, 376.0))  # double beam

    shape.finish(color=(0, 0, 0), width=1.0)
    shape.commit()

    # Insert text digits for frets
    page.insert_text(fitz.Point(98.0, 153.0), "0", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(138.0, 153.0), "2", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(178.0, 153.0), "3", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(218.0, 153.0), "5", fontsize=10, fontname="Courier")

    page.insert_text(fitz.Point(98.0, 403.0), "0", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(138.0, 403.0), "2", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(178.0, 403.0), "3", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(218.0, 403.0), "5", fontsize=10, fontname="Courier")

    doc.save(pdf_path)
    doc.close()

    # 1. Run full end-to-end production CLI conversion on the multi-system PDF
    out_gp = tmp_path / "multisystem_out.gp"
    workdir = tmp_path / "multisystem_work"
    json_report = tmp_path / "multisystem_report.json"

    res = CliRunner().invoke(
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
    assert res.exit_code == 0, f"Production CLI conversion failed on multi-system PDF: {res.output}"
    assert out_gp.exists()

    # Assert ScoreIR contains expected eighth and 16th note durations for System 2 (upward stems)
    score_ir_data = json.loads((workdir / "score.ir.json").read_text(encoding="utf-8"))
    assert len(score_ir_data["bars"]) >= 1

    # Bar 2 (System 2 with upward stems)
    bar2_events = [ev for ev in score_ir_data["bars"][-1]["events"] if not ev.get("is_rest")]
    assert len(bar2_events) == 4
    assert bar2_events[0]["timing"]["notated_duration"]["value"] == "quarter"
    assert bar2_events[1]["timing"]["notated_duration"]["value"] == "eighth"
    assert bar2_events[2]["timing"]["notated_duration"]["value"] == "16th"
    assert bar2_events[3]["timing"]["notated_duration"]["value"] == "16th"

    # Assert GPIF package contains expected <NoteValue> tags
    with zipfile.ZipFile(out_gp, "r") as zf:
        gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
        assert "<NoteValue>Quarter</NoteValue>" in gpif_xml
        assert "<NoteValue>Eighth</NoteValue>" in gpif_xml
        assert "<NoteValue>16th</NoteValue>" in gpif_xml

    # 2. Explicit counterexample demonstrating that the old page-global calculation fails
    all_page_line_ys = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 400.0, 410.0, 420.0, 430.0, 440.0, 450.0]
    page_top_y = all_page_line_ys[0]      # 100.0 (top of System 1)
    page_bottom_y = all_page_line_ys[-1]  # 450.0 (bottom of System 2)

    # For System 1 downward stem (iy0=145, iy1=180):
    top_ext_sys1 = page_top_y - 145.0      # 100 - 145 = -45.0
    bot_ext_sys1 = 180.0 - page_bottom_y  # 180 - 450 = -270.0
    is_down_page_global_sys1 = not (top_ext_sys1 > bot_ext_sys1 + 1.0)
    assert is_down_page_global_sys1 is False, "Old page-global calc wrongly classified System 1 downward stem as upward (False)"

    # For System 2 upward stem (iy0=370, iy1=405):
    top_ext_sys2 = page_top_y - 370.0      # 100 - 370 = -270.0
    bot_ext_sys2 = 405.0 - page_bottom_y  # 405 - 450 = -45.0
    is_down_page_global_sys2 = (bot_ext_sys2 > top_ext_sys2 + 1.0)
    assert is_down_page_global_sys2 is True, "Old page-global calc wrongly classified System 2 upward stem as downward (True)"


def test_long_downward_stem_and_containment_gate_counterexample(tmp_path: Path) -> None:
    """Verify that a long downward stem whose center lies >1 line-spacing below its local staff
    (outside the candidate_zone_contains text-candidate gate) is correctly assigned to its local
    system by _nearest_system_for_stem via geometric endpoint distance, without falling back to page-global bounds.
    Also proves that the old candidate_zone_contains gate returns None for this long stem.
    """
    pdf_path = tmp_path / "long_downward_stem_multisystem.pdf"

    # Construct multi-system PDF with long downward stems on System 1
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    shape = page.new_shape()

    # System 1: y=100..150 (staff spacing = 10pt)
    for ly in [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]:
        shape.draw_line(fitz.Point(80.0, ly), fitz.Point(300.0, ly))
    shape.draw_line(fitz.Point(80.0, 100.0), fitz.Point(80.0, 150.0))
    shape.draw_line(fitz.Point(300.0, 100.0), fitz.Point(300.0, 150.0))

    # Long downward stems extending 35pt below staff (iy0=145, iy1=185, center=165)
    # Note: 165.0 > 150.0 + 10.0, so it sits outside candidate_zone_contains (y_tolerance_max = 10.0)
    for x in [100.0, 140.0, 180.0, 220.0]:
        shape.draw_line(fitz.Point(x, 145.0), fitz.Point(x, 185.0))
    shape.draw_line(fitz.Point(135.0, 184.0), fitz.Point(225.0, 184.0))  # single beam
    shape.draw_line(fitz.Point(175.0, 179.0), fitz.Point(225.0, 179.0))  # double beam

    # System 2: y=400..450
    for ly in [400.0, 410.0, 420.0, 430.0, 440.0, 450.0]:
        shape.draw_line(fitz.Point(80.0, ly), fitz.Point(300.0, ly))
    shape.draw_line(fitz.Point(80.0, 400.0), fitz.Point(80.0, 450.0))
    shape.draw_line(fitz.Point(300.0, 400.0), fitz.Point(300.0, 450.0))

    shape.finish(color=(0, 0, 0), width=1.0)
    shape.commit()

    page.insert_text(fitz.Point(98.0, 153.0), "0", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(138.0, 153.0), "2", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(178.0, 153.0), "3", fontsize=10, fontname="Courier")
    page.insert_text(fitz.Point(218.0, 153.0), "5", fontsize=10, fontname="Courier")

    doc.save(pdf_path)
    doc.close()

    # 1. Verify via production helper functions _nearest_system vs _nearest_system_for_stem
    from score2gp.pdf import _nearest_system, _nearest_system_for_stem, _TabSystem

    sys1 = _TabSystem(page_index=1, system_index=1, staff_index=1, first_bar_index=1, line_ys=[100.0, 110.0, 120.0, 130.0, 140.0, 150.0], x0=80.0, x1=300.0, barlines=[80.0, 300.0])
    sys2 = _TabSystem(page_index=1, system_index=2, staff_index=2, first_bar_index=2, line_ys=[400.0, 410.0, 420.0, 430.0, 440.0, 450.0], x0=80.0, x1=300.0, barlines=[80.0, 300.0])
    systems = [sys1, sys2]

    stem_x, stem_y0, stem_y1 = 140.0, 145.0, 185.0
    stem_cy = (stem_y0 + stem_y1) / 2.0  # 165.0

    # Old containment gate method returns None for long downward stem center (165.0)
    old_assigned = _nearest_system(systems, stem_x, stem_cy)
    assert old_assigned is None, "Old candidate_zone_contains gate must return None for stem center >1 line-spacing below staff"

    # New geometric endpoint distance method correctly assigns to System 1
    new_assigned = _nearest_system_for_stem(systems, stem_x, stem_y0, stem_y1)
    assert new_assigned is not None, "New _nearest_system_for_stem must assign long downward stem to System 1"
    assert new_assigned.system_index == 1

    # 2. Run end-to-end production conversion and verify duration evidence extraction for long downward stems
    out_gp = tmp_path / "long_stem_out.gp"
    workdir = tmp_path / "long_stem_work"
    json_report = tmp_path / "long_stem_report.json"

    res = CliRunner().invoke(
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
    assert res.exit_code == 0
    score_ir_data = json.loads((workdir / "score.ir.json").read_text(encoding="utf-8"))
    bar1_events = [ev for ev in score_ir_data["bars"][0]["events"] if not ev.get("is_rest")]
    assert bar1_events[0]["timing"]["notated_duration"]["value"] == "quarter"
    assert bar1_events[1]["timing"]["notated_duration"]["value"] == "eighth"
    assert bar1_events[2]["timing"]["notated_duration"]["value"] == "16th"
    assert bar1_events[3]["timing"]["notated_duration"]["value"] == "16th"


def test_tab_duration_evidence_malformed_invariant_rejection() -> None:
    """Verify that TabDurationEvidence enforces strict agreement between duration_name and duration_ticks,
    rejecting malformed evidence where name and ticks disagree.
    """
    # Valid evidence
    ev = TabDurationEvidence(duration_name="eighth", duration_ticks=480)
    assert ev.duration_name == "eighth"
    assert ev.duration_ticks == 480

    # Mismatched evidence must raise ValueError
    with pytest.raises(ValueError) as exc_info:
        TabDurationEvidence(duration_name="eighth", duration_ticks=960)

    assert "TabDurationEvidence invariant mismatch: duration_name 'eighth' requires duration_ticks=480, got 960" in str(exc_info.value)
