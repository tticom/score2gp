"""Real scanned sources do not pay to decode images for a font-text probe.

The wrapper observes extraction flags and forbids outlining a text-free page;
it does not replace source data or supply recognition acceptance evidence.
"""
from pathlib import Path

import pymupdf
import pytest

from score2gp.notation_omr.font_glyphs import music_font_drawings
from score2gp.notation_omr.note_duration import extract_page_symbols

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", [
    "Hal Leonard Corporation. Rock Ballads.pdf",
    "Jazz Classics for Solo Guitar- Chord Melody Arrangements.pdf",
])
def test_text_free_source_pages_skip_images_and_outlines(name):
    source = ROOT / "fixtures/private" / name
    assert source.is_file(), "required approved private source missing"

    class Probe:
        def __init__(self, page):
            self.page = page

        def __getattr__(self, name):
            return getattr(self.page, name)

        def get_text(self, kind, *, flags):
            assert not flags & pymupdf.TEXT_PRESERVE_IMAGES
            return self.page.get_text(kind, flags=flags)

        def get_svg_image(self, **kwargs):
            pytest.fail("text-free source page reached font outline parsing")

    with pymupdf.open(source) as document:
        assert len(document) > 1
        for index, page in enumerate(document):
            assert music_font_drawings(Probe(page)) == []
            symbols = extract_page_symbols(Probe(page), index)
            assert not symbols.glyphs and not symbols.segments and not symbols.texts
