"""PDF-observed staff anchors and locations for layouts the TAB route refuses.

Refusal localization is diagnostic only: short pieces never authorize a TAB
assignment, bar, pitch, or duration.
"""

from pathlib import Path
from typing import Any


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
