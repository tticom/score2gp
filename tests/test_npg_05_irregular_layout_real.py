import pytest
import warnings
from pathlib import Path
from score2gp.pdf import extract_tab
from score2gp.pdf_only_chord_event_grouper import PdfOnlyChordEventGrouper
from score2gp.tabraw import TabCandidate
from score2gp.pdf_staff_tab_timing_aligner import (
    PdfStaffTabTimingAligner,
    PdfStaffTimingEvent,
)

def test_real_source_irregular_layout_alignment(tmp_path) -> None:
    # This test provides real-world evidence for the NPG-05 Layout Resilience domain change.
    repo_root = Path(__file__).resolve().parent.parent
    lesson7_path = repo_root.parent / "score2gp-private-fixtures" / "fixtures" / "private" / "Lesson-7.pdf"

    if not lesson7_path.exists():
        pytest.skip("Lesson-7.pdf required for this private-fixture acceptance test.")

    tabraw_path = tmp_path / "lesson7.tabraw.json"

    raw = extract_tab(lesson7_path, tabraw_path)

    frets_raw = [c for c in raw["candidates"] if c.get("kind") == "fret"]

    frets = []
    for c in frets_raw:
        frets.append(TabCandidate(
            id=c["id"],
            kind=c["kind"],
            page_index=c.get("page_index"),
            system_index=c.get("system_index"),
            staff_index=c.get("staff_index"),
            bar_index=c.get("bar_index"),
            string=c.get("string"),
            raw_text=c.get("raw_text"),
            parsed_fret=c.get("parsed_fret"),
            x=c.get("x"),
            y=c.get("y"),
            bbox=c.get("bbox"),
            confidence=c.get("confidence", 0.9),
            raw=c.get("raw", {})
        ))

    grouper = PdfOnlyChordEventGrouper(tolerance=10.0)
    tab_groups_by_bar = {}

    for f in frets:
        p = f.page_index or 1
        sys = f.system_index or 1
        st = f.staff_index or 1
        b = f.bar_index or 1
        key = (p, sys, st, b)

        if key not in tab_groups_by_bar:
            bar_frets = [cf for cf in frets if cf.page_index == p and cf.system_index == sys and cf.bar_index == b]
            tab_groups_by_bar[key] = grouper.candidate_x_groups(bar_frets)

    # L3-01: Lesson-7 system 1 has 2 TAB bars. Its reference GP has 50 measures and production now
    # detects exactly 50. The former "9 bars" came from note stems mis-read as barlines.
    assert sorted(b for (p, s, st, b) in tab_groups_by_bar if (p, s) == (1, 1)) == [1, 2]
    # NOTE(GOVERNANCE_EXCEPTION): The staff events below are intentionally mocked
    # to simulate a parser desync (staff_bar_indices != tab_bar_indices).
    # Because the upstream pipeline cannot currently reproduce this failure
    # organically on real data, this test substitutes mocked staff events
    # to verify the alignment fallback logic.
    # To test the irregular alignment logic (where staff_bar_indices != tab_bar_indices),
    # we simulate the Staff Events having different local_bar_indices due to upstream parsing discrepancies.
    # We'll just take the exact X coordinates of the first 5 tab groups and make them Staff Events,
    # but give them different local_bar_indices.

    # Desync: the staff reports fewer bars than the TAB. Take the last 5 groups of TAB bar 1 and the
    # first 5 of TAB bar 2, so they cross a real TAB boundary, and put all 10 in a single staff bar.
    bar1 = tab_groups_by_bar[(1, 1, 1, 1)]
    bar2 = tab_groups_by_bar[(1, 1, 1, 2)]
    assert len(bar1) >= 5 and len(bar2) >= 5
    straddling = bar1[-5:] + bar2[:5]

    staff_events = []
    for i, grp in enumerate(straddling):
        staff_events.append(
            PdfStaffTimingEvent(id=f"s{i}", page_index=1, system_index=1, staff_index=1, local_bar_index=1, x=grp.x, onset_ticks=0, duration_ticks=480)
        )

    aligner = PdfStaffTabTimingAligner(tolerance=15.0)

    result = aligner.align(staff_events, tab_groups_by_bar)

    # The dynamic boundary system maps every event across the TAB boundary.
    assert len(result.aligned_pairs) == 10
