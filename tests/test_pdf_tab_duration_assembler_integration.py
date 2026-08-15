from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]

import pytest
from pathlib import Path

def _get_dynamic_private_pdf():
    pdfs = list(Path("fixtures/private").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No private fixtures found")
    return pdfs[0]

def _get_dynamic_private_musicxml():
    xmls = list(Path("fixtures/private").glob("*.musicxml"))
    if not xmls:
        # Fallback to pdf just so Path doesn't fail, test will likely skip or fail gracefully
        return _get_dynamic_private_pdf()
    return xmls[0]


from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
from score2gp.pdf_tab_bar_assembler import PdfTabBarAssemblerError, assemble_pdf_tab_bar
from score2gp.pdf_tab_duration_associator import (
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    resolve_tab_duration_evidence_for_events,
)
from score2gp.pdf_tab_duration_types import TabDurationEvidence
from score2gp.tabraw import make_tab_candidate


def test_pdf_tab_duration_assembler_oracle_integration():
    """Verify that assemble_pdf_tab_bar processes candidates with visual TabDurationEvidence
    extracted from generated_pdf_tab_duration.pdf, matching the exact expected oracle.
    """
    pdf_path = _get_dynamic_private_pdf()
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    # Extract text-span event x-coordinates and fret numbers
    text_dict = page.get_text("dict")
    extracted_spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt.isdigit() and span.get("font") == "Courier":
                    bbox = span.get("bbox")
                    if bbox:
                        event_x = (bbox[0] + bbox[2]) / 2.0
                        extracted_spans.append((event_x, txt))

    extracted_spans.sort(key=lambda t: t[0])
    extracted_xs = [t[0] for t in extracted_spans]
    assert len(extracted_xs) == 12

    # Extract drawings
    stems: list[StemPrimitiveCandidate] = []
    beams: list[BeamPrimitiveCandidate] = []
    flags: list[FlagPrimitiveCandidate] = []
    drawing_lines: list[tuple[float, float, float, float]] = []

    for draw in page.get_drawings():
        for item in draw.get("items", []):
            if not item:
                continue
            itype = item[0]
            if itype == "l" and len(item) >= 3:
                p0, p1 = item[1], item[2]
                dx = abs(p0.x - p1.x)
                dy = abs(p0.y - p1.y)
                ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                drawing_lines.append((ix0, iy0, ix1, iy1))

                if dy >= 5.0 and dx <= 2.0:
                    stems.append(StemPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1), is_downward=True))
                elif dy <= 1.0 and dx >= 7.0:
                    if not (149.0 <= iy0 <= 221.0 and dx > 300.0):
                        beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))
                elif dx >= 3.0 and dy >= 3.0:
                    flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))

    staff_line_ys = sorted({round(iy0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(iy0 - iy1) <= 1.0 and abs(ix1 - ix0) >= 300.0})
    staff_space = (staff_line_ys[-1] - staff_line_ys[0]) / (len(staff_line_ys) - 1)
    barline_xs = sorted({round((ix0 + ix1) / 2.0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(ix0 - ix1) <= 1.0 and (iy1 - iy0) >= 60.0 and iy0 <= staff_line_ys[0] + 2.0 and iy1 >= staff_line_ys[-1] - 2.0})

    context = StaffSystemContext(
        line_y_coords=staff_line_ys,
        barline_x_coords=barline_xs,
        staff_space=staff_space,
    )

    ev_mapping = resolve_tab_duration_evidence_for_events(extracted_xs, stems, beams, flags, context)

    # Bar 1: first 4 events (x < barline_xs[1])
    bar1_candidates = []
    for idx, (ex, fret_text) in enumerate(extracted_spans[:4], start=1):
        cand = make_tab_candidate(
            candidate_id=f"b1-cand-{idx}",
            raw_text=fret_text,
            page_index=1,
            bbox_values=(ex - 2, staff_line_ys[0], ex + 2, staff_line_ys[0] + 4),
            confidence=1.0,
            system_index=1,
            staff_index=1,
            bar_index=1,
            string=6,
            duration_evidence=ev_mapping[ex],
        )
        bar1_candidates.append(cand)

    bar1 = assemble_pdf_tab_bar(
        bar1_candidates,
        output_bar_idx=1,
        track_id="track-1",
    )

    assert len(bar1.events) == 4
    for ev in bar1.events:
        assert not ev.is_rest
        assert ev.timing.notated_duration.value == "quarter"
        assert ev.timing.duration_ticks == 960

    # Bar 2: next 8 events (x > barline_xs[1])
    bar2_candidates = []
    for idx, (ex, fret_text) in enumerate(extracted_spans[4:], start=1):
        cand = make_tab_candidate(
            candidate_id=f"b2-cand-{idx}",
            raw_text=fret_text,
            page_index=1,
            bbox_values=(ex - 2, staff_line_ys[1], ex + 2, staff_line_ys[1] + 4),
            confidence=1.0,
            system_index=1,
            staff_index=1,
            bar_index=2,
            string=6,
            duration_evidence=ev_mapping[ex],
        )
        bar2_candidates.append(cand)

    bar2 = assemble_pdf_tab_bar(
        bar2_candidates,
        output_bar_idx=2,
        track_id="track-1",
    )

    note_events = [ev for ev in bar2.events if not ev.is_rest]
    rest_events = [ev for ev in bar2.events if ev.is_rest]

    assert len(note_events) == 8

    # 2 flagged eighth notes (480 ticks each)
    assert note_events[0].timing.notated_duration.value == "eighth"
    assert note_events[0].timing.duration_ticks == 480
    assert note_events[1].timing.notated_duration.value == "eighth"
    assert note_events[1].timing.duration_ticks == 480

    # 2 beamed eighth notes (480 ticks each)
    assert note_events[2].timing.notated_duration.value == "eighth"
    assert note_events[2].timing.duration_ticks == 480
    assert note_events[3].timing.notated_duration.value == "eighth"
    assert note_events[3].timing.duration_ticks == 480

    # 4 double-beamed sixteenth notes (240 ticks each)
    for ev in note_events[4:8]:
        assert ev.timing.notated_duration.value == "16th"
        assert ev.timing.duration_ticks == 240

    # Total note ticks = 4*480 + 4*240 = 1920 + 960 = 2880 ticks.
    # Remainder rest = 3840 - 2880 = 960 ticks (1 quarter rest)
    assert len(rest_events) == 1
    assert rest_events[0].timing.notated_duration.value == "quarter"
    assert rest_events[0].timing.duration_ticks == 960
    assert rest_events[0].timing.onset_ticks == 2880

    doc.close()


def test_unstemmed_fallback_preservation():
    """Verify that candidates lacking visual duration evidence fall back to equal-spacing heuristics."""
    candidates = []
    for i in range(4):
        cand = make_tab_candidate(
            candidate_id=f"unstemmed-{i}",
            raw_text="3",
            page_index=1,
            bbox_values=(100 + i * 40, 150, 104 + i * 40, 154),
            confidence=0.8,
            string=1,
        )
        candidates.append(cand)

    bar = assemble_pdf_tab_bar(candidates, output_bar_idx=1, track_id="t1")
    # For N=4 <= 8, equal spacing yields eighth notes (480 ticks each)
    note_events = [ev for ev in bar.events if not ev.is_rest]
    assert len(note_events) == 4
    for ev in note_events:
        assert ev.timing.notated_duration.value == "eighth"
        assert ev.timing.duration_ticks == 480

    # Trailing rest for remaining 1920 ticks (3840 - 4*480 = 1920 = half rest)
    rest_events = [ev for ev in bar.events if ev.is_rest]
    assert len(rest_events) == 1
    assert rest_events[0].timing.notated_duration.value == "half"
    assert rest_events[0].timing.duration_ticks == 1920


def test_measure_capacity_enforcement_overcapacity():
    """Verify that visual duration evidence causing measure capacity overflow (>3840 ticks) fails closed."""
    # 5 quarter notes = 4800 ticks > 3840 ticks capacity
    candidates = []
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )

    for i in range(5):
        cand = make_tab_candidate(
            candidate_id=f"overcap-{i}",
            raw_text="0",
            page_index=1,
            bbox_values=(100 + i * 30, 150, 104 + i * 30, 154),
            confidence=0.9,
            string=6,
            duration_evidence=quarter_ev,
        )
        candidates.append(cand)

    with pytest.raises(PdfTabBarAssemblerError) as exc_info:
        assemble_pdf_tab_bar(candidates, output_bar_idx=1, track_id="t1")

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"
    assert "exceed measure capacity 3840 ticks" in exc_info.value.message


def test_ambiguous_duration_evidence_fail_closed():
    """Verify that ambiguous duration evidence on event candidates fails closed with PdfTabBarAssemblerError."""
    ambiguous_ev = TabDurationEvidence(
        duration_name="ambiguous",
        duration_ticks=0,
        stem_present=True,
        source="ambiguous_conflict",
        is_ambiguous=True,
        diagnostic_message="Conflicting stem geometry",
    )

    cand = make_tab_candidate(
        candidate_id="amb-1",
        raw_text="5",
        page_index=1,
        bbox_values=(100, 150, 104, 154),
        confidence=0.9,
        string=1,
        duration_evidence=ambiguous_ev,
    )

    with pytest.raises(PdfTabBarAssemblerError) as exc_info:
        assemble_pdf_tab_bar([cand], output_bar_idx=1, track_id="t1")

    assert exc_info.value.category == "pdf_only_tab_ambiguous_duration"
    assert "Ambiguous duration evidence" in exc_info.value.message


def test_mixed_stemmed_and_unstemmed_subgroup_behavior():
    """Verify that stemmed events use explicit duration evidence while unstemmed events fall back."""
    stemmed_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )
    unstemmed_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=False,
        source="equal_spacing_fallback",
        is_fallback_placeholder=True,
    )

    cand1 = make_tab_candidate(
        candidate_id="mixed-1",
        raw_text="3",
        page_index=1,
        bbox_values=(100, 150, 104, 154),
        confidence=0.9,
        string=1,
        duration_evidence=stemmed_ev,
    )
    cand2 = make_tab_candidate(
        candidate_id="mixed-2",
        raw_text="5",
        page_index=1,
        bbox_values=(150, 150, 154, 154),
        confidence=0.9,
        string=1,
        duration_evidence=unstemmed_ev,
    )

    bar = assemble_pdf_tab_bar([cand1, cand2], output_bar_idx=1, track_id="t1")
    note_events = [ev for ev in bar.events if not ev.is_rest]

    assert len(note_events) == 2
    assert note_events[0].timing.duration_ticks == 960
    assert note_events[1].timing.duration_ticks == 480  # Unstemmed event falls back to equal spacing grid (N=2 -> eighth)


