from __future__ import annotations

import json
from pathlib import Path

from score2gp.tabraw import TabCandidate
from score2gp.pdf_only_chord_event_grouper import PdfOnlyChordEventGrouper
from score2gp.build_ir import build_ir_from_tabraw_only


def test_pdf_only_chord_event_grouper_groups_small_x_offsets_across_strings() -> None:
    # 1. Create candidates within 10.0 pt offset on different strings
    candidates = [
        TabCandidate(
            id="c-1",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=1,
            raw_text="5",
            parsed_fret=5,
            x=10.0,
            y=20.0,
            confidence=0.9,
        ),
        TabCandidate(
            id="c-2",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=2,
            raw_text="7",
            parsed_fret=7,
            x=19.0,  # 9.0 pt delta (<= 10.0)
            y=20.0,
            confidence=0.9,
        ),
    ]

    grouper = PdfOnlyChordEventGrouper(tolerance=10.0)
    groups = grouper.group_bar_candidates(candidates)

    # They should group into 1 event (chord) containing both candidates
    assert len(groups) == 1
    assert len(groups[0]) == 2
    assert {c.id for c in groups[0]} == {"c-1", "c-2"}


def test_pdf_only_chord_event_grouper_keeps_large_x_gaps_sequential() -> None:
    # 2. Create candidates with delta > 10.0 pt
    candidates = [
        TabCandidate(
            id="c-1",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=1,
            raw_text="5",
            parsed_fret=5,
            x=10.0,
            y=20.0,
            confidence=0.9,
        ),
        TabCandidate(
            id="c-2",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=2,
            raw_text="7",
            parsed_fret=7,
            x=21.0,  # 11.0 pt delta (> 10.0)
            y=20.0,
            confidence=0.9,
        ),
    ]

    grouper = PdfOnlyChordEventGrouper(tolerance=10.0)
    groups = grouper.group_bar_candidates(candidates)

    # They should remain sequential (2 events)
    assert len(groups) == 2
    assert len(groups[0]) == 1
    assert groups[0][0].id == "c-1"
    assert len(groups[1]) == 1
    assert groups[1][0].id == "c-2"


def test_pdf_only_chord_event_grouper_splits_duplicate_string_candidates() -> None:
    # 3. Create duplicate string candidates close in x (<= 10.0 pt delta)
    candidates = [
        TabCandidate(
            id="c-1",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=1,
            raw_text="5",
            parsed_fret=5,
            x=10.0,
            y=20.0,
            confidence=0.9,
        ),
        TabCandidate(
            id="c-2",
            kind="fret",
            page_index=1,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=1,  # Same string!
            raw_text="7",
            parsed_fret=7,
            x=15.0,  # 5.0 pt delta (<= 10.0)
            y=20.0,
            confidence=0.9,
        ),
    ]

    grouper = PdfOnlyChordEventGrouper(tolerance=10.0)
    groups = grouper.group_bar_candidates(candidates)

    # They must not group (duplicate string split safety) -> 2 sequential events
    assert len(groups) == 2
    assert len(groups[0]) == 1
    assert groups[0][0].id == "c-1"
    assert len(groups[1]) == 1
    assert groups[1][0].id == "c-2"


def test_pdf_only_chord_event_grouper_does_not_cross_source_bar_identity(tmp_path) -> None:
    # 4. Verify that when candidates are built via build_ir_from_tabraw_only,
    # grouping does not stack candidates across page/system/staff/bar boundaries.
    tabraw_data = {
        "schema_version": "tabraw.v0.1",
        "source_pdf": "test.pdf",
        "pdf_layout_class": "drawn",
        "pdf_layout_warnings": [],
        "candidates": [
            {
                "id": "c-1",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 1,  # Bar 1
                "string": 1,
                "raw_text": "5",
                "parsed_fret": 5,
                "x": 10.0,
                "y": 20.0,
                "confidence": 0.9,
            },
            {
                "id": "c-2",
                "kind": "fret",
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "bar_index": 2,  # Bar 2
                "string": 2,
                "raw_text": "7",
                "parsed_fret": 7,
                "x": 12.0,  # 2.0 pt delta, but different bars
                "y": 20.0,
                "confidence": 0.9,
            },
        ],
        "warnings": [],
    }
    tabraw_file = tmp_path / "tabraw_boundary.json"
    tabraw_file.write_text(json.dumps(tabraw_data), encoding="utf-8")

    score, diagnostics = build_ir_from_tabraw_only(tabraw_file)

    # Must produce 2 distinct bars, each with 1 event
    assert len(score.bars) == 2
    assert len(score.bars[0].events) == 1
    assert score.bars[0].events[0].notes[0].fret == 5
    assert len(score.bars[1].events) == 1
    assert score.bars[1].events[0].notes[0].fret == 7
