
import pytest
from pathlib import Path

def _get_dynamic_private_pdf():
    pdfs = list(Path("fixtures/private").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No private fixtures found", allow_module_level=True)
    return pdfs[0]

def _get_dynamic_private_musicxml():
    xmls = list(Path("fixtures/private").glob("*.musicxml"))
    if not xmls:
        # Fallback to pdf just so Path doesn't fail, test will likely skip or fail gracefully
        return _get_dynamic_private_pdf()
    return xmls[0]

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
    pdf_path = _get_dynamic_private_pdf()
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
    pdf_path = _get_dynamic_private_pdf()
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
    pdf_path = _get_dynamic_private_pdf()
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
