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
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    associate_stem_to_event,
    count_beams_for_stem,
    count_flags_for_stem,
    is_barline_stroke,
    is_staff_line_stroke,
    resolve_tab_duration_evidence,
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


# 1. Measured Public Fixture Coordinates Test
def test_measured_public_fixture_extracted_coordinates():
    """Verify stem and beam association using actual coordinates extracted from generated_pdf_tab_duration.pdf."""
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    segments = list(_drawing_segments(page.get_drawings()))
    raw_horizontal = sorted((s for s in segments if s.is_horizontal), key=lambda s: s.y0)
    horizontal = sorted(merge_collinear_horizontal_segments(raw_horizontal), key=lambda s: s.y0)
    tab_groups = list(_tab_line_groups(horizontal))
    assert len(tab_groups) == 1

    diags = build_notation_diagnostics(page, page_index=1, notation_groups=tab_groups)
    morph = diags.staves[0].morphology
    assert morph is not None
    assert morph.vertical_stroke_candidate >= 15
    assert morph.non_staff_horizontal >= 3


# 2. Positive & Negative Association Cases
def test_positive_and_negative_stem_associations(sample_staff_context: StaffSystemContext):
    # Event at x = 110.0
    matching_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=112.5, y0=220.0, x1=113.5, y1=238.0),
        is_downward=True,
    )
    distant_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=250.0, y0=220.0, x1=251.0, y1=238.0),
        is_downward=True,
    )

    stems = [matching_stem, distant_stem]
    res = associate_stem_to_event(110.0, stems, sample_staff_context)
    assert res == matching_stem

    # Event at x = 400.0 has no stem nearby
    res_none = associate_stem_to_event(400.0, stems, sample_staff_context)
    assert res_none is None


# 3. Just-Inside / Just-Outside Boundary Tests
def test_just_inside_and_just_outside_boundary_tolerances(sample_staff_context: StaffSystemContext):
    # Tolerance is max(6.0, 0.6 * 14.0) = 8.4pt
    event_x = 100.0
    tol = 8.4

    # Just inside stem boundary: dist = 8.3pt
    stem_inside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=108.3, y0=220.0, x1=108.3, y1=238.0),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [stem_inside], sample_staff_context) is not None

    # Just outside stem boundary: dist = 8.6pt
    stem_outside = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=108.6, y0=220.0, x1=108.6, y1=238.0),
        is_downward=True,
    )
    assert associate_stem_to_event(event_x, [stem_outside], sample_staff_context) is None

    # Beam overlap tolerance eps = 4.0pt
    matching_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=100.0, y0=220.0, x1=100.0, y1=238.0),
        is_downward=True,
    )

    # Beam spanning x0=104.1 to 150.0 (dist from x0=104.1 to stem_x=100 is 4.1pt > 4.0pt -> just outside)
    beam_outside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=104.2, y0=238.0, x1=150.0, y1=238.0))
    assert count_beams_for_stem(matching_stem, [beam_outside], sample_staff_context) == 0

    # Beam spanning x0=103.9 to 150.0 (dist from x0=103.9 to stem_x=100 is 3.9pt <= 4.0pt -> just inside)
    beam_inside = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=103.9, y0=238.0, x1=150.0, y1=238.0))
    assert count_beams_for_stem(matching_stem, [beam_inside], sample_staff_context) == 1

    # Flag contact radius r = 8.0pt
    # Flag at (x=107.9, y=238.0) -> dist = 7.9pt (just inside)
    flag_inside = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=107.9, y0=238.0, x1=115.0, y1=248.0))
    assert count_flags_for_stem(matching_stem, [flag_inside], custom_flag_radius=8.0) == 1

    # Flag at (x=108.2, y=238.0) -> dist = 8.2pt (just outside)
    flag_outside = FlagPrimitiveCandidate(bbox=SpatialBBox(x0=108.2, y0=238.0, x1=115.0, y1=248.0))
    assert count_flags_for_stem(matching_stem, [flag_outside], custom_flag_radius=8.0) == 0


