from __future__ import annotations

from dataclasses import dataclass
import statistics
import logging

logger = logging.getLogger(__name__)
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, field_validator

FRAGMENTED_STAFF_LINE_NEIGHBOR_MAX_GAP = 360.0


class VisualVibratoEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    bbox: tuple[float, float, float, float]
    cycles: int
    amplitude: float
    staff_index: int | None = None

    @field_validator("cycles")
    @classmethod
    def validate_cycles(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cycles must be non-negative")
        return v


class VisualSlideEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    bbox: tuple[float, float, float, float]
    slope: float
    direction: str  # "up" | "down"
    staff_index: int | None = None
    string_index: int | None = None

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError("direction must be 'up' or 'down'")
        return v


def _get_coord(pt: Any, name: str, idx: int) -> float | None:
    """Safely extract coordinate with error handling for malformed points."""
    try:
        if isinstance(pt, (int, float)):
            return float(pt)
        val = getattr(pt, name, None)
        if val is not None:
            return float(val)
        if hasattr(pt, "__getitem__"):
            return float(pt[idx])
    except (AttributeError, TypeError, ValueError, IndexError):
        pass
    return None


def extract_visual_vibrato_evidence(
    drawings: list[dict[str, Any]],
    staves: list[Any] | None = None,
    max_proximity_y: float = 25.0,
) -> list[VisualVibratoEvidence]:
    """Detect wavy bezier curve sequences ('c') near TAB staves as VisualVibratoEvidence.

    Performs spatial proximity clustering to split page-wide drawings into local curve groups,
    and requires cycles >= 2 to filter out single slurs and ties.
    """
    vibratos: list[VisualVibratoEvidence] = []
    for drawing in drawings:
        items = drawing.get("items", [])
        curve_items = [item for item in items if item and item[0] == "c" and len(item) >= 5]
        if not curve_items:
            continue
        curve_items.sort(key=lambda item: _get_coord(item[1], "x", 0) if _get_coord(item[1], "x", 0) is not None else 0.0)

        # Spatial clustering of curve items: group contiguous curves within gap_x <= 20.0
        clusters: list[list[Any]] = []
        current_cluster: list[Any] = []

        for item in curve_items:
            p1_x = _get_coord(item[1], "x", 0)
            if p1_x is None:
                continue

            if not current_cluster:
                current_cluster.append(item)
            else:
                prev_last_x = _get_coord(current_cluster[-1][4], "x", 0)
                if prev_last_x is not None and abs(p1_x - prev_last_x) <= 20.0:
                    current_cluster.append(item)
                else:
                    clusters.append(current_cluster)
                    current_cluster = [item]
        if current_cluster:
            clusters.append(current_cluster)

        for cluster in clusters:
            # Wavy vibratos require at least 2 cycles (filters out single slurs / ties)
            if len(cluster) < 2:
                continue

            xs: list[float] = []
            ys: list[float] = []
            valid = True
            for item in cluster:
                for pt in item[1:5]:
                    cx = _get_coord(pt, "x", 0)
                    cy = _get_coord(pt, "y", 1)
                    if cx is None or cy is None:
                        valid = False
                        break
                    xs.append(cx)
                    ys.append(cy)
                if not valid:
                    break

            if not valid or not xs or not ys:
                continue

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            amp = (max_y - min_y) / 2.0

            if amp <= 0.5:
                continue

            bbox = (round(min_x, 3), round(min_y, 3), round(max_x, 3), round(max_y, 3))
            cycles = len(cluster)

            staff_idx = None
            if staves:
                best_dist = float("inf")
                mid_y = (bbox[1] + bbox[3]) / 2.0
                for idx, staff in enumerate(staves, start=1):
                    staff_y0 = getattr(staff, "y0", None)
                    staff_y1 = getattr(staff, "y1", None)
                    line_ys = getattr(staff, "line_ys", [])
                    if staff_y0 is None and line_ys:
                        staff_y0 = line_ys[0]
                    if staff_y1 is None and line_ys:
                        staff_y1 = line_ys[-1]
                    if staff_y0 is not None and staff_y1 is not None:
                        staff_mid_y = (staff_y0 + staff_y1) / 2.0
                        dist = abs(mid_y - staff_mid_y)
                        if dist < best_dist and dist <= max_proximity_y:
                            best_dist = dist
                            staff_idx = idx

            vibratos.append(
                VisualVibratoEvidence(
                    bbox=bbox,
                    cycles=cycles,
                    amplitude=round(amp, 4),
                    staff_index=staff_idx,
                )
            )
    return vibratos


def extract_visual_slide_evidence(
    drawings: list[dict[str, Any]],
    staves: list[Any] | None = None,
    max_proximity_y: float = 25.0,
    max_string_proximity_y: float = 15.0,
) -> list[VisualSlideEvidence]:
    """Detect diagonal line primitives near TAB fret numbers as VisualSlideEvidence."""
    slides: list[VisualSlideEvidence] = []
    for drawing in drawings:
        items = drawing.get("items", [])
        for item in items:
            if not item or item[0] != "l" or len(item) < 3:
                continue
            p0, p1 = item[1], item[2]
            x0 = _get_coord(p0, "x", 0)
            y0 = _get_coord(p0, "y", 1)
            x1 = _get_coord(p1, "x", 0)
            y1 = _get_coord(p1, "y", 1)

            if x0 is None or y0 is None or x1 is None or y1 is None:
                continue

            dx = x1 - x0
            dy = y1 - y0
            length = (dx * dx + dy * dy) ** 0.5

            if not (5.0 <= length <= 50.0):
                continue

            if abs(dx) < 1e-3:
                continue

            slope = dy / dx
            if not (0.15 <= abs(slope) <= 3.0):
                continue

            if (dx > 0 and dy < 0) or (dx < 0 and dy > 0):
                direction = "up"
            else:
                direction = "down"

            bbox = (
                round(min(x0, x1), 3),
                round(min(y0, y1), 3),
                round(max(x0, x1), 3),
                round(max(y0, y1), 3),
            )

            staff_idx = None
            string_idx = None
            if staves:
                mid_y = (bbox[1] + bbox[3]) / 2.0
                best_staff_dist = float("inf")
                matched_staff = None
                for idx, staff in enumerate(staves, start=1):
                    staff_y0 = getattr(staff, "y0", None)
                    staff_y1 = getattr(staff, "y1", None)
                    line_ys = getattr(staff, "line_ys", [])
                    if staff_y0 is None and line_ys:
                        staff_y0 = line_ys[0]
                    if staff_y1 is None and line_ys:
                        staff_y1 = line_ys[-1]
                    if staff_y0 is not None and staff_y1 is not None:
                        staff_mid_y = (staff_y0 + staff_y1) / 2.0
                        dist = abs(mid_y - staff_mid_y)
                        if dist < best_staff_dist and dist <= max_proximity_y:
                            best_staff_dist = dist
                            staff_idx = idx
                            matched_staff = staff

                if matched_staff:
                    line_ys = getattr(matched_staff, "line_ys", [])
                    best_string_dist = float("inf")
                    for s_idx, s_y in enumerate(line_ys, start=1):
                        s_dist = abs(mid_y - s_y)
                        if s_dist < best_string_dist and s_dist <= max_string_proximity_y:
                            best_string_dist = s_dist
                            string_idx = s_idx

            slides.append(
                VisualSlideEvidence(
                    bbox=bbox,
                    slope=round(slope, 4),
                    direction=direction,
                    staff_index=staff_idx,
                    string_index=string_idx,
                )
            )
    return slides


def is_exact_duplicate_or_reverse(s1: _LineSegment, s2: _LineSegment) -> bool:
    """Returns True if s1 and s2 are exact geometric duplicates or reverse duplicates of the same line segment."""
    if s1.primitive_kind != s2.primitive_kind or s1.primitive_kind is None:
        return False

    x1 = (s1.x0 + s1.x1) / 2.0
    x2 = (s2.x0 + s2.x1) / 2.0
    if abs(x1 - x2) > 1e-3:
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

def extract_floating_barlines(segments: list[_LineSegment], staff_top_y: float, staff_bottom_y: float, dot_candidates=None) -> list[_LineSegment]:
    raw_barlines = []
    for seg in segments:
        if not seg.is_vertical:
            continue
        y_min = min(seg.y0, seg.y1)
        y_max = max(seg.y0, seg.y1)
        if y_max >= staff_top_y and y_min <= staff_bottom_y:
            raw_barlines.append(seg)

    raw_barlines.sort(key=lambda s: min(s.x0, s.x1))

    # Degrade thick barlines or double barlines into a single logical barline.
    # Checks actual geometry (thickness) and groups closely drawn double barlines.
    merged_barlines = []
    skip_next = False
    for i in range(len(raw_barlines)):
        if skip_next:
            skip_next = False
            continue

        seg = raw_barlines[i]

        # Standalone thick barline (e.g. single thick line)
        if seg.stroke_width and seg.stroke_width >= 3.0:
            logger.warning(
                f"Floating barline at x={seg.x0} has thickness {seg.stroke_width} "
                "matching a repeat marker but lacks dots. Degrading to standard barline."
            )

        if i + 1 < len(raw_barlines):
            next_seg = raw_barlines[i+1]
            dist = min(next_seg.x0, next_seg.x1) - min(seg.x0, seg.x1)

            # Double barline or thick+thin repeat marker
            if dist < 5.0:
                seg_thick = (seg.stroke_width and seg.stroke_width >= 3.0)
                next_thick = (next_seg.stroke_width and next_seg.stroke_width >= 3.0)
                if seg_thick or next_thick:
                    logger.warning(
                        f"Floating barline pair at x={seg.x0} has thickness matching a repeat marker "
                        "but lacks dots. Degrading to standard barline."
                    )
                # Group them together because double barlines and repeat markers without dots
                # both act as a single logical barline boundary.
                merged_barlines.append(seg)
                skip_next = True
                continue

        merged_barlines.append(seg)

    return merged_barlines
