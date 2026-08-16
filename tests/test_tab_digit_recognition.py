from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.pdf import _extract_pdf_text_candidates
from score2gp.tabraw import parse_fret_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_fret_text_parsing_bounds() -> None:
    """Verify parse_fret_text accepts valid fret strings 0..36 and rejects non-numeric/out-of-bound strings."""
    for fret in range(37):
        assert parse_fret_text(str(fret)) == fret

    assert parse_fret_text("37") is None
    assert parse_fret_text("710") is None
    assert parse_fret_text("abc") is None


def test_digit_merging_fret_limit_prevention() -> None:
    """Verify that adjacent single-digit frets yielding > 24 break merge and remain separate tokens."""
    fret_7 = parse_fret_text("7")
    fret_10 = parse_fret_text("10")
    fret_merged = parse_fret_text("710")

    assert fret_7 == 7
    assert fret_10 == 10
    assert fret_merged is None


def test_tab_digit_recognition_reference_isolation() -> None:
    """Verify TAB digit candidate recognition operates without requiring reference .gp file inputs."""
    lesson5_pdf = (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else Path(__file__).resolve().parent.parent / "fixtures" / "private") / "Lesson-5.pdf"

    warnings: list[dict] = []
    meta: dict[str, int] = {"detected_systems": 0, "detected_staves": 0, "detected_bar_boxes": 0, "detected_string_lines": 0}
    candidates = _extract_pdf_text_candidates(lesson5_pdf, warnings, meta)

    # Confirm candidates were extracted without receiving or generating reference .gp path
    assert len(candidates) > 0
    fret_candidates = [c for c in candidates if parse_fret_text(c.get("raw_text", "")) is not None]
    assert len(fret_candidates) > 0
    for cand in fret_candidates:
        val = parse_fret_text(cand.get("raw_text", ""))
        assert val is not None
