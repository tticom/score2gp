import pytest
from pydantic import ValidationError
from score2gp.pdf_geometry import (
    VisualVibratoEvidence,
    VisualSlideEvidence,
    extract_visual_vibrato_evidence,
    extract_visual_slide_evidence,
)


class DummyPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


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
        string_index=2,
    )
    assert s.slope == 1.0
    assert s.direction == "down"
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
    vibratos = extract_visual_vibrato_evidence(drawings)
    assert len(vibratos) == 1
    assert vibratos[0].cycles == 2
    assert vibratos[0].amplitude == 5.0
    assert vibratos[0].bbox == (10.0, 15.0, 40.0, 25.0)


def test_extract_visual_slide_from_synthetic_line():
    drawings_up = [
        {
            "items": [
                ("l", DummyPoint(10, 50), DummyPoint(30, 30))
            ]
        }
    ]
    slides_up = extract_visual_slide_evidence(drawings_up)
    assert len(slides_up) == 1
    assert slides_up[0].direction == "up"
    assert slides_up[0].slope == -1.0
    assert slides_up[0].bbox == (10.0, 30.0, 30.0, 50.0)

    drawings_down = [
        {
            "items": [
                ("l", DummyPoint(10, 30), DummyPoint(30, 50))
            ]
        }
    ]
    slides_down = extract_visual_slide_evidence(drawings_down)
    assert len(slides_down) == 1
    assert slides_down[0].direction == "down"
    assert slides_down[0].slope == 1.0


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
