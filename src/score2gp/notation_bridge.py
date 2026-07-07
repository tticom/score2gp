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
    valid_outcomes = []
    
    for outcome in outcomes:
        sym_type = outcome.get("symbol_type")
        if sym_type not in [
            "whole_note_candidate", "half_note_candidate", "quarter_note_candidate",
            "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate",
            "sixty_fourth_note_candidate", "quarter_rest_candidate"
        ]:
            continue
        if outcome.get("association_status") != "success":
            continue
        duration = outcome.get("duration")
        if duration not in valid_durations:
            continue
            
        if sym_type == "quarter_rest_candidate":
            if duration != "quarter":
                continue
            bbox = outcome.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                continue
            try:
                float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue
        else:
            expected_sym_type = f"{duration}_note_candidate"
            if sym_type != expected_sym_type:
                continue
            
            pitch_str = outcome.get("clef_resolved_staff_pitch")
            if not pitch_str:
                continue
            
        valid_outcomes.append(outcome)

    if len(valid_outcomes) == 0:
        raise NotationBridgeInputError("no_valid_notation_outcomes_found")

    candidate_lookup = {o.get("candidate_id"): o for o in outcomes if o.get("candidate_id")}

    def get_actual_x_pos(out: dict[str, Any]) -> float:
        q_id = out.get("quarter_component_id")
        if q_id:
            q_cand = candidate_lookup.get(q_id)
            if q_cand:
                q_bbox = q_cand.get("bbox")
                if q_bbox and len(q_bbox) >= 4:
                    return float(q_bbox[0])
        bbox = out.get("bbox")
        if bbox and len(bbox) >= 4:
            return float(bbox[0])
        return 0.0

    def has_position_evidence(out: dict[str, Any]) -> bool:
        if out.get("page_index") is None:
            return False
        if out.get("system_index") is None:
            return False
        if out.get("staff_index") is None and out.get("system_staff_index") is None:
            return False
        q_id = out.get("quarter_component_id")
        if q_id:
            q_cand = candidate_lookup.get(q_id)
            if q_cand:
                q_bbox = q_cand.get("bbox")
                if q_bbox and len(q_bbox) >= 4:
                    return True
        bbox = out.get("bbox")
        if bbox and len(bbox) >= 4:
            return True
        return False

    def sort_key(out: dict[str, Any]) -> tuple:
        page = out.get("page_index", 0)
        sys = out.get("system_index", 0)
        staff = out.get("staff_index", out.get("system_staff_index", 0))
        x_pos = get_actual_x_pos(out)
        candidate_id = out.get("candidate_id", "")
        return (page, sys, staff, x_pos, candidate_id)

    valid_outcomes.sort(key=sort_key)

    grouped_outcomes = []
    for outcome in valid_outcomes:
        is_rest = outcome.get("symbol_type") == "quarter_rest_candidate"
        page = outcome.get("page_index")
        sys = outcome.get("system_index")
        staff = outcome.get("staff_index", outcome.get("system_staff_index"))
        x_pos = get_actual_x_pos(outcome)
        
        if is_rest or not has_position_evidence(outcome):
            grouped_outcomes.append([outcome])
        else:
            if grouped_outcomes:
                last_group = grouped_outcomes[-1]
                first_in_last = last_group[0]
                last_is_rest = first_in_last.get("symbol_type") == "quarter_rest_candidate"
                
                if not last_is_rest and has_position_evidence(first_in_last):
                    last_page = first_in_last.get("page_index")
                    last_sys = first_in_last.get("system_index")
                    last_staff = first_in_last.get("staff_index", first_in_last.get("system_staff_index"))
                    last_x_pos = get_actual_x_pos(first_in_last)
                    
                    if (page == last_page and 
                        sys == last_sys and 
                        staff == last_staff and 
                        abs(x_pos - last_x_pos) <= 1.0):
                        last_group.append(outcome)
                        continue
            grouped_outcomes.append([outcome])

    unique_staves = set()
    for group in grouped_outcomes:
        first_outcome = group[0]
        staff = first_outcome.get("staff_index", first_outcome.get("system_staff_index"))
        if staff is not None:
            unique_staves.add(staff)

    sorted_unique_staves = sorted(list(unique_staves))
    if not sorted_unique_staves:
        sorted_unique_staves = [0]

    staff_to_track_idx = {staff: idx for idx, staff in enumerate(sorted_unique_staves)}

    def get_track_id(staff_val: int | None) -> str:
        if staff_val is None:
            return "trk_0"
        idx = staff_to_track_idx.get(staff_val, 0)
        return f"trk_{idx}"

    events = []
    current_onset_ticks = {}
    max_ticks_in_4_4_bar = 4 * DEFAULT_TICKS_PER_QUARTER

    for i, group in enumerate(grouped_outcomes):
        first_outcome = group[0]
        is_rest = first_outcome.get("symbol_type") == "quarter_rest_candidate"
        
        if is_rest:
            note_list = []
        else:
            note_list = []
            for outcome in group:
                pitch_str = outcome.get("clef_resolved_staff_pitch")
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
                    
                note_list.append(Note(
                    string=best_string,
                    fret=best_fret,
                    pitch=sounding_midi,
                    confidence=1.0,
                ))
            if not note_list:
                continue
        
        duration = first_outcome.get("duration")
        if duration == "whole":
            dur_ticks = 4 * DEFAULT_TICKS_PER_QUARTER
            note_val = "whole"
        elif duration == "half":
            dur_ticks = 2 * DEFAULT_TICKS_PER_QUARTER
            note_val = "half"
        elif duration == "quarter":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER
            note_val = "quarter"
        elif duration == "eighth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 2
            note_val = "eighth"
        elif duration == "sixteenth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 4
            note_val = "16th"
        elif duration == "thirty_second":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 8
            note_val = "32nd"
        elif duration == "sixty_fourth":
            dur_ticks = DEFAULT_TICKS_PER_QUARTER // 16
            note_val = "64th"
        else:
            raise NotationBridgeInputError(f"unsupported_duration_value_{duration}")

        staff = first_outcome.get("staff_index", first_outcome.get("system_staff_index"))
        track_id = get_track_id(staff)

        onset_ticks = current_onset_ticks.get(track_id, 0)

        if onset_ticks + dur_ticks > max_ticks_in_4_4_bar:
            raise NotationBridgeInputError("cumulative_duration_exceeds_one_4_4_bar")

        events.append(Event(
            id=f"evt_{i}",
            track_id=track_id,
            timing=Timing(
                bar_index=1,
                onset_ticks=onset_ticks,
                duration_ticks=dur_ticks,
                ticks_per_quarter=DEFAULT_TICKS_PER_QUARTER,
                notated_duration=NotatedDuration(value=note_val)
            ),
            notes=note_list,
            is_rest=is_rest
        ))
        
        current_onset_ticks[track_id] = onset_ticks + dur_ticks

    if not events:
        raise NotationBridgeInputError("no_playable_notation_outcomes_found")

    tracks = []
    for idx, s in enumerate(sorted_unique_staves):
        tracks.append(Track(
            id=f"trk_{idx}",
            name="Guitar" if idx == 0 else f"Guitar {idx + 1}",
            tuning=tuning,
        ))

    return ScoreIR(
        tempo=Tempo(bpm=120),
        tracks=tracks,
        bars=[
            Bar(
                index=1,
                time_signature=TimeSignature(numerator=4, denominator=4),
                events=events
            )
        ]
    )

