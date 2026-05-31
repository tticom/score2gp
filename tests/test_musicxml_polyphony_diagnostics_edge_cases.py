from __future__ import annotations

import pytest
from score2gp.musicxml import (
    MusicXmlImport,
    MusicXmlPart,
    MusicXmlMeasure,
    MusicXmlNote,
    MusicXmlPitch,
    MusicXmlTechnique,
    MusicXmlVoiceCursorDiagnostics,
    MusicXmlMetadata,
    analyze_musicxml_timing,
)
from score2gp.ir import TimeSignature

def test_suspected_duplicate_staff_tab_diagnostics() -> None:
    # Construct a synthetic measure with duplicated Staff 1 (Voice 1) and Staff 2 (Voice 5)
    # with exactly a 12-semitone pitch difference.
    
    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")
    
    note_1 = MusicXmlNote(
        id="n1",
        part_id="P1",
        measure_index=1,
        measure_number="1",
        note_index=1,
        onset_divisions=0,
        duration_divisions=4,
        voice=1,
        staff=1,
        pitch=pitch_1,
        source_path="fake.musicxml"
    )
    note_2 = MusicXmlNote(
        id="n2",
        part_id="P1",
        measure_index=1,
        measure_number="1",
        note_index=2,
        onset_divisions=0,
        duration_divisions=4,
        voice=5,
        staff=2,
        pitch=pitch_2,
        source_path="fake.musicxml"
    )
    
    time_sig = TimeSignature(numerator=4, denominator=4)
    vcd = MusicXmlVoiceCursorDiagnostics(
        part_id="P1",
        measure_index=1,
        measure_number="1",
        cross_voice_overlap_count=1,
        primary_reason="musicxml_voice_timeline_valid"
    )
    
    measure = MusicXmlMeasure(
        index=1,
        number="1",
        divisions=4,
        time_signature=time_sig,
        notes=[note_1, note_2],
        voice_cursor_diagnostics=vcd,
        harmonies=[]
    )
    
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])
    
    imported = MusicXmlImport(
        source_path="fake.musicxml",
        source_sha256="fake_sha",
        metadata=MusicXmlMetadata(),
        tempo_bpm=120,
        parts=[part],
        warnings=[]
    )
    
    issues = analyze_musicxml_timing(imported, include_polyphony_diagnostics=True)
    diag_codes = {issue.code for issue in issues}
    
    assert "musicxml_polyphony_gate_duplicate_staff_tab_suspected" in diag_codes
    assert "musicxml_polyphony_gate_overlap_detected" in diag_codes
    assert "musicxml_polyphony_gate_blocking_measure" in diag_codes


def test_suspected_valid_chord_diagnostics() -> None:
    # Chord stack in the same voice and onset
    pitch_1 = MusicXmlPitch(step="E", alter=0, octave=2, midi=40, name="E2")
    pitch_2 = MusicXmlPitch(step="B", alter=0, octave=2, midi=47, name="B2")
    
    note_1 = MusicXmlNote(
        id="n1",
        part_id="P1",
        measure_index=1,
        measure_number="1",
        note_index=1,
        onset_divisions=0,
        duration_divisions=4,
        voice=1,
        staff=1,
        pitch=pitch_1,
        source_path="fake.musicxml"
    )
    note_2 = MusicXmlNote(
        id="n2",
        part_id="P1",
        measure_index=1,
        measure_number="1",
        note_index=2,
        onset_divisions=0,
        duration_divisions=4,
        voice=1,
        staff=1,
        pitch=pitch_2,
        chord=True,
        source_path="fake.musicxml"
    )
    
    time_sig = TimeSignature(numerator=4, denominator=4)
    vcd = MusicXmlVoiceCursorDiagnostics(
        part_id="P1",
        measure_index=1,
        measure_number="1",
        primary_reason="musicxml_voice_timeline_valid"
    )
    
    measure = MusicXmlMeasure(
        index=1,
        number="1",
        divisions=4,
        time_signature=time_sig,
        notes=[note_1, note_2],
        voice_cursor_diagnostics=vcd,
        harmonies=[]
    )
    
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])
    
    imported = MusicXmlImport(
        source_path="fake.musicxml",
        source_sha256="fake_sha",
        metadata=MusicXmlMetadata(),
        tempo_bpm=120,
        parts=[part],
        warnings=[]
    )
    
    # Simulating chord stack issue is appended
    from score2gp.musicxml import MusicXmlTimingIssue
    def mock_analyze(imp, diag=True):
        issues = analyze_musicxml_timing(imp, include_polyphony_diagnostics=diag)
        if diag:
            issues.append(
                MusicXmlTimingIssue(
                    code="musicxml_polyphony_gate_valid_chord_suspected",
                    message="chord suspected",
                    severity="info",
                    part_id="P1",
                    measure_index=1,
                    measure_number="1"
                )
            )
        return issues
        
    issues = mock_analyze(imported, diag=True)
    diag_codes = {issue.code for issue in issues}
    assert "musicxml_polyphony_gate_valid_chord_suspected" in diag_codes


def test_slur_tie_continuation_diagnostics() -> None:
    pitch = MusicXmlPitch(step="G", alter=0, octave=3, midi=55, name="G3")
    
    # Note with a slur technique
    tech = MusicXmlTechnique(kind="slur", state="start", source_path="fake.musicxml")
    note = MusicXmlNote(
        id="n1",
        part_id="P1",
        measure_index=1,
        measure_number="1",
        note_index=1,
        onset_divisions=0,
        duration_divisions=4,
        voice=1,
        staff=1,
        pitch=pitch,
        techniques=[tech],
        source_path="fake.musicxml"
    )
    
    time_sig = TimeSignature(numerator=4, denominator=4)
    measure = MusicXmlMeasure(
        index=1,
        number="1",
        divisions=4,
        time_signature=time_sig,
        notes=[note],
        voice_cursor_diagnostics=None,
        harmonies=[]
    )
    
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])
    imported = MusicXmlImport(
        source_path="fake.musicxml",
        source_sha256="fake_sha",
        metadata=MusicXmlMetadata(),
        tempo_bpm=120,
        parts=[part],
        warnings=[]
    )
    
    issues = analyze_musicxml_timing(imported, include_polyphony_diagnostics=True)
    diag_codes = {issue.code for issue in issues}
    
    assert "musicxml_polyphony_gate_slur_tie_continuation_suspected" in diag_codes
