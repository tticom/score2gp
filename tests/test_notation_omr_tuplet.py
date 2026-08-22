from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.pipeline import run_recognition_on_file

def test_tuplet_recognition_integration() -> None:
    """Verify tuplet recognition runs successfully over Lesson-6.pdf without synthetic data."""
    lesson6_pdf = (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else Path(__file__).resolve().parent.parent / "fixtures" / "private") / "Lesson-6.pdf"

    result = run_recognition_on_file(lesson6_pdf, assume_treble_clef=True)
    assert result is not None
    assert "tuplet_associations" in result
    
    tuplets = result["tuplet_associations"]
    # We assert it's a list; it may be empty depending on the fixture.
    assert isinstance(tuplets, list)
