from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]
import pytest

from score2gp.pdf_staff_detection import (
    _drawing_segments,
    merge_collinear_horizontal_segments,
    _tab_line_groups,
)
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
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
    """Prove that a midpoint stem placed between two neighbouring events marks both as ambiguous."""
    events_x = [100.0, 110.0]
    # Midpoint stem placed at x = 105.0 (equidistant 5.0pt to both events)
    midpoint_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=105.0, y0=220.0, x1=105.0, y1=238.0),
        is_downward=True,
    )

    mapping = associate_stems_to_events(events_x, [midpoint_stem], sample_staff_context)
    assert isinstance(mapping[100.0], AmbiguityDiagnostic)
    assert isinstance(mapping[110.0], AmbiguityDiagnostic)

    ev_mapping = resolve_tab_duration_evidence_for_events(events_x, [midpoint_stem], [], [], sample_staff_context)
    assert ev_mapping[100.0].is_ambiguous is True
    assert ev_mapping[100.0].duration_ticks == 0
    assert ev_mapping[100.0].source == "ambiguous_conflict"

    assert ev_mapping[110.0].is_ambiguous is True
    assert ev_mapping[110.0].duration_ticks == 0
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

    # Verify order independence: passing events in reverse order produces identical mapping
    mapping_rev = associate_stems_to_events([110.0, 100.0], [stem], sample_staff_context)
    assert mapping_rev[100.0] == stem
    assert mapping_rev[110.0] is None


# 2. Distinguish Absence from Ambiguity
def test_distinguish_unstemmed_absence_from_ambiguity(sample_staff_context: StaffSystemContext):
    """Prove that unstemmed events emit equal-spacing placeholders while ambiguous events fail closed."""
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


# 3. Exercise Actual Extracted Fixture Geometry
def test_exercise_actual_extracted_fixture_geometry():
    """Extract actual primitives and event coordinates from generated_pdf_tab_duration.pdf and run associator."""
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    segments = list(_drawing_segments(page.get_drawings()))
    raw_horizontal = sorted((s for s in segments if s.is_horizontal), key=lambda s: s.y0)
    horizontal = sorted(merge_collinear_horizontal_segments(raw_horizontal), key=lambda s: s.y0)
    tab_groups = list(_tab_line_groups(horizontal))
    assert len(tab_groups) == 1

    context = StaffSystemContext(
        line_y_coords=[150.0, 164.0, 178.0, 192.0, 206.0, 220.0],
        barline_x_coords=[88.0, 306.0, 526.0],
        staff_space=14.0,
    )

    # Extract actual vertical stems, beams, and flags from page drawings
    stems: list[StemPrimitiveCandidate] = []
    beams: list[BeamPrimitiveCandidate] = []
    flags: list[FlagPrimitiveCandidate] = []

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
                # Vertical stem candidate (dy >= 5.0, dx <= 2.0)
                if dy >= 5.0 and dx <= 2.0:
                    stems.append(StemPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1), is_downward=True))
                # Horizontal non-staff beam candidate
                elif dy <= 1.0 and dx >= 0.5 * context.staff_space:
                    if not any(abs(iy0 - ly) <= 1.0 for ly in context.line_y_coords):
                        beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))
                # Diagonal flag candidate
                elif dx >= 3.0 and dy >= 3.0:
                    flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))

    # Bar 1 event x-coords (4 quarter notes)
    bar1_events = [110.0, 150.0, 190.0, 230.0]
    ev1_res = resolve_tab_duration_evidence_for_events(bar1_events, stems, beams, flags, context)
    for x in bar1_events:
        assert ev1_res[x].duration_name == "quarter"
        assert ev1_res[x].duration_ticks == 960
        assert ev1_res[x].stem_present is True
        assert ev1_res[x].beam_count == 0
        assert ev1_res[x].flag_count == 0

    # Bar 2 event x-coords
    # 2 flagged eighth notes (330, 370), 2 beamed eighth notes (410, 450), 4 beamed 16th notes (470, 485, 500, 515)
    bar2_events = [330.0, 370.0, 410.0, 450.0, 470.0, 485.0, 500.0, 515.0]
    ev2_res = resolve_tab_duration_evidence_for_events(bar2_events, stems, beams, flags, context)

    # Flagged eighth notes
    assert ev2_res[330.0].duration_name == "eighth"
    assert ev2_res[330.0].duration_ticks == 480
    assert ev2_res[330.0].flag_count == 1

    assert ev2_res[370.0].duration_name == "eighth"
    assert ev2_res[370.0].duration_ticks == 480
    assert ev2_res[370.0].flag_count == 1

    # Beamed eighth notes
    assert ev2_res[410.0].duration_name == "eighth"
    assert ev2_res[410.0].duration_ticks == 480
    assert ev2_res[410.0].beam_count == 1

    assert ev2_res[450.0].duration_name == "eighth"
    assert ev2_res[450.0].duration_ticks == 480
    assert ev2_res[450.0].beam_count == 1

    # Beamed sixteenth notes
    for x in [470.0, 485.0, 500.0, 515.0]:
        assert ev2_res[x].duration_name == "16th"
        assert ev2_res[x].duration_ticks == 240
        assert ev2_res[x].beam_count == 2


