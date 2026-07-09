def map_staff_step_to_midi_pitch(
    staff_step_index: int,
    clef_kind: str
) -> int:
    """
    Maps a staff_step_index to a MIDI pitch based on the logical clef kind.
    - staff_step_index: even values correspond to staff lines, odd to spaces.
      Index 0 is the top line of the 5-line staff.
    - clef_kind: one of "treble", "bass", or "alto".

    Raises ValueError if clef_kind is unsupported or invalid.
    """
    # 1. Determine the starting diatonic offset constant C_clef for the top line (index 0)
    # offset is the diatonic distance relative to Middle C (C4, diatonic step 0)
    if clef_kind == "treble":
        c_clef = 10  # Top line is F5
    elif clef_kind == "bass":
        c_clef = -2  # Top line is A3
    elif clef_kind == "alto":
        c_clef = 4   # Top line is G4
    else:
        raise ValueError(f"Unsupported or unknown clef kind for pitch mapping: {clef_kind}")

    # 2. Compute diatonic step d (decreasing as step index increases/goes downwards)
    d = c_clef - staff_step_index

    # 3. Translate diatonic step d to natural MIDI pitch (diatonic step 0 = MIDI 60)
    # Using integer floor division in Python for octave calculation
    octave = d // 7
    note_index = d % 7

    # MIDI offsets for C, D, E, F, G, A, B relative to C (0, 2, 4, 5, 7, 9, 11)
    note_offsets = [0, 2, 4, 5, 7, 9, 11]

    midi_pitch = 60 + 12 * octave + note_offsets[note_index]
    return midi_pitch


def midi_to_note_name(midi: int) -> str:
    """
    Translates a MIDI pitch integer to a note name string (e.g. 60 -> "C4", 77 -> "F5").
    Supports natural notes only (assumes sharps/flats are not present in baseline mapping).
    """
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi // 12) - 1
    name = note_names[midi % 12]
    return f"{name}{octave}"
