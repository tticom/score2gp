import pytest
from pydantic import ValidationError
from score2gp.build_ir import BuildIrInputRiskError
from score2gp.pdf_geometry import (
    VisualVibratoEvidence,
    VisualSlideEvidence,
    extract_visual_vibrato_evidence,
    extract_visual_slide_evidence,
    _get_coord,
)


class DummyPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class DummyStaff:
    def __init__(self, y0: float, y1: float, line_ys: list[float]):
        self.y0 = y0
        self.y1 = y1
        self.line_ys = line_ys


def test_visual_vibrato_evidence_model():
    v = VisualVibratoEvidence(
        bbox=(10.0, 20.0, 50.0, 30.0),
        cycles=3,
        amplitude=5.0,
        staff_index=1,
    )
    assert v.cycles == 3
    assert v.amplitude == 5.0
    assert v.staff_index == 1
    assert v.bbox == (10.0, 20.0, 50.0, 30.0)


def test_visual_slide_evidence_model():
    s = VisualSlideEvidence(
        bbox=(10.0, 20.0, 30.0, 40.0),
        slope=1.0,
        direction="down",
        staff_index=1,
        string_index=2,
    )
    assert s.slope == 1.0
    assert s.direction == "down"
    assert s.staff_index == 1
    assert s.string_index == 2

    with pytest.raises(ValidationError):
        VisualSlideEvidence(
            bbox=(10.0, 20.0, 30.0, 40.0),
            slope=1.0,
            direction="invalid_direction",
        )


def test_extract_visual_vibrato_from_synthetic_bezier():
    drawings = [
        {
            "items": [
                ("c", DummyPoint(10, 20), DummyPoint(15, 25), DummyPoint(20, 15), DummyPoint(25, 20)),
                ("c", DummyPoint(25, 20), DummyPoint(30, 25), DummyPoint(35, 15), DummyPoint(40, 20)),
            ]
        }
    ]
    staves = [DummyStaff(15.0, 45.0, [15.0, 21.0, 27.0, 33.0, 39.0, 45.0])]
    vibratos = extract_visual_vibrato_evidence(drawings, staves=staves)
    assert len(vibratos) == 1
    assert vibratos[0].cycles == 2
    assert vibratos[0].amplitude == 5.0
    assert vibratos[0].staff_index == 1
    assert vibratos[0].bbox == (10.0, 15.0, 40.0, 25.0)


def test_single_slur_bezier_filtered_out():
    # Single slur arc (cycles == 1) should be filtered out as false positive vibrato
    drawings = [
        {
            "items": [
                ("c", DummyPoint(10, 20), DummyPoint(20, 30), DummyPoint(40, 30), DummyPoint(50, 20)),
            ]
        }
    ]
    vibratos = extract_visual_vibrato_evidence(drawings)
    assert len(vibratos) == 0


def test_extract_visual_slide_from_synthetic_line():
    staves = [DummyStaff(20.0, 50.0, [20.0, 26.0, 32.0, 38.0, 44.0, 50.0])]
    drawings_up = [
        {
            "items": [
                ("l", DummyPoint(10, 50), DummyPoint(30, 30))
            ]
        }
    ]
    slides_up = extract_visual_slide_evidence(drawings_up, staves=staves)
    assert len(slides_up) == 1
    assert slides_up[0].direction == "up"
    assert slides_up[0].slope == -1.0
    assert slides_up[0].staff_index == 1
    assert slides_up[0].string_index == 4  # mid_y 40.0 is closest to string_y 38.0 (index 4)
    assert slides_up[0].bbox == (10.0, 30.0, 30.0, 50.0)

    drawings_down = [
        {
            "items": [
                ("l", DummyPoint(10, 30), DummyPoint(30, 50))
            ]
        }
    ]
    slides_down = extract_visual_slide_evidence(drawings_down, staves=staves)
    assert len(slides_down) == 1
    assert slides_down[0].direction == "down"
    assert slides_down[0].slope == 1.0
    assert slides_down[0].staff_index == 1


def test_proximity_cutoff():
    # Graphic element at y=300.0 far from staff at y=20.0..50.0 should not associate staff_index
    staves = [DummyStaff(20.0, 50.0, [20.0, 26.0, 32.0, 38.0, 44.0, 50.0])]
    drawings_far = [
        {
            "items": [
                ("l", DummyPoint(10, 320), DummyPoint(30, 300))
            ]
        }
    ]
    slides_far = extract_visual_slide_evidence(drawings_far, staves=staves)
    assert len(slides_far) == 1
    assert slides_far[0].staff_index is None
    assert slides_far[0].string_index is None


def test_malformed_point_handling():
    assert _get_coord(None, "x", 0) is None
    assert _get_coord("invalid", "x", 0) is None
    assert _get_coord(DummyPoint(12.3, 45.6), "x", 0) == 12.3
    assert _get_coord((7.5, 8.5), "x", 0) == 7.5


