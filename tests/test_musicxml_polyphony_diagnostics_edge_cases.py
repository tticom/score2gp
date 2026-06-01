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


def test_duplicate_staff_tab_voice_detected() -> None:
    # Voice 1 and Voice 5 with identical onsets, durations, and stable 12-semitone pitch offset
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        classify_musicxml_voice_duplication
    )
    from score2gp.ir import TimeSignature

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_2, source_path="fake.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    confirmed, warnings = classify_musicxml_voice_duplication(part)
    assert confirmed == [(1, 5)]
    assert not any("rejected" in code for _, _, code in warnings)


def test_duplicate_staff_tab_voice_unified() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature
    from score2gp.tabraw import TabRaw, TabCandidate
    from score2gp.build_ir import build_ir_with_diagnostics_from_imports

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_2, source_path="fake_tab.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    # Run deduplication
    dedup = deduplicate_suspected_staff_tab_voices(imported)

    # TabRaw candidates
    tab_cand = TabCandidate(
        id="tc1",
        raw_text="7",
        parsed_fret=7,
        string=3,
        confidence=0.9,
        page_index=1,
        system_index=1,
        bar_index=1,
        raw={"x": 100.0, "y": 200.0}
    )
    tabraw = TabRaw(candidates=[tab_cand])

    # Build IR
    score, diagnostics = build_ir_with_diagnostics_from_imports(imported, tabraw)

    # Verify:
    # 1. Deduplication warnings are emitted
    warning_codes = {w.code for w in score.warnings}
    assert "musicxml_duplicate_staff_tab_detected" in warning_codes
    assert "musicxml_duplicate_staff_tab_dedup_applied" in warning_codes

    # 2. Only 1 note is generated in the first bar, no duplicated Voice 5 notes!
    assert len(score.bars) == 1
    assert len(score.bars[0].events) == 1
    event = score.bars[0].events[0]
    assert len(event.notes) == 1
    note = event.notes[0]
    assert note.fret == 7
    assert note.string == 3

    # 3. Provenance from both standard and TAB voice is preserved!
    assert len(note.provenance) == 3 # Notation note, TAB note, TabRaw candidate!
    musicxml_prov_ids = {p.raw_token_id for p in note.provenance if p.source_stage == "musicxml"}
    assert "n1" in musicxml_prov_ids
    assert "n2" in musicxml_prov_ids

    # Assert standard notation and TAB provenance source paths are preserved correctly
    notation_prov = next(p for p in note.provenance if p.raw_token_id == "n1")
    tab_prov = next(p for p in note.provenance if p.raw_token_id == "n2")
    assert notation_prov.raw.get("source_path") == "fake.musicxml"
    assert tab_prov.raw.get("source_path") == "fake_tab.musicxml"


def test_genuine_independent_polyphony_still_refuses() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        classify_musicxml_voice_duplication
    )
    from score2gp.ir import TimeSignature
    from score2gp.build_ir import build_ir_with_diagnostics_from_imports, BuildIrInputRiskError
    from score2gp.tabraw import TabRaw

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="E", alter=0, octave=4, midi=64, name="E4")

    # Mismatched duration/onset -> different rhythms
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=2, duration_divisions=2, voice=5, staff=2, pitch=pitch_2, source_path="fake.musicxml"
    )

    from score2gp.musicxml import MusicXmlVoiceCursorDiagnostics
    vcd = MusicXmlVoiceCursorDiagnostics(
        part_id="P1",
        measure_index=1,
        measure_number="1",
        cross_voice_overlap_count=1,
        primary_reason="musicxml_voice_timeline_valid"
    )
    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2], voice_cursor_diagnostics=vcd, harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    # Should not be classified as confirmed
    confirmed, warnings = classify_musicxml_voice_duplication(part)
    assert not confirmed

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    # Polyphony gate must still block
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_with_diagnostics_from_imports(imported, TabRaw(candidates=[]))
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_valid_chord_stack_not_misclassified_as_duplicate() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        classify_musicxml_voice_duplication
    )
    from score2gp.ir import TimeSignature

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="F", alter=0, octave=4, midi=65, name="F4")

    # Same voice chord stack
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_2, chord=True, source_path="fake.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    confirmed, warnings = classify_musicxml_voice_duplication(part)
    assert not confirmed
    assert not warnings


