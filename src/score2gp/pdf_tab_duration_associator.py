from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .pdf_tab_duration_types import DURATION_TICKS_MAP, DurationName, TabDurationEvidence


class PdfTabDurationAssociatorError(Exception):
    """Exception raised when candidate duration geometry is ambiguous or corrupted."""

    def __init__(self, message: str, category: str = "ambiguous_duration_geometry") -> None:
        self.message = message
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class SpatialBBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2.0


@dataclass(frozen=True)
class StemPrimitiveCandidate:
    bbox: SpatialBBox
    is_downward: bool = True

    @property
    def x_coord(self) -> float:
        return self.bbox.center_x

    @property
    def free_end_y(self) -> float:
        return self.bbox.y1 if self.is_downward else self.bbox.y0

    @property
    def staff_end_y(self) -> float:
        return self.bbox.y0 if self.is_downward else self.bbox.y1


@dataclass(frozen=True)
class BeamPrimitiveCandidate:
    bbox: SpatialBBox


@dataclass(frozen=True)
class FlagPrimitiveCandidate:
    bbox: SpatialBBox


@dataclass(frozen=True)
class StaffSystemContext:
    line_y_coords: Sequence[float]
    barline_x_coords: Sequence[float] = ()
    staff_space: float = 14.0

    @property
    def top_y(self) -> float:
        return min(self.line_y_coords) if self.line_y_coords else 0.0

    @property
    def bottom_y(self) -> float:
        return max(self.line_y_coords) if self.line_y_coords else 0.0


def is_barline_stroke(
    stroke: SpatialBBox,
    context: StaffSystemContext,
    tolerance_x: float = 2.0,
) -> bool:
    """Return True if a vertical stroke matches a known barline position and crosses the staff."""
    if not context.line_y_coords:
        return False
    crosses_staff = (stroke.y0 <= context.top_y + 2.0) and (stroke.y1 >= context.bottom_y - 2.0)
    if not crosses_staff:
        return False
    return any(abs(stroke.center_x - bx) <= tolerance_x for bx in context.barline_x_coords)


def is_staff_line_stroke(
    stroke: SpatialBBox,
    context: StaffSystemContext,
    tolerance_y: float = 1.0,
) -> bool:
    """Return True if a horizontal stroke lies directly along a staff line."""
    if stroke.height > 2.0:
        return False
    return any(abs(stroke.center_y - ly) <= tolerance_y for ly in context.line_y_coords)


def associate_stem_to_event(
    event_x: float,
    stems: Sequence[StemPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    custom_stem_tol: float | None = None,
) -> StemPrimitiveCandidate | None:
    """Find the single matching vertical stem candidate for an event subgroup position `event_x`.

    Fails closed (returns None or raises error) if multiple stems are ambiguously equidistant.
    """
    stem_tol = (
        custom_stem_tol
        if custom_stem_tol is not None
        else max(6.0, 0.6 * context.staff_space)
    )

    valid_stems: list[tuple[float, StemPrimitiveCandidate]] = []
    for stem in stems:
        if is_barline_stroke(stem.bbox, context):
            continue
        dist_x = abs(stem.x_coord - event_x)
        if dist_x <= stem_tol:
            # Check vertical attachment to staff
            near_top = abs(stem.bbox.y0 - context.top_y) <= 1.5 * context.staff_space
            near_bottom = abs(stem.bbox.y0 - context.bottom_y) <= 1.5 * context.staff_space or abs(stem.bbox.y1 - context.bottom_y) <= 1.5 * context.staff_space
            if near_top or near_bottom or (stem.bbox.y0 >= context.bottom_y - 2.0):
                valid_stems.append((dist_x, stem))

    if not valid_stems:
        return None

    valid_stems.sort(key=lambda t: t[0])
    if len(valid_stems) > 1:
        best_dist, best_stem = valid_stems[0]
        second_dist, _ = valid_stems[1]
        # Ambiguity check: if two stems are within 0.5pt distance of each other
        if abs(second_dist - best_dist) <= 0.5:
            return None
        return best_stem

    return valid_stems[0][1]


def count_beams_for_stem(
    stem: StemPrimitiveCandidate,
    beams: Sequence[BeamPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    custom_beam_overlap_eps: float | None = None,
    custom_beam_y_tol: float | None = None,
) -> int:
    """Count distinct stacked beam strokes associated with a vertical stem."""
    overlap_eps = custom_beam_overlap_eps if custom_beam_overlap_eps is not None else 4.0
    beam_y_tol = custom_beam_y_tol if custom_beam_y_tol is not None else 6.0

    stem_x = stem.x_coord
    free_y = stem.free_end_y

    matched_y_levels: list[float] = []
    for beam in beams:
        if is_staff_line_stroke(beam.bbox, context):
            continue
        # Horizontal overlap check
        if (beam.bbox.x0 - overlap_eps) <= stem_x <= (beam.bbox.x1 + overlap_eps):
            # Vertical proximity to stem free end
            dist_y = abs(beam.bbox.center_y - free_y)
            if dist_y <= beam_y_tol + (3.0 * len(matched_y_levels)):
                matched_y_levels.append(beam.bbox.center_y)

    return len(matched_y_levels)


def count_flags_for_stem(
    stem: StemPrimitiveCandidate,
    flags: Sequence[FlagPrimitiveCandidate],
    *,
    custom_flag_radius: float | None = None,
) -> int:
    """Count flag candidates attached to the free end of a vertical stem."""
    flag_radius = custom_flag_radius if custom_flag_radius is not None else 8.0
    stem_x = stem.x_coord
    free_y = stem.free_end_y

    count = 0
    for flag in flags:
        # Distance from flag origin/start to stem free end
        dist = math.hypot(flag.bbox.x0 - stem_x, flag.bbox.y0 - free_y)
        dist_end = math.hypot(flag.bbox.x1 - stem_x, flag.bbox.y1 - free_y)
        if min(dist, dist_end) <= flag_radius:
            count += 1
    return count


def resolve_tab_duration_evidence(
    event_x: float,
    stems: Sequence[StemPrimitiveCandidate],
    beams: Sequence[BeamPrimitiveCandidate],
    flags: Sequence[FlagPrimitiveCandidate],
    context: StaffSystemContext,
) -> TabDurationEvidence:
    """Associate visual duration candidates for a tab event subgroup position and resolve TabDurationEvidence.

    Returns equal_spacing_fallback if unstemmed or ambiguous.
    """
    stem = associate_stem_to_event(event_x, stems, context)
    if stem is None:
        return TabDurationEvidence(
            duration_name="quarter",
            duration_ticks=960,
            stem_present=False,
            beam_count=0,
            flag_count=0,
            confidence=0.5,
            source="equal_spacing_fallback",
        )

    beam_count = count_beams_for_stem(stem, beams, context)
    flag_count = count_flags_for_stem(stem, flags)

    total_duration_marks = max(beam_count, flag_count)

    if total_duration_marks == 0:
        duration_name: DurationName = "quarter"
    elif total_duration_marks == 1:
        duration_name = "eighth"
    elif total_duration_marks == 2:
        duration_name = "16th"
    elif total_duration_marks >= 3:
        duration_name = "32nd"
    else:
        duration_name = "quarter"

    duration_ticks = DURATION_TICKS_MAP[duration_name]

    return TabDurationEvidence(
        duration_name=duration_name,
        duration_ticks=duration_ticks,
        stem_present=True,
        beam_count=beam_count,
        flag_count=flag_count,
        confidence=1.0,
        source="visual_morphology",
    )
