from __future__ import annotations
import pytest
from score2gp.pdf_geometry import compute_staff_position_index


def test_compute_staff_position_index_positive_control_lines_and_spaces() -> None:
    line_y_coords = [100.0, 108.0, 116.0, 124.0, 132.0]

    # Verify line positions (exact matches)
    idx_0 = compute_staff_position_index(100.0, line_y_coords)
    assert idx_0.nearest_index == 0
    assert idx_0.is_snapped is True
    assert idx_0.snap_delta == 0.0

    idx_2 = compute_staff_position_index(108.0, line_y_coords)
    assert idx_2.nearest_index == 2
    assert idx_2.is_snapped is True
    assert idx_2.snap_delta == 0.0

    idx_4 = compute_staff_position_index(116.0, line_y_coords)
    assert idx_4.nearest_index == 4
    assert idx_4.is_snapped is True
    assert idx_4.snap_delta == 0.0

    idx_8 = compute_staff_position_index(132.0, line_y_coords)
    assert idx_8.nearest_index == 8
    assert idx_8.is_snapped is True
    assert idx_8.snap_delta == 0.0

    # Verify space positions
    idx_1 = compute_staff_position_index(104.0, line_y_coords)
    assert idx_1.nearest_index == 1
    assert idx_1.is_snapped is True
    assert idx_1.snap_delta == 0.0


def test_compute_staff_position_index_scaled_staff() -> None:
    # Scale: spacing = 12.0
    line_y_coords = [200.0, 212.0, 224.0, 236.0, 248.0]

    # Verify lines snap correctly at scale 12.0
    idx_0 = compute_staff_position_index(200.0, line_y_coords)
    assert idx_0.nearest_index == 0
    assert idx_0.is_snapped is True

    idx_2 = compute_staff_position_index(212.0, line_y_coords)
    assert idx_2.nearest_index == 2
    assert idx_2.is_snapped is True

    # Space index at scale
    idx_1 = compute_staff_position_index(206.0, line_y_coords)
    assert idx_1.nearest_index == 1
    assert idx_1.is_snapped is True

    # Coordinate slightly off but within tolerance (tolerance 0.25 on scale 12.0 is 0.25 * 6.0 = 1.5 points)
    idx_tolerant = compute_staff_position_index(201.0, line_y_coords) # diff = 1.0, snap_delta = 1.0 / 6.0 = 0.1666
    assert idx_tolerant.nearest_index == 0
    assert idx_tolerant.is_snapped is True


def test_compute_staff_position_index_above_and_below_staff() -> None:
    line_y_coords = [100.0, 108.0, 116.0, 124.0, 132.0]

    # Above top line (negative index)
    idx_neg_2 = compute_staff_position_index(92.0, line_y_coords)
    assert idx_neg_2.nearest_index == -2
    assert idx_neg_2.is_snapped is True

    # Below bottom line (greater than 8 index)
    idx_10 = compute_staff_position_index(140.0, line_y_coords)
    assert idx_10.nearest_index == 10
    assert idx_10.is_snapped is True


def test_compute_staff_position_index_unsnapped_dead_zone() -> None:
    line_y_coords = [100.0, 108.0, 116.0, 124.0, 132.0]

    # Ambiguous coordinate (y=102.5 -> raw = 0.625)
    idx_ambiguous = compute_staff_position_index(102.5, line_y_coords)
    assert idx_ambiguous.nearest_index == 1
    assert idx_ambiguous.is_snapped is False
    assert idx_ambiguous.snap_delta == 0.375

    # Exact half-way coordinate (y=102.0 -> raw = 0.5)
    # Testing exact half-way coordinate to assert is_snapped is False and snap_delta > tolerance,
    # without asserting a specific nearest_index to avoid banker's rounding dependencies.
    idx_halfway = compute_staff_position_index(102.0, line_y_coords)
    assert idx_halfway.is_snapped is False
    assert idx_halfway.snap_delta > 0.25


def test_compute_staff_position_index_invalid_inputs() -> None:
    # Fewer than 5 staff lines
    with pytest.raises(ValueError, match="exactly 5 lines"):
        compute_staff_position_index(100.0, [100.0, 108.0, 116.0, 124.0])

    # More than 5 staff lines
    with pytest.raises(ValueError, match="exactly 5 lines"):
        compute_staff_position_index(100.0, [100.0, 108.0, 116.0, 124.0, 132.0, 140.0])

    # Duplicated staff lines causing zero gap
    with pytest.raises(ValueError, match="gaps must all be positive"):
        compute_staff_position_index(100.0, [100.0, 108.0, 108.0, 124.0, 132.0])

    # Negative tolerance
    with pytest.raises(ValueError, match="Tolerance must be non-negative"):
        compute_staff_position_index(100.0, [100.0, 108.0, 116.0, 124.0, 132.0], tolerance=-0.1)

    with pytest.raises(ValueError, match="Line spacing must be greater than zero"):
        compute_staff_position_index(100.0, [100.0, 100.0, 100.0, 100.0, 100.0])


def test_line_segment_is_horizontal_threshold() -> None:
    from score2gp.pdf_geometry import _LineSegment

    # A segment matching the new 75.0 threshold (e.g. from tab-only fixtures)
    valid_segment = _LineSegment(x0=10.0, y0=20.0, x1=85.0, y1=20.0) # width = 75.0
    assert valid_segment.is_horizontal is True

    # A segment just below the 75.0 threshold
    invalid_segment = _LineSegment(x0=10.0, y0=20.0, x1=84.9, y1=20.0) # width = 74.9
    assert invalid_segment.is_horizontal is False

    # A segment perfectly horizontal and long enough
    long_segment = _LineSegment(x0=10.0, y0=20.0, x1=100.0, y1=20.0) # width = 90.0
    assert long_segment.is_horizontal is True

    # A segment slightly angled but within the 1.0 vertical delta allowance
    angled_segment = _LineSegment(x0=10.0, y0=20.0, x1=90.0, y1=20.9) # width = 80.0, dy = 0.9
    assert angled_segment.is_horizontal is True

    # A segment too angled
    too_angled = _LineSegment(x0=10.0, y0=20.0, x1=90.0, y1=21.1) # dy = 1.1
    assert too_angled.is_horizontal is False