def test_matching_multi_string_chord_duration_evidence():
    """Verify that a multi-string chord where all candidates share identical explicit duration evidence assembles cleanly."""
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )

    cand_string1 = make_tab_candidate(
        candidate_id="chord-s1",
        raw_text="0",
        page_index=1,
        bbox_values=(100.0, 150.0, 104.0, 154.0),
        confidence=0.9,
        string=1,
        duration_evidence=quarter_ev,
    )
    cand_string2 = make_tab_candidate(
        candidate_id="chord-s2",
        raw_text="1",
        page_index=1,
        bbox_values=(100.0, 164.0, 104.0, 168.0),
        confidence=0.9,
        string=2,
        duration_evidence=quarter_ev,
    )
    cand_string3 = make_tab_candidate(
        candidate_id="chord-s3",
        raw_text="0",
        page_index=1,
        bbox_values=(100.0, 178.0, 104.0, 182.0),
        confidence=0.9,
        string=3,
        duration_evidence=quarter_ev,
    )

    bar = assemble_pdf_tab_bar([cand_string1, cand_string2, cand_string3], output_bar_idx=1, track_id="t1")
    note_events = [ev for ev in bar.events if not ev.is_rest]

    assert len(note_events) == 1
    assert len(note_events[0].notes) == 3
    assert note_events[0].timing.notated_duration.value == "quarter"
    assert note_events[0].timing.duration_ticks == 960


