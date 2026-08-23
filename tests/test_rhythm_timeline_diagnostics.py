from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.pipeline import run_recognition_on_file

def test_rhythm_timeline_diagnostics_integration() -> None:
    """Verify rhythm timeline diagnostics run successfully over Lesson-6.pdf without synthetic data."""
    lesson6_pdf = (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else Path(__file__).resolve().parent.parent / "fixtures" / "private") / "Lesson-6.pdf"

    result = run_recognition_on_file(lesson6_pdf, assume_treble_clef=True)
    assert result is not None
    assert "timeline_preview" in result

    previews = result["timeline_preview"]
    assert len(previews) > 0

    # Verify events are correctly produced without synthetic intervention
    for preview in previews:
        for m in preview["measures"]:
            for event in m["events"]:
                assert "symbol_type" in event
                assert "duration_ticks" in event
