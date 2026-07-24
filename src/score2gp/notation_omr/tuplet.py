"""Tuplet evidence extraction and local geometric tuplet association."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TupletMarkerEvidence:
    """Read-only evidence for a candidate printed tuplet digit '3'."""

    marker_id: str
    literal: str = "3"
    page_index: int | None = None
    system_index: int | None = None
    staff_index: int | None = None
    span_id: str | None = None
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
    competing_candidate_ids: tuple[str, ...] = ()
    ratio: tuple[int, int] = (3, 2)
    span_id: str | None = None
    geometry_facts: dict[str, Any] = field(default_factory=dict)
    status: str = "associated"  # "associated" or "ambiguous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "associated_candidate_ids": list(self.associated_candidate_ids),
            "competing_candidate_ids": list(self.competing_candidate_ids),
            "ratio": f"{self.ratio[0]}:{self.ratio[1]}",
            "span_id": self.span_id,
            "geometry_facts": self.geometry_facts,
            "status": self.status,
        }


def _get_x_center(cand: dict[str, Any]) -> float:
    bbox = cand.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return (float(bbox[0]) + float(bbox[2])) / 2.0
    if "x0" in cand and "x1" in cand:
        return (float(cand["x0"]) + float(cand["x1"])) / 2.0
    return float(cand.get("x0", 0.0))


def derive_measure_spans_for_staff(
    staff_info: dict[str, Any],
    outcomes: list[dict[str, Any]] | None = None,
) -> list[tuple[float, float, str]]:
    """
    Derives measure spans [x_start, x_end, span_id] for a staff using barlines from:
    1. `outcomes` (symbol_type in ("barline_candidate", "barline"))
    2. `staff_info.get("barlines")` or `staff_info.get("barline_candidates")`
    If no barlines exist but staff_info has an explicit `span_id`, returns [(staff_x0, staff_x1, explicit_span_id)].
    If no barlines exist and no explicit span_id is set, returns [] (cannot observe a genuine measure span).
    """
    s_obj = staff_info.get("staff", staff_info)
    page = staff_info.get("page_index", s_obj.get("page_index", 1))
    sys_idx = s_obj.get("system_index", 1)
    staff_idx = s_obj.get("staff_index", 1)

    staff_x0 = float(s_obj.get("x0", 0.0))
    staff_x1 = float(s_obj.get("x1", 1000.0))

    explicit_span = s_obj.get("span_id") or staff_info.get("span_id")

    barline_xs: set[float] = set()

    if outcomes:
        for o in outcomes:
            st_type = o.get("symbol_type")
            if st_type in ("barline_candidate", "barline"):
                if (
                    o.get("page_index") == page
                    and o.get("system_index") == sys_idx
                    and o.get("staff_index") == staff_idx
                ):
                    b_x = _get_x_center(o)
                    if staff_x0 < b_x < staff_x1:
                        barline_xs.add(b_x)

    raw_barlines = (
        staff_info.get("barlines")
        or staff_info.get("barline_candidates")
        or s_obj.get("barlines")
        or s_obj.get("barline_candidates")
        or []
    )
    for b in raw_barlines:
        b_dict = (
            b
            if isinstance(b, dict)
            else (
                b.model_dump() if hasattr(b, "model_dump") else getattr(b, "__dict__", {})
            )
        )
        cls = b_dict.get("classification") or b_dict.get("kind")
        if cls in ("confirmed_barline", "barline_candidate", "barline"):
            b_x = _get_x_center(b_dict)
            if staff_x0 < b_x < staff_x1:
                barline_xs.add(b_x)

    if not barline_xs:
        if explicit_span:
            return [(staff_x0, staff_x1, str(explicit_span))]
        return []

    sorted_barline_xs = sorted(barline_xs)
    spans: list[tuple[float, float, str]] = []

    curr_x = staff_x0
    for m_idx, b_x in enumerate(sorted_barline_xs, start=1):
        spans.append((curr_x, b_x, f"span_m{m_idx}_p{page}_sys{sys_idx}_s{staff_idx}"))
        curr_x = b_x

    spans.append(
        (
            curr_x,
            staff_x1,
            f"span_m{len(sorted_barline_xs) + 1}_p{page}_sys{sys_idx}_s{staff_idx}",
        )
    )
    return spans


def find_measure_span_id(
    page: int | None,
    sys_idx: int | None,
    staff_idx: int | None,
    x_center: float,
    staff_spans_map: dict[tuple[int, int, int], list[tuple[float, float, str]]],
    explicit_span_id: str | None = None,
) -> str | None:
    if explicit_span_id:
        return explicit_span_id

    if page is None or sys_idx is None or staff_idx is None:
        return None

    spans = staff_spans_map.get((page, sys_idx, staff_idx), [])
    for x_start, x_end, span_id in spans:
        if x_start - 1.0 <= x_center <= x_end + 1.0:
            return span_id

    return None


def extract_tuplet_marker_evidence(
    raw_text_elements: list[dict[str, Any]],
    staves_geometry: list[dict[str, Any]] | None = None,
    page_index: int = 1,
    outcomes: list[dict[str, Any]] | None = None,
) -> list[TupletMarkerEvidence]:
    """
    Extracts candidate printed tuplet digit '3' evidence from text elements.
    Derives ownership and genuine measure span from staves_geometry and barlines.
    Rejects text that is not a plain '3' or is labeled as TAB fret, measure label, or metadata.
    """
    markers: list[TupletMarkerEvidence] = []
    idx = 1

    staff_spans_map: dict[tuple[int, int, int], list[tuple[float, float, str]]] = {}
    valid_staves: list[dict[str, Any]] = []

    if staves_geometry:
        for sg in staves_geometry:
            line_ys = sg.get("line_y_coords") or sg.get("staff", {}).get("line_y_coords")
            if isinstance(line_ys, list) and len(line_ys) == 5:
                s_info = sg.get("staff", sg)
                sys_idx = s_info.get("system_index")
                staff_idx = s_info.get("staff_index")
                if sys_idx is not None and staff_idx is not None:
                    top_y = float(line_ys[0])
                    bot_y = float(line_ys[4])
                    spacing = (bot_y - top_y) / 4.0
                    x0 = float(s_info.get("x0", 0.0))
                    x1 = float(s_info.get("x1", 1000.0))

                    spans = derive_measure_spans_for_staff(sg, outcomes)
                    key = (page_index, sys_idx, staff_idx)
                    staff_spans_map[key] = spans

                    valid_staves.append({
                        "system_index": sys_idx,
                        "staff_index": staff_idx,
                        "top_line_y": top_y,
                        "lane_top": top_y - 2.5 * spacing,
                        "lane_bottom": top_y + 0.5 * spacing,
                        "x0": x0 - 10.0,
                        "x1": x1 + 10.0,
                    })

    for elem in raw_text_elements:
        text = str(elem.get("text", "")).strip()
        if text != "3":
            continue

        bbox = elem.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue

        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except (TypeError, ValueError):
            continue

        kind = elem.get("kind", "text_span")
        if kind in ("tab_fret", "measure_label", "metadata_text"):
            continue

        y_center = (y0 + y1) / 2.0
        x_center = (x0 + x1) / 2.0

        sys_idx = elem.get("system_index")
        staff_idx = elem.get("staff_index")
        span_id = elem.get("span_id")

        if sys_idx is None or staff_idx is None:
            matched_staff = None
            for s in valid_staves:
                if s["lane_top"] <= y_center <= s["lane_bottom"] and s["x0"] <= x_center <= s["x1"]:
                    matched_staff = s
                    break

            if matched_staff:
                sys_idx = matched_staff["system_index"]
                staff_idx = matched_staff["staff_index"]

        if sys_idx is None or staff_idx is None:
            continue

        if span_id is None:
            span_id = find_measure_span_id(
                page_index, sys_idx, staff_idx, x_center, staff_spans_map, explicit_span_id=None
            )

        marker_id = f"tuplet_marker_{idx:03d}"
        idx += 1

        markers.append(
            TupletMarkerEvidence(
                marker_id=marker_id,
                literal="3",
                page_index=elem.get("page_index", page_index),
                system_index=sys_idx,
                staff_index=staff_idx,
                span_id=span_id,
                bbox=(x0, y0, x1, y1),
                source=elem.get("source", "diagnostic_candidate_evidence"),
                geometry_facts={
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": x1 - x0,
                    "height": y1 - y0,
                    "kind": kind,
                },
            )
        )

    return markers


def associate_local_tuplets(
    markers: list[TupletMarkerEvidence | dict[str, Any]],
    outcomes: list[dict[str, Any]],
    staff_geometries: list[dict[str, Any]] | None = None,
) -> list[TupletAssociation]:
    """
    Associates candidate tuplet '3' markers with local 3-eighth-note sequences according to 5 strict rules:
    1. Above-staff lane: requires valid 5-line staff geometry. Marker y-center must fall in top_line_y - 2.5*spacing to top_line_y.
    2. Hierarchy ownership: page, system, staff, and genuine measure span_id must match. Fails closed if span cannot be derived.
    3. X-center tolerance: marker x-center is strictly between 1st and 3rd notehead x-centers.
    4. Exact 3-event sequential group: 3 consecutive eighth notes with no intervening rests/durations.
    5. Unique matching group: exactly 1 matching group per marker. Competing groups or markers -> status='ambiguous'.
    """
    staff_geom_map: dict[tuple[int, int, int], dict[str, Any]] = {}
    staff_spans_map: dict[tuple[int, int, int], list[tuple[float, float, str]]] = {}

    if staff_geometries:
        for sg in staff_geometries:
            page = sg.get("page_index")
            s_obj = sg.get("staff", sg)
            sys_idx = sg.get("system_index") or s_obj.get("system_index")
            staff_idx = sg.get("staff_index") or s_obj.get("staff_index")
            line_ys = sg.get("line_y_coords") or s_obj.get("line_y_coords")
            if (
                type(page) is int
                and type(sys_idx) is int
                and type(staff_idx) is int
                and isinstance(line_ys, list)
                and len(line_ys) == 5
            ):
                key = (page, sys_idx, staff_idx)
                staff_geom_map[key] = {
                    "top_line_y": float(line_ys[0]),
                    "staff_spacing": float(line_ys[4] - line_ys[0]) / 4.0,
                }
                spans = derive_measure_spans_for_staff(sg, outcomes)
                staff_spans_map[key] = spans

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
                    page_index=m.get("page_index"),
                    system_index=m.get("system_index"),
                    staff_index=m.get("staff_index"),
                    span_id=m.get("span_id"),
                    bbox=bbox,  # type: ignore
                    source=m.get("source", "diagnostic_candidate_evidence"),
                    geometry_facts=m.get("geometry_facts", {}),
                )
            )

    associations: list[TupletAssociation] = []

    # Group note events by (page, system, staff, span_id)
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

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")
        explicit_span = cand.get("span_id")

        note_x = _get_x_center(cand)
        span_id = find_measure_span_id(
            page, sys_idx, staff_idx, note_x, staff_spans_map, explicit_span_id=explicit_span
        )

        # Do NOT invent synthetic span_id! Require explicit or derived span_id!
        if (
            type(page) is not int
            or type(sys_idx) is not int
            or type(staff_idx) is not int
            or not span_id
        ):
            continue

        key = (page, sys_idx, staff_idx, str(span_id))
        if key not in grouped_events:
            grouped_events[key] = []
        grouped_events[key].append(cand)

    # Sort events horizontally
    for key in grouped_events:
        grouped_events[key].sort(key=_get_x_center)

    candidate_to_markers: dict[str, list[str]] = {}

    for marker in norm_markers:
        if marker.literal != "3":
            continue

        page = marker.page_index
        sys_idx = marker.system_index
        staff_idx = marker.staff_index
        explicit_span = marker.span_id

        marker_x_center = (marker.bbox[0] + marker.bbox[2]) / 2.0
        span_id = find_measure_span_id(
            page, sys_idx, staff_idx, marker_x_center, staff_spans_map, explicit_span_id=explicit_span
        )

        if (
            type(page) is not int
            or type(sys_idx) is not int
            or type(staff_idx) is not int
            or not span_id
        ):
            continue

        sg = staff_geom_map.get((page, sys_idx, staff_idx))
        if not sg:
            continue

        top_line_y = sg["top_line_y"]
        staff_spacing = sg["staff_spacing"]

        if staff_spacing <= 0.0:
            continue

        marker_y_center = (marker.bbox[1] + marker.bbox[3]) / 2.0
        lane_top = top_line_y - 2.5 * staff_spacing
        lane_bottom = top_line_y + 0.5

        if not (lane_top - 0.5 <= marker_y_center <= lane_bottom):
            continue

        events = grouped_events.get((page, sys_idx, staff_idx, str(span_id)), [])
        if not events:
            continue

        matching_groups: list[tuple[str, str, str]] = []

        for i in range(len(events) - 2):
            g = events[i : i + 3]
            if not all(
                e.get("symbol_type") in ("eighth_note_candidate", "eighth_note")
                for e in g
            ):
                continue

            c1_x = _get_x_center(g[0])
            c3_x = _get_x_center(g[2])

            if c1_x < marker_x_center < c3_x:
                cand_ids = (
                    g[0].get("candidate_id", ""),
                    g[1].get("candidate_id", ""),
                    g[2].get("candidate_id", ""),
                )
                if all(cand_ids):
                    matching_groups.append(cand_ids)

        if len(matching_groups) == 1:
            group_ids = matching_groups[0]
            associations.append(
                TupletAssociation(
                    marker_id=marker.marker_id,
                    associated_candidate_ids=group_ids,
                    competing_candidate_ids=(),
                    ratio=(3, 2),
                    span_id=str(span_id),
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
            all_competing = tuple(
                cid for grp in matching_groups for cid in grp
            )
            associations.append(
                TupletAssociation(
                    marker_id=marker.marker_id,
                    associated_candidate_ids=(),
                    competing_candidate_ids=all_competing,
                    ratio=(3, 2),
                    span_id=str(span_id),
                    geometry_facts={
                        "competing_group_count": len(matching_groups),
                    },
                    status="ambiguous",
                )
            )
            for cid in all_competing:
                candidate_to_markers.setdefault(cid, []).append(
                    marker.marker_id
                )

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
                    competing_candidate_ids=assoc.competing_candidate_ids,
                    ratio=assoc.ratio,
                    span_id=assoc.span_id,
                    geometry_facts=assoc.geometry_facts,
                    status="ambiguous",
                )
            )
        else:
            final_associations.append(assoc)

    return final_associations
