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


KEY_SIGNATURE_ALTERATIONS = {
    # Sharp keys
    "C Major": {}, "A Minor": {},
    "G Major": {"F": 1}, "E Minor": {"F": 1},
    "D Major": {"F": 1, "C": 1}, "B Minor": {"F": 1, "C": 1},
    "A Major": {"F": 1, "C": 1, "G": 1}, "F# Minor": {"F": 1, "C": 1, "G": 1},
    "E Major": {"F": 1, "C": 1, "G": 1, "D": 1}, "C# Minor": {"F": 1, "C": 1, "G": 1, "D": 1},
    "B Major": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1}, "G# Minor": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1},
    "F# Major": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1, "E": 1}, "D# Minor": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1, "E": 1},
    "C# Major": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1, "E": 1, "B": 1}, "A# Minor": {"F": 1, "C": 1, "G": 1, "D": 1, "A": 1, "E": 1, "B": 1},
    # Flat keys
    "F Major": {"B": -1}, "D Minor": {"B": -1},
    "Bb Major": {"B": -1, "E": -1}, "G Minor": {"B": -1, "E": -1},
    "Eb Major": {"B": -1, "E": -1, "A": -1}, "C Minor": {"B": -1, "E": -1, "A": -1},
    "Ab Major": {"B": -1, "E": -1, "A": -1, "D": -1}, "F Minor": {"B": -1, "E": -1, "A": -1, "D": -1},
    "Db Major": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1}, "Bb Minor": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1},
    "Gb Major": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1, "C": -1}, "Eb Minor": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1, "C": -1},
    "Cb Major": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1, "C": -1, "F": -1}, "Ab Minor": {"B": -1, "E": -1, "A": -1, "D": -1, "G": -1, "C": -1, "F": -1},
}

LOCAL_ACCIDENTAL_MODIFIERS = {
    "flat": -1,
    "b": -1,
    "natural": 0,
    "n": 0,
    "♮": 0,
    "sharp": 1,
    "#": 1,
    "double_flat": -2,
    "bb": -2,
    "double_sharp": 2,
    "##": 2,
    "x": 2
}

def get_spelled_note_name(natural_midi: int, modifier: int) -> str:
    natural_name = midi_to_note_name(natural_midi)
    letter = natural_name[0]
    octave = natural_name[1:]

    if modifier == 1:
        acc = "#"
    elif modifier == -1:
        acc = "b"
    elif modifier == 2:
        acc = "##"
    elif modifier == -2:
        acc = "bb"
    else:
        acc = ""

    return f"{letter}{acc}{octave}"
