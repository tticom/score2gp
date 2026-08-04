import pytest
from pydantic import ValidationError
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
    if not pdf_path.exists():
        pytest.skip("Public PDF fixture not available")

    with fitz.open(pdf_path) as doc:
        drawings = doc[0].get_drawings()
        vibratos = extract_visual_vibrato_evidence(drawings)
        slides = extract_visual_slide_evidence(drawings)

        assert isinstance(vibratos, list)
        assert isinstance(slides, list)
        for v in vibratos:
            assert v.cycles >= 2
            assert v.amplitude > 0.5
        for s in slides:
            assert s.direction in ("up", "down")
            assert 0.15 <= abs(s.slope) <= 3.0