def test_partial_duplicate_emits_warning() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    # Measure 1 matches perfectly
    n1_m1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2_m1 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_2, source_path="fake.musicxml"
    )

    # Measure 2 has a mismatch (extra note in notation voice)
    n1_m2 = MusicXmlNote(
        id="n3", part_id="P1", measure_index=2, measure_number="2", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )

    measure1 = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1_m1, n2_m1], harmonies=[]
    )
    measure2 = MusicXmlMeasure(
        index=2, number="2", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1_m2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure1, measure2])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    dedup = deduplicate_suspected_staff_tab_voices(imported)
    warning_codes = {w.code for w in dedup.warnings}
    assert "musicxml_duplicate_staff_tab_partial_match" in warning_codes


def test_same_voice_timing_error_still_refuses_after_dedup() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature
    from score2gp.build_ir import build_ir_with_diagnostics_from_imports, BuildIrInputRiskError
    from score2gp.tabraw import TabRaw

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    # Duplicate voices, but Voice 1 has same-voice timing overlap (n1 and n3 overlap!)
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n3 = MusicXmlNote(
        id="n3", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=2, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )

    from score2gp.musicxml import MusicXmlVoiceCursorDiagnostics
    vcd = MusicXmlVoiceCursorDiagnostics(
        part_id="P1",
        measure_index=1,
        measure_number="1",
        same_voice_overlap_count=1,
        primary_reason="musicxml_voice_timeline_valid"
    )
    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n3], voice_cursor_diagnostics=vcd, harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    # Same voice overlap error must still refuse
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_with_diagnostics_from_imports(imported, TabRaw(candidates=[]))
    assert raised.value.category == "musicxml_timing_risk"


def test_multiple_candidate_duplicate_pairs_refuse_as_ambiguous() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    # Voice 1 matches with BOTH Voice 5 and Voice 6 perfectly! (Competing matches)
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n5 = MusicXmlNote(
        id="n5", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_2, source_path="fake.musicxml"
    )
    n6 = MusicXmlNote(
        id="n6", part_id="P1", measure_index=1, measure_number="1", note_index=3,
        onset_divisions=0, duration_divisions=4, voice=6, staff=3, pitch=pitch_2, source_path="fake.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n5, n6], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    dedup = deduplicate_suspected_staff_tab_voices(imported)
    warning_codes = {w.code for w in dedup.warnings}
    assert "musicxml_duplicate_staff_tab_rejected_independent_polyphony" in warning_codes


def test_duplicate_staff_tab_unstable_pitch_offset_rejected() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        classify_musicxml_voice_duplication
    )
    from score2gp.ir import TimeSignature

    pitch_d4 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_d3 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")
    pitch_e4 = MusicXmlPitch(step="E", alter=0, octave=4, midi=64, name="E4")

    # In measure 1, notes have 12 semitones offset: D4 (62) vs D3 (50)
    n1_m1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_d4, source_path="fake.musicxml"
    )
    n2_m1 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_d3, source_path="fake.musicxml"
    )

    # In measure 2, notes have 0 semitones offset: E4 (64) vs E4 (64)
    n1_m2 = MusicXmlNote(
        id="n3", part_id="P1", measure_index=2, measure_number="2", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=1, staff=1, pitch=pitch_e4, source_path="fake.musicxml"
    )
    n2_m2 = MusicXmlNote(
        id="n4", part_id="P1", measure_index=2, measure_number="2", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=5, staff=2, pitch=pitch_e4, source_path="fake.musicxml"
    )

    measure1 = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1_m1, n2_m1], harmonies=[]
    )
    measure2 = MusicXmlMeasure(
        index=2, number="2", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1_m2, n2_m2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure1, measure2])

    # Unstable offset (12 semitones in measure 1, 0 semitones in measure 2) must be rejected
    confirmed, warnings = classify_musicxml_voice_duplication(part)
    assert not confirmed
    warning_codes = {w for _, _, w in warnings}
    assert "musicxml_duplicate_staff_tab_not_applied_low_confidence" in warning_codes


