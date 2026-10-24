"""PDF-observed staff anchors and locations for layouts the TAB route refuses.

Refusal localization is diagnostic only: short pieces never authorize a TAB
assignment, bar, pitch, or duration.
"""

from pathlib import Path
from typing import Any


def locate_unsafe_notation_bars(tabraw: Any, note_durations: dict,
                               unsafe_codes: set[str]) -> list[dict]:
    """Keep every notation bar and its strikes visible at a whole-file refusal.

    This does not accept TAB geometry or assign a duration/string/fret. Warnings
    can block the whole source when independent partitioning is unavailable;
    distinguish that fact from a local candidate warning instead of attributing
    the first warning to every bar. Locations are the notation reader's own.
    """
    from .pdf_tab_bar_assembler import place_tab_digits

    digits = [c for c in tabraw.candidates if c.kind == "percussive-strike"
              or c.kind == "fret" and c.parsed_fret is not None]
    geometric = [c for c in digits if c.x is not None and c.y is not None
                 and c.page_index is not None]
    placed, unplaced = place_tab_digits(geometric, note_durations)
    unlocated_count = len(digits) - len(geometric) + len(unplaced)
    blockers = [
        {key: warning[key] for key in ("code", "page_index", "system_index") if key in warning}
        for warning in list(tabraw.warnings) + [{"code": c} for c in tabraw.pdf_layout_warnings]
        if warning.get("code") in unsafe_codes
    ]
    records: dict[int, list[dict]] = {}
    for record in note_durations.get("events", []):
        records.setdefault(record["bar_index"], []).append(record)
    located = []
    for system in note_durations.get("systems", []):
        for local, (left, right) in enumerate(system["bars"]):
            index = system["first_bar_index"] + local
            events = records.get(index, [])
            candidates = placed.get(index, [])
            local_codes = sorted({code for candidate in candidates
                                  for code in (candidate.raw or {}).get("grouping_warnings", [])
                                  + (candidate.raw or {}).get("assignment_warnings", [])
                                  if code in unsafe_codes})
            strikes = [
                {"location": event["location"], "head_count": len(heads),
                 "head_sources": [head["source"] for head in heads]}
                for event in events
                if (heads := [h for h in (event.get("notehead") or {}).get("heads", [])
                              if h["kind"] == "cross"])
            ]
            # These are observations, not a hypothetical successful conversion.
            # In particular, an unread event blocks its own bar even if a later
            # layout repair succeeds. Keep inherited file blockers separate: a
            # warning on another system is not evidence of a local defect.
            unread = [
                {"code": event["reason"], "location": event["location"]}
                for event in events if event.get("status") != "read"
            ]
            strike_count = sum(s["head_count"] for s in strikes)
            tab_strike_count = sum(c.kind == "percussive-strike" for c in candidates)
            located.append({
                "reason": "unsafe_tab_layout_not_independently_partitionable",
                "location": {"page_index": system["page_index"],
                             "system_index": system["system_index"], "bar_index": index,
                             "bbox": [left, system["staff"]["top"], right, system["staff"]["bottom"]]},
                "blocking_layout_warnings": blockers,
                "local_candidate_warning_codes": local_codes,
                "unread_notation_events": unread,
                "strike_candidate_count_matches": strike_count == tab_strike_count,
                "refusal_scope": "source_layout",
                "notation_head_count": sum((e.get("notehead") or {}).get("count", 0) for e in events),
                "tab_candidate_count": len(candidates),
                "unlocated_tab_candidate_count": unlocated_count,
                "nearest_tab_dx_spaces": [
                    {"event_index": event["event_index"],
                     "distance": round(min(abs(c.x - (event["location"]["bbox"][0]
                                                        + event["location"]["bbox"][2]) / 2)
                                           for c in candidates) / system["staff_space"], 3)}
                    for event in events if event.get("notehead") and candidates
                ],
                "notation_strike_count": strike_count,
                "notation_strikes": strikes,
                "tab_strike_candidate_count": tab_strike_count,
            })
    return located


