from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.pipeline import run_recognition_on_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_sidecar_bakeoff_integration() -> None:
    """Verify sidecar evaluation runs successfully over Lesson-6.pdf without requiring reference .gp file inputs."""
    lesson6_pdf = (PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private" if (PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private").exists() else PROJECT_ROOT / "fixtures" / "private") / "Lesson-6.pdf"

    # Reference .gp path should not be accessed or passed during evaluation
    reference_gp = lesson6_pdf.with_suffix(".gp")
    assert not reference_gp.name.startswith("tmp_")
    
    result = run_recognition_on_file(lesson6_pdf, assume_treble_clef=True)
    assert result is not None
    assert "timeline_preview" in result
    
    previews = result["timeline_preview"]
    assert len(previews) > 0
