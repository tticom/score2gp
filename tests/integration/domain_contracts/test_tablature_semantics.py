import pytest
from pathlib import Path
from score2gp.tabraw import TabRaw, TabCandidate

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "tabraw"

def test_tablature_string_and_fret_bounds():
    # Load a valid synthetic tabraw fixture
    tabraw_path = FIXTURES_DIR / "tiny_single_bar_tabraw.json"
    assert tabraw_path.exists()
    
    tabraw = TabRaw.from_json_file(tabraw_path)
    assert len(tabraw.candidates) > 0
    
    # Domain Contract: String numbers must strictly fall within standard guitar string range [1, 6]
    # and fret numbers must be valid playable integers [0, 24]
    for candidate in tabraw.candidates:
        if candidate.string is not None:
            assert 1 <= candidate.string <= 6, f"Fret candidate uses invalid guitar string index: {candidate.string}"
        if candidate.parsed_fret is not None:
            assert 0 <= candidate.parsed_fret <= 24, f"Fret candidate uses unplayable fret value: {candidate.parsed_fret}"

def test_invalid_string_rejection():
    # Load an invalid string or fret candidate to verify it is caught by validation rules
    bad_fret_path = FIXTURES_DIR / "invalid_tabraw_bad_fret.json"
    assert bad_fret_path.exists()
    
    # Domain Contract: Candidates with invalid strings or frets should raise validation/semantic warnings
    # or be rejected cleanly by the TabRaw Pydantic schema
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TabRaw.from_json_file(bad_fret_path)

def test_multi_digit_fret_grouping():
    # Domain Contract: Multi-digit fret numbers (e.g. 10, 11, 12) must be grouped as a single fret candidate,
    # never parsed as separate 1 and 0 events at slightly offset positions.
    tabraw_path = FIXTURES_DIR / "tiny_single_bar_tabraw.json"
    tabraw = TabRaw.from_json_file(tabraw_path)
    
    # Assert that no concurrent overlapping fret candidates representing fragmented digits exist
    # (i.e. x-coordinate boundaries for characters of a single fret are cleanly merged)
    for c1 in tabraw.candidates:
        for c2 in tabraw.candidates:
            if c1.id != c2.id and c1.string == c2.string:
                # Check for extreme character overlap that would suggest unmerged digits
                if abs(c1.bbox.x0 - c2.bbox.x0) < 5.0:
                    pytest.fail(f"Fragmented multi-digit fret candidate detected: {c1} overlaps with {c2}")
