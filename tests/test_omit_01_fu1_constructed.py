"""Constructed P3 coverage permitted only by OMIT-01-FU1 acceptance item 4."""

from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from score2gp.notation_omr.key_signature import (
    read_bar_key_signatures, read_system_key_signature,
)
from score2gp.notation_omr.note_duration import (
    extract_page_symbols, find_staves, read_note_durations,
)


@pytest.mark.parametrize("gap_spaces", [0.5, 0.7, 1.0, 1.2, 1.4, 1.5])
def test_constructed_p3_detached_slot0_flat_has_located_refusal(gap_spaces):
    """Constructed ambiguity: reject base silent carry, always-key and always-note.

    Move a public PDF's note to the single flat's pitch and requested gap.
    This deliberately constructed geometry carries acceptance only for the
    detached slot-0 ambiguity branch, under the maintainer's 2026-10-22
    exception. Genuine Lesson 7 tests supply the displaced-note controls;
    this test makes no real-source recognition or fidelity claim.
    """
    source = Path(__file__).parent / "fixtures/pdf/omit_01/mid_system_flat.pdf"
    sidecar = read_note_durations(source, time_signature=(4, 4))
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staff = find_staves(symbols)[0][1]
    bars = sidecar["systems"][1]["bars"]
    header = read_system_key_signature(staff, symbols)
    assert (header["status"], header["fifths"]) == ("read", 1)
    accidental = next(t for t in symbols.texts if t.ident == "p0:t8")
    head = next(g for g in symbols.glyphs if g.ident == "p0:d17")
    assert accidental.text == "b"
    # The public text bbox top is -0.34583 sp, within the reader's slot-0
    # tolerance of the conventional flat top (0.2 sp); it is not a contour.
    assert (accidental.bbox[1] - staff.top) / staff.space == pytest.approx(-0.34583, abs=0.00001)
    assert 0.25 <= (accidental.bbox[0] - bars[1][0]) / staff.space <= 1.5

    dx = accidental.bbox[2] + gap_spaces * staff.space - head.bbox[0]
    dy = accidental.bbox[3] - head.cy

    def translate(box):
        return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)

    shape = replace(
        head.shape, bbox=translate(head.shape.bbox),
        fill_edges=tuple(translate(b) for b in head.shape.fill_edges),
        stroke_edges=tuple(translate(b) for b in head.shape.stroke_edges),
    )
    shifted = replace(head, bbox=translate(head.bbox), shape=shape)
    assert (shifted.bbox[0] - accidental.bbox[2]) / staff.space == pytest.approx(gap_spaces)
    assert shifted.cy == pytest.approx(accidental.bbox[3])
    constructed = replace(symbols, glyphs=[shifted if g is head else g for g in symbols.glyphs])

    key = read_bar_key_signatures(staff, constructed, bars, header)[1]
    assert (key["status"], key["fifths"], key["mode"]) == ("refused", None, None)
    assert key["reason"] == "key_signature_partial_or_ambiguous"
    assert key["sources"] == [accidental.ident]
    assert key["refuse_bar"] is True
    assert key["location"] == dict(
        page_index=staff.page_index, staff_top=round(staff.top, 3),
        staff_x0=round(staff.x0, 3), bar_index=1, bar_x0=round(bars[1][0], 3),
    )
