"""Genuine-source metadata agreement through the normal PDF-to-GP CLI."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest
from score2gp.pdf_score_metadata import read_pdf_score_metadata


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
spec = importlib.util.spec_from_file_location("omit05_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


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
