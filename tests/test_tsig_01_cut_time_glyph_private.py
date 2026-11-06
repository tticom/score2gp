"""Read the cut-time meter glyph that stopped a TAB-only source before any bar (TSIG-01).

Measured on the whole private set (counts and codes only): one three-page TAB-only source with printed rhythm
stopped with `pdf_only_tab_time_signature_unread` (38 bars, first bar 0). The meter printed after its TAB
clef is a C with a stroke beside it, one painted drawing of two forms about 1.9 by 3.5 staff spaces. The TAB
rhythm reader read stacked numerals only. It now reads common time (C) and cut time (C with a stroke) from the
contour: the C must be open and the stroke a tall second form, level with the C, standing against it and
reaching past its top and bottom. The bar totals are never consulted, and cut time is written as printed (2/2).
The maintainer expected 4/4 for this source; the two have equal bar capacity (4 quarters), so the bar checks
cannot tell them apart. The handback reports this so the maintainer can choose.

Source: `PARANOID - BLACK SABBATH.pdf`. It has no reference `.gp`, so the bars written here are NOT
independently verified; they were checked against the printed page by eye. Synthetic tests carry no acceptance
weight; none are used. Mutants (each fails a test below):
  DROP_RULE        `pdf_tab_rhythm.ENABLE_COMMON_CUT_GLYPH` False: the source stops again, no bar written.
  STROKE_IGNORED   a classifier that returns 'common' for any open C: the glyph reads 4/4, not 2/2.
  (Tests 1-3 fail under DROP_RULE; tests 1-2 fail under STROKE_IGNORED, both run and shown failing.)
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from typer.testing import CliRunner

from score2gp import pdf_tab_rhythm as rhythm
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/private/PARANOID - BLACK SABBATH.pdf"


def _convert(tmp_path):
    assert SOURCE.is_file(), "REQUIRED_TSIG_01_SOURCE_MISSING"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(SOURCE), "--pdf-only-tab",
                                      "--out", str(tmp_path / "output.gp"), "--work-dir", str(tmp_path / "w")])
    return result, tmp_path


def test_cut_time_glyph_is_read_as_printed_and_bars_are_written(tmp_path):
    """Rejects DROP_RULE (no bar written, exit non-zero) and STROKE_IGNORED (4/4 instead of 2/2)."""
    result, build = _convert(tmp_path)
    assert result.exit_code == 0, result.output
    route = json.loads((build / "w" / "note-type-route.json").read_bytes())
    written = [b for b in route["bars"] if b["status"] == "written"]
    assert len(written) == 23
    assert len(route["bars"]) == 38
    assert {b["time_signature"] for b in route["bars"]} == {"2/2"}
    assert {b["time_signature_source"] for b in route["bars"]} == {"vector_glyphs"}
    assert {b["time_signature_basis"] for b in route["bars"]} == {"printed"}
    root = ET.fromstring(zipfile.ZipFile(build / "output.gp").read("Content/score.gpif"))
    assert {m.find("Time").text for m in root.find("MasterBars")} == {"2/2"}


def test_signature_names_the_glyph_not_the_bar_totals(tmp_path):
    """Rejects STROKE_IGNORED and DROP_RULE: the one reading is the glyph drawing at the first system, shape cut_time."""
    _, build = _convert(tmp_path)
    durations = json.loads((build / "w" / "note-durations.json").read_bytes())
    readings = durations["diagnostics"]["time_signatures"]
    assert len(readings) == 1
    assert readings[0]["status"] == "read" and readings[0]["value"] == [2, 2]
    assert readings[0]["first_bar_index"] == 0 and len(readings[0]["sources"]) == 1


def test_refused_bars_keep_their_located_reasons(tmp_path):
    """The 15 bars the evidence cannot yet settle stay refused, each with a located reason (unfinished work)."""
    _, build = _convert(tmp_path)
    route = json.loads((build / "w" / "note-type-route.json").read_bytes())
    refused = [b for b in route["bars"] if b["status"] != "written"]
    assert len(refused) == 15
    assert all(b["reason"] and b["location"].get("page_index") is not None for b in refused)


def test_drop_rule_mutant_stops_the_source(tmp_path, monkeypatch):
    """The named mutant: with the rule off the source stops at bar 0 as before, which test 1 would catch."""
    monkeypatch.setattr(rhythm, "ENABLE_COMMON_CUT_GLYPH", False)
    result, build = _convert(tmp_path)
    assert result.exit_code != 0
    assert not (build / "output.gp").exists()


def _convert_declared(tmp_path, declared):
    assert SOURCE.is_file(), "REQUIRED_TSIG_01_SOURCE_MISSING"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(SOURCE), "--pdf-only-tab", "--time-signature", declared,
                                      "--out", str(tmp_path / "output.gp"), "--work-dir", str(tmp_path / "w")])
    return result, tmp_path


def test_declared_equal_capacity_meter_is_the_maintainers_choice(tmp_path):
    """`--time-signature 4/4` (the maintainer's expectation) still converts the source as 4/4, as it did before the glyph
    was read; the glyph reading stays on record. Rejects: the glyph reading turning the declared choice into a
    conflict that refuses every bar (the regression this change first had)."""
    result, build = _convert_declared(tmp_path, "4/4")
    assert result.exit_code == 0, result.output
    root = ET.fromstring(zipfile.ZipFile(build / "output.gp").read("Content/score.gpif"))
    assert {m.find("Time").text for m in root.find("MasterBars")} == {"4/4"}
    basis = json.loads((build / "w" / "note-durations.json").read_bytes())["diagnostics"]["bar_time_signatures"]["0"]
    assert basis["unread"]["glyph_value"] == [2, 2]


def test_declared_meter_of_other_capacity_is_still_a_conflict(tmp_path):
    """Rejects: letting any declared meter override the glyph. 3/4 holds 3 quarters, the glyph's 2/2 holds 4."""
    result, build = _convert_declared(tmp_path, "3/4")
    assert result.exit_code != 0
    assert not (build / "output.gp").exists()
