from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Any, Literal

FRAGMENTED_STAFF_LINE_NEIGHBOR_MAX_GAP = 360.0


def is_exact_duplicate_or_reverse(s1: _LineSegment, s2: _LineSegment) -> bool:
    """Returns True if s1 and s2 are exact geometric duplicates or reverse duplicates of the same line segment."""
    if s1.primitive_kind != s2.primitive_kind or s1.primitive_kind is None:
        return False

    x1 = (s1.x0 + s1.x1) / 2.0
    x2 = (s2.x0 + s2.x1) / 2.0
    if abs(x1 - x2) > 0.5:
        return False

    y1_0, y1_1 = s1.y0, s1.y1
    y2_0, y2_1 = s2.y0, s2.y1

    forward_match = abs(y1_0 - y2_0) <= 1.0 and abs(y1_1 - y2_1) <= 1.0
    reverse_match = abs(y1_0 - y2_1) <= 1.0 and abs(y1_1 - y2_0) <= 1.0

    return forward_match or reverse_match


@dataclass(frozen=True)
class _LineSegment:
    x0: float
    y0: float
    x1: float
    y1: float
    primitive_kind: Literal["line", "rect_edge", "mixed"] | None = None
    primitive_id: str | None = None
    stroke_width: float | None = None
    source_rect_width: float | None = None

    @property
    def is_horizontal(self) -> bool:
        return abs(self.y0 - self.y1) <= 1.0 and abs(self.x1 - self.x0) >= 75.0

    @property
    def is_vertical(self) -> bool:
        return abs(self.x0 - self.x1) <= 1.0 and abs(self.y1 - self.y0) >= 40.0

    def merge_with(self, other: _LineSegment, new_x0: float, new_y0: float, new_x1: float, new_y1: float) -> _LineSegment:
        is_exact_dup = is_exact_duplicate_or_reverse(self, other)
        if (
            self.primitive_kind == other.primitive_kind
            and (is_exact_dup or (self.primitive_id == other.primitive_id and self.primitive_id is not None))
        ):
            merged_kind = self.primitive_kind
            merged_id = self.primitive_id or other.primitive_id
            merged_rect_w = self.source_rect_width
        else:
            merged_kind = "mixed"
            merged_id = None
            rect_widths = [w for w in (self.source_rect_width, other.source_rect_width) if w is not None]
            merged_rect_w = max(rect_widths) if rect_widths else None

        widths = [w for w in (self.stroke_width, other.stroke_width) if w is not None]
        merged_stroke_w = max(widths) if widths else None

        return _LineSegment(
            x0=new_x0,
            y0=new_y0,
            x1=new_x1,
            y1=new_y1,
            primitive_kind=merged_kind,
            primitive_id=merged_id,
            stroke_width=merged_stroke_w,
            source_rect_width=merged_rect_w,
        )


def _drawing_segments(drawings: list[dict[str, Any]]) -> list[_LineSegment]:
    segments = []
    for drawing_idx, drawing in enumerate(drawings):
        pen_width = float(drawing.get("width", 1.0)) if drawing.get("width") is not None else None
        for item_idx, item in enumerate(drawing.get("items", [])):
            if not item:
                continue
            item_id = f"drawing_{drawing_idx}_item_{item_idx}"
            if item[0] == "l" and len(item) >= 3:
                p0 = item[1]
                p1 = item[2]
                segments.append(
                    _LineSegment(
                        float(p0.x),
                        float(p0.y),
                        float(p1.x),
                        float(p1.y),
                        primitive_kind="line",
                        primitive_id=item_id,
                        stroke_width=pen_width,
                        source_rect_width=None,
                    )
                )
            elif item[0] == "re" and len(item) >= 2:
                rect = item[1]
                rect_w = abs(float(rect.x1) - float(rect.x0))
                segments.extend(
                    [
                        _LineSegment(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y0), primitive_kind="rect_edge", primitive_id=item_id, stroke_width=pen_width, source_rect_width=rect_w),
                        _LineSegment(float(rect.x1), float(rect.y0), float(rect.x1), float(rect.y1), primitive_kind="rect_edge", primitive_id=item_id, stroke_width=pen_width, source_rect_width=rect_w),
                        _LineSegment(float(rect.x1), float(rect.y1), float(rect.x0), float(rect.y1), primitive_kind="rect_edge", primitive_id=item_id, stroke_width=pen_width, source_rect_width=rect_w),
                        _LineSegment(float(rect.x0), float(rect.y1), float(rect.x0), float(rect.y0), primitive_kind="rect_edge", primitive_id=item_id, stroke_width=pen_width, source_rect_width=rect_w),
                    ]
                )
    return segments


