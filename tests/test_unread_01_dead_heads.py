"""Real-source X ownership remains refused for UNREAD-02; no synthetic evidence."""
from pathlib import Path
import tempfile

import pymupdf
import pytest

from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]


def test_every_real_x_head_is_located_including_ledger_line_heads():
    source = ROOT / "fixtures/private/G-Am-C-Lick.pdf"
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    dead = [e for e in result["events"] if e["reason"] == "dead_note_x_head"]
    # Source contour census: twenty crosses, including sixteen formerly outside rest reach.
    assert len(dead) == 20
    assert {e["bar_index"] for e in dead} == set(range(8))
    for e in dead:
        assert e["status"] == "unread" and e["written"] is None
        assert all(e["location"][k] is not None for k in
                   ("page_index", "system_index", "bar_index", "event_index"))
    assert all(c["status"] == "incomplete" for c in result["bar_checks"][:8])
    blocked = {e["rest"]["source"] for e in result["events"]
               if e["reason"] == "beam_attached_to_dead_note_x_head"}
    assert blocked
    read_beams = {source for e in result["events"] if e["status"] == "read"
                  for group in e["beams"]["sources"] for source in group.split(",")}
    assert not blocked & read_beams


@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_real_source_crosses_keep_their_located_refusal_when_scaled(scale):
    """Copy the approved source page itself; no generated notation supplies evidence."""
    source = ROOT / "fixtures/private/G-Am-C-Lick.pdf"
    assert source.is_file(), "required approved private source missing"
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-", dir=work) as directory:
        target = Path(directory) / "scaled.pdf"
        with pymupdf.open(source) as original, pymupdf.open() as derived:
            for i, page in enumerate(original):
                output = derived.new_page(width=page.rect.width * scale,
                                          height=page.rect.height * scale)
                output.show_pdf_page(output.rect, original, i)
            derived.save(target)
        result = read_note_durations(target)
        dead = [e for e in result["events"] if e["reason"] == "dead_note_x_head"]
        assert len(dead) == 20
        assert all(e["status"] == "unread" for e in dead)
        assert all(e["location"][k] is not None for e in dead for k in
                   ("page_index", "system_index", "bar_index", "event_index"))
        # This checks the cross classifier's scale, not the existing staff detector.
        # A separate frozen-base probe finds extra staff partitions at scale 2;
        # do not claim that the source's bar indices survive this transformation.
