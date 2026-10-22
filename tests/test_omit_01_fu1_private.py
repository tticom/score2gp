"""Genuine-source negative controls for the single-accidental ambiguity gate."""

from pathlib import Path
from copy import deepcopy
import tempfile

import pymupdf
import pytest

from score2gp.notation_omr.note_duration import (
    _glyph_anchor, extract_page_symbols, find_staves, read_note_durations,
)


PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"


@pytest.fixture(scope="module")
def lesson7():
    return read_note_durations(PRIVATE / "Lesson-7.pdf", time_signature=(4, 4))


def test_displaced_lesson7_accidentals_remain_notes_and_keep_the_key(lesson7):
    """Reject always-key, blanket refusal, and an enlarged barline window.

    IDs and bar indices identify the four reviewed flats and one additional
    sharp found on remeasurement. All five belong to four-head chords.
    """
    source = PRIVATE / "Lesson-7.pdf"
    sidecar = lesson7
    controls = {
        "p3:d72": (35, "p3:d69", "flat", -1),
        "p3:d73": (35, "p3:d70", "flat", -1),
        "p3:d296": (41, "p3:d292", "flat", -2),
        "p3:d375": (43, "p3:d371", "flat", -2),
        "p4:d144": (49, "p4:d141", "sharp", -2),
    }
    found = set()
    with pymupdf.open(source) as doc:
        for page_index in (3, 4):
            symbols = extract_page_symbols(doc[page_index], page_index)
            glyphs = {g.ident: g for g in symbols.glyphs}
            staves, _ = find_staves(symbols)
            for event in sidecar["events"]:
                if event["page_index"] != page_index:
                    continue
                for mark in event.get("accidentals", []):
                    ident = mark["source"]
                    if ident not in controls:
                        continue
                    bar, head_id, direction, fifths = controls[ident]
                    assert ident not in found
                    found.add(ident)
                    assert event["bar_index"] == bar
                    assert event["status"] == "read"
                    assert event["notehead"]["count"] == 4
                    assert head_id in event["notehead"]["sources"]
                    assert mark["direction"] == direction
                    staff = sorted(staves, key=lambda s: s.top)[event["system_index"]]
                    accidental, head = glyphs[ident], glyphs[head_id]
                    gap = (head.bbox[0] - accidental.bbox[2]) / staff.space
                    assert 1.3 < gap < 1.5
                    assert abs(_glyph_anchor(accidental, direction, staff.space) - head.cy) < 0.1 * staff.space
                    key = sidecar["diagnostics"]["bar_key_signatures"][bar]
                    assert (key["status"], key["fifths"], key["reason"]) == ("read", fifths, None)
                    assert ident not in key["sources"]
    assert found == set(controls)


def test_explicit_key_refusal_reaches_empty_bar_and_located_route(lesson7):
    """Reject dropping an explicit refusal between the reader and assembler.

    This is diagnostic transport coverage, not recognition acceptance: the
    refusal is injected into otherwise genuine source records, without moving
    or inventing notation. The displaced-note tests above use unmodified reads.
    """
    from score2gp.build_ir import build_ir_from_tabraw_only
    from score2gp.pdf import extract_tab

    work = PRIVATE.parents[1] / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omit01fu1-", dir=work) as directory:
        scratch = Path(directory)
        tabraw = scratch / "tab_raw.json"
        extract_tab(PRIVATE / "Lesson-7.pdf", tabraw, diagnostic_artifacts=False)
        before, baseline = build_ir_from_tabraw_only(tabraw, note_durations=lesson7)
        records = deepcopy(lesson7)
        key = deepcopy(records["diagnostics"]["bar_key_signatures"][35])
        records["diagnostics"]["bar_key_signatures"][35] = key
        key.update(status="refused", fifths=None, mode=None,
                   reason="key_signature_partial_or_ambiguous", refuse_bar=True,
                   sources=["p3:d72"])
        after, diagnostics = build_ir_from_tabraw_only(tabraw, note_durations=records)
        assert baseline.note_type_route["bars"][35]["status"] == "written"
        assert before.bars[35].events
        assert after.bars[35].events == []
        entry = diagnostics.note_type_route["bars"][35]
        assert (entry["status"], entry["reason"]) == (
            "refused", "key_signature_partial_or_ambiguous")
        assert entry["location"] == dict(page_index=3, system_index=0, bar_index=35)
        assert entry["refusal_evidence"] == dict(
            source="bar_key_signature", source_ids=["p3:d72"], location=key["location"])
        assert any(w.code == "pdf_only_tab_bar_refused" and "Bar 36 refused" in w.message
                   for w in after.warnings)
        for index, bar in enumerate(before.bars):
            if index != 35:
                assert after.bars[index] == bar


def test_close_lesson7_note_accidentals_do_not_become_ambiguous_keys(lesson7):
    """Reject refusing every slot-compatible accidental, including close ones."""
    controls = {"p1:d331": 17, "p1:d417": 19}
    found = set()
    for event in lesson7["events"]:
        for mark in event.get("accidentals", []):
            ident = mark["source"]
            if ident not in controls:
                continue
            assert ident not in found
            found.add(ident)
            assert event["bar_index"] == controls[ident]
            assert event["status"] == "read"
            assert mark["direction"] == "sharp"
            key = lesson7["diagnostics"]["bar_key_signatures"][controls[ident]]
            assert (key["status"], key["fifths"], key["reason"]) == ("read", 0, None)
            assert ident not in key["sources"]
    assert found == set(controls)