def test_negative_controls():
    horizontal_drawings = [
        {
            "items": [
                ("l", DummyPoint(10, 50), DummyPoint(200, 50))
            ]
        }
    ]
    assert len(extract_visual_slide_evidence(horizontal_drawings)) == 0
    assert len(extract_visual_vibrato_evidence(horizontal_drawings)) == 0

    vertical_drawings = [
        {
            "items": [
                ("l", DummyPoint(50, 10), DummyPoint(50, 100))
            ]
        }
    ]
    assert len(extract_visual_slide_evidence(vertical_drawings)) == 0
    assert len(extract_visual_vibrato_evidence(vertical_drawings)) == 0


def test_real_pdf_fixture_drawing_extraction():
    import fitz
    from pathlib import Path
    pdf_path = Path("fixtures/public/Derek Trucks BB King.pdf")

    with fitz.open(pdf_path) as doc:
        drawings = doc[0].get_drawings()
        vibratos = extract_visual_vibrato_evidence(drawings)
        slides = extract_visual_slide_evidence(drawings)

        assert isinstance(vibratos, list)
        assert isinstance(slides, list)
        assert len(vibratos) > 0
        assert len(slides) > 0
        for v in vibratos:
            assert v.cycles >= 2
            assert v.amplitude > 0.5
        for s in slides:
            assert s.direction in ("up", "down")
            assert 0.15 <= abs(s.slope) <= 3.0


def test_end_to_end_visual_vibrato_and_slide_scoreir_attachment_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import (
        TabRaw,
        make_tab_candidate,
        make_visual_vibrato_candidate,
        make_visual_slide_candidate,
    )
    from score2gp.build_ir import build_ir_from_tabraw_only

    vibrato_cand = make_visual_vibrato_candidate(
        candidate_id="vib-01",
        raw_text="vibrato",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        bbox_values=(100.0, 20.0, 120.0, 30.0),
        cycles=3,
        amplitude=4.0,
    )
    slide_cand = make_visual_slide_candidate(
        candidate_id="slide-01",
        raw_text="slide",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(115.0, 20.0, 155.0, 30.0),
        slope=1.0,
        direction="up",
    )

    fret1 = make_tab_candidate(
        candidate_id="fret-01",
        raw_text="5",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 30.0),
        confidence=0.9,
    )
    fret2 = make_tab_candidate(
        candidate_id="fret-02",
        raw_text="7",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(160.0, 20.0, 170.0, 30.0),
        confidence=0.9,
    )

    tabraw = TabRaw(candidates=[fret1, fret2, vibrato_cand, slide_cand])
    tabraw_file = tmp_path / "tabraw.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"


def test_multi_system_bar_index_alignment_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import TabRaw, make_tab_candidate, make_visual_vibrato_candidate
    from score2gp.build_ir import build_ir_from_tabraw_only

    fret_sys1 = make_tab_candidate(
        candidate_id="fret-s1",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 30.0),
        confidence=0.9,
    )
    fret_sys2 = make_tab_candidate(
        candidate_id="fret-s2",
        raw_text="5",
        page_index=1,
        system_index=2,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 60.0, 110.0, 70.0),
        confidence=0.9,
    )
    vibrato_sys2 = make_visual_vibrato_candidate(
        candidate_id="vib-s2",
        raw_text="vibrato",
        page_index=1,
        system_index=2,
        staff_index=1,
        bar_index=1,
        bbox_values=(100.0, 55.0, 120.0, 65.0),
        cycles=3,
        amplitude=4.0,
    )

    tabraw = TabRaw(candidates=[fret_sys1, fret_sys2, vibrato_sys2])
    tabraw_file = tmp_path / "tabraw_multi_sys.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"


def test_downward_slide_style_and_chord_vibrato_snapping_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import (
        TabRaw,
        make_tab_candidate,
        make_visual_vibrato_candidate,
        make_visual_slide_candidate,
    )
    from score2gp.build_ir import build_ir_from_tabraw_only

    slide_down = make_visual_slide_candidate(
        candidate_id="slide-down",
        raw_text="slide",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=2,
        bbox_values=(100.0, 20.0, 130.0, 30.0),
        slope=-1.0,
        direction="down",
    )

    vib_cand = make_visual_vibrato_candidate(
        candidate_id="vib-chord",
        raw_text="vibrato",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=2,
        bbox_values=(100.0, 20.0, 120.0, 30.0),
        cycles=3,
        amplitude=4.0,
    )

    fret_c1_s1 = make_tab_candidate(
        candidate_id="fret-1a",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 25.0),
        confidence=0.9,
    )
    fret_c1_s2 = make_tab_candidate(
        candidate_id="fret-1b",
        raw_text="5",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=2,
        bbox_values=(100.0, 30.0, 110.0, 35.0),
        confidence=0.9,
    )
    fret_c2_s2 = make_tab_candidate(
        candidate_id="fret-2",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=2,
        bbox_values=(140.0, 30.0, 150.0, 35.0),
        confidence=0.9,
    )

    tabraw = TabRaw(candidates=[fret_c1_s1, fret_c1_s2, fret_c2_s2, slide_down, vib_cand])
    tabraw_file = tmp_path / "tabraw_chord_slide.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"


