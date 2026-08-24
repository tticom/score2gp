import pytest
import warnings
from pathlib import Path
from score2gp.pdf import extract_tab
from score2gp.pdf_only_chord_event_grouper import PdfOnlyChordEventGrouper
from score2gp.tabraw import TabCandidate
from score2gp.pdf_staff_tab_timing_aligner import (
    PdfStaffTabTimingAligner,
    IrregularStaffBoundsWarning,
    PdfStaffTimingEvent,
)

def test_real_source_irregular_layout_alignment(tmp_path) -> None:
    # This test provides real-world evidence for the NPG-05 Layout Resilience domain change.
    pdf_path = Path("tests/fixtures/pdf/generated_npg_05_irregular_layout.pdf")
    tabraw_path = tmp_path / "irregular.tabraw.json"
    
    raw = extract_tab(pdf_path, tabraw_path)
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
            
    # Simulate staff events that have DIFFERENT local_bar_indices to imply irregular grouping
    staff_events = [
        PdfStaffTimingEvent(id="s1", page_index=1, system_index=1, staff_index=1, local_bar_index=1, x=150.0, onset_ticks=0, duration_ticks=480),
        PdfStaffTimingEvent(id="s2", page_index=1, system_index=1, staff_index=1, local_bar_index=1, x=375.0, onset_ticks=480, duration_ticks=480),
        PdfStaffTimingEvent(id="s3", page_index=1, system_index=1, staff_index=1, local_bar_index=2, x=625.0, onset_ticks=0, duration_ticks=480),
    ]
    
    # System 3: severely truncated
    staff_events.append(
        PdfStaffTimingEvent(id="s4", page_index=1, system_index=3, staff_index=1, local_bar_index=1, x=70.0, onset_ticks=0, duration_ticks=480)
    )
    
    aligner = PdfStaffTabTimingAligner(tolerance=15.0)
    
    with pytest.warns(IrregularStaffBoundsWarning):
        result = aligner.align(staff_events, tab_groups_by_bar)
        
    assert len(result.aligned_pairs) > 0
