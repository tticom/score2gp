"""Genuine PDF title transport through both unified compiler entry points.

These tests judge metadata only; empty timelines make no recognition claim.
No reference value enters production and private output stays under work/.
"""

from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pymupdf
import pytest

from score2gp.gpif_builder import GPIFBuilder
from score2gp.scoreir_compiler import ScoreIRCompiler


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _source(name):
    source = PRIVATE / name
    if not source.is_file():
        pytest.skip("private corpus absent")
    return source


def _compile(route, **kwargs):
    if route == "compiler":
        return ScoreIRCompiler().compile([], [], **kwargs)
    return GPIFBuilder().compile_to_score_ir([], [], **kwargs)


def _packaged_title(score):
    scratch = ROOT / "work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        output = Path(directory) / "score.gp"
        GPIFBuilder().write_gp_file(score, output)
        with zipfile.ZipFile(output) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
        return (root.findtext("Score/Title") or "").encode("utf-8")


@pytest.mark.parametrize("route", ["compiler", "builder"])
def test_missing_source_leaves_final_title_empty_with_route_diagnostic(route):
    """Reject restoring the placeholder, including only in the packaged GPIF."""
    score = _compile(route)
    assert score.metadata.title == ""
    assert _packaged_title(score) == b""
    assert any(w.code == "scoreir_title_source_missing"
               and "scoreir_compiler.compile" in w.message for w in score.warnings)


@pytest.mark.parametrize("route", ["compiler", "builder"])
def test_readable_private_title_keeps_source_bytes_in_final_gpif(route):
    """Reject a placeholder, dropped source forwarding, or an always-empty title."""
    source = _source("Lesson-3.pdf")
    # Independent PDF text read: the first line is the engraved score title.
    # Assert the geometry so a corpus change cannot silently select a new line.
    with pymupdf.open(source) as document:
        page = document[0]
        spans = page.get_text("dict")["blocks"][0]["lines"][0]["spans"]
        assert all(span["size"] >= 24 for span in spans)
        expected = "".join(span["text"] for span in spans).encode("utf-8")
    assert expected
    with zipfile.ZipFile(_source("Lesson-3.gp")) as package:
        reference = ET.fromstring(package.read("Content/score.gpif"))
    assert (reference.findtext("Score/Title") or "").encode("utf-8") == expected
    score = _compile(route, source_pdf=source)
    assert score.metadata.title.encode("utf-8") == expected
    assert _packaged_title(score) == expected
    assert not score.warnings


@pytest.mark.parametrize("route", ["compiler", "builder"])
def test_unreadable_private_title_stays_empty_with_page_and_route(route):
    """Reject using the filename/placeholder or dropping the located refusal."""
    source = _source("5_Grateful_Dead_Intros.pdf")
    score = _compile(route, source_pdf=source)
    assert score.metadata.title == ""
    assert _packaged_title(score) == b""
    assert any(w.code == "pdf_title_unreadable" and "page 1" in w.message
               and "scoreir_compiler.compile" in w.message for w in score.warnings)
