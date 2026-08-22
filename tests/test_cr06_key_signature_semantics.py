from __future__ import annotations

from score2gp.notation_omr.pitch import map_clef_resolved_staff_pitch


def test_cr06_key_signature_unevidenced_returns_unknown() -> None:
    """Verify that unevidenced notation staves have status UNKNOWN and resolved_key_signature None."""
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "staff_position_index": 0,
            "x0": 10.0,
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]

    map_clef_resolved_staff_pitch(outcomes, explicit_clef="treble", semantic_candidates=None)

    note = outcomes[0]
    assert note.get("clef_resolved_staff_pitch") == "F5"
    assert note.get("clef_resolved_midi_pitch") == 77
    assert note.get("key_signature_status") == "UNKNOWN"
    assert note.get("resolved_key_signature") is None


def test_cr06_key_signature_evidenced_applies_alterations() -> None:
    """Verify that an explicit valid key signature (e.g. G Major) maps to EVIDENCED and applies alterations."""
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "staff_position_index": 0,  # F5 on treble staff -> F#5 in G Major
            "x0": 10.0,
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]

    map_clef_resolved_staff_pitch(
        outcomes,
        explicit_clef="treble",
        explicit_key_signature="G Major",
    )

    note = outcomes[0]
    assert note.get("clef_resolved_staff_pitch") == "F#5"
    assert note.get("clef_resolved_midi_pitch") == 78
    assert note.get("key_signature_status") == "EVIDENCED"
    assert note.get("resolved_key_signature") == "G Major"


def test_cr06_key_signature_ambiguous_returns_ambiguous() -> None:
    """Verify that an unrecognized or ambiguous key signature maps to AMBIGUOUS and applies 0 key alterations."""
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "staff_position_index": 0,
            "x0": 10.0,
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]

    map_clef_resolved_staff_pitch(
        outcomes,
        explicit_clef="treble",
        explicit_key_signature="Invalid Nonexistent Key",
    )

    note = outcomes[0]
    assert note.get("clef_resolved_staff_pitch") == "F5"
    assert note.get("clef_resolved_midi_pitch") == 77
    assert note.get("key_signature_status") == "AMBIGUOUS"
    assert note.get("resolved_key_signature") is None


def test_cr06_cli_key_signature_formatting() -> None:
    """Verify CLI diagnostics report formats unevidenced key signatures as 'Unknown' instead of 'C Major'."""
    from score2gp.cli import _format_diagnostics_report

    # Case 1: Unevidenced (empty semantic_candidates)
    data_empty = {
        "source": "test.pdf",
        "recognition_mode": "omr",
        "semantic_candidates": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
            }
        ],
        "read_only_recognition_outcomes": [],
    }
    text_empty = _format_diagnostics_report(data_empty)
    assert "Key Signature: Unknown" in text_empty

    # Case 2: Explicit UNKNOWN status
    data_unknown = {
        "source": "test.pdf",
        "recognition_mode": "omr",
        "semantic_candidates": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "logical_key_signature": {"status": "UNKNOWN"},
            }
        ],
        "read_only_recognition_outcomes": [],
    }
    text_unknown = _format_diagnostics_report(data_unknown)
    assert "Key Signature: Unknown" in text_unknown

    # Case 3: Explicit AMBIGUOUS status
    data_ambiguous = {
        "source": "test.pdf",
        "recognition_mode": "omr",
        "semantic_candidates": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "logical_key_signature": {"status": "AMBIGUOUS"},
            }
        ],
        "read_only_recognition_outcomes": [],
    }
    text_ambiguous = _format_diagnostics_report(data_ambiguous)
    assert "Key Signature: Ambiguous" in text_ambiguous

    # Case 4: Explicit valid key signature
    data_evidenced = {
        "source": "test.pdf",
        "recognition_mode": "omr",
        "semantic_candidates": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "logical_key_signature": {"status": "EVIDENCED", "key_name": "D Major"},
            }
        ],
        "read_only_recognition_outcomes": [],
    }
    text_evidenced = _format_diagnostics_report(data_evidenced)
    assert "Key Signature: D Major" in text_evidenced
