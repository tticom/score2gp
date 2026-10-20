"""Real-source technique placement through the normal packaged CLI output."""
import importlib.util
import hashlib
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile

import pytest
from slide_gpif import gpif_without_slides_sha256, without_verified_default_template_sizes

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
SOURCE = "Can't Find My Way Home (open chord shenanigans)"


def _oracle():
    spec = importlib.util.spec_from_file_location("fu5_oracle", ROOT / "tests/test_dur_02_oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gpif_hash(output):
    # Close before asserting: a failing assertion must not leave the package
    # locked during TemporaryDirectory cleanup on Windows.
    with zipfile.ZipFile(output) as package:
        # OMIT-05-FU1 adds verified default sizes; preserve the old whole-file
        # hash over every other byte, rejecting missing/wrong sizes first.
        data = without_verified_default_template_sizes(package.read("Content/score.gpif"))
        return hashlib.sha256(data).hexdigest()


@contextmanager
def _convert(source):
    pdf = PRIVATE / (source + ".pdf")
    reference = PRIVATE / (source + ".gp")
    assert pdf.is_file() and reference.is_file()
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="dur02fu5-", dir=work) as directory:
        scratch = Path(directory)
        output = scratch / "result.gp"
        run = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
            "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
            "--work-dir", str(scratch / "build"),
        ], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
        oracle = _oracle()
        result = oracle.compare_gp(reference, output)
        yield result, output


@pytest.fixture(scope="module")
def converted():
    with _convert(SOURCE) as result:
        yield result


def test_real_source_techniques_survive_notation_bar_placement(converted):
    """Reject the old whole-TAB-system key mapping which drops every technique."""
    result, _ = converted
    assert result["written_bars"] == 18
    assert result["refused_bars"] == [3, 6, 9]
    differences = [(d["bar_index"], d["event_index"], d["field"])
                   for d in result["differences"] if d["field"] in _oracle().TECHNIQUE_FIELDS]
    # SLIDE-01: slides whose type the page does not decide are no longer guessed. The three reference
    # slides the old fixed-type writer matched by default are now reported as slide_mark_not_extracted
    # (one refused bar, one label without a drawn stroke, one stroke end bound to no digit); every
    # other technique still matches exactly.
    assert [d for d in differences if d[2] != "slide"] == []
    assert [d for d in differences if d[2] == "slide"] == [(7, 2, "slide"), (15, 4, "slide"), (15, 12, "slide")]


def test_preserve_second_source():
    """Reject applying split-system pair selection to one-to-one TAB bars."""
    # Measured at e8bdd3d: preserve the complete GPIF, including existing
    # independent-comparator differences. This is output preservation, not a
    # reference-derived recognition target.
    with _convert("Bebop Licks in Am") as (result, output):
        assert result["written_bars"] == 14
        assert result["refused_bars"] == []
        # SLIDE-01 changes the written slides only (four shift slides now carry the shift flag); the
        # whole-GPIF digest is the new head value and the digest without slide marks is the base one.
        assert _gpif_hash(output) == (
            "b3083f043c1e20e74d090f805fe1cca27e47e419fe3fcde1122f826020f476dd")
        with zipfile.ZipFile(output) as package:
            before_sizes = without_verified_default_template_sizes(package.read("Content/score.gpif"))
            assert gpif_without_slides_sha256(before_sizes) == (
                "fda893ce3ac4a7e9dea5c40a07b4787a3d28a04bd3f71eea5e0daf7b6812af15")


@pytest.mark.parametrize("cause,fields,bars", [
    ("split_bar_placement", {"hopo_origin", "hopo_destination"}, None),  # slides: see SLIDE-01 above
    ("bounded_pair", {"hopo_origin", "hopo_destination"}, {10, 14, 18}),
    ("grace_pair", {"hopo_origin"}, {1, 5, 17}),
    ("destination_event_identity", {"hopo_destination"}, {1, 5, 17}),
    ("leading_slide", {"slide"}, {16}),
    ("printed_vibrato", {"vibrato"}, {11, 19}),
])
def test_real_source_cause(converted, cause, fields, bars):
    """Reject restoring the old implementation of each named cause."""
    result, _ = converted
    assert [(d["bar_index"], d["event_index"], d["field"])
            for d in result["differences"]
            if d["field"] in fields and (bars is None or d["bar_index"] in bars)] == []
