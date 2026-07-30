from __future__ import annotations

from .ir import Bar, Event, NotatedDuration, TimeSignature, Timing, DEFAULT_TICKS_PER_QUARTER
from .pdf_only_chord_event_grouper import PDF_ONLY_CHORD_X_TOLERANCE_PT, PdfOnlyChordEventGrouper
from .pdf_tab_event_factory import (
    build_pdf_tab_event_from_subgroup,
    determine_pdf_tab_event_duration,
)
from .pdf_tab_measure_timing import (
    PdfTabBarAssemblerError,
    decompose_pdf_tab_measure_remainder_to_rests,
    is_within_pdf_tab_measure_capacity,
    select_pdf_tab_grid_spacing_and_duration_name,
)
from .tabraw import TabCandidate



def assemble_pdf_tab_bar(
    subgroup_candidates: list[TabCandidate],
    *,
    output_bar_idx: int,
    track_id: str,
    editable_draft: bool = False,
    tempo_bpm: int = 120,
    tempo_is_explicit: bool = False,
    chord_x_tolerance_pt: float = PDF_ONLY_CHORD_X_TOLERANCE_PT,
) -> Bar:
    """Assemble one PDF-only Tab source bar into a normalized score2gp Bar.

    Coordinates candidate subgrouping, duration selection, event construction,
    capacity checks, trailing remainder rests, and Bar creation.
    """
    if not subgroup_candidates:
        rest_event = Event(
            id=f"bar-{output_bar_idx}-rest",
            track_id=track_id,
            timing=Timing(
                bar_index=output_bar_idx,
                onset_ticks=0,
                duration_ticks=3840,
                ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                notated_duration=NotatedDuration(value="whole", dots=0),
            ),
            is_rest=True,
            notes=[],
            confidence=1.0,
        )
        return Bar(
            index=output_bar_idx,
            time_signature=TimeSignature(numerator=4, denominator=4),
            events=[rest_event],
        )

    grouper = PdfOnlyChordEventGrouper(tolerance=chord_x_tolerance_pt)
    event_subgroups = grouper.group_bar_candidates(subgroup_candidates)

    N = len(event_subgroups)
    if N > 64:
        raise PdfTabBarAssemblerError(
            category="pdf_only_tab_grouping_unsafe",
            stage="layout-gating",
            message=f"PDF-only tab building refused: too many events ({N}) in bar {output_bar_idx}.",
        )

    grid_spacing, duration_name = select_pdf_tab_grid_spacing_and_duration_name(
        N, editable_draft=editable_draft
    )

    events: list[Event] = []
    current_onset = 0
    for i, subgroup in enumerate(event_subgroups):
        _, ev_duration_ticks, _ = determine_pdf_tab_event_duration(
            subgroup, grid_spacing, duration_name
        )

        if not is_within_pdf_tab_measure_capacity(current_onset, ev_duration_ticks):
            raise PdfTabBarAssemblerError(
                category="pdf_only_tab_measure_overcapacity",
                stage="measure-assembly",
                message=(
                    f"Candidate note events in bar {output_bar_idx} exceed measure capacity 3840 ticks "
                    f"(accumulated {current_onset + ev_duration_ticks} ticks)."
                ),
                details={
                    "bar_index": str(output_bar_idx),
                    "accumulated_ticks": str(current_onset + ev_duration_ticks),
                    "measure_capacity": "3840",
                },
            )

        event = build_pdf_tab_event_from_subgroup(
            subgroup,
            output_bar_idx=output_bar_idx,
            event_idx=i,
            onset_ticks=current_onset,
            grid_spacing=grid_spacing,
            duration_name=duration_name,
            track_id=track_id,
            editable_draft=editable_draft,
            tempo_bpm=tempo_bpm,
            tempo_is_explicit=tempo_is_explicit,
        )
        events.append(event)
        current_onset += ev_duration_ticks

    remainder = 3840 - current_onset
    if remainder > 0:
        rest_descriptors = decompose_pdf_tab_measure_remainder_to_rests(remainder)
        for seq_idx, desc in enumerate(rest_descriptors, start=1):
            events.append(
                Event(
                    id=f"bar-{output_bar_idx}-rest-{seq_idx}",
                    track_id=track_id,
                    timing=Timing(
                        bar_index=output_bar_idx,
                        onset_ticks=current_onset,
                        duration_ticks=desc.ticks,
                        ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                        notated_duration=NotatedDuration(value=desc.name, dots=0),
                    ),
                    is_rest=True,
                    notes=[],
                    text=None,
                    confidence=1.0,
                    provenance=[],
                )
            )
            current_onset += desc.ticks

    return Bar(
        index=output_bar_idx,
        time_signature=TimeSignature(numerator=4, denominator=4),
        events=events,
    )