def notation_anchored_line_groups(page: Any, horizontal: list, groups: list) -> list:
    """Keep five actual notation rows out of six-line TAB/ledger hypotheses.

    The notation reader independently requires uniform spacing, common ends and
    painted coverage. Only repair a legacy grouping that consumes its rows in a
    six-line hypothesis; ordinary accepted groupings retain their exact objects.
    """
    from .notation_omr.note_duration import (
        STAFF_LINE_END_TOLERANCE_PT, extract_page_symbols, find_staves,
    )
    from .pdf import _tab_line_groups

    # A ledger hypothesis has rows with different drawn ends. Common-ended
    # six-row groups already stand on their own; preserve the geometry-only
    # interface and avoid extracting text/fonts for those ordinary groups.
    if not any(len(group) == 6 and (
        max(min(line.x0, line.x1) for line in group) - min(min(line.x0, line.x1) for line in group)
        > STAFF_LINE_END_TOLERANCE_PT
        or max(max(line.x0, line.x1) for line in group) - min(max(line.x0, line.x1) for line in group)
        > STAFF_LINE_END_TOLERANCE_PT
    ) for group in groups):
        return groups
    notation, _ = find_staves(extract_page_symbols(page, 0))
    conflicts = any(
        len(group) == 6 and sum(
            any(abs((line.y0 + line.y1) / 2 - y) <= 1.0 for line in group)
            for y in staff.lines
        ) >= 2
        for group in groups for staff in notation
    )
    if not conflicts:
        return groups

    anchors = []
    for staff in notation:
        rows = []
        for y in staff.lines:
            drawn = [line for line in horizontal if abs((line.y0 + line.y1) / 2 - y) <= 1.0]
            if not drawn:
                # Every anchor must retain its five actual drawn rows.
                return groups
            rows.append(max(drawn, key=lambda line: abs(line.x1 - line.x0)))
        anchors.append(rows)
    remaining = [line for line in horizontal if not any(
        staff.top - 1.0 <= (line.y0 + line.y1) / 2 <= staff.bottom + 1.0
        and min(max(line.x0, line.x1), staff.x1) > max(min(line.x0, line.x1), staff.x0)
        for staff in notation
    )]
    return sorted(_tab_line_groups(remaining) + anchors,
                  key=lambda group: (min(line.y0 for line in group), min(line.x0 for line in group)))


def locate_unclassified_tab_groups(source_pdf: str | Path, note_durations: dict) -> list[dict]:
    """Locate six drawn rows on a refused, notation-free PDF without accepting them.

    The ordinary 75 pt filter can discard digit-interrupted rows. For locations
    only, retain pieces longer than the page's measured staff step. Require six
    uniformly spaced rows, text digits and a full-height drawn vertical. The
    existing classifier's verdict is retained; no unsupported spacing is accepted.
    """
    import pymupdf

    from .notation_omr.note_duration import STAFF_GAP_TOLERANCE, _measured_page_staff_space
    from .pdf import (
        _drawing_segments, _has_fret_digit_intersection, _tab_line_groups,
        classify_staff_line_group, merge_collinear_horizontal_segments,
    )

    if note_durations.get("systems") or not Path(source_pdf).is_file():
        return []
    located = []
    with pymupdf.open(source_pdf) as document:
        for page_index, page in enumerate(document):
            drawings = page.get_drawings()
            space = _measured_page_staff_space(drawings, page.rect.width)
            if space is None:
                continue
            segments = _drawing_segments(drawings)
            pieces = [line for line in segments if abs(line.y0 - line.y1) <= 0.1
                      and abs(line.x1 - line.x0) > space]
            groups = _tab_line_groups(merge_collinear_horizontal_segments(pieces))
            system_index = 0
            for group in groups:
                if len(group) != 6 or classify_staff_line_group(group, page) != "ambiguous":
                    continue
                ys = sorted((line.y0 + line.y1) / 2 for line in group)
                step = (ys[-1] - ys[0]) / 5
                if any(abs(b - a - step) > STAFF_GAP_TOLERANCE * step for a, b in zip(ys, ys[1:])):
                    continue
                x0 = min(min(line.x0, line.x1) for line in group)
                x1 = max(max(line.x0, line.x1) for line in group)
                if not _has_fret_digit_intersection(group, page):
                    continue
                if not any(abs(line.x0 - line.x1) <= 1.0
                           and x0 <= line.x0 <= x1
                           and min(line.y0, line.y1) <= ys[0] + 0.15 * step
                           and max(line.y0, line.y1) >= ys[-1] - 0.15 * step for line in segments):
                    continue
                located.append({
                    "page_index": page_index, "system_index": system_index,
                    "code": "tab_group_staff_spacing_unclassified", "line_count": 6,
                    "notation_bar_count": 0, "timing_code": "tab_group_without_notation_timing",
                    "bbox": [x0, ys[0], x1, ys[-1]],
                })
                system_index += 1
    return located