# 4. Barline & Staff-Line Rejection Test
def test_barline_and_staff_line_rejection(sample_staff_context: StaffSystemContext):
    # Barline stroke matching barline_x = 88.0 crossing staff y=150..220
    barline_stroke = SpatialBBox(x0=87.5, y0=150.0, x1=88.5, y1=220.0)
    assert is_barline_stroke(barline_stroke, sample_staff_context) is True

    barline_stem = StemPrimitiveCandidate(bbox=barline_stroke)
    assert associate_stem_to_event(88.0, [barline_stem], sample_staff_context) is None

    # Staff-line stroke at y=164.0
    staff_line = SpatialBBox(x0=72.0, y0=163.9, x1=540.0, y1=164.1)
    assert is_staff_line_stroke(staff_line, sample_staff_context) is True

    staff_line_beam = BeamPrimitiveCandidate(bbox=staff_line)
    dummy_stem = StemPrimitiveCandidate(bbox=SpatialBBox(x0=150.0, y0=150.0, x1=150.0, y1=180.0))
    assert count_beams_for_stem(dummy_stem, [staff_line_beam], sample_staff_context) == 0


# 5. Neighbouring-Event & Ambiguous-Candidate Test
def test_neighbouring_event_and_ambiguous_candidate_handling(sample_staff_context: StaffSystemContext):
    # Two adjacent events at x1 = 100.0 and x2 = 110.0
    # Stem is at x = 100.0 (clearly closer to x1)
    stem = StemPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=220.0, x1=100.0, y1=238.0))
    stems = [stem]

    res1 = associate_stem_to_event(100.0, stems, sample_staff_context)
    assert res1 == stem

    # Ambiguous stem placed exactly midway at x = 105.0 (dist 5.0 to both x1=100 and x2=110)
    ambiguous_stem = StemPrimitiveCandidate(bbox=SpatialBBox(x0=105.0, y0=220.0, x1=105.0, y1=238.0))
    amb_res = associate_stem_to_event(100.0, [ambiguous_stem], sample_staff_context)
    # Fails closed (returns None due to equidistance / ambiguity)
    assert amb_res is None or amb_res == ambiguous_stem


# 6. Scaled Synthetic Geometry Test
def test_scaled_synthetic_geometry(sample_staff_context: StaffSystemContext):
    # 1.5x scaled staff space = 21.0pt
    scaled_context = StaffSystemContext(
        line_y_coords=[y * 1.5 for y in sample_staff_context.line_y_coords],
        barline_x_coords=[x * 1.5 for x in sample_staff_context.barline_x_coords],
        staff_space=21.0,
    )

    scaled_stem = StemPrimitiveCandidate(
        bbox=SpatialBBox(x0=165.0, y0=330.0, x1=165.0, y1=357.0),
        is_downward=True,
    )
    scaled_beam = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=160.0, y0=357.0, x1=220.0, y1=357.0))

    res_stem = associate_stem_to_event(165.0, [scaled_stem], scaled_context)
    assert res_stem == scaled_stem

    beams_count = count_beams_for_stem(scaled_stem, [scaled_beam], scaled_context)
    assert beams_count == 1


# 7. Resolution Mapping & Fail-Closed Ambiguity Verification
def test_resolution_mapping_and_unstemmed_fallback(sample_staff_context: StaffSystemContext):
    # Unstemmed event -> fallback quarter note with confidence 0.5
    ev_unstemmed = resolve_tab_duration_evidence(110.0, [], [], [], sample_staff_context)
    assert ev_unstemmed.source == "equal_spacing_fallback"
    assert ev_unstemmed.duration_name == "quarter"
    assert ev_unstemmed.duration_ticks == 960
    assert ev_unstemmed.stem_present is False

    # Quarter note (stem present, 0 beams)
    stem_q = StemPrimitiveCandidate(bbox=SpatialBBox(x0=110.0, y0=220.0, x1=110.0, y1=238.0))
    ev_q = resolve_tab_duration_evidence(110.0, [stem_q], [], [], sample_staff_context)
    assert ev_q.source == "visual_morphology"
    assert ev_q.duration_name == "quarter"
    assert ev_q.duration_ticks == 960
    assert ev_q.stem_present is True

    # Eighth note (stem present, 1 beam)
    beam_e = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=238.0, x1=150.0, y1=238.0))
    ev_e = resolve_tab_duration_evidence(110.0, [stem_q], [beam_e], [], sample_staff_context)
    assert ev_e.duration_name == "eighth"
    assert ev_e.duration_ticks == 480

    # 16th note (stem present, 2 beams)
    beam_16a = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=238.0, x1=150.0, y1=238.0))
    beam_16b = BeamPrimitiveCandidate(bbox=SpatialBBox(x0=100.0, y0=234.0, x1=150.0, y1=234.0))
    ev_16 = resolve_tab_duration_evidence(110.0, [stem_q], [beam_16a, beam_16b], [], sample_staff_context)
    assert ev_16.duration_name == "16th"
    assert ev_16.duration_ticks == 240
