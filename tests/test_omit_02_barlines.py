"""Public engraved-score PDF to GPIF barline regressions.

The PDFs are derived from a standard notation and TAB source. The six marks
are drawn as ordinary notation, independently of the production stroke table.
"""

import os
import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
import pymupdf
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.build_ir import build_ir_from_tabraw_only
from score2gp.gp_package import write_gp
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import (_classify_wide_notation_pair, _is_thin_barline_pair,
                         read_notation_barline_signals)
from score2gp.tabraw import TabRaw, make_tab_candidate


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/pdf/omit_02"


@pytest.mark.parametrize(("width_a", "width_b", "gap"), [
    (0.68, 0.68, 3.201), (0.449, 0.449, 2.38),
    (1.001, 1.001, 2.38),
])
def test_double_pair_rejects_values_just_outside_measured_bounds(width_a, width_b, gap):
    assert not _is_thin_barline_pair("rect_edge", width_a, "rect_edge", width_b, gap)
    source_root = os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))
    code = ("from score2gp.pdf import _is_thin_barline_pair; "
            f"print(_is_thin_barline_pair('rect_edge',{width_a},'rect_edge',{width_b},{gap}))")
    result = subprocess.run([sys.executable, "-c", code],
                            env={**os.environ, "PYTHONPATH": source_root},
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize(("thin_width", "thick_width", "gap"), [
    (0.449, 1.875, 3.375), (1.001, 1.875, 3.375),
    (0.6, 1.499, 3.375), (0.6, 3.001, 3.375),
    (0.6, 1.875, 1.999), (0.6, 1.875, 5.001),
])
def test_wide_pair_rejects_values_just_outside_measured_bounds(thin_width, thick_width, gap):
    strokes = [SimpleNamespace(x0=100.0, x1=100.0),
               SimpleNamespace(x0=100.0 + gap, x1=100.0 + gap)]
    kind, _ = _classify_wide_notation_pair(
        strokes, [], [], 80.0, 100.0, True, (thin_width, thick_width), gap)
    assert kind is None


def test_mid_piece_undotted_wide_pair_is_refused():
    strokes = [SimpleNamespace(x0=100.0, x1=100.0),
               SimpleNamespace(x0=103.375, x1=103.375)]
    kind, _ = _classify_wide_notation_pair(
        strokes, [], [], 80.0, 100.0, False, (0.6, 1.875), 3.375)
    assert kind is None
    source_root = os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))
    code = ("from types import SimpleNamespace; "
            "from score2gp.pdf import _classify_wide_notation_pair; "
            "strokes=[SimpleNamespace(x0=x,x1=x) for x in (100.0,103.375)]; "
            "print(_classify_wide_notation_pair(strokes,[],[],80,100,False,"
            "(0.6,1.875),3.375)[0])")
    result = subprocess.run([sys.executable, "-c", code],
                            env={**os.environ, "PYTHONPATH": source_root},
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "None"

    # Exercise the PDF reader as well: the same painted final pair is made
    # interior by a later-system count, without changing its geometry.
    pdf = FIXTURES / "final_heavy.pdf"
    durations = read_note_durations(pdf, time_signature=(4, 4))
    durations["systems"][0]["bar_count"] += 1
    signals = read_notation_barline_signals(pdf, durations)
    pair = next(signal for signal in signals if signal["bar_index"] == 2)
    assert (pair["status"], pair["kind"], pair["reason"]) == (
        "refused", None, "pdf_barline_pair_kind_unresolved")


def test_one_music_font_dot_cannot_be_called_a_final_barline():
    strokes = [SimpleNamespace(x0=100.0, x1=100.0),
               SimpleNamespace(x0=103.375, x1=103.375)]
    glyphs = [("Bravura", 0xe044, (0, 0, 0, 0), 96.0, 90.0,
               pymupdf.Rect(96.0, 82.0, 97.5, 97.0))]
    kind, candidates = _classify_wide_notation_pair(
        strokes, [], glyphs, 80.0, 100.0, True, (0.6, 1.875), 3.375)
    assert kind is None and len(candidates) == 1


def test_cli_mocked_extraction_without_tabraw_file_preserves_success(tmp_path):
    """Optional barline enrichment must not reopen an absent extraction artifact."""
    spec = importlib.util.spec_from_file_location(
        "pdf_tab_route_support", ROOT / "tests/test_pdf_tab_route_support.py"
    )
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    specs = [support.note(20.0, "half"), support.note(80.0),
             support.note(120.0, "eighth"), support.note(140.0, "eighth")]
    tabraw = TabRaw(candidates=[support.digit(f"c-{i}", 0, item["x"], 1, i)
                            for i, item in enumerate(specs)])
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    report_path = tmp_path / "report.json"
    with patch("score2gp.cli.extract_tab_file", return_value={"candidates_count": 4}), \
            patch("score2gp.cli.inspect_pdf_file", return_value={}), \
            patch("score2gp.build_ir.TabRaw.from_json_file", return_value=tabraw), \
            patch("score2gp.notation_omr.note_duration.read_note_durations",
                  return_value=support.records([[specs]])), \
            patch("score2gp.pdf.read_notation_barline_signals",
                  side_effect=AssertionError("barline reader must not run")):
        result = CliRunner().invoke(app, ["convert", "--pdf",
                                          "tests/fixtures/pdf/generated_tiny_tab.pdf",
                                          "--pdf-only-tab", "--out", str(out_gp),
                                          "--work-dir", str(workdir),
                                          "--json-report", str(report_path)])
    assert result.exit_code == 0, report_path.read_text(encoding="utf-8")
    assert out_gp.exists()
    assert not (workdir / "tab" / "tab_raw.json").exists()


@pytest.mark.parametrize(("source", "expected"), [
    ("standard_single", [(False, False, None), (False, False, None)]),
    ("standard_double", [(True, False, None), (False, False, None)]),
    ("repeat_dots", [(False, False, 2), (False, False, None)]),
    ("repeat_glyph_final", [(False, False, None), (False, False, 2)]),
    ("repeat_start", [(False, False, None), (False, True, None)]),
    ("final_heavy", [(False, False, None), (False, False, None)]),
    ("thick_single", [(False, False, None), (False, False, None)]),
    ("system_start_bracket", [(False, False, None), (False, False, None)]),
])
def test_engraved_barline_reaches_master_gpif(source, expected):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omit02_", dir=work) as directory:
        scratch = Path(directory)
        pdf = scratch / "input.pdf"
        gp = scratch / "output.gp"
        shutil.copyfile(FIXTURES / f"{source}.pdf", pdf)
        source_root = os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(gp),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": source_root}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        with ZipFile(gp) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
        bars = root.find("MasterBars").findall("MasterBar")
        flags = [(bar.find("DoubleBar") is not None,
                  bar.find("RepeatStart") is not None,
                  int(bar.find("Repeat").get("count")) if bar.find("Repeat") is not None else None)
                 for bar in bars]
        assert flags == expected
        if source in {"standard_double", "repeat_dots", "repeat_glyph_final", "repeat_start", "final_heavy", "thick_single"}:
            ir = json.loads((scratch / "work/score.ir.json").read_text(encoding="utf-8"))
            code = {"standard_double": "pdf_double_barline_read",
                    "repeat_dots": "pdf_repeat_end_barline_read",
                    "repeat_glyph_final": "pdf_repeat_end_barline_read",
                    "repeat_start": "pdf_repeat_start_barline_read",
                    "final_heavy": "pdf_end_barline_read",
                    "thick_single": "pdf_barline_thick_single_kind_unresolved"}[source]
            evidence = [warning for warning in ir["warnings"] if warning["code"] == code]
            assert len(evidence) == 1
            strokes = evidence[0]["provenance"][0]["raw"]["strokes"]
            assert len(strokes) >= (1 if source == "thick_single" else 2)
            assert all(stroke["primitive_id"] for stroke in strokes)
            if source == "repeat_glyph_final":
                assert len([stroke for stroke in strokes
                            if stroke["primitive_id"].startswith("text-Bravura-e044")]) == 2
                assert bars[-1].findtext("Barline") != "End"
        if source == "final_heavy":
            assert bars[-1].find("Barline") is None


@pytest.mark.parametrize("carry_evidence", [False, True])
def test_saved_tabraw_converts_without_source_pdf(tmp_path, carry_evidence):
    """The public engraved source supplies the evidence; IR building only sees TabRaw."""
    pdf = tmp_path / "source.pdf"
    shutil.copyfile(FIXTURES / "standard_double.pdf", pdf)
    tabraw_path = tmp_path / "tab_raw.json"
    source_durations = read_note_durations(pdf, time_signature=(4, 4))
    spec = importlib.util.spec_from_file_location("route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    digit = support.digit("c1", 0, 20.0, 1, 0)
    candidate = make_tab_candidate(candidate_id="c1", raw_text="0", page_index=1,
                                   system_index=1, staff_index=1, bar_index=1, string=1,
                                   bbox_values=[digit.bbox.x0, digit.bbox.y0, digit.bbox.x1, digit.bbox.y1],
                                   confidence=1.0)
    tabraw = TabRaw(source_pdf=str(tmp_path / "missing.pdf"), candidates=[candidate])
    if carry_evidence:
        signals = read_notation_barline_signals(pdf, source_durations)
        assert any(signal["kind"] == "double" for signal in signals)
        assert all(stroke["primitive_id"] for signal in signals for stroke in signal["strokes"])
        tabraw.structural_signals["notation_barlines"] = signals
    tabraw.to_json_file(tabraw_path)
    pdf.unlink()

    score, _ = build_ir_from_tabraw_only(
        tabraw_path, note_durations=support.records([[[support.note(20.0, "whole")]]]))
    gp = tmp_path / "result.gp"
    write_gp(score, gp)
    with ZipFile(gp) as package:
        root = ET.fromstring(package.read("Content/score.gpif"))
    actual = [i for i, bar in enumerate(root.find(".//MasterBars").findall("MasterBar"), 1)
              if bar.find("DoubleBar") is not None]
    assert actual == ([1] if carry_evidence else [])
    warnings = [w for w in score.warnings if w.code == "barline_evidence_unavailable"]
    assert len(warnings) == (0 if carry_evidence else 1)
    if warnings:
        assert warnings[0].provenance[0].page == 1
        assert warnings[0].provenance[0].bar_index == 1
