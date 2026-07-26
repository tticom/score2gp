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


def is_within_pdf_tab_measure_capacity(
    current_onset_ticks: int,
    ev_duration_ticks: int,
    measure_capacity_ticks: int = MEASURE_CAPACITY_TICKS,
) -> bool:
    """Return True if adding an event of duration `ev_duration_ticks` fits within `measure_capacity_ticks`."""
    return (current_onset_ticks + ev_duration_ticks) <= measure_capacity_ticks


def decompose_pdf_tab_measure_remainder_to_rests(
    remainder_ticks: int,
) -> list[RestDurationDescriptor]:
    """Greedily decompose a non-negative measure tick remainder into standard un-dotted rest descriptors.

    The descriptors are ordered by onset appearance and sum strictly to remainder_ticks.

    Raises:
        ValueError if remainder_ticks is negative or cannot be evenly decomposed (e.g. residual != 0).
    """
    if remainder_ticks < 0:
        raise ValueError(f"Remainder ticks must be non-negative, got {remainder_ticks}")

    descriptors: list[RestDurationDescriptor] = []
    rem = remainder_ticks
    for rest_name, rest_ticks in REST_DURATION_HIERARCHY:
        while rem >= rest_ticks:
            descriptors.append(RestDurationDescriptor(name=rest_name, ticks=rest_ticks))
            rem -= rest_ticks

    if rem != 0:
        raise ValueError(
            f"Remainder ticks ({remainder_ticks}) cannot be decomposed into standard rest durations; "
            f"residual of {rem} ticks remains."
        )

    return descriptors
