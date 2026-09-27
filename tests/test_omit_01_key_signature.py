"""Public key-signature PDF regression and refusal cases."""

from pathlib import Path

import pymupdf

from score2gp.notation_omr.key_signature import read_system_key_signature
from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves, read_note_durations


FIXTURE = Path(__file__).parent / "fixtures/pdf/omit_01/key_signatures.pdf"


def test_public_signature_pdf_reads_zero_sharps_flats_and_change():
    sidecar = read_note_durations(FIXTURE, time_signature=(4, 4))
    results = sidecar["diagnostics"]["key_signatures"]
    assert len(results) == 7
    assert [r["fifths"] for r in results[:6]] == [0, 1, 3, -2, -2, 1]
    assert all(r["status"] == "read" for r in results[:6])
    assert results[4]["sources"] == [] and len(results[4]["inherited_from"]) == 2
    assert all(len(results[i]["sources"]) == abs(results[i]["fifths"]) for i in (0, 1, 2, 3, 5))
    assert results[6]["status"] == "refused"
    assert results[6]["reason"] == "key_signature_partial_or_ambiguous"
    assert results[6]["location"]["page_index"] == 0


def test_mode_is_not_inferred_from_accidental_count():
    with pymupdf.open(FIXTURE) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[1], symbols)
    assert result["fifths"] == 1
    assert result["mode"] is None
    assert result["mode_diagnostic"] == "key_mode_unresolved"


def test_first_note_accidental_is_not_key_signature():
    source = FIXTURE.parent / "note_accidental.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 0
    assert result["sources"] == []


def test_key_glyph_before_first_note_accidental_is_preserved():
    source = FIXTURE.parent / "key_and_note_accidental.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 1
    assert len(result["sources"]) == 1


def test_exact_printed_key_name_supplies_mode():
    source = FIXTURE.parent / "named_mode.pdf"
    with pymupdf.open(source) as doc:
        symbols = extract_page_symbols(doc[0], 0)
        staves, _ = find_staves(symbols)
        result = read_system_key_signature(staves[0], symbols)
    assert result["status"] == "read"
    assert result["fifths"] == 1
    assert result["mode"] == "minor"
    assert len(result["mode_sources"]) == 1
    assert result["mode_diagnostic"] is None
