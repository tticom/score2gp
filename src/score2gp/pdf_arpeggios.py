"""Attach PDF vector rolled-chord marks to uniquely identified source chords."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pymupdf

from .ir import Bar, Event, Provenance, ScoreIR, SourceStage, WarningItem


def _kind(drawing: dict[str, Any]) -> str:
    return "".join(item[0] for item in drawing["items"])


def _marks(page: pymupdf.Page) -> list[dict[str, Any]]:
    """Find a vertical repeated curl path ending in a triangular direction arrow.

    Dimensions are in PDF points. Individual curls may be separate filled paths;
    the repeated geometry, not a private source's drawing index, identifies them.
    """
    drawings = page.get_drawings()
    curls = [(i, drawing) for i, drawing in enumerate(drawings)
             if drawing["type"] == "f" and 4 <= _kind(drawing).count("c") <= 24
             and set(_kind(drawing)) == {"c"}
             and 1 <= drawing["rect"].width <= 4
             and 3 <= drawing["rect"].height <= 8]
    marks = []
    for index, arrow in enumerate(drawings):
        path = _kind(arrow)
        rect = arrow["rect"]
        if (arrow["type"] != "f" or path.count("l") < 2 or path.count("c") < 3
                or not 2 <= rect.width <= 9 or not 6 <= rect.height <= 16):
            continue
        lines = [item for item in arrow["items"] if item[0] == "l"]
        diagonals = [line for line in lines if abs(line[2].y - line[1].y) >= 0.3 * rect.height]
        if len(diagonals) < 2:
            continue
        tip = diagonals[-2][2]
        if abs(tip.x - diagonals[-1][1].x) > 0.2 or abs(tip.y - diagonals[-1][1].y) > 0.2:
            continue
        # Direction is the GPIF strum value, not the arrow's page direction.
        # PDF y increases downward: a tip near y0 points upward on the staff.
        # That low-to-high roll is GPIF Down; the reverse is GPIF Up.
        direction = "down" if abs(tip.y - rect.y0) < abs(tip.y - rect.y1) else "up"
        # The tip is at one end; the curls run away from it through the chord.
        nearby = [(i, curl) for i, curl in curls
                  if abs(curl["rect"].x0 - rect.x0) <= 2
                  and (rect.y0 - 45 <= curl["rect"].y0 <= rect.y1 + 45)]
        if direction == "down":
            nearby = [(i, curl) for i, curl in nearby if curl["rect"].y0 >= rect.y0 + 3]
        else:
            nearby = [(i, curl) for i, curl in nearby if curl["rect"].y1 <= rect.y1 - 3]
        nearby.sort(key=lambda pair: pair[1]["rect"].y0, reverse=direction == "up")
        contiguous = []
        previous_y = rect.y0 if direction == "down" else rect.y1
        for pair in nearby:
            next_y = pair[1]["rect"].y0 if direction == "down" else pair[1]["rect"].y1
            if abs(next_y - previous_y) > 9:
                break
            contiguous.append(pair)
            previous_y = next_y
        nearby = contiguous
        if len(nearby) < 3:
            continue
        # Reject distant independent squiggles and broken stacks.
        if any(b[1]["rect"].y0 - a[1]["rect"].y0 > 7
               for a, b in zip(nearby, nearby[1:])):
            continue
        bounds = pymupdf.Rect(arrow["rect"])
        for _, curl in nearby:
            bounds |= curl["rect"]
        if bounds.height < 15 or bounds.height / bounds.width < 3:
            continue
        marks.append({"bbox": [bounds.x0, bounds.y0, bounds.x1, bounds.y1],
                      "direction": direction, "stroke_indices": [index, *(i for i, _ in nearby)]})
    return marks


# Attachment distances are PDF points; staff margins are multiples of staff_space.
_TAB_DUPLICATE_X_TOLERANCE = 5
_TAB_DUPLICATE_MAX_GAP = 70
_NOTATION_MARGIN_BELOW = 4
_NOTATION_MARGIN_ABOVE = 2
_NOTATION_MIN_OVERLAP = 0.5
_TAB_MIN_OFFSET = 2
_TAB_MAX_OFFSET = 18
_BAR_EDGE_MARGIN = 1
_CHORD_MIN_NOTES = 2
_CHORD_MAX_GAP = 12
_CHORD_MIN_OVERLAP = 0.6


def _is_tab_duplicate(mark: dict[str, Any], earlier_marks: list[dict[str, Any]]) -> bool:
    """Recognize the lower copy of a roll printed on notation and TAB staves."""
    x0, y0, _, _ = mark["bbox"]
    return any(abs(prior["bbox"][0] - x0) <= _TAB_DUPLICATE_X_TOLERANCE
               and 0 <= y0 - prior["bbox"][3] <= _TAB_DUPLICATE_MAX_GAP
               for prior in earlier_marks)


def _candidate_systems(
    mark: dict[str, Any], page_index: int, systems: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    """Select staff systems overlapping the mark, retaining notation/TAB kind."""
    x0, y0, _, y1 = mark["bbox"]
    possible = []
    for system in systems:
        if system["page_index"] != page_index:
            continue
        staff = system["staff"]
        spacing = float(system["staff_space"])
        overlap = (min(y1, float(staff["bottom"]) + _NOTATION_MARGIN_BELOW * spacing)
                   - max(y0, float(staff["top"]) - _NOTATION_MARGIN_ABOVE * spacing))
        if not float(staff["x0"]) <= x0 <= float(staff["x1"]):
            continue
        if overlap > _NOTATION_MIN_OVERLAP * (y1 - y0):
            possible.append((system, "notation"))
        elif (float(staff["bottom"]) + _TAB_MIN_OFFSET * spacing
              <= y0 <= float(staff["bottom"]) + _TAB_MAX_OFFSET * spacing):
            possible.append((system, "tab"))
    return possible


def _choose_beat(
    mark: dict[str, Any], staff_kind: str,
    candidates: list[dict[str, Any]], target: Bar,
) -> tuple[int, Event] | None:
    """Choose exactly one source chord by horizontal gap and vertical overlap."""
    _, y0, x1, y1 = mark["bbox"]
    matched = []
    for beat_index, (source, beat) in enumerate(zip(candidates, target.events)):
        bx0, by0, _, by1 = source["location"]["bbox"]
        gap = float(bx0) - x1
        overlap = min(float(by1), y1) - max(float(by0), y0)
        if (len(beat.notes) >= _CHORD_MIN_NOTES and 0 <= gap <= _CHORD_MAX_GAP
                and (staff_kind == "tab"
                     or overlap >= _CHORD_MIN_OVERLAP * (float(by1) - float(by0)))):
            matched.append((beat_index, beat))
    return matched[0] if len(matched) == 1 else None


def _locate_chord(
    mark: dict[str, Any], page_index: int, systems: list[dict[str, Any]],
    source_events: dict[int, list[dict[str, Any]]], bars: dict[int, Bar],
) -> tuple[dict[str, Any], int, int, Event] | str:
    """Locate a unique system, bar and beat, or return the original refusal code."""
    possible_systems = _candidate_systems(mark, page_index, systems)
    if len(possible_systems) != 1:
        return "pdf_arpeggio_system_ambiguous"
    system, staff_kind = possible_systems[0]
    x0 = mark["bbox"][0]
    local_bars = [int(system["first_bar_index"]) + local
                  for local, (left, right) in enumerate(system["bars"])
                  if float(left) + _BAR_EDGE_MARGIN < x0 < float(right) - _BAR_EDGE_MARGIN]
    if len(local_bars) != 1:
        return "pdf_arpeggio_bar_ambiguous"
    bar_index = local_bars[0]
    target = bars.get(bar_index + 1)
    candidates = source_events[bar_index]
    if target is None or len(candidates) != len(target.events):
        return "pdf_arpeggio_beat_unavailable"
    matched = _choose_beat(mark, staff_kind, candidates, target)
    if matched is None:
        return "pdf_arpeggio_chord_ambiguous"
    beat_index, beat = matched
    return system, bar_index, beat_index, beat


def _attach_mark(
    location: dict[str, Any], systems: list[dict[str, Any]],
    source_events: dict[int, list[dict[str, Any]]], bars: dict[int, Bar],
) -> str:
    """Apply a located roll and its source citation, preserving existing rolls."""
    page_index = location["page_index"]
    chord = _locate_chord(location, page_index, systems, source_events, bars)
    if isinstance(chord, str):
        return chord
    system, bar_index, beat_index, beat = chord
    if beat.arpeggio in ("up", "down"):
        return "pdf_arpeggio_duplicate"
    beat.arpeggio = location["direction"]
    beat.provenance.append(Provenance(
        source_stage=SourceStage.PDF_TEXT, page=page_index + 1,
        system_id=f"system-{system['system_index'] + 1}",
        bar_index=bar_index + 1,
        raw_token_id=f"pdf-p{page_index + 1}-d{location['stroke_indices'][0]}",
        raw={"bbox": location["bbox"], "stroke_indices": location["stroke_indices"]},
    ))
    location.update({"bar_index": bar_index + 1, "beat_index": beat_index + 1})
    return "pdf_arpeggio_attached"


def attach_pdf_arpeggios(pdf: Path, note_durations: dict[str, Any], score: ScoreIR) -> dict[str, Any]:
    """Use source staff/bar/event geometry; refuse a mark without one source chord."""
    systems = note_durations.get("systems", [])
    source_events: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in note_durations.get("events", []):
        if event.get("status") == "read":
            source_events[int(event["bar_index"])].append(event)
    bars = {bar.index: bar for bar in score.bars}
    decisions: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    with pymupdf.open(pdf) as document:
        for page_index, page in enumerate(document):
            page_marks = _marks(page)
            for mark_number, mark in enumerate(page_marks):
                location = {"page_index": page_index, **mark}
                # Engraved notation+TAB pairs print the same roll twice. The
                # upper mark carries beat geometry; keep the lower one's stroke
                # IDs in the same source citation, without emitting twice.
                if _is_tab_duplicate(mark, page_marks[:mark_number]):
                    location["code"] = "pdf_arpeggio_tab_duplicate"
                    counts[location["code"]] += 1
                    decisions.append(location)
                    continue
                reason = _attach_mark(location, systems, source_events, bars)
                counts[reason] += 1
                location["code"] = reason
                decisions.append(location)
                if reason not in {"pdf_arpeggio_attached", "pdf_arpeggio_duplicate"}:
                    score.warnings.append(WarningItem(
                        code=reason, message=f"Rolled-chord mark cannot be attached on page {page_index + 1}.",
                        provenance=[Provenance(source_stage=SourceStage.PDF_TEXT, page=page_index + 1,
                                               raw={"bbox": mark["bbox"], "stroke_indices": mark["stroke_indices"]})],
                    ))
    return {"counts_by_reason": dict(sorted(counts.items())), "decisions": decisions}
