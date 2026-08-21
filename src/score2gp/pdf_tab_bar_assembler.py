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
    floating_barlines: list | None = None,
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

    if floating_barlines:
        measures = split_tab_candidates_by_floating_barlines(subgroup_candidates, floating_barlines)
    else:
        measures = [subgroup_candidates]

    events: list[Event] = []
    global_onset = 0
    event_idx_counter = 0
    rest_idx_counter = 1
    grouper = PdfOnlyChordEventGrouper(tolerance=chord_x_tolerance_pt)

    for measure_cands in measures:

        event_subgroups = grouper.group_bar_candidates(measure_cands)
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
                event_idx=event_idx_counter,
                onset_ticks=global_onset + current_onset,
                grid_spacing=grid_spacing,
                duration_name=duration_name,
                track_id=track_id,
                editable_draft=editable_draft,
                tempo_bpm=tempo_bpm,
                tempo_is_explicit=tempo_is_explicit,
            )
            events.append(event)
            current_onset += ev_duration_ticks
            event_idx_counter += 1

        remainder = 3840 - current_onset
        if remainder > 0:
            rest_descriptors = decompose_pdf_tab_measure_remainder_to_rests(remainder)
            for seq_idx, desc in enumerate(rest_descriptors, start=1):
                events.append(
                    Event(
                        id=f"bar-{output_bar_idx}-rest-{rest_idx_counter}",
                        track_id=track_id,
                        timing=Timing(
                            bar_index=output_bar_idx,
                            onset_ticks=global_onset + current_onset,
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
                rest_idx_counter += 1

        global_onset += 3840

    total_numerator = 4 * len(measures)
    if total_numerator == 0:
        total_numerator = 4
    return Bar(
        index=output_bar_idx,
        time_signature=TimeSignature(numerator=total_numerator, denominator=4),
        events=events,
    )

def split_tab_candidates_by_floating_barlines(candidates: list[TabCandidate], barlines: list) -> list[list[TabCandidate]]:
    """Split a list of TabCandidates into measures based on floating barline X-coordinates."""
    if not candidates:
        return [candidates]

    sorted_candidates = sorted(candidates, key=lambda c: c.x)
    min_x = sorted_candidates[0].x
    max_x = sorted_candidates[-1].x

    # Get the system/page context from the first candidate
    page_index = candidates[0].page_index
    system_index = candidates[0].system_index

    # Filter barlines to only those belonging to this system AND within the candidate bounds
    relevant_barlines = [
        b.x for b in barlines
        if getattr(b, "page_index", None) == page_index
        and getattr(b, "system_index", None) == system_index
        and min_x < b.x < max_x
    ]

    if not relevant_barlines:
        return [sorted_candidates]

    relevant_barlines.sort()

    measures: list[list[TabCandidate]] = [[] for _ in range(len(relevant_barlines) + 1)]

    barline_idx = 0
    num_barlines = len(relevant_barlines)

    for cand in sorted_candidates:
        while barline_idx < num_barlines and cand.x > relevant_barlines[barline_idx]:
            barline_idx += 1
        measures[barline_idx].append(cand)

    return measures