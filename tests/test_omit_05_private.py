"""Genuine-source metadata agreement through the normal PDF-to-GP CLI."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import zipfile

import pytest
from score2gp.pdf_score_metadata import read_pdf_score_metadata


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
spec = importlib.util.spec_from_file_location("omit05_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


@pytest.mark.parametrize("index", range(3, 8))
def test_private_template_sizes_without_reference_access(index):
    """Reject missing sizes, swapped field sizes and runtime reference reads.

    Domain evidence is the genuine PDF through the production CLI against its
    app-created reference. The audit hook is supplemental I/O isolation only.
    """
    source = PRIVATE / f"Lesson-{index}.pdf"
    reference = PRIVATE / f"Lesson-{index}.gp"
    assert source.is_file() and reference.is_file(), "required approved private pair missing"
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "produced.gp"
        (scratch / "sitecustomize.py").write_text(textwrap.dedent('''
            import os
            from pathlib import Path
            import sys
            allowed = Path(__file__).resolve().parent
            def no_reference(event, args):
                if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(args[0]))
                    if path.suffix.lower() in {".gp", ".gpx", ".gpif"} and not path.resolve().is_relative_to(allowed):
                        raise RuntimeError("reference access forbidden during conversion")
            sys.addaudithook(no_reference)
        '''), encoding="utf-8")
        source_root = os.environ.get("SCORE2GP_OMIT05_MUTANT_SRC", str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": os.pathsep.join((str(scratch), source_root))},
            text=True, capture_output=True,
        )
        # Do not include private conversion output in an assertion failure.
        reference_read_blocked = "reference access forbidden during conversion" in result.stderr
        assert result.returncode == 0, (
            f"conversion exit code {result.returncode}; reference_read_blocked={reference_read_blocked}"
        )
        differences = oracle.compare_gp_metadata(reference, output)
        assert not differences, sorted(differences)

        # Challenge the oracle on this freshly converted genuine source. A
        # comparator that ignores CSS must fail even with a correct writer.
        with zipfile.ZipFile(output) as package:
            gpif = package.read("Content/score.gpif")
        controls = [
            (re.sub(rb'font-size:\d+pt;', b'', gpif),
             {f"{field}.font_sizes" for field in
              ("FirstPageHeader", "FirstPageFooter", "PageFooter")}),
            (gpif.replace(b"font-size:35pt", b"font-size:SWAPpt")
                 .replace(b"font-size:12pt", b"font-size:35pt")
                 .replace(b"font-size:SWAPpt", b"font-size:12pt"),
             {"FirstPageHeader.font_sizes"}),
        ]
        for changed, expected_fields in controls:
            assert changed != gpif
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as package:
                package.writestr("Content/score.gpif", changed)
            assert set(oracle.compare_gp_metadata(reference, buffer.getvalue())) == expected_fields


@pytest.mark.parametrize("name", ["Derek Trucks BB King", "Melodic Soloing Masterclass", "Ex 2 Hands Up"])
def test_private_copyright_reader_never_returns_gp_rights_boilerplate(name):
    source, reference = PRIVATE / f"{name}.pdf", PRIVATE / f"{name}.gp"
    if not source.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    reading = read_pdf_score_metadata(source)
    expected = oracle.read_gp_metadata(reference)["Copyright"]
    assert "All Rights Reserved - International Copyright Secured" not in reading.copyright
    assert reading.copyright == expected or (
        not reading.copyright and
        any(item.startswith("pdf_copyright_ambiguous: page 1 bbox") for item in reading.diagnostics)
    )


@pytest.mark.parametrize("name", [*(f"Lesson-{index}" for index in range(3, 8)),
                                "Can't Find My Way Home (open chord shenanigans)"])
def test_private_source_metadata_matches_reference(name):
    source, reference = PRIVATE / f"{name}.pdf", PRIVATE / f"{name}.gp"
    if not source.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "produced.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        assert oracle.compare_gp_metadata(reference, output) == {}
        metadata = oracle.read_gp_metadata(output)
        assert all(metadata["Music"] not in value for value in oracle.read_gp_template_text(output).values()
                   if metadata["Music"])
