"""Tuplet evidence extraction and local geometric tuplet association."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TupletMarkerEvidence:
    """Read-only evidence for a candidate printed tuplet digit '3'."""

    marker_id: str
    literal: str = "3"
    page_index: int = 1
    system_index: int = 1
    staff_index: int = 1
    span_id: str = "span_001"
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    source: str = "tuplet_marker_candidate_evidence"
    geometry_facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "literal": self.literal,
            "page_index": self.page_index,
            "system_index": self.system_index,
            "staff_index": self.staff_index,
            "span_id": self.span_id,
            "bbox": list(self.bbox),
            "source": self.source,
            "geometry_facts": self.geometry_facts,
        }


@dataclass(frozen=True)
class TupletAssociation:
    """Representation of a resolved or ambiguous 3:2 tuplet association."""

    marker_id: str
    associated_candidate_ids: tuple[str, ...] = ()
    ratio: tuple[int, int] = (3, 2)
    span_id: str = "span_001"
    geometry_facts: dict[str, Any] = field(default_factory=dict)
    status: str = "associated"  # "associated" or "ambiguous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "associated_candidate_ids": list(self.associated_candidate_ids),
            "ratio": f"{self.ratio[0]}:{self.ratio[1]}",
            "span_id": self.span_id,
            "geometry_facts": self.geometry_facts,
            "status": self.status,
        }


def extract_tuplet_marker_evidence(
    raw_text_elements: list[dict[str, Any]],
    staves_geometry: list[dict[str, Any]] | None = None,
    page_index: int = 1,
) -> list[TupletMarkerEvidence]:
    """
    Extracts candidate printed tuplet digit '3' evidence from text elements.
    Filters out obvious metadata/bracket strings like '[3:50]' or non-'3' text.
    """
    markers: list[TupletMarkerEvidence] = []
    idx = 1

    for elem in raw_text_elements:
        text = str(elem.get("text", "")).strip()
        # Reject metadata regex like '[3:50]' or text containing ':' or non-3 characters
        if text != "3":
            continue

        bbox = elem.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue

        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except (TypeError, ValueError):
            continue

        sys_idx = elem.get("system_index", 1)
        staff_idx = elem.get("staff_index", 1)
        span_id = elem.get("span_id", "span_001")
        kind = elem.get("kind", "text_span")

        # Must not be labeled as TAB fret digit, measure label, or metadata
        if kind in ("tab_fret", "measure_label", "metadata_text"):
            continue

        marker_id = f"tuplet_marker_{idx:03d}"
        idx += 1

        markers.append(
            TupletMarkerEvidence(
                marker_id=marker_id,
                literal="3",
                page_index=page_index,
                system_index=sys_idx,
                staff_index=staff_idx,
                span_id=span_id,
                bbox=(x0, y0, x1, y1),
                source=elem.get("source", "diagnostic_candidate_evidence"),
                geometry_facts={
                    "x_center": (x0 + x1) / 2.0,
                    "y_center": (y0 + y1) / 2.0,
                    "width": x1 - x0,
                    "height": y1 - y0,
                    "kind": kind,
                },
            )
        )

    return markers


def _get_x_center(cand: dict[str, Any]) -> float:
    bbox = cand.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return (float(bbox[0]) + float(bbox[2])) / 2.0
    if "x0" in cand and "x1" in cand:
        return (float(cand["x0"]) + float(cand["x1"])) / 2.0
    return float(cand.get("x0", 0.0))


def associate_local_tuplets(
    markers: list[TupletMarkerEvidence | dict[str, Any]],
    outcomes: list[dict[str, Any]],
    staff_geometries: list[dict[str, Any]] | None = None,
) -> list[TupletAssociation]:
    """
    Associates candidate tuplet '3' markers with local 3-eighth-note sequences according to the
    5 strict CR-03D rules:
    1. Above-staff lane: marker y-center is between top staff line - 2*spacing and top staff line.
    2. Hierarchy ownership: page, system, staff, and explicit span_id must match.
    3. X-center tolerance: marker x-center is strictly between 1st and 3rd notehead x-centers.
    4. Exact 3-event sequential group: 3 consecutive eighth notes with no intervening rests/durations.
    5. Unique matching group: exactly 1 matching group per marker; multiple matches or competing markers -> ambiguous.
    """
    staff_geom_map: dict[tuple[int, int, int], dict[str, Any]] = {}
    if staff_geometries:
        for sg in staff_geometries:
            page = sg.get("page_index")
            sys_idx = sg.get("system_index")
            staff_idx = sg.get("staff_index")
            if (
                type(page) is int
                and type(sys_idx) is int
                and type(staff_idx) is int
            ):
                staff_geom_map[(page, sys_idx, staff_idx)] = sg

    # Normalize markers
    norm_markers: list[TupletMarkerEvidence] = []
    for m in markers:
        if isinstance(m, TupletMarkerEvidence):
            norm_markers.append(m)
        elif isinstance(m, dict):
            bbox = m.get("bbox", (0.0, 0.0, 0.0, 0.0))
            if isinstance(bbox, list):
                bbox = tuple(bbox)
            norm_markers.append(
                TupletMarkerEvidence(
                    marker_id=m.get("marker_id", "tuplet_marker_000"),
                    literal=str(m.get("literal", "3")),
                    page_index=m.get("page_index", 1),
                    system_index=m.get("system_index", 1),
                    staff_index=m.get("staff_index", 1),
                    span_id=m.get("span_id", "span_001"),
                    bbox=bbox,  # type: ignore
                    source=m.get("source", "diagnostic_candidate_evidence"),
                    geometry_facts=m.get("geometry_facts", {}),
                )
            )

    associations: list[TupletAssociation] = []

    # Group notes by (page, system, staff, span_id)
    grouped_events: dict[tuple[int, int, int, str], list[dict[str, Any]]] = {}
    for cand in outcomes:
        st_type = cand.get("symbol_type")
        is_note = st_type in (
            "whole_note_candidate",
            "half_note_candidate",
            "quarter_note_candidate",
            "eighth_note_candidate",
            "sixteenth_note_candidate",
            "thirty_second_note_candidate",
            "sixty_fourth_note_candidate",
            "eighth_note",
            "quarter_note",
            "half_note",
            "whole_note",
        )
        is_rest = "rest" in str(st_type)
        if not (is_note or is_rest):
            continue

        if cand.get("association_status") in ("failed", "suppressed"):
            continue

        page = cand.get("page_index", 1)
        sys_idx = cand.get("system_index", 1)
        staff_idx = cand.get("staff_index", 1)
        span_id = cand.get("span_id", "span_001")

        key = (page, sys_idx, staff_idx, span_id)
        if key not in grouped_events:
            grouped_events[key] = []
        grouped_events[key].append(cand)

    # Sort events horizontally in each group
    for key in grouped_events:
        grouped_events[key].sort(key=_get_x_center)

    # Map candidate_id to associated markers to detect multi-marker competition
    candidate_to_markers: dict[str, list[str]] = {}

    for marker in norm_markers:
        # Require literal == "3"
        if marker.literal != "3":
            continue

        page = marker.page_index
        sys_idx = marker.system_index
        staff_idx = marker.staff_index
        span_id = marker.span_id

        # Rule 1: Above-staff lane
        # Determine staff top y and staff spacing
        sg = staff_geom_map.get((page, sys_idx, staff_idx))
        top_line_y = None
        staff_spacing = 10.0

        if sg:
            line_ys = sg.get("line_y_coords", [])
            if isinstance(line_ys, list) and len(line_ys) == 5:
                top_line_y = float(line_ys[0])
                staff_spacing = float(line_ys[4] - line_ys[0]) / 4.0
            else:
                bbox_sg = sg.get("bbox")
                if isinstance(bbox_sg, (list, tuple)) and len(bbox_sg) >= 4:
                    top_line_y = float(bbox_sg[1])

        if top_line_y is None:
            top_line_y = marker.bbox[1] + 10.0

        marker_y_center = (marker.bbox[1] + marker.bbox[3]) / 2.0
        # Lane: top_line_y - 2.0 * staff_spacing <= marker_y_center <= top_line_y + 0.5
        lane_top = top_line_y - 2.0 * staff_spacing
        lane_bottom = top_line_y + 0.5

        if not (lane_top - 0.5 <= marker_y_center <= lane_bottom):
            # Outside above-staff lane (e.g. TAB area or inside staff) -> reject
            continue

        # Rule 2: Hierarchy ownership matching
        events = grouped_events.get((page, sys_idx, staff_idx, span_id), [])
        if not events:
            continue

        # Rule 4: Find all candidate 3-sequential-eighth-note groups
        matching_groups: list[tuple[str, str, str]] = []
        marker_x_center = (marker.bbox[0] + marker.bbox[2]) / 2.0

        for i in range(len(events) - 2):
            g = events[i : i + 3]
            # Check all 3 are eighth notes
            if not all(
                e.get("symbol_type") in ("eighth_note_candidate", "eighth_note")
                for e in g
            ):
                continue

            c1_x = _get_x_center(g[0])
            c3_x = _get_x_center(g[2])

            # Rule 3: Strict X-center tolerance: c1_x < marker_x_center < c3_x
            if c1_x < marker_x_center < c3_x:
                cand_ids = (
                    g[0].get("candidate_id", ""),
                    g[1].get("candidate_id", ""),
                    g[2].get("candidate_id", ""),
                )
                if all(cand_ids):
                    matching_groups.append(cand_ids)

        # Rule 5: Unique matching group
        if len(matching_groups) == 1:
            group_ids = matching_groups[0]
            associations.append(
                TupletAssociation(
                    marker_id=marker.marker_id,
                    associated_candidate_ids=group_ids,
                    ratio=(3, 2),
                    span_id=span_id,
                    geometry_facts={
                        "marker_x_center": marker_x_center,
                        "marker_y_center": marker_y_center,
                        "lane_top": lane_top,
                        "lane_bottom": lane_bottom,
                    },
                    status="associated",
                )
            )
            for cid in group_ids:
                candidate_to_markers.setdefault(cid, []).append(
                    marker.marker_id
                )
        elif len(matching_groups) > 1:
            # Multiple matching groups for single marker -> ambiguous
            associations.append(
                TupletAssociation(
                    marker_id=marker.marker_id,
                    associated_candidate_ids=(),
                    ratio=(3, 2),
                    span_id=span_id,
                    geometry_facts={
                        "competing_group_count": len(matching_groups),
                    },
                    status="ambiguous",
                )
            )

    # Secondary check: If any candidate note belongs to multiple markers, mark associations as ambiguous
    final_associations: list[TupletAssociation] = []
    ambiguous_marker_ids = {
        m_id
        for cid, m_ids in candidate_to_markers.items()
        if len(m_ids) > 1
        for m_id in m_ids
    }

    for assoc in associations:
        if assoc.marker_id in ambiguous_marker_ids:
            final_associations.append(
                TupletAssociation(
                    marker_id=assoc.marker_id,
                    associated_candidate_ids=assoc.associated_candidate_ids,
                    ratio=assoc.ratio,
                    span_id=assoc.span_id,
                    geometry_facts=assoc.geometry_facts,
                    status="ambiguous",
                )
            )
        else:
            final_associations.append(assoc)

    return final_associations
