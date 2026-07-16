from __future__ import annotations
from typing import Any
from .pdf import (
    _tab_line_groups,
    classify_staff_line_group,
    _extend_staff_group,
)
from .pdf_geometry import (
    _LineSegment,
    _drawing_segments,
    merge_collinear_horizontal_segments,
)

def _detect_notation_staff_groups(page: Any) -> list[list[_LineSegment]]:
    """Detect non-TAB 5-line staff groups on the page."""
    notation_groups = []
    segments = list(_drawing_segments(page.get_drawings()))
    raw_horizontal = sorted((segment for segment in segments if segment.is_horizontal), key=lambda segment: segment.y0)
    horizontal = sorted(merge_collinear_horizontal_segments(raw_horizontal), key=lambda segment: segment.y0)
    for group in _tab_line_groups(horizontal):
        classification = classify_staff_line_group(group, page)
        if classification == "notation" and len(group) == 5:
            extended_group, _, _ = _extend_staff_group(group, segments)
            notation_groups.append(extended_group)
    return notation_groups
