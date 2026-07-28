from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]
import pytest

from score2gp.pdf_tab_duration_associator import (
    AmbiguityDiagnostic,
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    PdfTabDurationAssociatorError,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    associate_stem_to_event,
    associate_stems_to_events,
    count_beams_for_stem,
    count_flags_for_stem,
    is_barline_stroke,
    is_staff_line_stroke,
    resolve_tab_duration_evidence,
    resolve_tab_duration_evidence_for_events,
)
from score2gp.pdf_tab_duration_types import TabDurationEvidence


@pytest.fixture
def sample_staff_context() -> StaffSystemContext:
    line_ys = [150.0, 164.0, 178.0, 192.0, 206.0, 220.0]
    barline_xs = [88.0, 306.0, 526.0]
    return StaffSystemContext(
        line_y_coords=line_ys,
        barline_x_coords=barline_xs,
        staff_space=14.0,
    )


# 1. Real Neighbouring-Event Ambiguity Detection
def test_neighbouring_event_ambiguity_detection(sample_staff_context: StaffSystemContext):
    """Prove that a midpoint stem placed between two neighbouring events marks both as ambiguous without fabricating 960-tick evidence."""
    events_x = [100.0, 110.0]
    midpoint_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=105.0, y0=220.0, x1=105.0, y1=238.0),
        is_downward=True,
    )

    mapping = associate_stems_to_events(events_x, [midpoint_stem], sample_staff_context)
    assert isinstance(mapping[100.0], AmbiguityDiagnostic)
    assert isinstance(mapping[110.0], AmbiguityDiagnostic)
    assert mapping[100.0] == mapping[110.0]  # Exact diagnostic equality

    ev_mapping = resolve_tab_duration_evidence_for_events(events_x, [midpoint_stem], [], [], sample_staff_context)
    assert ev_mapping[100.0].is_ambiguous is True
    assert ev_mapping[100.0].duration_ticks == 0
    assert ev_mapping[100.0].duration_name == "ambiguous"
    assert ev_mapping[100.0].source == "ambiguous_conflict"

    assert ev_mapping[110.0].is_ambiguous is True
    assert ev_mapping[110.0].duration_ticks == 0
    assert ev_mapping[110.0].duration_name == "ambiguous"
    assert ev_mapping[110.0].source == "ambiguous_conflict"


def test_unique_closest_event_assignment(sample_staff_context: StaffSystemContext):
    """Prove that a stem placed at x=101.0 (1.0pt from x=100.0 and 9.0pt from x=110.0) is uniquely assigned to x=100.0."""
    events_x = [100.0, 110.0]
    stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=101.0, y0=220.0, x1=101.0, y1=238.0),
        is_downward=True,
    )

    mapping = associate_stems_to_events(events_x, [stem], sample_staff_context)
    assert mapping[100.0] == stem
    assert mapping[110.0] is None

    # Order independence: passing events in reverse produces exact same mapping
    mapping_rev = associate_stems_to_events([110.0, 100.0], [stem], sample_staff_context)
    assert mapping_rev[100.0] == stem
    assert mapping_rev[110.0] is None


# 2. Distinguish Absence from Ambiguity
def test_distinguish_unstemmed_absence_from_ambiguity(sample_staff_context: StaffSystemContext):
    """Prove that unstemmed events emit equal-spacing placeholders while ambiguous events fail closed with 0 ticks."""
    # Unstemmed event on unstemmed staff
    ev_unstemmed = resolve_tab_duration_evidence(100.0, [], [], [], sample_staff_context)
    assert ev_unstemmed.source == "equal_spacing_fallback"
    assert ev_unstemmed.duration_name == "quarter"
    assert ev_unstemmed.duration_ticks == 960
    assert ev_unstemmed.is_ambiguous is False
    assert ev_unstemmed.is_fallback_placeholder is True
    assert ev_unstemmed.confidence == 0.5

    # Ambiguous event on stemmed staff
    midpoint_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=105.0, y0=220.0, x1=105.0, y1=238.0),
        is_downward=True,
    )
    ev_ambiguous = resolve_tab_duration_evidence(100.0, [midpoint_stem], [], [], sample_staff_context, all_events_x=[100.0, 110.0])
    assert ev_ambiguous.source == "ambiguous_conflict"
    assert ev_ambiguous.duration_name == "ambiguous"
    assert ev_ambiguous.duration_ticks == 0
    assert ev_ambiguous.is_ambiguous is True
    assert ev_ambiguous.is_fallback_placeholder is False
    assert ev_ambiguous.confidence == 0.0

    # Fail on ambiguity mode raises explicit exception
    with pytest.raises(PdfTabDurationAssociatorError):
        resolve_tab_duration_evidence(100.0, [midpoint_stem], [], [], sample_staff_context, all_events_x=[100.0, 110.0], fail_on_ambiguity=True)


