from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Any, Sequence

from .ir import (
    DEFAULT_TICKS_PER_QUARTER,
    Event,
    GraceTiming,
    NotatedDuration,
    Note,
    NoteSpelling,
    Provenance,
    SourceStage,
    TieTechnique,
    Timing,
    Tuplet,
)
from .pdf_tab_measure_timing import ticks_for_quarters

if TYPE_CHECKING:
    from .tabraw import TabCandidate


# Guitar Pro writes a grace note as a 32nd beat tagged ``GraceNotes OnBeat``; the printed value read from the
# notation is evidence only, and a grace takes no time of its own.
GRACE_WRITTEN_VALUE = "32nd"

# A rest the page does not print (TABRHY-01 implied trailing rest) has no printed evidence at all: its duration
# is the remainder of the meter, not a reading. It is carried at zero confidence, never at the 1.0 of a read symbol.
IMPLIED_REST_CONFIDENCE = 0.0

BLACK_KEYS = frozenset({1, 3, 6, 8, 10})

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


def unjoined_accidentals(record: dict[str, Any], positions: Sequence[tuple[int, int]]) -> list[dict[str, Any]]:
    """Printed accidentals of a notation event whose pitch class no TAB note of the event has."""
    pitch_classes = {(_STRING_TO_BASE_PITCH[string] + fret) % 12 for string, fret in positions
                     if fret is not None}
    return [a for a in record.get("accidentals") or () if a["pitch_class"] not in pitch_classes]


def build_note_type_event(
    record: dict[str, Any],
    *,
    positions: Sequence[tuple[int, int]],
    candidates: Sequence[TabCandidate],
    output_bar_idx: int,
    event_idx: int,
    onset_ticks: int,
    track_id: str,
    inherited: Sequence[TabCandidate] = (),
) -> Event:
    """One Event whose duration is its note-type record's, and whose (string, fret) positions come from the TAB.

    ``positions`` are the matched TAB column's digits or, for a tie continuation printed without
    its own digit, the positions of the note it is tied from (``inherited`` are that note's TAB digits,
    recorded as the evidence of the copied positions). A rest carries none: a printed rest cites its
    notation glyph, and an implied rest (the page prints none) is labelled and carried at zero confidence.
    """
    is_rest = record["kind"] == "rest"
    tie_state = None if is_rest else _tie_state(record.get("tie") or {})
    by_position = {(c.string, c.parsed_fret): c for c in candidates}
    printed = {a["pitch_class"]: a["direction"] for a in record.get("accidentals") or ()}
    strike_heads = sorted((h for h in (record.get("notehead") or {}).get("heads", [])
                           if h["kind"] == "cross"), key=lambda h: h["staff_position_index"]) if not is_rest else []
    strike_candidates = sorted((c for c in candidates if c.kind == "percussive-strike"),
                               key=lambda c: c.string)
    head_by_candidate = {c.id: h for c, h in zip(strike_candidates, strike_heads)}
    inherited_by_position = {(c.string, c.parsed_fret): c for c in inherited}
    notes: list[Note] = []
    for string, fret in positions:
        candidate = by_position.get((string, fret))
        source = inherited_by_position.get((string, fret)) if candidate is None else None
        is_strike = candidate is not None and candidate.kind == "percussive-strike"
        pitch = None if is_strike else _STRING_TO_BASE_PITCH[string] + fret
        provenance = [candidate.to_provenance()] if candidate else []
        if source is not None:
            provenance = [source.to_provenance()]
            provenance[0].raw = {"derived_from": "tie_continuation"}
        if is_strike:
            head = head_by_candidate[candidate.id]
            provenance[0].raw = {"notation_head_source": head["source"],
                                 "staff_position_index": head["staff_position_index"]}
            if "printed_head_midi" in head:
                provenance[0].raw["printed_head_midi"] = head["printed_head_midi"]
                provenance[0].raw["printed_position_basis"] = head["printed_position_basis"]
        notes.append(
            Note(
                string=string,
                fret=fret,
                pitch=pitch,
                is_dead=is_strike,
                confidence=candidate.confidence if candidate else (source.confidence if source else 1.0),
                provenance=provenance,
                techniques=[TieTechnique(state=tie_state)] if tie_state else [],
                spelling=(NoteSpelling(accidental=printed[pitch % 12], source="printed")
                          if pitch is not None and pitch % 12 in printed and pitch % 12 in BLACK_KEYS else None),
            )
        )
    tuplet = record.get("tuplet")
    if record.get("grace"):
        timing = Timing(
            bar_index=output_bar_idx,
            onset_ticks=onset_ticks,
            duration_ticks=0,
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value=GRACE_WRITTEN_VALUE, dots=0),
            grace=GraceTiming(position="on-beat", duration=GRACE_WRITTEN_VALUE),
            tuplet=Tuplet(actual_notes=tuplet["actual"], normal_notes=tuplet["normal"]) if tuplet else None,
        )
    else:
        timing = Timing(
            bar_index=output_bar_idx,
            onset_ticks=onset_ticks,
            duration_ticks=ticks_for_quarters(Fraction(record["duration_quarters"])),
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value=record["written"], dots=record["dots"]["count"]),
            tuplet=Tuplet(actual_notes=tuplet["actual"], normal_notes=tuplet["normal"]) if tuplet else None,
        )
    event_provenance = [c.to_provenance() for c in candidates]
    event_confidence = sum(c.confidence for c in candidates) / len(candidates) if candidates else 1.0
    if not candidates and inherited:
        event_provenance = [c.to_provenance() for c in inherited]
        for item in event_provenance:
            item.raw = {"derived_from": "tie_continuation"}
        event_confidence = sum(c.confidence for c in inherited) / len(inherited)
    if is_rest:
        implied = bool((record.get("rest") or {}).get("implied"))
        location = record.get("location") or {}
        bbox = location.get("bbox")
        evidence = Provenance(
            source_stage=SourceStage.INFERRED if implied else SourceStage.UNKNOWN,
            page=record["page_index"] + 1,
            bar_index=output_bar_idx,
            raw_token_id=None if implied else (record.get("rest") or {}).get("source"),
            raw=({"basis": "implied_rest", "reason": "bar total below the time signature; no rest is printed",
                  "quarters": record["duration_quarters"]}
                 if implied else {"origin": "notation_rest_glyph", "glyph": (record.get("rest") or {}).get("glyph")}),
            confidence=IMPLIED_REST_CONFIDENCE if implied else 1.0,
        )
        event_provenance = [evidence]
        event_confidence = evidence.confidence
    return Event(
        id=f"bar-{output_bar_idx}-event-{event_idx + 1}",
        track_id=track_id,
        timing=timing,
        is_rest=is_rest,
        notes=notes,
        confidence=event_confidence,
        provenance=event_provenance,
    )
