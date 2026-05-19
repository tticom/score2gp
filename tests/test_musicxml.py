from __future__ import annotations

from pathlib import Path

from score2gp.musicxml import analyze_musicxml_timing, parse_musicxml

FIXTURES = Path("tests/fixtures/musicxml")


def test_musicxml_importer_parses_tiny_partwise_score() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_single_bar.musicxml")

    assert imported.metadata.title == "Tiny MusicXML Test"
    assert imported.metadata.composer == "Generated Fixture"
    assert imported.tempo_bpm == 96
    assert imported.parts[0].id == "P1"
    assert imported.parts[0].name == "Guitar"

    measure = imported.parts[0].measures[0]
    assert measure.divisions == 4
    assert measure.time_signature.numerator == 4
    assert measure.time_signature.denominator == 4
    assert [note.voice for note in measure.notes] == [1, 1, 1]
    assert measure.notes[0].pitch is not None
    assert measure.notes[0].pitch.midi == 64
    assert measure.notes[1].pitch is not None
    assert measure.notes[1].pitch.name == "F#4"
    assert measure.notes[1].ties == ["start"]
    assert measure.notes[2].is_rest is True


def test_musicxml_duration_normalizes_to_scoreir_ticks() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_single_bar.musicxml")
    measure = imported.parts[0].measures[0]

    first_ticks, exact = measure.notes[0].duration_ticks(measure.divisions)
    rest_ticks, rest_exact = measure.notes[2].duration_ticks(measure.divisions)

    assert (first_ticks, exact) == (960, True)
    assert (rest_ticks, rest_exact) == (1920, True)


def test_musicxml_importer_preserves_simple_voice_numbers() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_two_voice.musicxml")
    measure = imported.parts[0].measures[0]

    assert [note.voice for note in measure.notes] == [1, 2]
    assert measure.notes[1].is_rest is True


def test_musicxml_importer_warns_for_unsupported_repeat() -> None:
    imported = parse_musicxml(FIXTURES / "unsupported_repeat.musicxml")

    assert [warning.code for warning in imported.warnings] == ["unsupported-repeat"]


def test_musicxml_importer_preserves_harmony_tuplets_and_guitar_techniques() -> None:
    imported = parse_musicxml(FIXTURES / "rich_guitar_cases.musicxml")

    assert imported.metadata.title == "Rich Guitar Cases"
    assert imported.tempo_bpm == 72

    first_measure = imported.parts[0].measures[0]
    assert first_measure.divisions == 24
    assert first_measure.harmonies[0].text == "E7"
    assert first_measure.harmonies[0].onset_divisions == 0

    chord_note = first_measure.notes[1]
    assert chord_note.chord is True
    assert chord_note.onset_divisions == 0

    triplet_note = first_measure.notes[3]
    assert triplet_note.duration_ticks(first_measure.divisions) == (320, True)
    assert triplet_note.tuplet is not None
    assert triplet_note.tuplet.actual_notes == 3
    assert triplet_note.tuplet.normal_notes == 2

    technique_kinds = [technique.kind for note in first_measure.notes for technique in note.techniques]
    assert technique_kinds == ["slide", "hammer-on", "bend", "vibrato", "slur"]

    second_measure = imported.parts[0].measures[1]
    assert second_measure.harmonies[0].text == "Gmaj7"


def test_musicxml_importer_handles_multibar_onsets_and_divisions() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_multibar.musicxml")

    assert len(imported.parts[0].measures) == 2
    first, second = imported.parts[0].measures
    assert [note.onset_ticks(first.divisions)[0] for note in first.notes] == [0, 960, 1920]
    assert [note.onset_ticks(second.divisions)[0] for note in second.notes] == [0, 1920]


def test_musicxml_importer_handles_chord_without_advancing_onset() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_chords.musicxml")
    measure = imported.parts[0].measures[0]

    assert measure.harmonies[0].text == "Em"
    assert [note.onset_divisions for note in measure.notes] == [0, 0, 4]
    assert measure.notes[1].chord is True


def test_musicxml_importer_handles_backup_for_simple_voice_timing() -> None:
    imported = parse_musicxml(FIXTURES / "tiny_rests_voices.musicxml")
    measure = imported.parts[0].measures[0]

    assert [(note.onset_divisions, note.voice, note.is_rest) for note in measure.notes] == [
        (0, 1, False),
        (8, 1, False),
        (0, 2, True),
    ]


def test_musicxml_timing_preflight_detects_audiveris_like_overfull_bar() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_overfull_bar.musicxml")

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [("musicxml-overfull-bar", "error")]
    assert issues[0].expected_duration_divisions == 16
    assert issues[0].end_divisions == 20


def test_musicxml_timing_preflight_flags_12_8_compound_meter_without_error() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_12_8_timing.musicxml")

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [("musicxml-compound-meter-assumption", "info")]
    assert issues[0].expected_duration_divisions == 36


def test_musicxml_timing_preflight_records_backup_forward_risk() -> None:
    imported = parse_musicxml(FIXTURES / "audiveris_like_backup_forward.musicxml")

    assert [warning.code for warning in imported.warnings] == [
        "musicxml-backup-encountered",
        "musicxml-forward-encountered",
    ]

    issues = analyze_musicxml_timing(imported)

    assert [(issue.code, issue.severity) for issue in issues] == [("musicxml-overfull-bar", "error")]
    assert issues[0].voice == 2
