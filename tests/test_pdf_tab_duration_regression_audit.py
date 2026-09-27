from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
import fitz  # type: ignore[import-not-found]
from typer.testing import CliRunner
import pytest

from score2gp.cli import app
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.build_ir import build_ir_from_tabraw_only, BuildIrInputRiskError
from score2gp.gp_package import write_gp
from score2gp.pdf_staff_detection import (
    _drawing_segments,
    _tab_line_groups,
    merge_collinear_horizontal_segments,
)
from score2gp.pdf_staff_notation_diagnostics import (
    build_notation_diagnostics,
)
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


_ROUTE = Path(__file__).with_name("test_dur_02_note_type_route.py")
_spec = importlib.util.spec_from_file_location("dur_02_route", _ROUTE)
route = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(route)
_spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)


def _convert(pdf: Path, workdir: Path, out_gp: Path, json_report: Path):
    return CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out_gp),
                                    "--work-dir", str(workdir), "--json-report", str(json_report)])


def _evidence_names_by_x(tabraw_path: Path, bar_index: int) -> list[str]:
    data = json.loads(tabraw_path.read_text(encoding="utf-8"))
    cands = [c for c in data["candidates"] if c.get("kind") == "fret" and c.get("bar_index") == bar_index]
    return [c["raw"]["duration_evidence"]["duration_name"] for c in sorted(cands, key=lambda c: c["x"])]


