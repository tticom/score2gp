import pytest
import fitz
from score2gp.pdf_staff_notation_diagnostics import extract_measure_grid_diagnostics_dict

def test_measure_grid_quarter_note_exact_bounds():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")
    diag = extract_measure_grid_diagnostics_dict(doc[0], 1)

    assert diag["pages"][0]["diagnostic_status"] == "pass"
    systems = diag["pages"][0]["systems"]
    assert len(systems) == 1
    staves = systems[0]["staves"]
    assert len(staves) == 1

    staff = staves[0]
    regions = staff["measure_regions"]

    # 1 region starting at staff x0 (50.0) and ending at the trailing barline (550.0)
    assert len(regions) == 1
    assert regions[0]["start_x"] == 50.0
    assert regions[0]["end_x"] == 550.0

def test_measure_grid_multi_staff_regions_per_staff():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_multi_staff.pdf")
    diag = extract_measure_grid_diagnostics_dict(doc[0], 1)

    assert diag["pages"][0]["diagnostic_status"] == "pass"
    staves = diag["pages"][0]["systems"][0]["staves"]
    assert len(staves) == 2

    for staff in staves:
        regions = staff["measure_regions"]
        # Internal barline at 250.0 and staff end at 545.28 means 2 regions
        assert len(regions) == 2

        # First region
        assert regions[0]["start_x"] == 50.0
        assert regions[0]["end_x"] == 250.0

        # Second region
        assert regions[1]["start_x"] == 250.0
        assert regions[1]["end_x"] == 545.28

def test_measure_grid_ledger_lines_no_false_grids():
    doc = fitz.open("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")
    diag = extract_measure_grid_diagnostics_dict(doc[0], 1)

    assert diag["pages"][0]["diagnostic_status"] == "pass"
    staff = diag["pages"][0]["systems"][0]["staves"][0]
    regions = staff["measure_regions"]

    # Ledger line stems must not split the region. It should remain 1 region.
    assert len(regions) == 1
    assert regions[0]["start_x"] == 50.0
    assert regions[0]["end_x"] == 550.0

def test_measure_grid_failure_handling_is_private_safe():
    # Pass a None instead of a page to trigger an exception
    diag = extract_measure_grid_diagnostics_dict(None, 1)

    assert diag["diagnostic_status"] == "fail"
    assert len(diag["failure_reasons"]) >= 1
    # Ensure it's a fixed string, not a raw Exception string
    assert diag["failure_reasons"][0] in ["measure_grid_extraction_failed", "measure_grid_dependency_failed"]
    assert "NoneType" not in diag["failure_reasons"][0]

def test_measure_grid_double_barline_collapsed():
    doc = fitz.open("tests/fixtures/pdf/generated_paired_notation_tab_system_double_barline.pdf")
    diag = extract_measure_grid_diagnostics_dict(doc[0], 1)

    assert diag["pages"][0]["diagnostic_status"] == "pass"
    staff = diag["pages"][0]["systems"][0]["staves"][0]
    regions = staff["measure_regions"]

    # Ensure there's no tiny region created by the double barline.
    for r in regions:
        # A double barline gap is usually < 10 units.
        # A real measure is typically much wider.
        assert r["end_x"] - r["start_x"] > 10.0, f"Found false empty region: {r}"
