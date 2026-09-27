from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DurationName = Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th", "ambiguous"]

DURATION_TICKS_MAP: dict[DurationName, int] = {
    "whole": 3840,
    "half": 1920,
    "quarter": 960,
    "eighth": 480,
    "16th": 240,
    "32nd": 120,
    "64th": 60,
    "ambiguous": 0,
}


@dataclass(frozen=True)
class TabDurationEvidence:
    """Represents duration evidence extracted from visual morphology.

    An unstemmed event without visual candidates gets no evidence at all: no placeholder duration.

    For ambiguous or conflicting geometry, source is "ambiguous_conflict", is_ambiguous is True,
    duration_name is "ambiguous", and duration_ticks is 0 (failing closed without fabricating false evidence).
    """

    duration_name: DurationName
    duration_ticks: int
    stem_present: bool = False
    beam_count: int = 0
    flag_count: int = 0
    confidence: float = 1.0
    source: Literal["visual_morphology", "ambiguous_conflict"] = "visual_morphology"
    is_ambiguous: bool = False
    diagnostic_message: str = ""

    def __post_init__(self) -> None:
        if self.source not in ("visual_morphology", "ambiguous_conflict"):
            raise ValueError(f"TabDurationEvidence invariant mismatch: unknown source '{self.source}'")
        if self.duration_name not in DURATION_TICKS_MAP:
            raise ValueError(
                f"TabDurationEvidence invariant mismatch: unknown duration_name '{self.duration_name}'"
            )
        expected_ticks = DURATION_TICKS_MAP[self.duration_name]
        if self.duration_ticks != expected_ticks:
            raise ValueError(
                f"TabDurationEvidence invariant mismatch: duration_name '{self.duration_name}' "
                f"requires duration_ticks={expected_ticks}, got {self.duration_ticks}"
            )