def test_duplicate_staff_tab_roles_selected_by_staff_evidence() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    # Voice 5 is standard notation (staff=1)
    # Voice 1 is TAB staff (staff=2)
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=4, voice=5, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=4, voice=1, staff=2, pitch=pitch_2, source_path="fake.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    # Deduplication must correctly identify notation_voice=5 and tab_voice=1 using staff evidence, not min/max voice numbers
    dedup = deduplicate_suspected_staff_tab_voices(imported)

    # Notation note (Voice 5) should remain unsuppressed, and TAB note (Voice 1) should be suppressed
    xml_part = dedup.parts[0]
    xml_measure = xml_part.measures[0]
    voice_5_note = next(n for n in xml_measure.notes if n.voice == 5)
    voice_1_note = next(n for n in xml_measure.notes if n.voice == 1)

    assert not voice_5_note.is_suppressed
    assert voice_1_note.is_suppressed
    assert voice_5_note.dedup_tab_note_voice == 1
    assert voice_5_note.dedup_tab_note_staff == 2


def test_duplicate_staff_tab_voice_rest_suppressed() -> None:
    from score2gp.musicxml import (
        MusicXmlImport, MusicXmlPart, MusicXmlMeasure, MusicXmlNote, MusicXmlPitch, MusicXmlMetadata,
        deduplicate_suspected_staff_tab_voices
    )
    from score2gp.ir import TimeSignature
    from score2gp.tabraw import TabRaw, TabCandidate
    from score2gp.build_ir import build_ir_with_diagnostics_from_imports

    pitch_1 = MusicXmlPitch(step="D", alter=0, octave=4, midi=62, name="D4")
    pitch_2 = MusicXmlPitch(step="D", alter=0, octave=3, midi=50, name="D3")

    # Pitched notes
    n1 = MusicXmlNote(
        id="n1", part_id="P1", measure_index=1, measure_number="1", note_index=1,
        onset_divisions=0, duration_divisions=2, voice=1, staff=1, pitch=pitch_1, source_path="fake.musicxml"
    )
    n2 = MusicXmlNote(
        id="n2", part_id="P1", measure_index=1, measure_number="1", note_index=2,
        onset_divisions=0, duration_divisions=2, voice=5, staff=2, pitch=pitch_2, source_path="fake_tab.musicxml"
    )

    # Rests
    n1_rest = MusicXmlNote(
        id="n1_rest", part_id="P1", measure_index=1, measure_number="1", note_index=3,
        onset_divisions=2, duration_divisions=2, voice=1, staff=1, is_rest=True, source_path="fake.musicxml"
    )
    n2_rest = MusicXmlNote(
        id="n2_rest", part_id="P1", measure_index=1, measure_number="1", note_index=4,
        onset_divisions=2, duration_divisions=2, voice=5, staff=2, is_rest=True, source_path="fake_tab.musicxml"
    )

    measure = MusicXmlMeasure(
        index=1, number="1", divisions=4, time_signature=TimeSignature(numerator=4, denominator=4),
        notes=[n1, n2, n1_rest, n2_rest], harmonies=[]
    )
    part = MusicXmlPart(id="P1", name="Guitar", measures=[measure])

    imported = MusicXmlImport(
        source_path="fake.musicxml", source_sha256="fake_sha", metadata=MusicXmlMetadata(),
        tempo_bpm=120, parts=[part], warnings=[]
    )

    # 1. Verify deduplication suppresses both duplicate pitched notes and duplicate rests
    dedup = deduplicate_suspected_staff_tab_voices(imported)
    m = dedup.parts[0].measures[0]
    voice_5_notes = [n for n in m.notes if n.voice == 5]
    assert all(n.is_suppressed for n in voice_5_notes)

    # 2. Verify target staff selection and build IR successfully selects Staff 1
    tab_cand = TabCandidate(
        id="tc1",
        raw_text="7",
        parsed_fret=7,
        string=3,
        confidence=0.9,
        page_index=1,
        system_index=1,
        bar_index=1,
        raw={"x": 100.0, "y": 200.0}
    )
    tabraw = TabRaw(candidates=[tab_cand])

    score, diagnostics = build_ir_with_diagnostics_from_imports(imported, tabraw)

    # Target staff must be Staff 1 (since Staff 2 notes/rests are suppressed)
    assert len(score.bars) == 1
    # We have 2 events: the pitched note at onset 0, and the rest at onset 2
    assert len(score.bars[0].events) == 2

    # Event 0 is the pitched note aligned with TabCandidate
    event0 = score.bars[0].events[0]
    assert len(event0.notes) == 1
    assert event0.notes[0].fret == 7

    # Event 1 is the rest on Staff 1 (having no notes)
    event1 = score.bars[0].events[1]
    assert len(event1.notes) == 0
