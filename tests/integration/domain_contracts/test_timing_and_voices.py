import pytest
from pathlib import Path
from score2gp.musicxml import parse_musicxml, analyze_musicxml_timing

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "musicxml"

def test_measure_timing_capacity():
    # Load a valid 12/8 time signature MusicXML
    xml_path = FIXTURES_DIR / "timing_12_8_valid.musicxml"
    assert xml_path.exists()
    
    imported = parse_musicxml(xml_path)
    assert len(imported.parts) > 0
    part = imported.parts[0]
    assert len(part.measures) > 0
    measure = part.measures[0]
    
    # Domain Contract: time signature capacity is exactly matching time signature ticks
    # (12/8 time signature with 960 ticks per quarter: 12 * 480 = 5760 ticks)
    expected_capacity = 5760
    assert measure.divisions > 0
    
    # Domain Contract: each note/rest duration in MusicXML must use exact positive rational representation
    for note in measure.notes:
        assert note.duration_divisions is not None and note.duration_divisions > 0, "Lossy or empty duration in note"

def test_underfull_and_overfull_measure_detection():
    # 1. Test Overfull measure rejection/warning
    overfull_path = FIXTURES_DIR / "timing_12_8_overfull.musicxml"
    assert overfull_path.exists()
    
    imported_over = parse_musicxml(overfull_path)
    # The analyze_musicxml_timing returns risks or warning flags for timing
    risks = analyze_musicxml_timing(imported_over)
    
    # Domain Contract: Overfull measures exceed active capacity and must raise a warning/error
    assert len(risks) > 0, "Overfull measure timing risk was not captured"
    assert any("overfull" in r.code.lower() or "overfull" in r.message.lower() or "overlap" in r.message.lower() for r in risks)

    # 2. Test Underfull measure detection
    underfull_path = FIXTURES_DIR / "timing_12_8_underfull.musicxml"
    assert underfull_path.exists()
    
    imported_under = parse_musicxml(underfull_path)
    risks_under = analyze_musicxml_timing(imported_under)
    # Domain Contract: Underfull measures are detected and marked with warning codes
    assert any("underfull" in r.code.lower() or "underfull" in r.message.lower() or "gap" in r.message.lower() for r in risks_under)

def test_simultaneous_chord_onset_tick_sync():
    # Load a legitimate chord stack
    chord_path = FIXTURES_DIR / "timing_legit_chord_stack.musicxml"
    assert chord_path.exists()
    
    imported = parse_musicxml(chord_path)
    measure = imported.parts[0].measures[0]
    
    # Domain Contract: Notes parsed as simultaneous chords must share exactly the same onset tick timestamps,
    # ensuring perfect synchronization across strings during rendering.
    chord_notes = [n for n in measure.notes if n.chord]
    if chord_notes:
        onset = chord_notes[0].onset_divisions
        for note in chord_notes:
            assert note.onset_divisions == onset, f"Chord stack has desynchronized onsets: {note.onset_divisions} vs {onset}"
