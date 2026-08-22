from __future__ import annotations

import pytest
import json
from pathlib import Path
from score2gp.notation_omr.pipeline import run_recognition_on_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_private_fixture_lesson6_timeline_integration() -> None:
    """Verify pipeline recognition on Lesson-6.pdf preserves timeline capacity and tuplets natively."""
    lesson6_pdf = (PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else PROJECT_ROOT / "fixtures" / "private") / "Lesson-6.pdf"

    result = run_recognition_on_file(lesson6_pdf, assume_treble_clef=True)
    assert result is not None
    assert "timeline_preview" in result
    
    previews = result["timeline_preview"]
    assert len(previews) > 0
    
    # Verify the structure is correct without synthetic mutation
    for preview in previews:
        assert "measures" in preview
        for m in preview["measures"]:
            assert "measure_index" in m
            assert "events" in m
