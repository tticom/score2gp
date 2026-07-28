from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .pdf_tab_duration_types import DURATION_TICKS_MAP, DurationName, TabDurationEvidence


class PdfTabDurationAssociatorError(Exception):
    """Exception raised when candidate duration geometry is ambiguous or conflicting."""

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


@dataclass(frozen=True)
class AmbiguityDiagnostic:
    event_x: float
    message: str


def is_barline_stroke(
    stroke: SpatialBBox,
    context: StaffSystemContext,
    tolerance_x: float = 2.0,
) -> bool:
    """Return True if a vertical stroke matches a known barline position and crosses the staff lines.

    Note: tolerance_x (2.0pt) is an absolute physical alignment threshold.
    """
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
    """Return True if a horizontal stroke lies directly along a staff line.

    Note: tolerance_y (1.0pt) is an absolute physical alignment threshold.
    """
    if stroke.height > 2.0:
        return False
    return any(abs(stroke.center_y - ly) <= tolerance_y for ly in context.line_y_coords)


def associate_stems_to_events(
    events_x: Sequence[float],
    stems: Sequence[StemPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    custom_stem_tol: float | None = None,
) -> dict[float, StemPrimitiveCandidate | AmbiguityDiagnostic | None]:
    """Associate a collection of event subgroup x-positions with candidate vertical stems.

    Considers all event positions simultaneously to ensure stems are not silently assigned
    independently to multiple events or midway ambiguous positions.

    Returns a mapping from event_x -> StemPrimitiveCandidate | AmbiguityDiagnostic | None.
    """
    if not events_x:
        return {}

    sorted_events = sorted(events_x)
    sorted_stems = sorted(stems, key=lambda s: s.x_coord)

    # Filter out barline strokes
    valid_stems: list[StemPrimitiveCandidate] = []
    for s in sorted_stems:
        if not is_barline_stroke(s.bbox, context):
            # Check minimum stem height (scales with staff_space) and staff proximity
            if s.bbox.height >= 0.8 * context.staff_space:
                near_top = abs(s.bbox.y0 - context.top_y) <= 1.5 * context.staff_space
                near_bottom = abs(s.bbox.y0 - context.bottom_y) <= 1.5 * context.staff_space or abs(s.bbox.y1 - context.bottom_y) <= 1.5 * context.staff_space
                if near_top or near_bottom or (s.bbox.y0 >= context.bottom_y - 2.0):
                    valid_stems.append(s)

    stem_tol = (
        custom_stem_tol
        if custom_stem_tol is not None
        else max(6.0, 0.6 * context.staff_space)
    )

    result: dict[float, StemPrimitiveCandidate | AmbiguityDiagnostic | None] = {ev_x: None for ev_x in events_x}
    assigned_stems: set[int] = set()

    for ev_x in sorted_events:
        # Find candidate stems within stem_tol
        candidates: list[tuple[float, int, StemPrimitiveCandidate]] = []
        for idx, stem in enumerate(valid_stems):
            dist = abs(stem.x_coord - ev_x)
            if dist <= stem_tol:
                candidates.append((dist, idx, stem))

        if not candidates:
            result[ev_x] = None
            continue

        candidates.sort(key=lambda t: t[0])
        best_dist, best_idx, best_stem = candidates[0]

        # Check if another event competes for this exact stem
        competing_events = [
            other_x for other_x in sorted_events
            if abs(best_stem.x_coord - other_x) <= stem_tol
        ]

        if len(competing_events) > 1:
            # Calculate distance from stem to each competing event
            comp_dists = sorted([(abs(best_stem.x_coord - ex), ex) for ex in competing_events], key=lambda t: t[0])
            d1, e1 = comp_dists[0]
            d2, e2 = comp_dists[1]

            # If stem is midway or difference between competitors is <= 1.0pt, mark ambiguous
            if abs(d2 - d1) <= 1.0:
                diag = AmbiguityDiagnostic(
                    event_x=ev_x,
                    message=f"Stem at x={best_stem.x_coord:.1f} is ambiguously placed between events at x={e1:.1f} and x={e2:.1f}",
                )
                for ex in competing_events:
                    if abs(best_stem.x_coord - ex) - d1 <= 1.0:
                        result[ex] = diag
                continue

            # If ev_x is not the uniquely closest event e1, ev_x cannot claim best_stem
            if ev_x != e1:
                result[ev_x] = None
                continue

        # Check if event has a second stem candidate that is nearly equidistant
        if len(candidates) > 1:
            second_dist = candidates[1][0]
            if abs(second_dist - best_dist) <= 1.0:
                result[ev_x] = AmbiguityDiagnostic(
                    event_x=ev_x,
                    message=f"Event at x={ev_x:.1f} has multiple competing stem candidates",
                )
                continue

        if best_idx in assigned_stems:
            result[ev_x] = AmbiguityDiagnostic(
                event_x=ev_x,
                message=f"Stem at x={best_stem.x_coord:.1f} already assigned to another event",
            )
        else:
            result[ev_x] = best_stem
            assigned_stems.add(best_idx)

    return result


def associate_stem_to_event(
    event_x: float,
    all_events_x: Sequence[float],
    stems: Sequence[StemPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    custom_stem_tol: float | None = None,
) -> StemPrimitiveCandidate | AmbiguityDiagnostic | None:
    """Convenience wrapper for single event position stem association considering all events."""
    if event_x not in all_events_x:
        all_events_x = list(all_events_x) + [event_x]
    mapping = associate_stems_to_events(all_events_x, stems, context, custom_stem_tol=custom_stem_tol)
    return mapping.get(event_x)


def count_beams_for_stem(
    stem: StemPrimitiveCandidate,
    beams: Sequence[BeamPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    custom_beam_overlap_eps: float | None = None,
    custom_beam_y_tol: float | None = None,
) -> int:
    """Deterministically count distinct deduplicated beam levels associated with a vertical stem.

    Evaluates every beam against fixed geometric rules, deduplicating same-level beams (within <= 2.0pt),
    rejecting staff lines, and remaining 100% order-independent.
    """
    overlap_eps = custom_beam_overlap_eps if custom_beam_overlap_eps is not None else 4.0  # Absolute bound
    beam_y_tol = custom_beam_y_tol if custom_beam_y_tol is not None else (1.2 * context.staff_space)  # Scales with staff_space

    stem_x = stem.x_coord
    free_y = stem.free_end_y

    eligible_y_centers: list[float] = []
    for beam in beams:
        if is_staff_line_stroke(beam.bbox, context):
            continue
        # Fixed horizontal overlap check: beam spans stem_x (with absolute epsilon threshold)
        if (beam.bbox.x0 - overlap_eps) <= stem_x <= (beam.bbox.x1 + overlap_eps):
            # Vertical proximity check (scales with staff_space)
            dist_y = abs(beam.bbox.center_y - free_y)
            if dist_y <= beam_y_tol:
                eligible_y_centers.append(beam.bbox.center_y)

    if not eligible_y_centers:
        return 0

    # Order-independent deduplication: group y-centers within <= 2.0pt of each other
    sorted_y = sorted(eligible_y_centers)
    distinct_levels: list[float] = []
    for y_val in sorted_y:
        if not distinct_levels or any(abs(y_val - level) <= 2.0 for level in distinct_levels):
            if not distinct_levels:
                distinct_levels.append(y_val)
            else:
                # Merge into closest level
                closest_idx = min(range(len(distinct_levels)), key=lambda i: abs(distinct_levels[i] - y_val))
                if abs(distinct_levels[closest_idx] - y_val) > 2.0:
                    distinct_levels.append(y_val)
        else:
            distinct_levels.append(y_val)

    return len(distinct_levels)


def count_flags_for_stem(
    stem: StemPrimitiveCandidate,
    flags: Sequence[FlagPrimitiveCandidate],
    *,
    custom_flag_radius: float | None = None,
) -> tuple[int, bool]:
    """Deterministically count deduplicated flag candidates attached to a stem free end.

    Returns (flag_count, is_ambiguous).
    """
    flag_radius = custom_flag_radius if custom_flag_radius is not None else 8.0  # Absolute bound
    stem_x = stem.x_coord
    free_y = stem.free_end_y

    eligible_flags: list[tuple[float, FlagPrimitiveCandidate]] = []
    for flag in flags:
        dist_start = math.hypot(flag.bbox.x0 - stem_x, flag.bbox.y0 - free_y)
        dist_end = math.hypot(flag.bbox.x1 - stem_x, flag.bbox.y1 - free_y)
        min_dist = min(dist_start, dist_end)
        if min_dist <= flag_radius:
            eligible_flags.append((min_dist, flag))

    if not eligible_flags:
        return 0, False

    # Deduplicate flags with near-identical contact points (<= 2.0pt)
    sorted_flags = sorted(eligible_flags, key=lambda t: (t[1].bbox.x0, t[1].bbox.y0))
    distinct_flags: list[FlagPrimitiveCandidate] = []
    for _, f in sorted_flags:
        if not any(math.hypot(f.bbox.x0 - df.bbox.x0, f.bbox.y0 - df.bbox.y0) <= 2.0 for df in distinct_flags):
            distinct_flags.append(f)

    return len(distinct_flags), False


def resolve_tab_duration_evidence_for_events(
    events_x: Sequence[float],
    stems: Sequence[StemPrimitiveCandidate],
    beams: Sequence[BeamPrimitiveCandidate],
    flags: Sequence[FlagPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    fail_on_ambiguity: bool = False,
) -> dict[float, TabDurationEvidence]:
    """Resolve TabDurationEvidence for all event subgroup x-positions on a staff system.

    Handles unstemmed fallback, visual duration resolution, deduplication, and explicit ambiguity/conflict states.
    """
    if not events_x:
        return {}

    stem_assignments = associate_stems_to_events(events_x, stems, context)
    has_any_stems = any(isinstance(v, StemPrimitiveCandidate) for v in stem_assignments.values())

    results: dict[float, TabDurationEvidence] = {}

    for ev_x in events_x:
        assigned = stem_assignments.get(ev_x)

        if isinstance(assigned, AmbiguityDiagnostic):
            if fail_on_ambiguity:
                raise PdfTabDurationAssociatorError(assigned.message)
            results[ev_x] = TabDurationEvidence(
                duration_name="ambiguous",
                duration_ticks=0,
                stem_present=True,
                beam_count=0,
                flag_count=0,
                confidence=0.0,
                source="ambiguous_conflict",
                is_ambiguous=True,
                is_fallback_placeholder=False,
                diagnostic_message=assigned.message,
            )
            continue

        if assigned is None:
            if not has_any_stems:
                # Ordinary unstemmed event -> fallback placeholder
                results[ev_x] = TabDurationEvidence(
                    duration_name="quarter",
                    duration_ticks=960,
                    stem_present=False,
                    beam_count=0,
                    flag_count=0,
                    confidence=0.5,
                    source="equal_spacing_fallback",
                    is_ambiguous=False,
                    is_fallback_placeholder=True,
                    diagnostic_message="Unstemmed staff: using equal-spacing structural placeholder",
                )
            else:
                # Stemmed staff where this specific event lacks a stem -> ambiguous/missing stem
                if fail_on_ambiguity:
                    raise PdfTabDurationAssociatorError(f"Missing stem for event at x={ev_x:.1f} on stemmed staff")
                results[ev_x] = TabDurationEvidence(
                    duration_name="ambiguous",
                    duration_ticks=0,
                    stem_present=False,
                    beam_count=0,
                    flag_count=0,
                    confidence=0.0,
                    source="ambiguous_conflict",
                    is_ambiguous=True,
                    is_fallback_placeholder=False,
                    diagnostic_message=f"Event at x={ev_x:.1f} missing stem candidate on stemmed staff",
                )
            continue

        # Stem attached cleanly
        stem = assigned
        beam_count = count_beams_for_stem(stem, beams, context)
        flag_count, flag_ambiguous = count_flags_for_stem(stem, flags)

        if flag_ambiguous:
            if fail_on_ambiguity:
                raise PdfTabDurationAssociatorError(f"Ambiguous flag attachment for stem at x={stem.x_coord:.1f}")
            results[ev_x] = TabDurationEvidence(
                duration_name="ambiguous",
                duration_ticks=0,
                stem_present=True,
                beam_count=beam_count,
                flag_count=flag_count,
                confidence=0.0,
                source="ambiguous_conflict",
                is_ambiguous=True,
                diagnostic_message="Ambiguous flag attachment",
            )
            continue

        # Check for conflicting beam and flag counts
        if beam_count > 0 and flag_count > 0:
            if beam_count != flag_count:
                msg = f"Conflicting beam_count ({beam_count}) and flag_count ({flag_count}) on stem at x={stem.x_coord:.1f}"
                if fail_on_ambiguity:
                    raise PdfTabDurationAssociatorError(msg)
                results[ev_x] = TabDurationEvidence(
                    duration_name="ambiguous",
                    duration_ticks=0,
                    stem_present=True,
                    beam_count=beam_count,
                    flag_count=flag_count,
                    confidence=0.0,
                    source="ambiguous_conflict",
                    is_ambiguous=True,
                    diagnostic_message=msg,
                )
                continue

        total_marks = max(beam_count, flag_count)
        if total_marks == 0:
            duration_name: DurationName = "quarter"
        elif total_marks == 1:
            duration_name = "eighth"
        elif total_marks == 2:
            duration_name = "16th"
        elif total_marks >= 3:
            duration_name = "32nd"
        else:
            duration_name = "quarter"

        duration_ticks = DURATION_TICKS_MAP[duration_name]

        results[ev_x] = TabDurationEvidence(
            duration_name=duration_name,
            duration_ticks=duration_ticks,
            stem_present=True,
            beam_count=beam_count,
            flag_count=flag_count,
            confidence=1.0,
            source="visual_morphology",
            is_ambiguous=False,
            is_fallback_placeholder=False,
        )

    return results


def resolve_tab_duration_evidence(
    event_x: float,
    stems: Sequence[StemPrimitiveCandidate],
    beams: Sequence[BeamPrimitiveCandidate],
    flags: Sequence[FlagPrimitiveCandidate],
    context: StaffSystemContext,
    *,
    all_events_x: Sequence[float] | None = None,
    fail_on_ambiguity: bool = False,
) -> TabDurationEvidence:
    """Single event convenience wrapper for resolve_tab_duration_evidence_for_events."""
    events = list(all_events_x) if all_events_x is not None else [event_x]
    if event_x not in events:
        events.append(event_x)
    mapping = resolve_tab_duration_evidence_for_events(
        events, stems, beams, flags, context, fail_on_ambiguity=fail_on_ambiguity
    )
    return mapping[event_x]