def test_fret_candidate_none_system_index_no_crash_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import TabRaw, make_tab_candidate, make_visual_vibrato_candidate
    from score2gp.build_ir import build_ir_from_tabraw_only

    # Candidate with explicit system_index=1
    fret1 = make_tab_candidate(
        candidate_id="fret-1",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 30.0),
        confidence=0.9,
    )
    # Unparsed/raw fret candidate with system_index=None (kind="fret")
    fret_none_sys = make_tab_candidate(
        candidate_id="fret-none-sys",
        raw_text="?",
        page_index=1,
        system_index=None,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(120.0, 20.0, 130.0, 30.0),
        confidence=0.1,
    )
    fret_none_sys.kind = "fret"
    vibrato = make_visual_vibrato_candidate(
        candidate_id="vib-none-sys",
        raw_text="vibrato",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        bbox_values=(100.0, 15.0, 120.0, 25.0),
        cycles=3,
        amplitude=4.0,
    )

    tabraw = TabRaw(candidates=[fret1, fret_none_sys, vibrato])
    tabraw_file = tmp_path / "tabraw_valid.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"


def test_palm_mute_and_let_ring_span_attachments_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import (
        TabRaw,
        make_tab_candidate,
        make_palm_mute_candidate,
    )
    from score2gp.build_ir import build_ir_from_tabraw_only

    # 3 sequential fret events in Bar 1 (x=100, x=140, x=180)
    fret1 = make_tab_candidate(
        candidate_id="fret-1",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 30.0),
        confidence=0.9,
    )
    fret2 = make_tab_candidate(
        candidate_id="fret-2",
        raw_text="5",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(140.0, 20.0, 150.0, 30.0),
        confidence=0.9,
    )
    fret3 = make_tab_candidate(
        candidate_id="fret-3",
        raw_text="7",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(180.0, 20.0, 190.0, 30.0),
        confidence=0.9,
    )

    # Palm mute candidate spanning x0=95 to x1=185
    pm_cand = make_palm_mute_candidate(
        candidate_id="pm-1",
        raw_text="P.M.",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(95.0, 10.0, 185.0, 18.0),
    )

    tabraw = TabRaw(candidates=[fret1, fret2, fret3, pm_cand])
    tabraw_file = tmp_path / "tabraw_pm.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"


def test_track_wide_span_multi_string_propagation_refuses_without_note_durations(tmp_path):
    from score2gp.tabraw import (
        TabRaw,
        make_tab_candidate,
        make_palm_mute_candidate,
    )
    from score2gp.build_ir import build_ir_from_tabraw_only

    # Event 1 on String 1 (x=100)
    fret1 = make_tab_candidate(
        candidate_id="fret-1",
        raw_text="3",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(100.0, 20.0, 110.0, 30.0),
        confidence=0.9,
    )
    # Event 2 on String 2 (x=140) Ã¢â‚¬â€ different string!
    fret2 = make_tab_candidate(
        candidate_id="fret-2",
        raw_text="5",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=2,
        bbox_values=(140.0, 30.0, 150.0, 40.0),
        confidence=0.9,
    )
    # Event 3 on String 1 (x=180)
    fret3 = make_tab_candidate(
        candidate_id="fret-3",
        raw_text="7",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=1,
        bbox_values=(180.0, 20.0, 190.0, 30.0),
        confidence=0.9,
    )

    # Track-wide P.M. candidate (string=None) spanning x0=95 to x1=185
    pm_trackwide = make_palm_mute_candidate(
        candidate_id="pm-trackwide",
        raw_text="P.M.",
        page_index=1,
        system_index=1,
        staff_index=1,
        bar_index=1,
        string=None,  # Track-wide span!
        bbox_values=(95.0, 10.0, 185.0, 18.0),
    )

    tabraw = TabRaw(candidates=[fret1, fret2, fret3, pm_trackwide])
    tabraw_file = tmp_path / "tabraw_pm_trackwide.json"
    tabraw.to_json_file(tabraw_file)

    with pytest.raises(BuildIrInputRiskError) as exc:
        build_ir_from_tabraw_only(tabraw_file)
    assert exc.value.category == "pdf_only_tab_note_durations_missing"
