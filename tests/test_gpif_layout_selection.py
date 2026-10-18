"""Layout selection is infrastructure; these public inputs make no fidelity claim."""

from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from score2gp.build_ir import build_ir_from_files
from score2gp.gp_package import extract_score_ir_from_gp, validate_gp, validate_roundtrip, write_gp
from score2gp.gpif import build_gpif
from score2gp.ir import ScoreIR, ScoreBooklet
from gpif_test_helpers import assert_production_gpif, assert_production_package, legacy_write_gp


def test_src_has_no_test_runner_layout_sniffing():
    # Mutant: restore any pytest detection, including the original switch.
    src = Path(__file__).resolve().parents[1] / "src"
    matches = [str(p.relative_to(src)) for p in src.rglob("*.py")
               if re.search(r"\bpytest\b", p.read_text(encoding="utf-8"))]
    assert matches == []
    # argv used for runtime provenance elsewhere is legitimate; writers must
    # never use process/module/path state to choose a serialization format.
    for name in ("gpif.py", "gp_package.py"):
        assert not re.search(r"\b(?:sys|argv|environ)\b", (src / "score2gp" / name).read_text())


@pytest.mark.parametrize("argv", [["score2gp"], ["pytest"], ["score2gp", "--out", "pytest-output/out.gp"]])
def test_default_layout_is_production_independent_of_process(argv, monkeypatch):
    # Mutants: flip the default, restore module detection, or sniff any argv.
    monkeypatch.setattr(sys, "argv", argv)
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    assert_production_gpif(build_gpif(score))


def test_explicit_legacy_layout_reaches_every_booklet_movement(tmp_path):
    # Mutants: ignore the explicit option, or drop it at either booklet handoff.
    booklet = ScoreBooklet.from_json_file("fixtures/public/test_gpif_score_booklets.ir.json")
    out = tmp_path / "booklet.gp"
    legacy_write_gp(booklet, out)
    with ZipFile(out) as package:
        names = [n for n in package.namelist() if n.endswith(".gpif")]
        assert len(names) == len(booklet.scores) + 1
        for name in names:
            root = ET.fromstring(package.read(name))
            assert root.find("Score/Bars") is not None
            assert root.find("Bars") is None
    assert ET.fromstring(build_gpif(booklet, layout="legacy")).find("Score/Bars") is not None
    write_gp(booklet, out)
    assert_production_package(out)


def test_cli_output_path_cannot_select_legacy_layout(tmp_path):
    # Mutant: restore argv sniffing in a fresh interpreter with no pytest import.
    out = tmp_path / "pytest-output" / "score.gp"
    result = subprocess.run([sys.executable, "-m", "score2gp.cli", "write-gp",
                             "fixtures/public/tiny_score.ir.json", "--out", str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert_production_package(out)


def test_unknown_layout_is_refused():
    # Mutant: treat misspelled options as relational or legacy silently.
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    with pytest.raises(ValueError, match="layout"):
        build_gpif(score, layout="typo")


def _change_gpif(source, destination, change):
    with ZipFile(source) as package:
        members = {name: package.read(name) for name in package.namelist()}
    root = ET.fromstring(members["Content/score.gpif"])
    change(root)
    members["Content/score.gpif"] = ET.tostring(root)
    with ZipFile(destination, "w") as package:
        for name, data in members.items():
            package.writestr(name, data)
    assert validate_gp(destination)["errors"] == []


def test_native_roundtrip_preserves_metadata_and_track_reference_checks(tmp_path):
    # Public IR tests identifier/header transport, with no recognition claim.
    # Mutants: drop native recovery/normalization, copy expected metadata, or
    # discard unresolved layout references to make round-trip validation green.
    score = build_ir_from_files(
        musicxml_path=Path("tests/fixtures/musicxml/tiny_single_bar.musicxml"),
        tabraw_path=Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json"),
        out_path=tmp_path / "source.ir.json",
    )
    before = score.model_dump()
    output = tmp_path / "native.gp"
    write_gp(score, output)
    assert_production_package(output)
    result = validate_roundtrip(output, score)
    assert result["valid"], result["errors"]
    assert score.model_dump() == before

    changed = tmp_path / "wrong-title.gp"
    _change_gpif(output, changed, lambda root: setattr(root.find("Score/Title"), "text", "wrong-metadata"))
    result = validate_roundtrip(changed, score)
    assert not result["valid"]
    assert any("metadata.title mismatch" in error for error in result["errors"])

    changed = tmp_path / "wrong-reference.gp"
    _change_gpif(output, changed, lambda root: setattr(root.find("MasterTrack/Tracks"), "text", "missing-track"))
    with pytest.raises(ValueError, match="track references"):
        validate_roundtrip(changed, score)
    assert score.model_dump() == before


@pytest.mark.parametrize("lesson", [3, 4, 5])
def test_native_reference_rests_decode_without_rest_tags(lesson):
    # Genuine approved GPIF, with the pre-existing independent bar oracle.
    # Mutant: restore the Rest-tag-only reader; genuine rest beats then fail
    # Event validation instead of decoding the oracle's ordered kinds.
    from test_dur_02_oracle import read_gp_bars

    reference = Path(f"fixtures/private/Lesson-{lesson}.gp")
    assert reference.is_file(), "required approved reference is not mounted"
    expected = read_gp_bars(reference)
    assert all(bar["events"] is not None for bar in expected)
    recovered = extract_score_ir_from_gp(reference)
    track_id = recovered.tracks[0].id
    actual = [[event.is_rest for event in bar.events if event.track_id == track_id]
              for bar in recovered.bars]
    kinds = [[event["kind"] == "rest" for event in bar["events"]] for bar in expected]
    assert actual == kinds
    assert any(any(bar) for bar in actual)