def merge_collinear_horizontal_segments(segments: list[_LineSegment], tolerance_y: float = 1.0, max_gap_x: float = 120.0) -> list[_LineSegment]:
    if not segments:
        return []
    sorted_segs = sorted(segments, key=lambda s: ((s.y0 + s.y1) / 2, min(s.x0, s.x1)))

    # Pass 1: Merge touching/overlapping collinear segments (within 5.0 gap/overlap) on the same Y coordinate
    pass1_merged: list[_LineSegment] = []
    for seg in sorted_segs:
        if not pass1_merged:
            pass1_merged.append(seg)
            continue
        last = pass1_merged[-1]
        last_y = (last.y0 + last.y1) / 2
        seg_y = (seg.y0 + seg.y1) / 2
        if abs(last_y - seg_y) <= tolerance_y:
            last_x0, last_x1 = min(last.x0, last.x1), max(last.x0, last.x1)
            seg_x0, seg_x1 = min(seg.x0, seg.x1), max(seg.x0, seg.x1)
            if last_x1 - 5.0 <= seg_x0 <= last_x1 + 5.0:
                new_x0 = min(last_x0, seg_x0)
                new_x1 = max(last_x1, seg_x1)
                new_y0 = (last.y0 + seg.y0) / 2
                new_y1 = (last.y1 + seg.y1) / 2
                pass1_merged[-1] = last.merge_with(seg, new_x0, new_y0, new_x1, new_y1)
                continue
        pass1_merged.append(seg)

    # Pass 2: Execute the spacing-aware neighbor-check collinear gap merging logic on the output of Pass 1
    merged: list[_LineSegment] = []
    for seg in pass1_merged:
        if not merged:
            merged.append(seg)
            continue
        last = merged[-1]
        last_y = (last.y0 + last.y1) / 2
        seg_y = (seg.y0 + seg.y1) / 2

        if abs(last_y - seg_y) <= tolerance_y:
            last_x0, last_x1 = min(last.x0, last.x1), max(last.x0, last.x1)
            seg_x0, seg_x1 = min(seg.x0, seg.x1), max(seg.x0, seg.x1)

            gap_start = last_x1
            gap_end = seg_x0
            gap_len = gap_end - gap_start
            should_merge = False

            if last_x1 - 5.0 <= seg_x0 <= last_x1 + max_gap_x:
                # Close-gap regime: gap up to max_gap_x (120.0)
                if gap_len <= 5.0:
                    should_merge = True
                else:
                    # Check if there is at least one other segment (neighboring staff line)
                    # that spans continuously across the gap.
                    has_continuous_neighbor = False
                    for other in pass1_merged:
                        if other is seg or other is last:
                            continue
                        other_y = (other.y0 + other.y1) / 2
                        if 2.0 <= abs(other_y - seg_y) <= 45.0:  # neighboring lines in a staff
                            other_x0 = min(other.x0, other.x1)
                            other_x1 = max(other.x0, other.x1)
                            if other_x0 <= gap_start + 2.0 and other_x1 >= gap_end - 2.0:
                                has_continuous_neighbor = True
                                break

                    # Spacing-aware row-level fragment split check
                    has_matching_split_neighbors = False
                    if not has_continuous_neighbor:
                        if gap_len <= 40.0:
                            matching_split_count = 0
                            for other_left in pass1_merged:
                                if other_left is seg or other_left is last:
                                    continue
                                ol_y = (other_left.y0 + other_left.y1) / 2
                                if 2.0 <= abs(ol_y - seg_y) <= 45.0:
                                    ol_x1 = max(other_left.x0, other_left.x1)
                                    # Check if other_left ends near last_x1
                                    if abs(ol_x1 - last_x1) <= 15.0:
                                        # Find corresponding other_right
                                        for other_right in pass1_merged:
                                            if other_right is seg or other_right is last or other_right is other_left:
                                                continue
                                            or_y = (other_right.y0 + other_right.y1) / 2
                                            if abs(or_y - ol_y) <= tolerance_y:
                                                or_x0 = min(other_right.x0, other_right.x1)
                                                # Check if other_right starts near seg_x0
                                                if abs(or_x0 - seg_x0) <= 15.0:
                                                    matching_split_count += 1
                                                    break

                            # If we found at least 4 neighboring parallel lines with the same collinear split,
                            # this represents a split staff row of at least 5 lines (Guitar TAB staff split).
                            if matching_split_count >= 4:
                                has_matching_split_neighbors = True

                    if has_continuous_neighbor or has_matching_split_neighbors:
                        should_merge = True

            elif max_gap_x < gap_len <= FRAGMENTED_STAFF_LINE_NEIGHBOR_MAX_GAP:
                # Wide-gap regime: gap > 120.0 and <= 360.0
                continuous_neighbor_count = 0
                for other in pass1_merged:
                    if other is seg or other is last:
                        continue
                    other_y = (other.y0 + other.y1) / 2
                    if 2.0 <= abs(other_y - seg_y) <= 45.0:  # neighboring lines in a staff
                        other_x0 = min(other.x0, other.x1)
                        other_x1 = max(other.x0, other.x1)
                        if other_x0 <= gap_start + 2.0 and other_x1 >= gap_end - 2.0:
                            continuous_neighbor_count += 1
                if continuous_neighbor_count >= 2:
                    should_merge = True

            if should_merge:
                new_x0 = min(last_x0, seg_x0)
                new_x1 = max(last_x1, seg_x1)
                new_y0 = (last.y0 + seg.y0) / 2
                new_y1 = (last.y1 + seg.y1) / 2
                merged[-1] = last.merge_with(seg, new_x0, new_y0, new_x1, new_y1)
                continue

        merged.append(seg)
    return merged


