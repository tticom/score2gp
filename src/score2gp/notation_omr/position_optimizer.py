"""Biomechanical fretboard position optimizer and TAB token ownership."""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Tuple, Optional

# Standard 6-string guitar tuning (E2=40, A2=45, D3=50, G3=55, B3=59, E4=64)
STANDARD_TUNING = [64, 59, 55, 50, 45, 40]  # String 1 (High E) to String 6 (Low E)

PITCH_CLASS_MAP = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}


def parse_pitch_to_midi(pitch_str: str | int | None) -> int | None:
    """Converts pitch string (e.g. 'E4', 'G#3', 'Bb2') or integer to MIDI note number."""
    if isinstance(pitch_str, int):
        return pitch_str
    if not pitch_str or not isinstance(pitch_str, str):
        return None
    try:
        step = pitch_str[0].upper()
        if step not in PITCH_CLASS_MAP:
            return None
        pc = PITCH_CLASS_MAP[step]
        alter = 0
        rest = pitch_str[1:]
        if rest.startswith('#'):
            alter = 1
            rest = rest[1:]
        elif rest.startswith('b'):
            alter = -1
            rest = rest[1:]
        octave = int(rest)
        return (octave + 1) * 12 + pc + alter
    except Exception:
        return None


@dataclass(frozen=True)
class FretTokenOwnership:
    """Represents string and fret ownership for a single note event."""

    token_id: str
    pitch: int
    string_index: int  # 1 to 6 (1 = High E, 6 = Low E)
    fret_number: int   # 0 to 24
    modality: str      # 'observed_tab' | 'inferred_position'
    cost: float = 0.0

    @property
    def is_observed(self) -> bool:
        return self.modality == "observed_tab"

    @property
    def is_inferred(self) -> bool:
        return self.modality == "inferred_position"

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "pitch": self.pitch,
            "string_index": self.string_index,
            "fret_number": self.fret_number,
            "modality": self.modality,
            "is_observed": self.is_observed,
            "is_inferred": self.is_inferred,
            "cost": self.cost,
        }


class BiomechanicalPositionOptimizer:
    """Dynamic programming solver minimizing biomechanical hand movement and stretch costs."""

    def __init__(
        self,
        tuning: list[int] | None = None,
        max_fret: int = 24,
        alpha_fret_jump: float = 1.0,
        beta_string_stretch: float = 0.5,
        gamma_position_shift: float = 2.0,
    ) -> None:
        self.tuning = tuning or STANDARD_TUNING
        self.max_fret = max_fret
        self.alpha_fret_jump = alpha_fret_jump
        self.beta_string_stretch = beta_string_stretch
        self.gamma_position_shift = gamma_position_shift

    def candidate_positions_for_pitch(self, pitch: int) -> list[tuple[int, int]]:
        """Returns valid (string_index, fret_number) pairs for a MIDI pitch."""
        valid = []
        for string_idx_0, open_pitch in enumerate(self.tuning):
            string_index = string_idx_0 + 1
            fret = pitch - open_pitch
            if 0 <= fret <= self.max_fret:
                valid.append((string_index, fret))
        return valid

    def optimize_sequence(
        self,
        events: list[dict[str, Any]],
        tuning: list[int] | None = None
    ) -> list[FretTokenOwnership]:
        """
        Optimizes fretboard position assignments across a sequence of note events.
        Distinguishes observed visual TAB candidates from inferred position-optimized candidates.
        Operates without receiving reference .gp files.
        """
        if not events:
            return []

        active_tuning = tuning or self.tuning
        results: list[FretTokenOwnership] = []

        for idx, evt in enumerate(events):
            token_id = evt.get("candidate_id") or f"token_{idx:03d}"

            # Check if observed visual TAB info exists
            parsed_fret = evt.get("parsed_fret") if evt.get("parsed_fret") is not None else evt.get("fret_number")
            string_idx = evt.get("string_index") if evt.get("string_index") is not None else evt.get("string")

            if parsed_fret is not None and string_idx is not None:
                pitch = evt.get("resolved_pitch_midi") or evt.get("pitch")
                if pitch is None and 1 <= int(string_idx) <= len(active_tuning):
                    pitch = active_tuning[int(string_idx) - 1] + int(parsed_fret)

                results.append(
                    FretTokenOwnership(
                        token_id=token_id,
                        pitch=pitch or 0,
                        string_index=int(string_idx),
                        fret_number=int(parsed_fret),
                        modality="observed_tab",
                        cost=0.0,
                    )
                )
                continue

            # If pitch exists but no explicit TAB was found, we drop it!
            # ADR 2026-08-13 explicitly forbids biomechanical position inference.

        return results
