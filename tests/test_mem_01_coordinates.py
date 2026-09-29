"""Candidate references preserve the coordinates used for symbol attachment."""

from score2gp.build_ir import _get_note_x, _get_note_y
from score2gp.ir import BoundingBox, Note
from score2gp.tabraw import TabCandidate


def test_compact_provenance_uses_original_candidate_coordinates():
    candidate = TabCandidate(
        id="digit-1", kind="fret", raw_text="5", parsed_fret=5,
        x=7, y=8, bbox=BoundingBox(page=1, x0=0, y0=0, x1=10, y1=10),
        raw={"assignment_warnings": ["example"]},
    )
    note = Note(string=1, fret=5, pitch=69, provenance=[candidate.to_provenance()])

    assert note.provenance[0].raw == {}
    assert _get_note_x(note, {candidate.id: candidate}) == 7
    assert _get_note_y(note, {candidate.id: candidate}) == 8


def test_compact_provenance_uses_bbox_when_candidate_coordinate_is_missing():
    candidate = TabCandidate(
        id="digit-2", kind="fret", raw_text="5", parsed_fret=5,
        bbox=BoundingBox(page=1, x0=0, y0=0, x1=10, y1=10),
    )
    note = Note(string=1, fret=5, pitch=69, provenance=[candidate.to_provenance()])

    assert _get_note_x(note, {candidate.id: candidate}) == 5
    assert _get_note_y(note, {candidate.id: candidate}) == 5
