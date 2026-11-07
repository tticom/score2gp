"""Staff-location measurement on the three image-only approved sources (RASTER-00).

Real sources only (the private corpus, counts only). Synthetic tests carry no acceptance weight and none are used.
The located counts are NOT independently verified: no reference file exists for these sources. The only check is a
viewer's count of the printed sample page (VIEWED below), so a located count is held to be at most the viewed count.

Mutants (each must fail a test below):
  DROP_STAFF_LOCATION      `measure_staff_location` reports no chains          -> test_staff_location_finds_staves_on_sample_pages
  DROP_DIGIT_BAND          `tab_digit_candidates` reports no components        -> test_tab_band_has_digit_sized_components
  CLAIM_DIGITS_READ        `tab_digit_candidates` claims identified digits     -> test_tab_band_has_digit_sized_components
"""
from pathlib import Path

import pymupdf as fitz
import pytest

from score2gp.raster_scoping import measure_page, measure_staff_location, page_image_facts, tab_digit_candidates

PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"

# name -> (sample page index, pages, notation staves viewed, TAB staves viewed, located 5-line, located 6-line)
SOURCES = {
    "LegatoLicks": (0, 1, 6, 6, 4, 6),
    "Hal Leonard Corporation. Rock Ballads": (20, 177, 6, 3, 5, 4),
    "Jazz Classics for Solo Guitar- Chord Melody Arrangements": (10, 105, 4, 4, 4, 4),
}


def _open(name):
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_RASTER_00_SOURCE_MISSING"
    return fitz.open(pdf)


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_source_is_image_only(name):
    """Rejects: treating a scanned or hand-drawn source as vector (every page: 0 drawings, exactly 1 image)."""
    index, pages, *_ = SOURCES[name]
    doc = _open(name)
    assert len(doc) == pages
    for page in doc:
        facts = page_image_facts(page)
        assert facts["vector_drawings"] == 0
        assert facts["images"] == 1


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_staff_location_finds_staves_on_sample_pages(name):
    """Rejects: a measurement that locates no staves (mutant DROP_STAFF_LOCATION) or the existing locator's 0 of 9."""
    index, _pages, viewed_notation, viewed_tab, located_5, located_6 = SOURCES[name]
    page = _open(name)[index]
    measured = measure_page(page, index + 1)
    counts = measured["location"]["counts"]
    assert (counts["notation_5_line"], counts["tab_6_line"]) == (located_5, located_6)
    assert measured["location"]["staves_located"] >= 8
    assert measured["location"]["staves_located"] <= viewed_notation + viewed_tab
    # the existing raster locator (unbroken >35%-width runs at a 128 threshold) finds fewer staves than the measurement
    assert measured["existing_locator"]["staffs"] < measured["location"]["staves_located"]


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_tab_band_has_digit_sized_components(name):
    """Rejects: a digit stage that finds nothing (DROP_DIGIT_BAND) or claims digits were read (CLAIM_DIGITS_READ)."""
    index, *_ = SOURCES[name]
    page = _open(name)[index]
    chains = [c for c in measure_staff_location(page)["chains"] if c["lines"] == 6 and c["spacing"] > 10]
    assert chains
    for chain in chains:
        result = tab_digit_candidates(page, index + 1, chain)
        assert result["digit_sized_components"] >= 10
        assert result["digits_identified"] == 0