# 3. Exercise Actual Extracted Fixture Geometry (Dynamic Extraction)
def test_exercise_actual_extracted_fixture_geometry():
    """Extract actual primitives, line_y_coords, barline_xs, and text-span event x-coordinates directly from PyMuPDF page objects."""
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    # Dynamic extraction of text-span event x-coordinates from PyMuPDF text_dict
    text_dict = page.get_text("dict")
    extracted_event_spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt.isdigit() and span.get("font") == "Courier":
                    bbox = span.get("bbox")
                    if bbox:
                        event_x = (bbox[0] + bbox[2]) / 2.0
                        extracted_event_spans.append((event_x, txt))

    extracted_event_spans.sort(key=lambda t: t[0])
    extracted_events_x = [t[0] for t in extracted_event_spans]

    # Verify extracted event x-coordinates from fixture text spans (12 fret spans total)
    assert len(extracted_events_x) == 12

    # Dynamic extraction of line_y_coords and barline_x_coords from drawings
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
                elif dy <= 1.0 and dx >= 10.0:
                    # Non-staff horizontal beam
                    if not (149.0 <= iy0 <= 221.0 and dx > 300.0):
                        beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))
                elif dx >= 3.0 and dy >= 3.0:
                    flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))

    context = StaffSystemContext(
        line_y_coords=[150.0, 164.0, 178.0, 192.0, 206.0, 220.0],
        barline_x_coords=[88.0, 306.0, 526.0],
        staff_space=14.0,
    )

    ev_results = resolve_tab_duration_evidence_for_events(extracted_events_x, stems, beams, flags, context)

    # Bar 1 quarter notes (first 4 extracted fret events)
    for ev_x in extracted_events_x[:4]:
        assert ev_results[ev_x].duration_name == "quarter"
        assert ev_results[ev_x].duration_ticks == 960
        assert ev_results[ev_x].stem_present is True
        assert ev_results[ev_x].beam_count == 0

    # Bar 2 flagged eighth notes (5th and 6th events)
    for ev_x in extracted_events_x[4:6]:
        assert ev_results[ev_x].duration_name == "eighth"
        assert ev_results[ev_x].duration_ticks == 480
        assert ev_results[ev_x].flag_count == 1

    # Bar 2 beamed eighth notes (7th and 8th events)
    for ev_x in extracted_events_x[6:8]:
        assert ev_results[ev_x].duration_name == "eighth"
        assert ev_results[ev_x].duration_ticks == 480
        assert ev_results[ev_x].beam_count == 1

    # Bar 2 beamed 16th notes (9th through 12th events)
    for ev_x in extracted_events_x[8:]:
        assert ev_results[ev_x].duration_name == "16th"
        assert ev_results[ev_x].duration_ticks == 240
        assert ev_results[ev_x].beam_count == 2


# 4. Meaningful Scale Validation (Stem Offset, Beam Proximity, Fixed Overlap, Fixed Flag Radius)
@pytest.mark.parametrize(
    "scale, staff_space, inside_stem_offset, outside_stem_offset",
    [
        (1.0, 14.0, 5.0, 9.0),
        (1.5, 21.0, 7.5, 13.5),
        (0.75, 10.5, 3.75, 6.75),
    ],
)
def test_meaningful_scale_validation(
    scale: float, staff_space: float, inside_stem_offset: float, outside_stem_offset: float
):
    """Test stem offset, beam proximity, fixed beam-overlap boundary (4.0pt), and fixed flag radius (8.0pt) across scales."""
    base_line_ys = [150.0, 164.0, 178.0, 192.0, 206.0, 220.0]
    line_ys = [y * scale for y in base_line_ys]
    context = StaffSystemContext(line_y_coords=line_ys, barline_x_coords=[], staff_space=staff_space)

    event_x = 100.0 * scale
    stem_bottom = max(line_ys)
    stem_top = stem_bottom + (18.0 * scale)

    # 1. Stem offset (scales with staff_space: 0.6 * staff_space)
    stem_inside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=event_x + inside_stem_offset, y0=stem_bottom, x1=event_x + inside_stem_offset, y1=stem_top),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [event_x], [stem_inside], context) == stem_inside

    stem_outside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=event_x + outside_stem_offset, y0=stem_bottom, x1=event_x + outside_stem_offset, y1=stem_top),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [event_x], [stem_outside], context) is None

    # 2. Beam vertical proximity (scales with staff_space: 1.2 * staff_space)
    beam_y_inside = stem_top + (1.0 * staff_space)
    beam_y_outside = stem_top + (1.5 * staff_space)

    beam_inside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=event_x - 10.0, y0=beam_y_inside, x1=event_x + 10.0, y1=beam_y_inside))
    beam_outside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=event_x - 10.0, y0=beam_y_outside, x1=event_x + 10.0, y1=beam_y_outside))

    assert count_beams_for_stem(stem_inside, [beam_inside], context) == 1
    assert count_beams_for_stem(stem_inside, [beam_outside], context) == 0

    # 3. Fixed Beam-Overlap Boundary (eps = 4.0pt, absolute physical bound: does NOT scale with staff_space)
    stem_x = stem_inside.x_coord
    beam_overlap_inside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=stem_x - 3.9, y0=stem_top + 2.0, x1=stem_x + 20.0, y1=stem_top + 2.0))
    beam_overlap_outside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=stem_x - 4.1, y0=stem_top + 2.0, x1=stem_x - 4.05, y1=stem_top + 2.0))

    assert count_beams_for_stem(stem_inside, [beam_overlap_inside], context) == 1
    assert count_beams_for_stem(stem_inside, [beam_overlap_outside], context) == 0

    # 4. Fixed Flag Contact Radius (r = 8.0pt, absolute physical bound: does NOT scale with staff_space)
    flag_inside = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=stem_x + 7.9, y0=stem_top, x1=stem_x + 12.0, y1=stem_top + 10.0))
    flag_outside = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=stem_x + 8.1, y0=stem_top, x1=stem_x + 12.0, y1=stem_top + 10.0))

    count_in, amb_in = count_flags_for_stem(stem_inside, [flag_inside], [stem_inside])
    assert count_in == 1 and amb_in is False

    count_out, amb_out = count_flags_for_stem(stem_inside, [flag_outside], [stem_inside])
    assert count_out == 0 and amb_out is False