def test_conflicting_multi_string_chord_duration_evidence_fails_closed():
    """Verify that a multi-string chord containing conflicting explicit duration evidence across candidates fails closed."""
    quarter_ev = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
        source="visual_morphology",
    )
    eighth_ev = TabDurationEvidence(
        duration_name="eighth",
        duration_ticks=480,
        stem_present=True,
        source="visual_morphology",
    )

    cand_string1 = make_tab_candidate(
        candidate_id="conflict-s1",
        raw_text="0",
        page_index=1,
        bbox_values=(100.0, 150.0, 104.0, 154.0),
        confidence=0.9,
        string=1,
        duration_evidence=quarter_ev,
    )
    cand_string2 = make_tab_candidate(
        candidate_id="conflict-s2",
        raw_text="1",
        page_index=1,
        bbox_values=(100.0, 164.0, 104.0, 168.0),
        confidence=0.9,
        string=2,
        duration_evidence=eighth_ev,
    )

    with pytest.raises(PdfTabBarAssemblerError) as exc_info:
        assemble_pdf_tab_bar([cand_string1, cand_string2], output_bar_idx=1, track_id="t1")

    assert exc_info.value.category == "pdf_only_tab_ambiguous_duration"
    assert "Conflicting duration evidence across candidates in chord subgroup" in exc_info.value.message