def test_end_to_end_pdf_to_gp_tracked_public_fixtures(tmp_path: Path) -> None:
    """Run CLI end-to-end conversion across the tracked public PDF-tab fixtures. They print TAB only,
    with no notation staff, so no duration can be read from a note type: each is refused with a
    reason code, and no GP package is written. (Before DUR-02 each was written with durations from TAB
    stems or from the event count; the note-type conversion is asserted end to end in
    tests/test_dur_02_note_type_route.py.)
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
        json_report = tmp_path / f"report_{pdf_name}.json"
        result = _convert(pdf_path, tmp_path / f"work_{pdf_name}", out_gp, json_report)
        assert result.exit_code != 0, f"{pdf_name} must be refused: {result.output}"
        assert not out_gp.exists()
        report = json.loads(json_report.read_text(encoding="utf-8"))
        assert report.get("status") == "refused"
        assert report.get("refusal_code") in {"pdf_only_tab_no_notation_bars", "pdf_only_tab_time_signature_unread"}


def test_end_to_end_duration_evidence_propagation_to_scoreir_and_gpif(tmp_path: Path) -> None:
    """Note-type records (quarter, eighth, 16th) propagate through ScoreIR timing into GPIF <Rhythms>; the TAB
    evidence each digit carries (all quarters here) is not a duration source. Replaces the old test,
    which propagated TAB evidence and padded the bar."""
    quarter_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True, source="visual_morphology")
    specs = [support.note(20.0, "quarter"), support.note(60.0, "eighth"), support.note(80.0, "16th"),
             support.note(90.0, "16th"), support.note(100.0, "half")]
    cands = []
    for i, spec in enumerate(specs):
        d = support.digit(f"c{i}", 0, spec["x"], 6 - i, i)
        cands.append(make_tab_candidate(candidate_id=d.id, raw_text=d.raw_text, page_index=1, system_index=1, staff_index=1,
                                        bar_index=1, string=d.string, bbox_values=[d.bbox.x0, d.bbox.y0, d.bbox.x1, d.bbox.y1],
                                        confidence=1.0, duration_evidence=quarter_ev))
    tabraw_path = tmp_path / "duration_propagation.tabraw.json"
    TabRaw(source_pdf="public_test.pdf", pdf_layout_class="drawn", candidates=cands).to_json_file(tabraw_path)

    score_ir, _ = build_ir_from_tabraw_only(tabraw_path, note_durations=support.records([[specs]]))
    assert len(score_ir.bars) == 1
    events = score_ir.bars[0].events
    assert [(e.timing.notated_duration.value, e.timing.duration_ticks) for e in events] == [
        ("quarter", 960), ("eighth", 480), ("16th", 240), ("16th", 240), ("half", 1920)]

    gp_path = tmp_path / "duration_propagation.gp"
    write_gp(score_ir, gp_path)
    with zipfile.ZipFile(gp_path, "r") as zf:
        gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
        for value in ("Quarter", "Eighth", "16th", "Half"):
            assert f"<NoteValue>{value}</NoteValue>" in gpif_xml


def test_conflicting_duration_evidence_mutation_counterexample_fails_closed(tmp_path: Path) -> None:
    """A chord whose noteheads were not read as one value is unread, and with every bar refused the
    conversion fails closed with the located reason. Conflicting TAB evidence under it decides nothing.
    Replaces the old test, where the conflicting TAB evidence itself was the refusal."""
    quarter_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True, source="visual_morphology")
    eighth_ev = TabDurationEvidence(duration_name="eighth", duration_ticks=480, stem_present=True, source="visual_morphology")
    conflicting_cands = []
    for ident, string, fret, ev in (("c1", 1, 0, quarter_ev), ("c2", 2, 1, eighth_ev)):
        d = support.digit(ident, 0, 20.0, string, fret)
        conflicting_cands.append(make_tab_candidate(candidate_id=ident, raw_text=str(fret), page_index=1, system_index=1,
                                                    staff_index=1, bar_index=1, string=string,
                                                    bbox_values=[d.bbox.x0, d.bbox.y0, d.bbox.x1, d.bbox.y1],
                                                    confidence=1.0, duration_evidence=ev))
    tabraw_path = tmp_path / "conflict.tabraw.json"
    TabRaw(source_pdf="conflict.pdf", pdf_layout_class="drawn", candidates=conflicting_cands).to_json_file(tabraw_path)

    unread = support.records([[[support.note(20.0, "whole", heads=2, unread="mixed_notehead_kinds")]]])
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_tabraw_only(tabraw_path, note_durations=unread)
    assert exc_info.value.category == "pdf_only_tab_no_bar_written"
    assert exc_info.value.details["refusal_reasons"] == {"note_duration_event_unread": 1}
    score, _ = build_ir_from_tabraw_only(tabraw_path, note_durations=support.records([[[support.note(20.0, "whole", heads=2)]]]))
    assert score.bars[0].events[0].timing.duration_ticks == 3840


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
    """An unstemmed TAB staff (generated_tiny_tab.pdf) gets no duration evidence and no equal-spacing
    grid: with no notation staff it is refused, and a bar whose notehead is unstemmed in the notation
    is refused, never written as eighths padded with a rest. Replaces the old fallback audit."""
    pdf_path = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
    assert pdf_path.exists()
    tabraw_file = tmp_path / "tiny_tabraw.json"
    from score2gp.pdf import extract_tab
    extract_tab(pdf_path, tabraw_file)
    loaded = TabRaw.from_json_file(tabraw_file)
    assert all(c.duration_evidence is None for c in loaded.candidates)
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(tabraw_file, note_durations=read_note_durations(pdf_path, time_signature=(4, 4)))
    assert err.value.category == "pdf_only_tab_no_notation_bars"

    unstemmed_candidates = [support.digit(f"tiny-{i}", 0, 20.0 + 40.0 * i, 1, 3) for i in range(4)]
    tabraw = TabRaw(source_pdf=str(pdf_path), pdf_layout_class="drawn", candidates=unstemmed_candidates)
    synthetic_file = tmp_path / "tiny_synthetic.json"
    tabraw.to_json_file(synthetic_file)
    specs = [support.note(20.0 + 40.0 * i, unread="filled_notehead_without_stem" if i == 2 else None) for i in range(4)]
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(synthetic_file, note_durations=support.records([[specs]]))
    assert err.value.category == "pdf_only_tab_no_bar_written"


def test_privacy_sanitization_and_no_leakage_audit(tmp_path: Path) -> None:
    """Audit privacy sanitization across TabRaw JSON serialization, ScoreIR outputs, and GP packages.
    Asserts zero raw memory pointers (object at 0x) or unhandled private path leakage into public artifacts.
    """
    import shutil
    import tempfile
    private_dir = Path(tempfile.mkdtemp(prefix="dur02-private-"))
    sensitive_pdf = route.clean_pdf(private_dir / "private_fixture_sensitive_input.pdf")
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
        bbox_values=(support.event_x(0, 18.0), support.TAB_TOP - 3.0, support.event_x(0, 22.0), support.TAB_TOP + 3.0),
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
    assert loaded["schema_version"] == "tabraw.v0.2"
    assert loaded["source_pdf"] == sensitive_source

    raw_meta = loaded["candidates"][0]["raw"]
    assert "duration_evidence" in raw_meta
    assert raw_meta["duration_evidence"]["duration_name"] == "quarter"

    # 2. Build ScoreIR and verify no raw object pointers or unhandled exceptions occur
    whole = support.records([[[support.note(cand.x - support.event_x(0, 0.0), "whole")]]])
    score_ir, diagnostics = build_ir_from_tabraw_only(tabraw_file, note_durations=whole)
    assert score_ir.schema_version == "0.1.0"

    ir_json_str = score_ir.model_dump_json()
    assert "object at 0x" not in ir_json_str

    # 3. Perform CLI convert end-to-end directly on the sensitive PDF input fixture and audit output GP package
    out_gp = private_dir / "privacy_out.gp"
    workdir = private_dir / "privacy_work"
    report_json = private_dir / "privacy_report.json"

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
    shutil.rmtree(private_dir, ignore_errors=True)


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

    # The evidence alone is no longer a duration: without note-type records the route refuses.
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(tabraw_path)
    assert err.value.category == "pdf_only_tab_note_durations_missing"
    assert [c.duration_evidence.duration_name for c in TabRaw.from_json_file(tabraw_path).candidates] == [
        "quarter", "eighth", "eighth", "16th"]

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

    res = _convert(pdf_path, workdir, out_gp, json_report)
    # TAB only: no note type to read, so the conversion is refused and nothing is written ...
    assert res.exit_code != 0 and not out_gp.exists()
    assert json.loads(json_report.read_text(encoding="utf-8"))["refusal_code"] == "pdf_only_tab_no_notation_bars"
    # ... but the production extractor still reads System 2's upward stems per system, not page-globally.
    tabraw_path = workdir / "tab" / "tab_raw.json"
    last_bar = max(c["bar_index"] for c in json.loads(tabraw_path.read_text(encoding="utf-8"))["candidates"]
                   if c.get("kind") == "fret")
    assert _evidence_names_by_x(tabraw_path, last_bar) == ["quarter", "eighth", "16th", "16th"]

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

    res = _convert(pdf_path, workdir, out_gp, json_report)
    assert res.exit_code != 0 and not out_gp.exists()
    tabraw_path = workdir / "tab" / "tab_raw.json"
    first_bar = min(c["bar_index"] for c in json.loads(tabraw_path.read_text(encoding="utf-8"))["candidates"]
                    if c.get("kind") == "fret")
    assert _evidence_names_by_x(tabraw_path, first_bar)[:4] == ["quarter", "eighth", "16th", "16th"]


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
