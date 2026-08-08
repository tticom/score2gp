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


_REST_CANDIDATE_MAP: dict[str, tuple[int, str]] = {
    "whole_rest": (3840, "whole"),
    "whole_rest_candidate": (3840, "whole"),
    "whole": (3840, "whole"),
    "half_rest": (1920, "half"),
    "half_rest_candidate": (1920, "half"),
    "half": (1920, "half"),
    "quarter_rest": (960, "quarter"),
    "quarter_rest_candidate": (960, "quarter"),
    "quarter": (960, "quarter"),
    "eighth_rest": (480, "eighth"),
    "eighth_rest_candidate": (480, "eighth"),
    "eighth": (480, "eighth"),
    "sixteenth_rest": (240, "16th"),
    "sixteenth_rest_candidate": (240, "16th"),
    "16th_rest": (240, "16th"),
    "16th_rest_candidate": (240, "16th"),
    "16th": (240, "16th"),
    "sixteenth": (240, "16th"),
    "thirty_second_rest": (120, "32nd"),
    "thirty_second_rest_candidate": (120, "32nd"),
    "32nd_rest": (120, "32nd"),
    "32nd": (120, "32nd"),
    "thirty_second": (120, "32nd"),
    "sixty_fourth_rest": (60, "64th"),
    "sixty_fourth_rest_candidate": (60, "64th"),
    "64th_rest": (60, "64th"),
    "64th": (60, "64th"),
    "sixty_fourth": (60, "64th"),
}


def determine_pdf_tab_event_duration(
    subgroup_candidates: Sequence[TabCandidate],
    grid_spacing: int,
    duration_name: str,
) -> tuple[bool, int, str]:
    """Determine if a subgroup candidate list is a rest, and return (is_rest, ev_duration_ticks, ev_duration_name)."""
    for c in subgroup_candidates:
        r_text = (c.raw_text or "").lower()
        r_kind = (c.kind or "").lower()
        if r_text in _REST_CANDIDATE_MAP:
            ticks, name = _REST_CANDIDATE_MAP[r_text]
            return True, ticks, name
        if r_kind in _REST_CANDIDATE_MAP and r_kind not in ("fret", "chord-symbol", "technique-text"):
            ticks, name = _REST_CANDIDATE_MAP[r_kind]
            return True, ticks, name

    explicit_evidences: list[TabDurationEvidence] = []
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
                explicit_evidences.append(ev)

    if explicit_evidences:
        first_ticks = explicit_evidences[0].duration_ticks
        first_name = explicit_evidences[0].duration_name
        for ev in explicit_evidences[1:]:
            if ev.duration_ticks != first_ticks or ev.duration_name != first_name:
                raise PdfTabBarAssemblerError(
                    category="pdf_only_tab_ambiguous_duration",
                    stage="measure-assembly",
                    message=(
                        f"Conflicting duration evidence across candidates in chord subgroup: "
                        f"found {first_name} ({first_ticks} ticks) and {ev.duration_name} ({ev.duration_ticks} ticks)"
                    ),
                )
        return False, first_ticks, first_name

    return False, grid_spacing, duration_name




_BASE_DURATION_TICKS: dict[str, int] = {
    "whole": 3840,
    "half": 1920,
    "quarter": 960,
    "eighth": 480,
    "16th": 240,
    "32nd": 120,
    "64th": 60,
}


def _infer_dots_from_duration(ticks: int, name: str) -> int:
    base = _BASE_DURATION_TICKS.get(name, 0)
    if base > 0 and ticks == int(base * 1.5):
        return 1
    if base > 0 and ticks == int(base * 1.75):
        return 2
    return 0


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

    ev_dots = _infer_dots_from_duration(ev_duration_ticks, ev_duration_name)
    for c in subgroup_candidates:
        if c.duration_evidence and getattr(c.duration_evidence, "dots", 0) > 0:
            ev_dots = max(ev_dots, getattr(c.duration_evidence, "dots", 0))

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
            notated_duration=NotatedDuration(value=ev_duration_name, dots=ev_dots),
        ),
        is_rest=is_rest,
        notes=notes,
        text=event_text,
        confidence=confidence,
        provenance=[c.to_provenance() for c in subgroup_candidates],
    )
