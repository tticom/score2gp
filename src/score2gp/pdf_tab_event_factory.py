from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from .ir import (
    DEFAULT_TICKS_PER_QUARTER,
    Event,
    NotatedDuration,
    Note,
    Timing,
)
from .pdf_tab_measure_timing import PdfTabBarAssemblerError

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


def build_pdf_tab_editable_draft_annotation_text(
    tempo_bpm: float = 120.0,
    *,
    tempo_is_explicit: bool = False,
) -> str:
    """Build standard first-event annotation text for editable draft mode."""
    tempo_fmt = int(tempo_bpm) if tempo_bpm == int(tempo_bpm) else tempo_bpm
    if tempo_is_explicit:
        tempo_phrase = f"Tempo set to {tempo_fmt} bpm."
    else:
        tempo_phrase = f"Tempo defaulted to {tempo_fmt} bpm."
    return (
        "Editable draft generated from PDF tablature. "
        "Rhythms defaulted to quarter notes; timing was not recognised. "
        "Tuning defaulted to E Standard unless corrected by the user. "
        "Time signature defaulted to 4/4. "
        f"{tempo_phrase} "
        "Standard notation and notation/tab alignment were skipped. "
        "Rests/silence may be omitted."
    )


def determine_pdf_tab_event_duration(
    subgroup_candidates: Sequence[TabCandidate],
    grid_spacing: int,
    duration_name: str,
) -> tuple[bool, int, str]:
    """Determine if a subgroup candidate list is a rest, and return (is_rest, ev_duration_ticks, ev_duration_name)."""
    is_rest = any(c.raw_text == "quarter_rest" for c in subgroup_candidates)
    if is_rest:
        return True, 960, "quarter"

    for c in subgroup_candidates:
        ev = c.duration_evidence
        if ev is not None:
            if ev.is_ambiguous or ev.source == "ambiguous_conflict" or ev.duration_ticks == 0:
                raise PdfTabBarAssemblerError(
                    category="pdf_only_tab_ambiguous_duration",
                    stage="measure-assembly",
                    message=(
                        f"Ambiguous duration evidence on event candidate: "
                        f"{ev.diagnostic_message or 'conflicting or ambiguous duration geometry'}"
                    ),
                )
            if ev.source == "visual_morphology" or (
                not ev.is_fallback_placeholder and not ev.is_ambiguous and ev.duration_ticks > 0
            ):
                return False, ev.duration_ticks, ev.duration_name

    return False, grid_spacing, duration_name



def build_pdf_tab_event_from_subgroup(
    subgroup_candidates: Sequence[TabCandidate],
    *,
    output_bar_idx: int,
    event_idx: int,
    onset_ticks: int,
    grid_spacing: int,
    duration_name: str,
    track_id: str,
    editable_draft: bool = False,
    tempo_bpm: float = 120.0,
    tempo_is_explicit: bool = False,
) -> Event:
    """Construct one Event (note or explicit rest) from a grouped list of TabCandidate objects."""
    is_rest, ev_duration_ticks, ev_duration_name = determine_pdf_tab_event_duration(
        subgroup_candidates, grid_spacing, duration_name
    )

    notes: list[Note] = []
    if not is_rest:
        for candidate in subgroup_candidates:
            base_pitch = _STRING_TO_BASE_PITCH.get(candidate.string, 40)
            pitch = base_pitch + (candidate.parsed_fret or 0)
            notes.append(
                Note(
                    string=candidate.string,
                    fret=candidate.parsed_fret or 0,
                    pitch=pitch,
                    confidence=candidate.confidence,
                    provenance=[candidate.to_provenance()],
                )
            )

    event_text: str | None = None
    if editable_draft and output_bar_idx == 1 and event_idx == 0:
        event_text = build_pdf_tab_editable_draft_annotation_text(
            tempo_bpm=tempo_bpm, tempo_is_explicit=tempo_is_explicit
        )

    confidence = (
        sum(c.confidence for c in subgroup_candidates) / len(subgroup_candidates)
        if subgroup_candidates
        else 1.0
    )

    return Event(
        id=f"bar-{output_bar_idx}-event-{event_idx+1}",
        track_id=track_id,
        timing=Timing(
            bar_index=output_bar_idx,
            onset_ticks=onset_ticks,
            duration_ticks=ev_duration_ticks,
            ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
            notated_duration=NotatedDuration(value=ev_duration_name, dots=0),
        ),
        is_rest=is_rest,
        notes=notes,
        text=event_text,
        confidence=confidence,
        provenance=[c.to_provenance() for c in subgroup_candidates],
    )
