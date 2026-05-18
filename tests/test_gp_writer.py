from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from score2gp.gp_package import compare_gp, inspect_gp, validate_gp, write_gp
from score2gp.ir import ScoreIR


def test_write_gp_creates_valid_zip(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    out = tmp_path / "tiny.gp"
    warnings = write_gp(score, out)

    assert warnings == []
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        assert "VERSION" in zf.namelist()
        assert "Content/score.gpif" in zf.namelist()
        ET.fromstring(zf.read("Content/score.gpif"))


def test_validate_and_inspect_generated_gp(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    out = tmp_path / "tiny.gp"
    write_gp(score, out)

    validation = validate_gp(out)
    assert validation["is_zip"] is True
    assert validation["xml_well_formed"] is True
    assert validation["errors"] == []

    summary = inspect_gp(out)
    assert summary["tracks"] == ["Guitar"]
    assert summary["tempo"] == "66"
    assert summary["time_signatures"] == ["12/8"]
    assert summary["bar_count"] == 1
    assert summary["note_count"] == 2
    assert summary["chord_symbols"] == ["E"]
    assert summary["techniques"] == ["slide"]


def test_compare_generated_gp_semantics(tmp_path) -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    expected = tmp_path / "expected.gp"
    actual = tmp_path / "actual.gp"
    write_gp(score, expected)
    write_gp(score, actual)

    comparison = compare_gp(expected, actual)
    assert comparison["matches"] is True
    assert comparison["differences"] == {}
