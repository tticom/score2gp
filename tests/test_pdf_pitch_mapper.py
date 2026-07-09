import pytest
from score2gp.pdf_pitch_mapper import map_staff_step_to_midi_pitch

def test_treble_clef_pitch_mapping():
    # Top line of Treble staff (step 0) -> F5 (MIDI 77)
    assert map_staff_step_to_midi_pitch(0, "treble") == 77

    # Space 1 (step 3) -> C5 (MIDI 72)
    assert map_staff_step_to_midi_pitch(3, "treble") == 72

    # Bottom line (step 8) -> E4 (MIDI 64)
    assert map_staff_step_to_midi_pitch(8, "treble") == 64

    # 1st ledger line below (step 10) -> C4 (MIDI 60, Middle C)
    assert map_staff_step_to_midi_pitch(10, "treble") == 60

    # 3rd ledger line above (step -6) -> E6 (MIDI 88)
    assert map_staff_step_to_midi_pitch(-6, "treble") == 88

    # 3rd ledger line below (step 14) -> F3 (MIDI 53)
    assert map_staff_step_to_midi_pitch(14, "treble") == 53


def test_bass_clef_pitch_mapping():
    # Top line of Bass staff (step 0) -> A3 (MIDI 57)
    assert map_staff_step_to_midi_pitch(0, "bass") == 57

    # Line 2 (step 4) -> D3 (MIDI 50)
    assert map_staff_step_to_midi_pitch(4, "bass") == 50

    # Bottom line (step 8) -> G2 (MIDI 43)
    assert map_staff_step_to_midi_pitch(8, "bass") == 43

    # 1st ledger line above (step -2) -> C4 (MIDI 60, Middle C)
    assert map_staff_step_to_midi_pitch(-2, "bass") == 60

    # 3rd ledger line above (step -6) -> G4 (MIDI 67)
    assert map_staff_step_to_midi_pitch(-6, "bass") == 67

    # 3rd ledger line below (step 14) -> A1 (MIDI 33)
    assert map_staff_step_to_midi_pitch(14, "bass") == 33


def test_alto_clef_pitch_mapping():
    # Top line of Alto staff (step 0) -> G4 (MIDI 67)
    assert map_staff_step_to_midi_pitch(0, "alto") == 67

    # Middle line (step 4) -> C4 (MIDI 60, Middle C)
    assert map_staff_step_to_midi_pitch(4, "alto") == 60

    # Bottom line (step 8) -> F3 (MIDI 53)
    assert map_staff_step_to_midi_pitch(8, "alto") == 53

    # 3rd ledger line above (step -6) -> F5 (MIDI 77)
    assert map_staff_step_to_midi_pitch(-6, "alto") == 77

    # 3rd ledger line below (step 14) -> G2 (MIDI 43)
    assert map_staff_step_to_midi_pitch(14, "alto") == 43


def test_invalid_clef_raises_value_error():
    with pytest.raises(ValueError):
        map_staff_step_to_midi_pitch(0, "invalid_clef")
    with pytest.raises(ValueError):
        map_staff_step_to_midi_pitch(0, "unknown")
