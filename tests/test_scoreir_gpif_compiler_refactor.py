"""Unit tests for CRP-12: Unified ScoreIR / GPIF Compiler Refactor & Binary Assembly Seam."""

from pathlib import Path
import pytest
import tempfile
import zipfile
import pytest
from score2gp.notation_omr.timeline import TopologicallyLockedBarTimeline
from score2gp.notation_omr.position_optimizer import FretTokenOwnership
from score2gp.scoreir_compiler import ScoreIRCompiler
from score2gp.gpif_builder import GPIFBuilder
from score2gp.notation_omr.pipeline import run_recognition_on_file





def test_private_fixture_lesson6_gp_compilation():
    lesson6 = Path("fixtures/private/Lesson-6.pdf")
    if not lesson6.exists():
        import pytest; pytest.skip("Missing fixture")

    res = run_recognition_on_file(lesson6, assume_treble_clef=True)
    assert res is not None

    builder = GPIFBuilder()
    score_ir = builder.compile_to_score_ir(
        bar_timelines=res.get("timeline_preview", []),
        position_ownership=res.get("fretboard_position_ownership", []),
    )

    assert score_ir.semantic_contract_is_valid() is score_ir
    assert len(score_ir.tracks) >= 1
    assert len(score_ir.bars) >= 1

    with tempfile.TemporaryDirectory() as tmpdir:
        out_gp = Path(tmpdir) / "lesson6_out.gp"
        builder.write_gp_file(score_ir, out_gp)
        assert out_gp.exists()
        assert out_gp.stat().st_size > 0

        with zipfile.ZipFile(out_gp, "r") as z:
            names = set(z.namelist())
            assert "VERSION" in names
            assert "Content/score.gpif" in names
