"""Local Scale Model for Optical Music & Tablature Recognition (REC-04).

Estimates local notation staff space, TAB string space, stroke thickness, and
glyph scale independently with support observations, uncertainty quantification,
and full raw/normalized diagnostic retaining. Expresses detector policies in
dimensionless units.
"""

from __future__ import annotations

from enum import StrEnum
import statistics
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from score2gp.recognition.schemas import (
    BoundingBox2D,
    DocumentObservations,
    ScaleEstimate,
    TextObservation,
    VectorPathObservation,
)


class ScaleStatus(StrEnum):
    """Recognition status for scale estimation."""

    ESTIMATED = "estimated"
    AMBIGUOUS = "ambiguous"
    INADEQUATE_EVIDENCE = "inadequate_evidence"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"


class StaffKind(StrEnum):
    """Kind of musical staff identified by line geometry."""

    NOTATION = "notation"
    TAB = "tab"
    UNKNOWN = "unknown"


class UnsupportedScaleError(RuntimeError):
    """Raised when scale estimation is unsupported or evidence is inadequate."""


class ScaleUncertainty(BaseModel):
    """Uncertainty quantification for scale measurements."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(ge=0, description="Number of supporting measurements")
    standard_deviation: float = Field(ge=0.0, description="Standard deviation of gap measurements")
    coefficient_of_variation: float = Field(ge=0.0, description="Relative uncertainty (std / mean)")
    min_gap: float = Field(ge=0.0, description="Smallest measured gap in points")
    max_gap: float = Field(ge=0.0, description="Largest measured gap in points")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score in [0.0, 1.0]")


class ScaleSupport(BaseModel):
    """Provenance and support observations backing a scale estimate."""

    model_config = ConfigDict(extra="forbid")

    vector_observation_ids: list[str] = Field(
        default_factory=list, description="IDs of vector path observations supporting lines"
    )
    text_observation_ids: list[str] = Field(
        default_factory=list, description="IDs of text observations supporting glyph scale"
    )
    region_bbox: BoundingBox2D | None = Field(
        default=None, description="Bounding box covering supporting observations"
    )
    line_count: int = Field(default=0, ge=0, description="Total supporting staff lines")
    staff_kind: StaffKind = Field(default=StaffKind.UNKNOWN, description="Classified staff kind")


class ScaleDiagnostics(BaseModel):
    """Raw and normalized measurements retained for debugging and auditing."""

    model_config = ConfigDict(extra="forbid")

    raw_line_ys: list[float] = Field(default_factory=list, description="Raw line center y-coordinates")
    raw_gaps: list[float] = Field(default_factory=list, description="Raw adjacent line gaps in points")
    raw_stroke_widths: list[float] = Field(default_factory=list, description="Raw stroke widths in points")
    raw_glyph_heights: list[float] = Field(default_factory=list, description="Raw glyph heights in points")
    normalized_gaps: list[float] = Field(
        default_factory=list, description="Gaps normalized by estimated local scale (dimensionless)"
    )
    normalized_stroke_widths: list[float] = Field(
        default_factory=list, description="Stroke widths normalized by estimated scale (dimensionless)"
    )
    normalized_glyph_heights: list[float] = Field(
        default_factory=list, description="Glyph heights normalized by estimated scale (dimensionless)"
    )
    detected_groups: list[dict[str, Any]] = Field(
        default_factory=list, description="Summary details of detected staff groups"
    )


class TypedScaleEstimate(BaseModel):
    """Complete typed scale estimate with support, uncertainty, and diagnostics."""

    model_config = ConfigDict(extra="forbid")

    scale_id: str = Field(description="Unique scale identifier, e.g. page-1-scale or staff-1-scale")
    page_index: int = Field(ge=1, description="1-based page index")
    status: ScaleStatus = Field(description="Estimation outcome status")
    notation_staff_space: float | None = Field(
        default=None, ge=0.0, description="Standard notation staff space (gap between lines) in points"
    )
    tab_string_space: float | None = Field(
        default=None, ge=0.0, description="TAB string space (gap between lines) in points"
    )
    stroke_thickness: float | None = Field(
        default=None, ge=0.0, description="Dominant staff/stem stroke thickness in points"
    )
    glyph_scale: float | None = Field(
        default=None, ge=0.0, description="Characteristic glyph / fret-digit height in points"
    )
    dpi: float | None = Field(default=72.0, ge=0.0, description="Resolution / coordinate density")
    uncertainty: ScaleUncertainty | None = Field(default=None, description="Uncertainty quantification")
    support: ScaleSupport = Field(default_factory=ScaleSupport, description="Supporting observation references")
    diagnostics: ScaleDiagnostics = Field(default_factory=ScaleDiagnostics, description="Detailed diagnostic data")
    error_message: str | None = Field(default=None, description="Diagnostic error reason if unsupported")

    def to_schema_estimate(self) -> ScaleEstimate:
        """Convert to the canonical recognition schema ScaleEstimate."""
        return ScaleEstimate(
            notation_staff_space=self.notation_staff_space,
            tab_string_space=self.tab_string_space,
            stroke_thickness=self.stroke_thickness,
            glyph_scale=self.glyph_scale,
            dpi=self.dpi,
        )


class PageScaleModel(BaseModel):
    """Scale model for a page combining page-wide and local system estimates."""

    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=1)
    overall: TypedScaleEstimate
    local_estimates: list[TypedScaleEstimate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dimensionless Detector Policies and Normalization Helpers
# ---------------------------------------------------------------------------

def normalize_dimension(value: float, scale: float) -> float:
    """Normalize a physical dimension by a scale factor into dimensionless units."""
    if scale <= 0.0:
        raise ValueError(f"scale must be strictly positive, got {scale}")
    return value / scale


def denormalize_dimension(norm_value: float, scale: float) -> float:
    """Denormalize a dimensionless value back into physical document units."""
    if scale <= 0.0:
        raise ValueError(f"scale must be strictly positive, got {scale}")
    return norm_value * scale


class DimensionlessDetectorPolicy:
    """Musical primitive detector policies expressed in dimensionless scale units."""

    # Notehead policy: standard noteheads span approximately 1 staff space vertically
    NOTEHEAD_MIN_HEIGHT_SP: float = 0.70
    NOTEHEAD_MAX_HEIGHT_SP: float = 1.45
    NOTEHEAD_MIN_WIDTH_SP: float = 0.75
    NOTEHEAD_MAX_WIDTH_SP: float = 1.85

    # Beam policy: horizontal beams span multiple notehead intervals with moderate thickness
    BEAM_MIN_WIDTH_SP: float = 0.50
    BEAM_MAX_HEIGHT_SP: float = 0.85
    BEAM_MIN_ASPECT_RATIO: float = 1.80

    # Barline policy: vertical lines spanning exactly the staff height
    BARLINE_MAX_WIDTH_SP: float = 0.35
    BARLINE_HEIGHT_TOLERANCE_SP: float = 0.55

    # Stem policy: vertical lines spanning 2.0 to 4.5 staff spaces
    STEM_MIN_HEIGHT_SP: float = 1.80
    STEM_MAX_HEIGHT_SP: float = 5.00
    STEM_MAX_WIDTH_SP: float = 0.30

    # Fret digit policy: digits in guitar tablature
    FRET_DIGIT_MIN_HEIGHT_SP: float = 0.40
    FRET_DIGIT_MAX_HEIGHT_SP: float = 1.30
    FRET_DIGIT_MIN_WIDTH_SP: float = 0.20
    FRET_DIGIT_MAX_WIDTH_SP: float = 1.60

    @classmethod
    def is_notehead(cls, width: float, height: float, staff_space: float) -> bool:
        """Check if dimensions match a notehead in dimensionless staff spaces."""
        if staff_space <= 0.0 or width <= 0.0 or height <= 0.0:
            return False
        h_norm = height / staff_space
        w_norm = width / staff_space
        return (
            cls.NOTEHEAD_MIN_HEIGHT_SP <= h_norm <= cls.NOTEHEAD_MAX_HEIGHT_SP
            and cls.NOTEHEAD_MIN_WIDTH_SP <= w_norm <= cls.NOTEHEAD_MAX_WIDTH_SP
        )

    @classmethod
    def is_beam(cls, width: float, height: float, staff_space: float) -> bool:
        """Check if dimensions match a beam in dimensionless staff spaces."""
        if staff_space <= 0.0 or width <= 0.0 or height <= 0.0:
            return False
        w_norm = width / staff_space
        h_norm = height / staff_space
        aspect = width / height
        return (
            w_norm >= cls.BEAM_MIN_WIDTH_SP
            and h_norm <= cls.BEAM_MAX_HEIGHT_SP
            and aspect >= cls.BEAM_MIN_ASPECT_RATIO
        )

    @classmethod
    def is_barline(cls, width: float, height: float, staff_space: float, line_count: int = 5) -> bool:
        """Check if dimensions match a barline spanning line_count lines."""
        if staff_space <= 0.0 or width <= 0.0 or height <= 0.0 or line_count < 2:
            return False
        w_norm = width / staff_space
        h_norm = height / staff_space
        expected_h = float(line_count - 1)
        return (
            w_norm <= cls.BARLINE_MAX_WIDTH_SP
            and abs(h_norm - expected_h) <= cls.BARLINE_HEIGHT_TOLERANCE_SP
        )

    @classmethod
    def is_stem(cls, width: float, height: float, staff_space: float) -> bool:
        """Check if dimensions match a stem in dimensionless staff spaces."""
        if staff_space <= 0.0 or width <= 0.0 or height <= 0.0:
            return False
        w_norm = width / staff_space
        h_norm = height / staff_space
        return (
            cls.STEM_MIN_HEIGHT_SP <= h_norm <= cls.STEM_MAX_HEIGHT_SP
            and w_norm <= cls.STEM_MAX_WIDTH_SP
        )

    @classmethod
    def is_fret_digit(cls, width: float, height: float, string_space: float) -> bool:
        """Check if dimensions match a fret number in dimensionless string spaces."""
        if string_space <= 0.0 or width <= 0.0 or height <= 0.0:
            return False
        w_norm = width / string_space
        h_norm = height / string_space
        return (
            cls.FRET_DIGIT_MIN_HEIGHT_SP <= h_norm <= cls.FRET_DIGIT_MAX_HEIGHT_SP
            and cls.FRET_DIGIT_MIN_WIDTH_SP <= w_norm <= cls.FRET_DIGIT_MAX_WIDTH_SP
        )


# ---------------------------------------------------------------------------
# Extraction & Clustering Algorithms
# ---------------------------------------------------------------------------

class _LineLevel:
    """Internal merged line level spanning a consistent y-coordinate."""

    def __init__(self, y: float, x0: float, x1: float, stroke_width: float | None, obs_ids: list[str]) -> None:
        self.y = y
        self.x0 = x0
        self.x1 = x1
        self.stroke_width = stroke_width
        self.obs_ids = obs_ids

    @property
    def width(self) -> float:
        return self.x1 - self.x0


def _extract_candidate_horizontal_lines(
    vectors: Sequence[VectorPathObservation],
    page_index: int,
    min_length: float = 20.0,
    max_thickness: float = 3.5,
) -> list[dict[str, Any]]:
    """Extract candidate horizontal line segments from vector observations."""
    candidates: list[dict[str, Any]] = []
    for vec in vectors:
        if vec.bbox.page_index != page_index:
            continue
        dx = abs(vec.bbox.x1 - vec.bbox.x0)
        dy = abs(vec.bbox.y1 - vec.bbox.y0)
        if dx < min_length or dy > max_thickness:
            continue

        # If explicit line points exist, verify slope
        if vec.path_type == "line" and len(vec.points) == 2:
            p_dy = abs(vec.points[1].y - vec.points[0].y)
            if p_dy > 1.0:
                continue

        stroke_w = vec.stroke_width if vec.stroke_width and vec.stroke_width > 0 else (dy if dy > 0 else 0.5)
        candidates.append({
            "id": vec.id,
            "y": (vec.bbox.y0 + vec.bbox.y1) / 2.0,
            "x0": min(vec.bbox.x0, vec.bbox.x1),
            "x1": max(vec.bbox.x0, vec.bbox.x1),
            "stroke_width": stroke_w,
            "bbox": vec.bbox,
        })
    return candidates


def _merge_collinear_fragments(
    candidates: list[dict[str, Any]],
    tolerance_y: float = 0.5,
) -> list[_LineLevel]:
    """Merge collinear horizontal line fragments that lie at the same y level."""
    if not candidates:
        return []
    sorted_candidates = sorted(candidates, key=lambda c: c["y"])
    levels: list[_LineLevel] = []

    current_group: list[dict[str, Any]] = [sorted_candidates[0]]
    for cand in sorted_candidates[1:]:
        ref_y = current_group[0]["y"]
        if abs(cand["y"] - ref_y) <= tolerance_y:
            current_group.append(cand)
        else:
            y_val = statistics.median([c["y"] for c in current_group])
            min_x0 = min(c["x0"] for c in current_group)
            max_x1 = max(c["x1"] for c in current_group)
            sw_vals = [c["stroke_width"] for c in current_group if c["stroke_width"] is not None]
            med_sw = statistics.median(sw_vals) if sw_vals else 0.5
            ids = [c["id"] for c in current_group]
            levels.append(_LineLevel(y=y_val, x0=min_x0, x1=max_x1, stroke_width=med_sw, obs_ids=ids))
            current_group = [cand]

    if current_group:
        y_val = statistics.median([c["y"] for c in current_group])
        min_x0 = min(c["x0"] for c in current_group)
        max_x1 = max(c["x1"] for c in current_group)
        sw_vals = [c["stroke_width"] for c in current_group if c["stroke_width"] is not None]
        med_sw = statistics.median(sw_vals) if sw_vals else 0.5
        ids = [c["id"] for c in current_group]
        levels.append(_LineLevel(y=y_val, x0=min_x0, x1=max_x1, stroke_width=med_sw, obs_ids=ids))

    return levels


def _cluster_by_horizontal_span(
    levels: list[_LineLevel],
    min_iou: float = 0.65,
) -> list[list[_LineLevel]]:
    """Group lines that share horizontal alignment (same column/system horizontal span)."""
    if not levels:
        return []

    used: set[int] = set()
    clusters: list[list[_LineLevel]] = []

    for i, l1 in enumerate(levels):
        if i in used:
            continue
        cluster = [l1]
        used.add(i)
        for j in range(i + 1, len(levels)):
            if j in used:
                continue
            l2 = levels[j]
            overlap = max(0.0, min(l1.x1, l2.x1) - max(l1.x0, l2.x0))
            union = max(l1.x1, l2.x1) - min(l1.x0, l2.x0)
            iou = overlap / union if union > 0 else 0.0
            if iou >= min_iou:
                cluster.append(l2)
                used.add(j)
        clusters.append(cluster)

    return clusters


class _DetectedStaffGroup:
    def __init__(
        self,
        lines: list[_LineLevel],
        staff_kind: StaffKind,
        space: float,
        uncertainty: ScaleUncertainty,
        raw_gaps: list[float],
    ) -> None:
        self.lines = lines
        self.staff_kind = staff_kind
        self.space = space
        self.uncertainty = uncertainty
        self.raw_gaps = raw_gaps

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def stroke_width(self) -> float:
        sws = [line.stroke_width for line in self.lines if line.stroke_width is not None]
        return statistics.median(sws) if sws else 0.5

    @property
    def observation_ids(self) -> list[str]:
        ids: list[str] = []
        for line in self.lines:
            ids.extend(line.obs_ids)
        return ids

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        x0 = min(line.x0 for line in self.lines)
        x1 = max(line.x1 for line in self.lines)
        y0 = min(line.y for line in self.lines)
        y1 = max(line.y for line in self.lines)
        return (x0, y0, x1, y1)


def _partition_cluster_into_staves(
    cluster: list[_LineLevel],
    min_staff_lines: int = 4,
    max_staff_lines: int = 8,
    min_gap: float = 2.0,
    max_gap: float = 80.0,
    gap_tolerance_ratio: float = 0.20,
) -> list[_DetectedStaffGroup]:
    """Partition a cluster of horizontally aligned lines into individual staves."""
    if len(cluster) < min_staff_lines:
        return []

    sorted_lines = sorted(cluster, key=lambda line: line.y)
    staves: list[_DetectedStaffGroup] = []

    cur_lines: list[_LineLevel] = [sorted_lines[0]]
    cur_gaps: list[float] = []

    def commit_staff(lines: list[_LineLevel], gaps: list[float]) -> None:
        if min_staff_lines <= len(lines) <= max_staff_lines and gaps:
            med_gap = statistics.median(gaps)
            stdev = statistics.stdev(gaps) if len(gaps) > 1 else 0.0
            mean_gap = statistics.mean(gaps)
            cv = (stdev / mean_gap) if mean_gap > 0 else 0.0

            # Reject staff if gaps are severely irregular (not periodic)
            if cv > 0.25:
                return

            confidence = max(0.0, min(1.0, 1.0 - cv * 3.0))
            uncertainty = ScaleUncertainty(
                sample_count=len(gaps),
                standard_deviation=round(stdev, 4),
                coefficient_of_variation=round(cv, 4),
                min_gap=round(min(gaps), 4),
                max_gap=round(max(gaps), 4),
                confidence=round(confidence, 4),
            )

            # Classify staff kind
            if len(lines) == 5:
                kind = StaffKind.NOTATION
            elif len(lines) == 6:
                kind = StaffKind.TAB
            else:
                kind = StaffKind.UNKNOWN

            staves.append(_DetectedStaffGroup(
                lines=list(lines),
                staff_kind=kind,
                space=med_gap,
                uncertainty=uncertainty,
                raw_gaps=list(gaps),
            ))

    for line in sorted_lines[1:]:
        gap = line.y - cur_lines[-1].y
        if gap < min_gap:
            # Redundant / overlapping line level, skip
            continue

        if not cur_gaps:
            if min_gap <= gap <= max_gap:
                cur_lines.append(line)
                cur_gaps.append(gap)
            else:
                cur_lines = [line]
                cur_gaps = []
        else:
            med_gap = statistics.median(cur_gaps)
            tol = max(0.8, gap_tolerance_ratio * med_gap)
            if abs(gap - med_gap) <= tol and gap <= max_gap:
                cur_lines.append(line)
                cur_gaps.append(gap)
            else:
                commit_staff(cur_lines, cur_gaps)
                cur_lines = [line]
                cur_gaps = []

    if cur_lines and cur_gaps:
        commit_staff(cur_lines, cur_gaps)

    return staves


def _estimate_glyph_scale(
    texts: Sequence[TextObservation],
    page_index: int,
) -> tuple[float | None, list[str], list[float]]:
    """Estimate characteristic glyph scale from page text observations."""
    candidate_heights: list[float] = []
    text_ids: list[str] = []

    for t in texts:
        if t.bbox.page_index != page_index:
            continue
        # Filter for music glyphs and fret digits (short strings: 1 to 6 chars)
        txt = t.raw_text.strip()
        if not txt or len(txt) > 6:
            continue
        h = abs(t.bbox.y1 - t.bbox.y0)
        if 2.0 <= h <= 40.0:
            candidate_heights.append(h)
            text_ids.append(t.id)

    if not candidate_heights:
        return None, [], []

    glyph_scale = statistics.median(candidate_heights)
    return glyph_scale, text_ids, candidate_heights


# ---------------------------------------------------------------------------
# Public Scale Estimation API
# ---------------------------------------------------------------------------

def estimate_local_scales(
    obs: DocumentObservations,
    page_index: int = 1,
    raise_on_unsupported: bool = False,
) -> list[TypedScaleEstimate]:
    """Estimate local scale models for each detected staff or system on a page.

    Estimates notation staff space and TAB string space independently for every
    detected staff group, retaining all raw and normalized diagnostic measurements.
    """
    if page_index < 1 or page_index > obs.page_count:
        if raise_on_unsupported:
            raise UnsupportedScaleError(f"Invalid page index {page_index}; page_count is {obs.page_count}")
        return [TypedScaleEstimate(
            scale_id=f"page-{page_index}-unsupported",
            page_index=page_index,
            status=ScaleStatus.UNSUPPORTED,
            error_message=f"Page index {page_index} out of bounds",
        )]

    candidates = _extract_candidate_horizontal_lines(obs.vectors, page_index)
    levels = _merge_collinear_fragments(candidates)
    clusters = _cluster_by_horizontal_span(levels)

    all_staves: list[_DetectedStaffGroup] = []
    for cluster in clusters:
        all_staves.extend(_partition_cluster_into_staves(cluster))

    glyph_scale, text_ids, raw_glyph_heights = _estimate_glyph_scale(obs.texts, page_index)

    if not all_staves:
        # Inadequate evidence: no valid staves detected
        status = ScaleStatus.UNSUPPORTED
        msg = "No periodic horizontal staff lines detected with sufficient support"
        if raise_on_unsupported:
            raise UnsupportedScaleError(msg)
        return [TypedScaleEstimate(
            scale_id=f"page-{page_index}-unsupported",
            page_index=page_index,
            status=status,
            error_message=msg,
        )]

    local_estimates: list[TypedScaleEstimate] = []
    for idx, staff in enumerate(all_staves, start=1):
        staff_id = f"page-{page_index}-staff-{idx}"
        not_space = staff.space if staff.staff_kind == StaffKind.NOTATION else None
        tab_space = staff.space if staff.staff_kind == StaffKind.TAB else None
        active_space = staff.space

        raw_line_ys = [line.y for line in staff.lines]
        raw_sws = [line.stroke_width for line in staff.lines if line.stroke_width is not None]
        norm_gaps = [g / active_space for g in staff.raw_gaps]
        norm_sws = [sw / active_space for sw in raw_sws]
        norm_glyphs = [gh / active_space for gh in raw_glyph_heights] if raw_glyph_heights else []

        bx0, by0, bx1, by1 = staff.bbox
        support_bbox = BoundingBox2D(page_index=page_index, x0=bx0, y0=by0, x1=bx1, y1=by1)

        diagnostics = ScaleDiagnostics(
            raw_line_ys=raw_line_ys,
            raw_gaps=staff.raw_gaps,
            raw_stroke_widths=raw_sws,
            raw_glyph_heights=raw_glyph_heights,
            normalized_gaps=norm_gaps,
            normalized_stroke_widths=norm_sws,
            normalized_glyph_heights=norm_glyphs,
            detected_groups=[{
                "staff_index": idx,
                "staff_kind": staff.staff_kind.value,
                "line_count": staff.line_count,
                "space": staff.space,
                "gaps": staff.raw_gaps,
            }],
        )

        support = ScaleSupport(
            vector_observation_ids=staff.observation_ids,
            text_observation_ids=text_ids if idx == 1 else [],
            region_bbox=support_bbox,
            line_count=staff.line_count,
            staff_kind=staff.staff_kind,
        )

        local_estimates.append(TypedScaleEstimate(
            scale_id=staff_id,
            page_index=page_index,
            status=ScaleStatus.ESTIMATED,
            notation_staff_space=not_space,
            tab_string_space=tab_space,
            stroke_thickness=round(staff.stroke_width, 4),
            glyph_scale=round(glyph_scale, 4) if glyph_scale is not None else None,
            uncertainty=staff.uncertainty,
            support=support,
            diagnostics=diagnostics,
        ))

    return local_estimates


def estimate_page_scale(
    obs: DocumentObservations,
    page_index: int = 1,
    raise_on_unsupported: bool = False,
) -> TypedScaleEstimate:
    """Estimate a consolidated page-level scale model without conflating notation and TAB.

    Maintains notation_staff_space and tab_string_space as strictly independent
    measurements. When both exist on a page, both are reported accurately and
    separately, never collapsed into a misleading aggregate mean.
    """
    local_estimates = estimate_local_scales(obs, page_index=page_index, raise_on_unsupported=raise_on_unsupported)

    # If any error or unsupported
    if len(local_estimates) == 1 and local_estimates[0].status != ScaleStatus.ESTIMATED:
        return local_estimates[0]

    notation_spaces: list[float] = []
    tab_spaces: list[float] = []
    stroke_widths: list[float] = []
    all_not_gaps: list[float] = []
    all_tab_gaps: list[float] = []
    all_line_ys: list[float] = []
    vector_ids: list[str] = []
    text_ids: list[str] = []

    for est in local_estimates:
        if est.notation_staff_space is not None:
            notation_spaces.append(est.notation_staff_space)
            all_not_gaps.extend(est.diagnostics.raw_gaps)
        if est.tab_string_space is not None:
            tab_spaces.append(est.tab_string_space)
            all_tab_gaps.extend(est.diagnostics.raw_gaps)
        if est.stroke_thickness is not None:
            stroke_widths.append(est.stroke_thickness)
        all_line_ys.extend(est.diagnostics.raw_line_ys)
        vector_ids.extend(est.support.vector_observation_ids)
        text_ids.extend(est.support.text_observation_ids)

    glyph_scale, g_text_ids, raw_glyph_heights = _estimate_glyph_scale(obs.texts, page_index)
    if g_text_ids:
        text_ids.extend(g_text_ids)
    text_ids = sorted(list(set(text_ids)))

    med_not_space = statistics.median(notation_spaces) if notation_spaces else None
    med_tab_space = statistics.median(tab_spaces) if tab_spaces else None
    med_stroke = statistics.median(stroke_widths) if stroke_widths else 0.5

    # Determine reference scale for page-level dimensionless normalization
    ref_scale = med_not_space or med_tab_space or 1.0

    raw_gaps = all_not_gaps + all_tab_gaps
    norm_gaps = [g / (med_not_space if i < len(all_not_gaps) else (med_tab_space or ref_scale))
                 for i, g in enumerate(raw_gaps)]
    norm_sws = [sw / ref_scale for sw in stroke_widths]
    norm_glyphs = [gh / ref_scale for gh in raw_glyph_heights] if raw_glyph_heights else []

    all_gaps_for_uncertainty = all_not_gaps if all_not_gaps else all_tab_gaps
    stdev = statistics.stdev(all_gaps_for_uncertainty) if len(all_gaps_for_uncertainty) > 1 else 0.0
    mean_gap = statistics.mean(all_gaps_for_uncertainty) if all_gaps_for_uncertainty else 0.0
    cv = (stdev / mean_gap) if mean_gap > 0 else 0.0
    confidence = max(0.0, min(1.0, 1.0 - cv * 3.0))

    uncertainty = ScaleUncertainty(
        sample_count=len(raw_gaps),
        standard_deviation=round(stdev, 4),
        coefficient_of_variation=round(cv, 4),
        min_gap=round(min(raw_gaps), 4) if raw_gaps else 0.0,
        max_gap=round(max(raw_gaps), 4) if raw_gaps else 0.0,
        confidence=round(confidence, 4),
    )

    detected_groups_summary = []
    for est in local_estimates:
        detected_groups_summary.extend(est.diagnostics.detected_groups)

    diagnostics = ScaleDiagnostics(
        raw_line_ys=sorted(all_line_ys),
        raw_gaps=raw_gaps,
        raw_stroke_widths=stroke_widths,
        raw_glyph_heights=raw_glyph_heights,
        normalized_gaps=norm_gaps,
        normalized_stroke_widths=norm_sws,
        normalized_glyph_heights=norm_glyphs,
        detected_groups=detected_groups_summary,
    )

    staff_kind = (
        StaffKind.UNKNOWN if (med_not_space and med_tab_space)
        else (StaffKind.NOTATION if med_not_space else (StaffKind.TAB if med_tab_space else StaffKind.UNKNOWN))
    )

    support = ScaleSupport(
        vector_observation_ids=sorted(list(set(vector_ids))),
        text_observation_ids=text_ids,
        region_bbox=None,
        line_count=len(all_line_ys),
        staff_kind=staff_kind,
    )

    return TypedScaleEstimate(
        scale_id=f"page-{page_index}-scale",
        page_index=page_index,
        status=ScaleStatus.ESTIMATED,
        notation_staff_space=round(med_not_space, 4) if med_not_space is not None else None,
        tab_string_space=round(med_tab_space, 4) if med_tab_space is not None else None,
        stroke_thickness=round(med_stroke, 4),
        glyph_scale=round(glyph_scale, 4) if glyph_scale is not None else None,
        uncertainty=uncertainty,
        support=support,
        diagnostics=diagnostics,
    )


def estimate_scales_for_document(
    obs: DocumentObservations,
    raise_on_unsupported: bool = False,
) -> DocumentObservations:
    """Populate scale_estimates in DocumentObservations for all pages."""
    estimates_dict: dict[str, ScaleEstimate] = {}
    for p_idx in range(1, obs.page_count + 1):
        est = estimate_page_scale(obs, page_index=p_idx, raise_on_unsupported=raise_on_unsupported)
        estimates_dict[f"page-{p_idx}"] = est.to_schema_estimate()

    return DocumentObservations(
        schema_version=obs.schema_version,
        document_id=obs.document_id,
        modality=obs.modality,
        source_file=obs.source_file,
        page_count=obs.page_count,
        vectors=obs.vectors,
        texts=obs.texts,
        rasters=obs.rasters,
        scale_estimates=estimates_dict,
        metadata=obs.metadata,
    )