# 4. Meaningful Scale Validation
@pytest.mark.parametrize(
    "scale, staff_space, inside_offset, outside_offset",
    [
        (1.0, 14.0, 5.0, 9.0),
        (1.5, 21.0, 7.5, 13.5),
        (0.75, 10.5, 3.75, 6.75),
    ],
)
def test_meaningful_scale_validation(scale: float, staff_space: float, inside_offset: float, outside_offset: float):
    """Test non-zero stem, beam, and flag offsets at 1.0x, 1.5x, and 0.75x staff space scales."""
    base_line_ys = [150.0, 164.0, 178.0, 192.0, 206.0, 220.0]
    line_ys = [y * scale for y in base_line_ys]
    context = StaffSystemContext(line_y_coords=line_ys, barline_x_coords=[], staff_space=staff_space)

    event_x = 100.0 * scale
    stem_bottom = max(line_ys)
    stem_top = stem_bottom + (18.0 * scale)

    # Just-inside stem candidate (offset = inside_offset)
    stem_inside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=event_x + inside_offset, y0=stem_bottom, x1=event_x + inside_offset, y1=stem_top),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [event_x], [stem_inside], context) == stem_inside

    # Just-outside stem candidate (offset = outside_offset)
    stem_outside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=event_x + outside_offset, y0=stem_bottom, x1=event_x + outside_offset, y1=stem_top),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [event_x], [stem_outside], context) is None

    # Beam vertical proximity scales with staff_space (1.2 * staff_space)
    beam_y_inside = stem_top + (1.0 * staff_space)  # inside
    beam_y_outside = stem_top + (1.5 * staff_space)  # outside

    beam_inside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=event_x - 10.0, y0=beam_y_inside, x1=event_x + 10.0, y1=beam_y_inside))
    beam_outside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=event_x - 10.0, y0=beam_y_outside, x1=event_x + 10.0, y1=beam_y_outside))

    assert count_beams_for_stem(stem_inside, [beam_inside], context) == 1
    assert count_beams_for_stem(stem_inside, [beam_outside], context) == 0


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

    # Reversing order produces identical deduplicated count of 2 distinct levels
    count_fw = count_beams_for_stem(stem, beams_forward, sample_staff_context)
    count_rv = count_beams_for_stem(stem, beams_reverse, sample_staff_context)

    assert count_fw == 2
    assert count_rv == 2

    # Verify duration mapping uses deduplicated count -> 16th note (240 ticks)
    ev = resolve_tab_duration_evidence(100.0, [stem], beams_forward, [], sample_staff_context)
    assert ev.duration_name == "16th"
    assert ev.duration_ticks == 240
    assert ev.beam_count == 2


# 6. Flag and Evidence Conflict Handling
def test_flag_deduplication_and_conflict_handling(sample_staff_context: StaffSystemContext):
    stem = StemPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=220.0, x1=100.0, y1=238.0))

    # Duplicate flags attached to same stem free end (y=238.0)
    flag1 = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=238.0, x1=108.0, y1=248.0))
    flag1_dup = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=100.5, y0=238.2, x1=108.5, y1=248.2))

    flags_count, _ = count_flags_for_stem(stem, [flag1, flag1_dup])
    assert flags_count == 1

    # Conflicting beam and flag counts: beam_count=1, flag_count=2
    beam = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=90.0, y0=238.0, x1=120.0, y1=238.0))
    flag2 = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=242.0, x1=108.0, y1=252.0))

    # Expect ambiguous_conflict outcome with duration_ticks = 0
    ev_conflict = resolve_tab_duration_evidence(100.0, [stem], [beam], [flag1, flag2], sample_staff_context)
    assert ev_conflict.is_ambiguous is True
    assert ev_conflict.duration_name == "ambiguous"
    assert ev_conflict.duration_ticks == 0
    assert ev_conflict.source == "ambiguous_conflict"
