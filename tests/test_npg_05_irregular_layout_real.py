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
            
    # Lesson-7 has 6 systems on Page 1. System 1 has 9 bars on TAB!
    # Let's verify we have system 1 with 9 bars.
    # To test the irregular alignment logic (where staff_bar_indices != tab_bar_indices),
    # we simulate the Staff Events having different local_bar_indices due to upstream parsing discrepancies.
    # We'll just take the exact X coordinates of the first 5 tab groups and make them Staff Events,
    # but give them different local_bar_indices.
    
    sys1_tab_groups = []
    for b in range(1, 10):
        if (1, 1, 1, b) in tab_groups_by_bar:
            sys1_tab_groups.extend(tab_groups_by_bar[(1, 1, 1, b)])
            
    # Create staff events matching these X coordinates, but group them into just 2 bars! (Irregular)
    staff_events = []
    for i, grp in enumerate(sys1_tab_groups[:10]):
        # The first 5 go to local_bar_index=1, the next 5 go to local_bar_index=2
        local_bar = 1 if i < 5 else 2
        staff_events.append(
            PdfStaffTimingEvent(id=f"s{i}", page_index=1, system_index=1, staff_index=1, local_bar_index=local_bar, x=grp.x, onset_ticks=0, duration_ticks=480)
        )
        
    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    
    result = aligner.align(staff_events, tab_groups_by_bar)
    
    # Verify that the dynamic boundary system safely mapped the irregular groupings!
    assert len(result.aligned_pairs) >= 10
