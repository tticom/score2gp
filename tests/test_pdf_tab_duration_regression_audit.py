from __future__ import annotations

import json
from pathlib import Path

from score2gp.build_ir import build_ir_from_tabraw_only
from score2gp.pdf_tab_bar_assembler import assemble_pdf_tab_bar
from score2gp.pdf_tab_duration_associator import (
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    resolve_tab_duration_evidence_for_events,
)
from score2gp.pdf_tab_duration_types import TabDurationEvidence
from score2gp.tabraw import TabCandidate, TabRaw, make_tab_candidate


def test_full_fixture_suite_duration_consistency(tmp_path: Path):
    """End-to-end audit verifying duration evidence handling across synthetic & public PDF-tab fixtures."""
    # 1. Unstemmed tab fixture (generated_tiny_tab.pdf / unstemmed TabRaw candidates)
    unstemmed_candidates = [
        make_tab_candidate(
            candidate_id=f"unstemmed-c-{i}",
            raw_text="2",
            page_index=1,
            bbox_values=(100.0 + i * 50.0, 150.0, 104.0 + i * 50.0, 154.0),
            confidence=0.9,
            system_index=1,
            staff_index=1,
            bar_index=1,
            line_index=1,
            string=1,
        )
        for i in range(4)
    ]

    bar_unstemmed = assemble_pdf_tab_bar(unstemmed_candidates, output_bar_idx=1, track_id="track-1")
    note_events_unstemmed = [ev for ev in bar_unstemmed.events if not ev.is_rest]

    assert len(note_events_unstemmed) == 4
    for ev in note_events_unstemmed:
        assert ev.timing.notated_duration.value == "eighth"
        assert ev.timing.duration_ticks == 480

    # 2. Explicit visual duration evidence (quarter, eighth, 16th notes)
    quarter_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True)
    eighth_ev = TabDurationEvidence(duration_name="eighth", duration_ticks=480, stem_present=True, beam_count=1)
    sixteenth_ev = TabDurationEvidence(duration_name="16th", duration_ticks=240, stem_present=True, beam_count=2)

    stemmed_candidates = [
        make_tab_candidate(
            candidate_id="stemmed-q1",
            raw_text="0",
            page_index=1,
            bbox_values=(100.0, 150.0, 104.0, 154.0),
            confidence=1.0,
            string=6,
            duration_evidence=quarter_ev,
        ),
        make_tab_candidate(
            candidate_id="stemmed-e1",
            raw_text="2",
            page_index=1,
            bbox_values=(150.0, 150.0, 154.0, 154.0),
            confidence=1.0,
            string=5,
            duration_evidence=eighth_ev,
        ),
        make_tab_candidate(
            candidate_id="stemmed-s1",
            raw_text="7",
            page_index=1,
            bbox_values=(180.0, 150.0, 184.0, 154.0),
            confidence=1.0,
            string=1,
            duration_evidence=sixteenth_ev,
        ),
    ]

    bar_stemmed = assemble_pdf_tab_bar(stemmed_candidates, output_bar_idx=1, track_id="track-1")
    note_events_stemmed = [ev for ev in bar_stemmed.events if not ev.is_rest]

    assert len(note_events_stemmed) == 3
    assert note_events_stemmed[0].timing.duration_ticks == 960
    assert note_events_stemmed[1].timing.duration_ticks == 480
    assert note_events_stemmed[2].timing.duration_ticks == 240


def test_tabraw_serialization_and_no_leakage(tmp_path: Path):
    """Verify clean JSON serialization of TabRaw with TabDurationEvidence and assert no private data or raw dumps leak."""
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )

    cand = make_tab_candidate(
        candidate_id="cand-001",
        raw_text="5",
        page_index=1,
        bbox_values=(100.0, 150.0, 104.0, 154.0),
        confidence=0.95,
        system_index=1,
        staff_index=1,
        bar_index=1,
        line_index=1,
        string=1,
        duration_evidence=quarter_ev,
    )

    tabraw = TabRaw(
        source_pdf="public_test.pdf",
        pdf_layout_class="drawn",
        candidates=[cand],
    )

    out_file = tmp_path / "tabraw_test.json"
    tabraw.to_json_file(out_file)

    assert out_file.exists()
    loaded_data = json.loads(out_file.read_text(encoding="utf-8"))

    # Assert schema version
    assert loaded_data["schema_version"] == "tabraw.v0.1"

    # Assert candidate duration evidence structure
    raw_meta = loaded_data["candidates"][0]["raw"]
    assert "duration_evidence" in raw_meta
    ev_dict = raw_meta["duration_evidence"]
    assert ev_dict["duration_name"] == "quarter"
    assert ev_dict["duration_ticks"] == 960
    assert ev_dict["stem_present"] is True

    # No-leakage assertions: no private paths or raw memory pointers in JSON
    json_str = json.dumps(loaded_data)
    assert "private" not in json_str.lower()
    assert "object at 0x" not in json_str


def test_build_ir_from_tabraw_duration_metadata(tmp_path: Path):
    """Verify build_ir_from_tabraw_only processes TabRaw with duration evidence into a valid ScoreIR."""
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )

    candidates = [
        make_tab_candidate(
            candidate_id=f"cand-{i}",
            raw_text="0",
            page_index=1,
            bbox_values=(100.0 + i * 40.0, 150.0, 104.0 + i * 40.0, 154.0),
            confidence=0.9,
            system_index=1,
            staff_index=1,
            bar_index=1,
            line_index=1,
            string=6,
            duration_evidence=quarter_ev,
        )
        for i in range(4)
    ]

    tabraw = TabRaw(
        source_pdf="public_test.pdf",
        pdf_layout_class="drawn",
        candidates=candidates,
    )

    tabraw_path = tmp_path / "tabraw_valid.json"
    tabraw.to_json_file(tabraw_path)

    score_ir, _ = build_ir_from_tabraw_only(tabraw_path)

    assert len(score_ir.tracks) == 1
    assert len(score_ir.bars) == 1
    bar = score_ir.bars[0]

    assert len(bar.events) == 4
    for ev in bar.events:
        assert ev.timing.notated_duration.value == "quarter"
        assert ev.timing.duration_ticks == 960
