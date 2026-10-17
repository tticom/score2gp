"""Recover unresolved annotations from notation geometry, without moving notes.

TAB text zones do not include labels above the paired notation staff. Those
labels must use that staff's barlines rather than the preceding TAB system.
Only an unambiguous source beat or an already read technique can own a mark.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .ir import ScoreIR, WarningItem
from .tabraw import TabRaw

UNPLACED = "pdf_only_tab_attachment_bar_unplaced"


def recover_unplaced_attachments(score: ScoreIR, tabraw: TabRaw,
                                 durations: dict[str, Any], *,
                                 classify: Callable[[str], str | None]) -> None:
    candidates = {c.id: c for c in tabraw.candidates}
    pending = {p.raw_token_id: w for w in score.warnings if w.code == UNPLACED
               for p in w.provenance if p.raw_token_id in candidates}
    source_events = defaultdict(list)
    for event in durations["events"]:
        source_events[event["bar_index"]].append(event)
    bars = {bar.index: bar for bar in score.bars}
    events = {event.id: event for bar in score.bars for event in bar.events}

    def note_x(note):
        for provenance in note.provenance:
            digit = candidates.get(provenance.raw_token_id)
            if digit is not None and digit.kind in {"fret", "percussive-strike"}:
                return digit.x
        return None

    for ident, warning in pending.items():
        candidate = candidates[ident]
        reason = "annotation_system_unresolved"
        provenance = candidate.to_provenance()
        target = None
        page = (candidate.page_index or 1) - 1
        if candidate.y is not None and candidate.x is not None and candidate.bbox is not None:
            offset = sum(durations["source"]["page_heights"][:page])
            # An above-staff annotation band, measured in this staff's spaces.
            # A mark below the staff cannot be reassigned to the preceding row.
            systems = [s for s in durations["systems"] if s["page_index"] == page
                       and 0 <= s["staff"]["top"] - (candidate.bbox.y1 - offset)
                       and 0 < s["staff"]["top"] - (candidate.y - offset) <= 10 * s["staff_space"]]
            if len(systems) == 1:
                system = systems[0]
                matches = [system["first_bar_index"] + i for i, (left, right) in enumerate(system["bars"])
                           if left + 1 < candidate.x < right - 1]
                provenance.system_id = f"system-{system['system_index'] + 1}"
                reason = "annotation_bar_ambiguous"
                if len(matches) == 1:
                    index = matches[0]
                    provenance.bar_index = index + 1
                    bar = bars.get(index + 1)
                    reason = "annotation_bar_refused"
                    if bar is not None and bar.events:
                        records = source_events[index]
                        reason = "annotation_event_mapping_unresolved"
                        if len(records) == len(bar.events):
                            if candidate.kind == "chord-symbol":
                                ranked = sorted((abs((r["location"]["bbox"][0] + r["location"]["bbox"][2]) / 2
                                                     - candidate.x), i) for i, r in enumerate(records))
                                reason = "annotation_beat_ambiguous"
                                reach = max(system["staff_space"], (candidate.bbox.x1 - candidate.bbox.x0) / 2)
                                if (ranked and ranked[0][0] <= reach and
                                        (len(ranked) == 1 or ranked[1][0] - ranked[0][0] >= 2)):
                                    event = bar.events[ranked[0][1]]
                                    reason = "annotation_beat_occupied"
                                    if event.chord_symbol in (None, candidate.raw_text) and event.chord_diagram is None:
                                        event.chord_symbol = candidate.raw_text
                                        provenance.raw["notation_attachment_recovered"] = True
                                        event.provenance.append(provenance)
                                        target = event
                            elif candidate.kind == "technique-text":
                                kind = classify(candidate.raw_text)
                                reason = "annotation_per_head_target_unresolved" if kind else "annotation_technique_unsupported"
                                # A label above notation can duplicate the TAB label.
                                # Confirm the already read endpoints, never guess a
                                # chord member or add a second technique from its text.
                                owners = []
                                for event in bar.events:
                                    for note in event.notes:
                                        x1 = note_x(note)
                                        for technique in note.techniques:
                                            destination = events.get(getattr(technique, "target_event_id", None))
                                            if technique.kind != kind or destination is None or x1 is None:
                                                continue
                                            for other in destination.notes:
                                                x2 = note_x(other)
                                                if other.string == note.string and x2 is not None and x1 < candidate.x < x2:
                                                    owners.append((event, note))
                                if len(owners) == 1:
                                    target, note = owners[0]
                                    note.provenance.append(provenance)
        if target is not None:
            score.warnings = [w for w in score.warnings if w is not warning and not (
                w.code == f"tabraw-{candidate.kind}-not-aligned" and
                any(p.raw_token_id == ident for p in w.provenance))]
            score.warnings.append(WarningItem(
                code="pdf_only_tab_attachment_placed", severity="info",
                message=f"Annotation placed by notation geometry; event={target.id}.",
                provenance=[provenance]))
        else:
            warning.message = f"{warning.message} reason={reason}."
            warning.provenance = [provenance]
