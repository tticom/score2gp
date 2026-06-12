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

    pages = res.get("whole_note_candidate_pages", [])
    assert len(pages) == 1
    assert pages[0]["page_index"] == 1
    assert pages[0]["whole_note_candidate"] == 2

    locations = res.get("whole_note_candidate_locations", [])
    assert len(locations) == 2
    loc1 = locations[0]
    assert loc1["page_index"] == 1
    assert len(loc1["bbox"]) == 4
    assert "pitch" not in loc1
    assert "duration" not in loc1

def test_raster_diagnostics_gate_report_half_note() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")
    assert pdf_path.exists()
    res = gate_run_diagnostics_on_file(pdf_path)
    assert res is not None
    assert res["whole_note_candidate"] == 0
    assert len(res.get("whole_note_candidate_pages", [])) == 0
    assert len(res.get("whole_note_candidate_locations", [])) == 0

def test_raster_diagnostics_gate_report_negative_noise() -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf")
    assert pdf_path.exists()
    res = gate_run_diagnostics_on_file(pdf_path)
    assert res is not None
    assert res["whole_note_candidate"] == 0
    assert len(res.get("whole_note_candidate_pages", [])) == 0
    assert len(res.get("whole_note_candidate_locations", [])) == 0
