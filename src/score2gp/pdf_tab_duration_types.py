from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DurationName = Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th"]

DURATION_TICKS_MAP: dict[DurationName, int] = {
    "whole": 3840,
    "half": 1920,
    "quarter": 960,
    "eighth": 480,
    "16th": 240,
    "32nd": 120,
    "64th": 60,
}


@dataclass(frozen=True)
class TabDurationEvidence:
    duration_name: DurationName
    duration_ticks: int
    stem_present: bool = False
    beam_count: int = 0
    flag_count: int = 0
    confidence: float = 1.0
    source: Literal["visual_morphology", "equal_spacing_fallback"] = "visual_morphology"
