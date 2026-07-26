from __future__ import annotations

from dataclasses import dataclass

MEASURE_CAPACITY_TICKS = 3840

REST_DURATION_HIERARCHY: tuple[tuple[str, int], ...] = (
    ("whole", 3840),
    ("half", 1920),
    ("quarter", 960),
    ("eighth", 480),
    ("16th", 240),
    ("32nd", 120),
    ("64th", 60),
)


@dataclass(frozen=True)
class RestDurationDescriptor:
    name: str
    ticks: int


def select_pdf_tab_grid_spacing_and_duration_name(
    event_subgroup_count: int,
    *,
    editable_draft: bool = False,
) -> tuple[int, str]:
    """Select grid tick spacing and nominal notated duration name for PDF-only TabRaw measures.

    Returns:
        tuple[grid_spacing_ticks, duration_name]
    """
    if editable_draft:
        return 960, "quarter"

    N = event_subgroup_count
    if N <= 8:
        return 480, "eighth"
    elif N <= 16:
        return 240, "16th"
    elif N <= 32:
        return 120, "32nd"
    else:
        return 60, "64th"


def validate_pdf_tab_measure_capacity(
    current_onset_ticks: int,
    ev_duration_ticks: int,
    output_bar_idx: int,
    measure_capacity_ticks: int = MEASURE_CAPACITY_TICKS,
) -> None:
    """Validate that adding an event of duration `ev_duration_ticks` does not exceed measure capacity.

    Raises:
        BuildIrInputRiskError(category="pdf_only_tab_measure_overcapacity") if over-capacity.
    """
    accumulated_ticks = current_onset_ticks + ev_duration_ticks
    if accumulated_ticks > measure_capacity_ticks:
        from score2gp.build_ir import BuildIrInputRiskError

        raise BuildIrInputRiskError(
            category="pdf_only_tab_measure_overcapacity",
            stage="measure-assembly",
            message=(
                f"Candidate note events in bar {output_bar_idx} exceed measure capacity {measure_capacity_ticks} ticks "
                f"(accumulated {accumulated_ticks} ticks)."
            ),
            details={
                "bar_index": str(output_bar_idx),
                "accumulated_ticks": str(accumulated_ticks),
                "measure_capacity": str(measure_capacity_ticks),
            },
        )


def decompose_pdf_tab_measure_remainder_to_rests(
    remainder_ticks: int,
) -> list[RestDurationDescriptor]:
    """Greedily decompose a non-negative measure tick remainder into standard un-dotted rest descriptors.

    The descriptors are ordered by onset appearance and sum strictly to remainder_ticks.
    """
    if remainder_ticks < 0:
        raise ValueError(f"Remainder ticks must be non-negative, got {remainder_ticks}")

    descriptors: list[RestDurationDescriptor] = []
    rem = remainder_ticks
    for rest_name, rest_ticks in REST_DURATION_HIERARCHY:
        while rem >= rest_ticks:
            descriptors.append(RestDurationDescriptor(name=rest_name, ticks=rest_ticks))
            rem -= rest_ticks

    return descriptors