@dataclass(frozen=True)
class StaffPositionIndex:
    raw_position: float
    nearest_index: int
    snap_delta: float
    is_snapped: bool


def compute_staff_position_index(
    y_coord: float,
    line_y_coords: list[float],
    tolerance: float = 0.25,
) -> StaffPositionIndex:
    if len(line_y_coords) != 5:
        raise ValueError("Standard staff must have exactly 5 lines.")

    if tolerance < 0.0:
        raise ValueError("Tolerance must be non-negative.")

    sorted_ys = sorted(line_y_coords)
    gaps = [
        sorted_ys[1] - sorted_ys[0],
        sorted_ys[2] - sorted_ys[1],
        sorted_ys[3] - sorted_ys[2],
        sorted_ys[4] - sorted_ys[3],
    ]

    for gap in gaps:
        if gap <= 0.0:
            raise ValueError("Adjacent staff-line gaps must all be positive.")

    staff_space = statistics.median(gaps)
    if staff_space <= 0.0:
        raise ValueError("Staff space must be positive.")

    half_staff_space = staff_space / 2.0
    top_line_y = sorted_ys[0]

    raw_position = (y_coord - top_line_y) / half_staff_space
    nearest_index = round(raw_position)
    snap_delta = abs(raw_position - nearest_index)
    is_snapped = snap_delta <= tolerance

    return StaffPositionIndex(
        raw_position=raw_position,
        nearest_index=nearest_index,
        snap_delta=snap_delta,
        is_snapped=is_snapped,
    )
