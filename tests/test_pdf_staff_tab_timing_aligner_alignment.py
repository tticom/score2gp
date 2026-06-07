from __future__ import annotations

from score2gp.pdf_staff_timing import PdfStaffTimingEvent
from score2gp.pdf_only_chord_event_grouper import CandidateXGroupDiagnostics
from score2gp.pdf_staff_tab_timing_aligner import PdfStaffTabTimingAligner


def test_pdf_staff_tab_timing_aligner_aligns_nearest_tab_event_in_same_bar() -> None:
    # 1. Aligns standard staff event to TAB group in the same bar when close
    staff_ev = PdfStaffTimingEvent(
        id="s-1",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
    )
    
    tab_grp = CandidateXGroupDiagnostics(
        x=105.0,  # 5.0 pt gap, within 15.0 pt tolerance
        x_min=105.0,
        x_max=105.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    result = aligner.align([staff_ev], {(1, 1, 1): [tab_grp]})

    assert len(result.aligned_pairs) == 1
    assert result.aligned_pairs[0][0].id == "s-1"
    assert result.aligned_pairs[0][1].candidate_ids == ["c-1"]
    assert len(result.unmatched_staff_events) == 0
    assert len(result.unmatched_tab_groups) == 0
    assert len(result.ambiguous_staff_events) == 0
    assert result.bars_using_staff_timing == [(1, 1, 1)]
    assert len(result.bars_using_fallback_timing) == 0


def test_pdf_staff_tab_timing_aligner_does_not_align_across_source_bar_identity() -> None:
    # 2. Does not align even if visually close, if bar keys differ
    staff_ev = PdfStaffTimingEvent(
        id="s-1",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
    )
    
    tab_grp = CandidateXGroupDiagnostics(
        x=100.0,
        x_min=100.0,
        x_max=100.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    # Passed under bar key (1, 1, 2) instead of (1, 1, 1)
    result = aligner.align([staff_ev], {(1, 1, 2): [tab_grp]})

    assert len(result.aligned_pairs) == 0
    assert len(result.unmatched_staff_events) == 1
    assert result.unmatched_staff_events[0].id == "s-1"
    assert len(result.unmatched_tab_groups) == 1
    assert result.unmatched_tab_groups[0].candidate_ids == ["c-1"]


def test_pdf_staff_tab_timing_aligner_reports_unmatched_tab_events() -> None:
    # 3. Reports TAB groups with no nearby staff events as unmatched
    staff_ev = PdfStaffTimingEvent(
        id="s-1",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
    )
    
    tab_grp_1 = CandidateXGroupDiagnostics(
        x=102.0,  # aligned
        x_min=102.0,
        x_max=102.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )
    tab_grp_2 = CandidateXGroupDiagnostics(
        x=150.0,  # unmatched (50 pt gap > 15.0 pt tolerance)
        x_min=150.0,
        x_max=150.0,
        candidate_count=1,
        candidate_ids=["c-2"],
        strings=[2],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    result = aligner.align([staff_ev], {(1, 1, 1): [tab_grp_1, tab_grp_2]})

    assert len(result.aligned_pairs) == 1
    assert result.aligned_pairs[0][0].id == "s-1"
    assert len(result.unmatched_tab_groups) == 1
    assert result.unmatched_tab_groups[0].candidate_ids == ["c-2"]


def test_pdf_staff_tab_timing_aligner_reports_unmatched_staff_events() -> None:
    # 4. Reports staff events with no nearby TAB groups as unmatched
    staff_ev_1 = PdfStaffTimingEvent(
        id="s-1",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
    )
    staff_ev_2 = PdfStaffTimingEvent(
        id="s-2",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=200.0,  # unmatched
        onset_ticks=480,
        duration_ticks=480,
    )
    
    tab_grp = CandidateXGroupDiagnostics(
        x=101.0,
        x_min=101.0,
        x_max=101.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    result = aligner.align([staff_ev_1, staff_ev_2], {(1, 1, 1): [tab_grp]})

    assert len(result.aligned_pairs) == 1
    assert result.aligned_pairs[0][0].id == "s-1"
    assert len(result.unmatched_staff_events) == 1
    assert result.unmatched_staff_events[0].id == "s-2"


def test_pdf_staff_tab_timing_aligner_keeps_rest_events_timing_only() -> None:
    # 5. Rest event appears in alignment result without consuming any TAB group
    staff_rest = PdfStaffTimingEvent(
        id="s-rest",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
        is_rest=True,  # rest event
    )
    
    tab_grp = CandidateXGroupDiagnostics(
        x=101.0,
        x_min=101.0,
        x_max=101.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    result = aligner.align([staff_rest], {(1, 1, 1): [tab_grp]})

    # The rest event aligns to None in aligned_pairs, and tab_grp remains unmatched
    assert len(result.aligned_pairs) == 1
    assert result.aligned_pairs[0][0].id == "s-rest"
    assert result.aligned_pairs[0][1] is None
    assert len(result.unmatched_tab_groups) == 1
    assert result.unmatched_tab_groups[0].candidate_ids == ["c-1"]


def test_pdf_staff_tab_timing_aligner_reports_ambiguous_matches() -> None:
    # 6. Reports ambiguous matches when multiple TAB groups are within tolerance of one staff event
    staff_ev = PdfStaffTimingEvent(
        id="s-1",
        page_index=1,
        system_index=1,
        local_bar_index=1,
        x=100.0,
        onset_ticks=0,
        duration_ticks=480,
    )
    
    # Both T1 and T2 are close to S1 (delta 5.0 and 8.0)
    tab_grp_1 = CandidateXGroupDiagnostics(
        x=105.0,
        x_min=105.0,
        x_max=105.0,
        candidate_count=1,
        candidate_ids=["c-1"],
        strings=[1],
    )
    tab_grp_2 = CandidateXGroupDiagnostics(
        x=108.0,
        x_min=108.0,
        x_max=108.0,
        candidate_count=1,
        candidate_ids=["c-2"],
        strings=[2],
    )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    result = aligner.align([staff_ev], {(1, 1, 1): [tab_grp_1, tab_grp_2]})

    assert len(result.aligned_pairs) == 0
    assert len(result.ambiguous_staff_events) == 1
    assert result.ambiguous_staff_events[0].id == "s-1"
    assert len(result.unmatched_tab_groups) == 2
