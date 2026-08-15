import pytest
from pathlib import Path
from score2gp.whole_note_recogniser import run_recognition_on_file

def _get_note_candidates(res: dict) -> list[dict]:
    outcomes = res.get("read_only_recognition_outcomes", [])
    return [
        o for o in outcomes
        if o.get("symbol_type", "").endswith("_note_candidate")
        and o.get("association_status") != "suppressed"
    ]

def test_fractional_double_beam_extraction_sixteenth_notes():
    pdf_path = Path("fixtures/public/generated_simple/simple/4SixteenthNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None

    candidates = _get_note_candidates(res)
    assert len(candidates) == 4, f"Expected 4 candidates, got {len(candidates)}"

    for cand in candidates:
        assert cand.get("symbol_type") == "sixteenth_note_candidate"
        assert cand.get("duration") == "sixteenth"


def test_fractional_double_beam_extraction_quarter_notes_no_false_positives():
    pdf_path = Path("fixtures/public/generated_simple/simple/4QuarterNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None

    candidates = _get_note_candidates(res)
    assert len(candidates) == 4, f"Expected 4 candidates, got {len(candidates)}"

    for cand in candidates:
        assert cand.get("symbol_type") == "quarter_note_candidate"
        assert cand.get("duration") == "quarter"


def test_fractional_double_beam_extraction_eighth_notes():
    pdf_path = Path("fixtures/public/generated_simple/simple/2EighthNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None

    candidates = _get_note_candidates(res)
    assert len(candidates) == 2, f"Expected 2 candidates, got {len(candidates)}"

    for cand in candidates:
        assert cand.get("symbol_type") == "eighth_note_candidate"
        assert cand.get("duration") == "eighth"
