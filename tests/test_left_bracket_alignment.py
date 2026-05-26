from __future__ import annotations

from score2gp.pdf import _detect_tab_systems


class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class MockPage:
    def __init__(self, drawings: list):
        self._drawings = drawings

    def get_drawings(self) -> list:
        return self._drawings


def test_left_bracket_barline_alignment_acceptance() -> None:
    # 1. Create a 6-line TAB staff from Y: 624.102 to 655.992
    y0 = 624.102
    y1 = 655.992
    gap = (y1 - y0) / 5  # 6.378
    ys = [y0 + idx * gap for idx in range(6)]

    # Draw 6 horizontal lines from X: 28.346 to X: 500.0
    x0 = 28.346
    x1 = 500.0
    drawings = []
    
    horizontal_items = []
    for y in ys:
        horizontal_items.append(("l", MockPoint(x0, y), MockPoint(x1, y)))
    drawings.append({"items": horizontal_items})

    # 2. Add an overarching left-edge system bracket/barline at X: 28.346 with height 82.833
    # bottom matches y1 (655.992), top spans upward (y_min = y1 - 82.833 = 573.159)
    y_max = y1
    y_min = y1 - 82.833
    vertical_items = [
        ("l", MockPoint(x0, y_min), MockPoint(x0, y_max))
    ]
    drawings.append({"items": vertical_items})

    # Mock the fitz page with our drawing dictionary structure
    mock_page = MockPage(drawings)

    # 3. Detect systems on this page
    detected_systems = _detect_tab_systems(mock_page, page_index=1)

    # Assert that a system is detected
    assert len(detected_systems) == 1
    system = detected_systems[0]

    # Assert that the left boundary at 28.346 is successfully accepted as a valid barline
    assert len(system.barlines) == 1
    assert abs(system.barlines[0] - 28.346) < 0.001
    assert system.valid_barline_count == 1
    assert system.rejected_barline_count == 0
