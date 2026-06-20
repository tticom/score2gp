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
    tuning = _standard_guitar_tuning()
    
    valid_durations = ["whole", "half", "quarter", "eighth", "sixteenth", "thirty_second", "sixty_fourth"]
    valid_candidates = []
    
    for outcome in outcomes:
        sym_type = outcome.get("symbol_type")
        if sym_type not in [
            "whole_note_candidate", "half_note_candidate", "quarter_note_candidate",
            "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate",
            "sixty_fourth_note_candidate"
        ]:
            continue
        if outcome.get("association_status") != "success":
            continue
        duration = outcome.get("duration")
        if duration not in valid_durations:
            continue
            
        expected_sym_type = f"{duration}_note_candidate"
        if sym_type != expected_sym_type:
            continue
        
        pitch_str = outcome.get("clef_resolved_staff_pitch")
        if not pitch_str:
            continue

        bbox = outcome.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue

        page = outcome.get("page_index")
        sys_idx = outcome.get("system_index")
        staff_idx = outcome.get("staff_index")
        if page is None or sys_idx is None or staff_idx is None:
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
            
        valid_candidates.append({
            "group": (page, sys_idx, staff_idx),
            "x0": bbox[0],
            "duration": duration,
            "note": Note(
                string=best_string,
                fret=best_fret,
                pitch=sounding_midi,
                confidence=1.0,
            )
        })

    if not valid_candidates:
        raise NotationBridgeInputError("no_valid_notation_outcomes_found")

    groups = {}
    for cand in valid_candidates:
        groups.setdefault(cand["group"], []).append(cand)
        
    if len(groups) > 1:
        raise NotationBridgeInputError("multiple_staff_groups_unsupported")

    cands = list(groups.values())[0]
    cands.sort(key=lambda c: c["x0"])

    events = []
    onset_ticks = 0

    for idx, cand in enumerate(cands):
        # Reject chords / same-x notes
        if idx > 0 and abs(cand["x0"] - cands[idx-1]["x0"]) < 5.0:
            raise NotationBridgeInputError("multiple_simultaneous_notes_unsupported")

        dur = cand["duration"]
        if dur == "whole":
            dur_ticks = 4 * DEFAULT_TICKS_PER_QUARTER
            note_val = "whole"
        elif dur == "half":
            dur_ticks = 2 * DEFAULT_TICKS_PER_QUARTER
            note_val = "half"
        elif dur == "quarter":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER
            note_val = "quarter"
        elif dur == "eighth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 2
            note_val = "eighth"
        elif dur == "sixteenth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 4
            note_val = "16th"
        elif dur == "thirty_second":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 8
            note_val = "32nd"
        elif dur == "sixty_fourth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 16
            note_val = "64th"
        else:
            raise NotationBridgeInputError(f"unsupported_duration_value_{dur}")
            
        if onset_ticks + dur_ticks > 4 * DEFAULT_TICKS_PER_QUARTER:
            raise NotationBridgeInputError("multi_bar_sequences_unsupported")

        events.append(Event(
            id=f"evt_{idx}",
            track_id="trk_0",
            timing=Timing(
                bar_index=1,
                onset_ticks=onset_ticks,
                duration_ticks=dur_ticks,
                ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                notated_duration=NotatedDuration(value=note_val)
            ),
            notes=[cand["note"]]
        ))
        onset_ticks += dur_ticks

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

