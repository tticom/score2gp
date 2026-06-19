import re
from typing import Any

from .ir import (
    ScoreIR,
    Track,
    Bar,
    Event,
    Note,
    Tempo,
    TimeSignature,
    Timing,
    NotatedDuration,
    DEFAULT_TICKS_PER_QUARTER,
)
from .build_ir import _standard_guitar_tuning

class NotationBridgeInputError(Exception):
    pass

def _parse_pitch_to_midi(pitch_str: str) -> int:
    """
    Parse a simple pitch string like 'B4' into a written MIDI pitch.
    """
    match = re.match(r"^([A-G])(\d)$", pitch_str.strip())
    if not match:
        raise ValueError(f"Unsupported pitch format: {pitch_str}")
    step = match.group(1)
    octave = int(match.group(2))
    
    step_to_semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return (octave + 1) * 12 + step_to_semitones[step]

def build_ir_from_notation_outcomes(outcomes: list[dict[str, Any]]) -> ScoreIR:
    notes = []
    tuning = _standard_guitar_tuning()
    
    for outcome in outcomes:
        if outcome.get("symbol_type") != "whole_note_candidate":
            continue
        if outcome.get("association_status") != "success":
            continue
        if outcome.get("duration") != "whole":
            continue
        
        pitch_str = outcome.get("clef_resolved_staff_pitch")
        if not pitch_str:
            continue
            
        written_midi = _parse_pitch_to_midi(pitch_str)
        sounding_midi = written_midi - 12
        
        # Route to lowest fret on standard guitar
        best_string = None
        best_fret = None
        
        for s in tuning.strings:
            fret = sounding_midi - s.pitch
            if fret >= 0:
                if best_fret is None or fret < best_fret:
                    best_fret = fret
                    best_string = s.number
                elif fret == best_fret:
                    # Break ties by highest string (lowest string number)
                    if best_string is None or s.number < best_string:
                        best_fret = fret
                        best_string = s.number
                        
        if best_string is None or best_fret is None or best_fret > 36:
            # Skip if unplayable
            continue
            
        notes.append(Note(
            string=best_string,
            fret=best_fret,
            pitch=sounding_midi,
            confidence=1.0,
        ))

    if len(notes) == 0:
        raise NotationBridgeInputError("no_valid_notation_outcomes_found")
    if len(notes) > 1:
        raise NotationBridgeInputError("multiple_valid_notation_outcomes_unsupported")

    events = []
    if notes:
        events.append(Event(
            id="evt_0",
            track_id="trk_0",
            timing=Timing(
                bar_index=1,
                onset_ticks=0,
                duration_ticks=4 * DEFAULT_TICKS_PER_QUARTER,
                ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                notated_duration=NotatedDuration(value="whole")
            ),
            notes=notes
        ))

    return ScoreIR(
        tempo=Tempo(bpm=120),
        tracks=[
            Track(
                id="trk_0",
                name="Guitar",
                tuning=tuning,
            )
        ],
        bars=[
            Bar(
                index=1,
                time_signature=TimeSignature(numerator=4, denominator=4),
                events=events
            )
        ]
    )

