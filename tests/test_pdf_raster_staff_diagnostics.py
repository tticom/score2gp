from __future__ import annotations

import pytest
import fitz  # type: ignore[import-not-found]
from pathlib import Path

from score2gp.pdf_raster_staff_diagnostics import build_raster_notation_diagnostics


@pytest.fixture
def treble_staff_paper_path() -> Path:
    return Path("fixtures/private/raster-treble-clef/treble-staff-paper.pdf")


@pytest.fixture
def flash_cards_path() -> Path:
    return Path("fixtures/private/raster-treble-clef/FlashCardsValues.pdf")


def test_build_raster_notation_diagnostics_on_treble_staff_paper(treble_staff_paper_path: Path):
    assert treble_staff_paper_path.exists(), f"Required fixture {treble_staff_paper_path} is missing."

    doc = fitz.open(treble_staff_paper_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)

    assert diags["status"] == "success"
    staffs = diags["staffs"]
    assert len(staffs) >= 1

    # Check the first staff group has an opening symbol candidate
    first_staff = staffs[0]
    assert len(first_staff["y_coords"]) == 5
    assert first_staff["raster_opening_symbol_candidate"] is not None

    cand = first_staff["raster_opening_symbol_candidate"]
    assert cand["kind"] == "raster_opening_symbol_candidate"
    assert cand["width"] >= first_staff["spacing"] * 1.5
    
    staff_height = first_staff["y_coords"][4] - first_staff["y_coords"][0]
    # Verify the candidate is not just staff lines: a treble clef is taller than the staff itself.
    assert cand["height"] > staff_height
    assert cand["height"] >= first_staff["spacing"] * 3.5

    # The candidate should be near the left margin
    x0 = cand["bbox"][0]
    staff_x0 = first_staff["x0"]
    assert x0 >= staff_x0 - 20  # Roughly inside or slightly left of the left margin


def test_build_raster_notation_diagnostics_on_flash_cards(flash_cards_path: Path):
    assert flash_cards_path.exists(), f"Required fixture {flash_cards_path} is missing."

    doc = fitz.open(flash_cards_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)

    assert diags["status"] == "success"
    staffs = diags["staffs"]
    assert len(staffs) >= 1

    first_staff = staffs[0]
    assert len(first_staff["y_coords"]) == 5
    assert first_staff["raster_opening_symbol_candidate"] is not None

    cand = first_staff["raster_opening_symbol_candidate"]
    assert cand["kind"] == "raster_opening_symbol_candidate"
    assert cand["width"] >= first_staff["spacing"] * 1.5
    
    staff_height = first_staff["y_coords"][4] - first_staff["y_coords"][0]
    # Verify the candidate is not just staff lines: a treble clef is taller than the staff itself.
    assert cand["height"] > staff_height
    assert cand["height"] >= first_staff["spacing"] * 3.5