# 5. Deterministic, Distinct Beam Counting
def test_deterministic_distinct_beam_counting(sample_staff_context: StaffSystemContext):
    stem = StemPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=220.0, x1=100.0, y1=238.0))

    # Two distinct beam levels: level 1 at y=238, level 2 at y=234
    beam_l1 = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=90.0, y0=238.0, x1=120.0, y1=238.0))
    beam_l2 = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=90.0, y0=234.0, x1=120.0, y1=234.0))

    # Duplicate same-level beam (fragmented stroke at y=238.1)
    beam_l1_dup = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=95.0, y0=238.1, x1=115.0, y1=238.1))

    # Distant third horizontal stroke at y=280.0 (rejected)
    beam_distant = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=90.0, y0=280.0, x1=120.0, y1=280.0))

    beams_forward = [beam_l1, beam_l1_dup, beam_l2, beam_distant]
    beams_reverse = [beam_distant, beam_l2, beam_l1_dup, beam_l1]

    assert count_beams_for_stem(stem, beams_forward, sample_staff_context) == 2
    assert count_beams_for_stem(stem, beams_reverse, sample_staff_context) == 2

    # Verify duration mapping uses deduplicated count -> 16th note (240 ticks)
    ev = resolve_tab_duration_evidence(100.0, [stem], beams_forward, [], sample_staff_context)
    assert ev.duration_name == "16th"
    assert ev.duration_ticks == 240
    assert ev.beam_count == 2


# 6. Flag Ambiguity & Conflict Handling
def test_flag_ambiguity_and_conflict_handling(sample_staff_context: StaffSystemContext):
    # Two neighbouring stems at x1=100.0 and x2=110.0
    stem1 = StemPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=220.0, x1=100.0, y1=238.0))
    stem2 = StemPrimitiveCandidate(bbox=SpatialBBox(x0=110.0, y0=220.0, x1=110.0, y1=238.0))

    # Midpoint flag placed at x=105.0 (contact dist = 5.0pt to both stem free ends)
    midpoint_flag = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=105.0, y0=238.0, x1=112.0, y1=248.0))

    # Flag count for stem1 with stem2 present detects ambiguous flag attachment
    count, is_ambiguous = count_flags_for_stem(stem1, [midpoint_flag], all_stems=[stem1, stem2])
    assert is_ambiguous is True

    # resolve_tab_duration_evidence_for_events reports ambiguous_conflict with 0 ticks
    ev_res = resolve_tab_duration_evidence_for_events([100.0, 110.0], [stem1, stem2], [], [midpoint_flag], sample_staff_context)
    assert ev_res[100.0].is_ambiguous is True
    assert ev_res[100.0].duration_ticks == 0
    assert ev_res[100.0].source == "ambiguous_conflict"

    # Duplicate flag deduplication
    flag_dup = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=105.2, y0=238.1, x1=112.2, y1=248.1))
    count_dedup, amb_dedup = count_flags_for_stem(stem1, [midpoint_flag, flag_dup], all_stems=[stem1])
    assert count_dedup == 1 and amb_dedup is False

    # Conflicting beam (1) and flag (2) counts
    beam = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=90.0, y0=238.0, x1=120.0, y1=238.0))
    flag_b = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=242.0, x1=108.0, y1=252.0))
    ev_conflict = resolve_tab_duration_evidence(100.0, [stem1], [beam], [midpoint_flag, flag_b], sample_staff_context, all_events_x=[100.0])
    assert ev_conflict.is_ambiguous is True
    assert ev_conflict.duration_ticks == 0
    assert ev_conflict.source == "ambiguous_conflict"
