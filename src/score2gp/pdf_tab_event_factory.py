from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Any, Sequence

from .ir import (
    DEFAULT_TICKS_PER_QUARTER,
    Event,
    NotatedDuration,
    Note,
    TieTechnique,
    Timing,
    Tuplet,
)
from .pdf_tab_measure_timing import ticks_for_quarters

if TYPE_CHECKING:
    from .tabraw import TabCandidate


_STRING_TO_BASE_PITCH: dict[int, int] = {
    1: 64,  # E4
    2: 59,  # B3
    3: 55,  # G3
    4: 50,  # D3
    5: 45,  # A2
    6: 40,  # E2
}


def _tie_state(tie: dict[str, Any]) -> str | None:
    if tie.get("start") and tie.get("stop"):
        return "continue"
    if tie.get("start"):
        return "start"
    if tie.get("stop"):
        return "stop"
    return None


def build_note_type_event(
    record: dict[str, Any],
    *,
    positions: Sequence[tuple[int, int]],
    candidates: Sequence[TabCandidate],
    output_bar_idx: int,
    event_idx: int,
    onset_ticks: int,
    track_id: str,
) -> Event:
    """One Event whose duration is its note-type record's, and whose (string, fret) positions come from the TAB.

    ``positions`` are the matched TAB column's digits or, for a tie continuation printed without
    its own digit, the positions of the note it is tied from. A rest carries none.
    """
    is_rest = record["kind"] == "rest"
    tie_state = None if is_rest else _tie_state(record.get("tie") or {})
    by_position = {(c.string, c.parsed_fret): c for c in candidates}
    notes: list[Note] = []
    for string, fret in positions:
        candidate = by_position.get((string, fret))
        notes.append(
            Note(
                string=string,
                fret=fret,
                pitch=_STRING_TO_BASE_PITCH[string] + fret,
                confidence=candidate.confidence if candidate else 1.0,
                provenance=[candidate.to_provenance()] if candidate else [],
                techniques=[TieTechnique(state=tie_state)] if tie_state else [],
            )
        )
    tuplet = record.get("tuplet")
    return Event(
        id=f"bar-{output_bar_idx}-event-{event_idx + 1}",
        track_id=track_id,
        timing=Timing(
            bar_index=output_bar_idx,
            onset_ticks=onset_ticks,
            duration_ticks=ticks_for_quarters(Fraction(record["duration_quarters"])),
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value=record["written"], dots=record["dots"]["count"]),
            tuplet=Tuplet(actual_notes=tuplet["actual"], normal_notes=tuplet["normal"]) if tuplet else None,
        ),
        is_rest=is_rest,
        notes=notes,
        confidence=sum(c.confidence for c in candidates) / len(candidates) if candidates else 1.0,
        provenance=[c.to_provenance() for c in candidates],
    )
