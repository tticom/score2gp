"""The same engraved geometry must be recognised at ordinary and enlarged scales."""

from pathlib import Path

import pymupdf
import pytest

from score2gp.notation_omr.note_duration import _barlines, extract_page_symbols, find_staves


FIXTURES = Path(__file__).parent / "fixtures" / "pdf" / "scale_01"


@pytest.mark.parametrize("name,space", [("normal.pdf", 5.31), ("large.pdf", 17.72)])
def test_scaled_staves_and_filled_rectangle_barlines(name: str, space: float) -> None:
    with pymupdf.open(FIXTURES / name) as document:
        symbols = extract_page_symbols(document[0], 0)
    notation, tab = find_staves(symbols)
    assert len(notation) == len(tab) == 1
    assert notation[0].space == pytest.approx(space, abs=0.01)
    assert tab[0].space == pytest.approx(space, abs=0.01)
    for staff in (notation[0], tab[0]):
        bars = _barlines(staff, symbols)
        assert [x for x, _ in bars] == pytest.approx(
            [300 * space / 5.31 - 0.08 * space, 500 * space / 5.31 - 0.08 * space], abs=0.05
        )
