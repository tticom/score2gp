import pytest
from pathlib import Path
import fitz
from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
from scripts.raster_diagnostics_gate_report import run_diagnostics_on_file as gate_run_diagnostics_on_file

def test_extract_notation_diagnostics_dict_whole_note() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]
    diags = extract_notation_diagnostics_dict(page, page_index=1)
    assert diags["status"] == "success"
    cands = diags.get("whole_note_candidates")
    assert cands is not None
    assert len(cands) == 2

def test_extract_notation_diagnostics_dict_half_note() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]
    diags = extract_notation_diagnostics_dict(page, page_index=1)
    assert diags["status"] == "success"
    cands = diags.get("whole_note_candidates")
    assert cands is None or len(cands) == 0

def test_raster_diagnostics_gate_report_whole_note() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    assert pdf_path.exists()
    res = gate_run_diagnostics_on_file(pdf_path)
    assert res is not None
    assert res["whole_note_candidate"] == 2

def test_raster_diagnostics_gate_report_half_note() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")
    assert pdf_path.exists()
    res = gate_run_diagnostics_on_file(pdf_path)
    assert res is not None
    assert res["whole_note_candidate"] == 0
