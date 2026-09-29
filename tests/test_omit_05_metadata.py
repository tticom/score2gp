"""Public page-one PDF metadata and production GPIF checks."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pymupdf

from score2gp.pdf_score_metadata import read_pdf_score_metadata


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/pdf/omit_05/engraved_title_credit.pdf"
spec = importlib.util.spec_from_file_location("omit05_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def test_engraved_pdf_reaches_final_gpif():
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        source = scratch / "input.pdf"  # neutral path exercises production extractor
        shutil.copyfile(FIXTURE, source)
        output = scratch / "output.gp"
        source_root = os.environ.get("SCORE2GP_OMIT05_MUTANT_SRC", str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": source_root},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        metadata = oracle.read_gp_metadata(output)
        assert metadata == {
            "Title": "Study in Motion", "Music": "Ada Clarke",
            "Copyright": "Copyright 2026 Example Press",
            "FirstPageHeader": ("%TITLE%", "%SUBTITLE%", "%ARTIST%", "%ALBUM%", "%WORDS&MUSIC%"),
            "FirstPageFooter": ("%page%", "%pages%"), "PageHeader": (),
            "PageFooter": ("%page%", "%pages%"),
        }
        assert all(metadata["Music"] not in value and metadata["Title"] not in value
                   and metadata["Copyright"] not in value
                   for value in oracle.read_gp_template_text(output).values())


def test_page_furniture_tempo_and_section_label_are_not_metadata():
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        path = Path(directory) / "negative.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=595, height=842)
            page.insert_text((250, 18), "Running Header", fontsize=10)
            page.insert_text((50, 70), "= 120", fontsize=12)
            page.insert_text((50, 125), "Lesson 4", fontsize=15)
            page.insert_text((260, 818), "Page 1", fontsize=10)
            document.save(path)
        result = read_pdf_score_metadata(path)
        assert (result.title, result.music, result.copyright) == ("", "", "")
        assert any("pdf_title_unreadable: page 1" in item for item in result.diagnostics)


def test_equal_large_centered_lines_refuse_title():
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        path = Path(directory) / "ambiguous.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=595, height=842)
            for y, label in ((35, "First Line"), (70, "Second Line")):
                page.insert_text(((595 - pymupdf.get_text_length(label, fontsize=24)) / 2, y),
                                 label, fontsize=24)
            document.save(path)
        result = read_pdf_score_metadata(path)
        assert result.title == ""
        assert any(item.startswith("pdf_title_ambiguous: page 1 bbox") for item in result.diagnostics)


def test_centered_subtitle_without_music_attribution_refuses_credit():
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        path = Path(directory) / "subtitle.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=595, height=842)
            for y, label, size in ((45, "Evening Study", 24), (65, "For Guitar", 12)):
                page.insert_text(((595 - pymupdf.get_text_length(label, fontsize=size)) / 2, y),
                                 label, fontsize=size)
            document.save(path)
        result = read_pdf_score_metadata(path)
        assert result.title == "Evening Study"
        assert result.music == ""
        assert any(item.startswith("pdf_music_unreadable: page 1") for item in result.diagnostics)
