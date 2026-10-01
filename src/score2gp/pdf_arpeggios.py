"""Attach PDF vector rolled-chord marks to uniquely identified source chords."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pymupdf

from .ir import Provenance, ScoreIR, SourceStage, WarningItem


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
                x0, y0, x1, y1 = mark["bbox"]
                location = {"page_index": page_index, **mark}
                # Engraved notation+TAB pairs print the same roll twice. The
                # upper mark carries beat geometry; keep the lower one's stroke
                # IDs in the same source citation, without emitting twice.
                paired = next((prior for prior in page_marks[:mark_number]
                               if abs(prior["bbox"][0] - x0) <= 5
                               and 0 <= y0 - prior["bbox"][3] <= 70), None)
                if paired is not None:
                    location["code"] = "pdf_arpeggio_tab_duplicate"
                    counts[location["code"]] += 1
                    decisions.append(location)
                    continue
                possible_systems = []
                for system in systems:
                    if system["page_index"] != page_index:
                        continue
                    staff = system["staff"]
                    spacing = float(system["staff_space"])
                    overlap = min(y1, float(staff["bottom"]) + 4 * spacing) - max(y0, float(staff["top"]) - 2 * spacing)
                    if not float(staff["x0"]) <= x0 <= float(staff["x1"]):
                        continue
                    if overlap > 0.5 * (y1 - y0):
                        possible_systems.append((system, "notation"))
                    elif float(staff["bottom"]) + 2 * spacing <= y0 <= float(staff["bottom"]) + 18 * spacing:
                        possible_systems.append((system, "tab"))
                reason = "pdf_arpeggio_system_ambiguous"
                if len(possible_systems) == 1:
                    system, staff_kind = possible_systems[0]
                    local_bars = [int(system["first_bar_index"]) + local
                                  for local, (left, right) in enumerate(system["bars"])
                                  if float(left) + 1 < x0 < float(right) - 1]
                    reason = "pdf_arpeggio_bar_ambiguous"
                    if len(local_bars) == 1:
                        bar_index = local_bars[0]
                        target = bars.get(bar_index + 1)
                        candidates = source_events[bar_index]
                        reason = "pdf_arpeggio_beat_unavailable"
                        if target is not None and len(candidates) == len(target.events):
                            matched = []
                            for beat_index, (source, beat) in enumerate(zip(candidates, target.events)):
                                bx0, by0, bx1, by1 = source["location"]["bbox"]
                                gap = float(bx0) - x1
                                overlap = min(float(by1), y1) - max(float(by0), y0)
                                if (len(beat.notes) >= 2 and 0 <= gap <= 12
                                        and (staff_kind == "tab" or overlap >= 0.6 * (float(by1) - float(by0)))):
                                    matched.append((beat_index, beat))
                            reason = "pdf_arpeggio_chord_ambiguous"
                            if len(matched) == 1:
                                beat_index, beat = matched[0]
                                if beat.arpeggio in ("up", "down"):
                                    reason = "pdf_arpeggio_duplicate"
                                else:
                                    beat.arpeggio = mark["direction"]
                                    beat.provenance.append(Provenance(
                                        source_stage=SourceStage.PDF_TEXT, page=page_index + 1,
                                        system_id=f"system-{system['system_index'] + 1}",
                                        bar_index=bar_index + 1,
                                        raw_token_id=f"pdf-p{page_index + 1}-d{mark['stroke_indices'][0]}",
                                        raw={"bbox": mark["bbox"], "stroke_indices": mark["stroke_indices"]},
                                    ))
                                    reason = "pdf_arpeggio_attached"
                                    location.update({"bar_index": bar_index + 1, "beat_index": beat_index + 1})
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
