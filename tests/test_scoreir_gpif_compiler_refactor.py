"""Unit tests for CRP-12: Unified ScoreIR / GPIF Compiler Refactor & Binary Assembly Seam."""

from pathlib import Path
import tempfile
import zipfile
import pytest
from score2gp.notation_omr.timeline import TopologicallyLockedBarTimeline
from score2gp.notation_omr.position_optimizer import FretTokenOwnership
from score2gp.scoreir_compiler import ScoreIRCompiler
from score2gp.gpif_builder import GPIFBuilder
from score2gp.notation_omr.pipeline import run_recognition_on_file


def test_scoreir_compilation_from_locked_timeline():
    compiler = ScoreIRCompiler()

    timeline = TopologicallyLockedBarTimeline(
        measure_index=1,
        capacity_ticks=3840,
        events=[
            {"candidate_id": "tok_01", "onset_ticks": 0, "duration_ticks": 960, "is_rest": False},
            {"candidate_id": "tok_02", "onset_ticks": 960, "duration_ticks": 960, "is_rest": False},
            {"candidate_id": "tok_03", "onset_ticks": 1920, "duration_ticks": 960, "is_rest": True},
            {"candidate_id": "tok_04", "onset_ticks": 2880, "duration_ticks": 960, "is_rest": False},
        ],
    )

    positions = [
        FretTokenOwnership("tok_01", pitch=64, string_index=1, fret_number=0, modality="observed_tab"),
        FretTokenOwnership("tok_02", pitch=59, string_index=2, fret_number=0, modality="inferred_position"),
        FretTokenOwnership("tok_04", pitch=55, string_index=3, fret_number=0, modality="inferred_position"),
    ]

    score_ir = compiler.compile(bar_timelines=[timeline], position_ownership=positions)

    assert score_ir is not None
    assert len(score_ir.tracks) == 1
    assert len(score_ir.bars) == 1
    assert len(score_ir.bars[0].events) == 4
    assert score_ir.semantic_contract_is_valid() is score_ir


def test_gpif_binary_assembly_seam():
    builder = GPIFBuilder()

    timeline = TopologicallyLockedBarTimeline(
        measure_index=1,
        capacity_ticks=3840,
        events=[
            {"candidate_id": "tok_01", "onset_ticks": 0, "duration_ticks": 3840, "is_rest": False},
        ],
    )

    positions = [
        FretTokenOwnership("tok_01", pitch=64, string_index=1, fret_number=0, modality="observed_tab"),
    ]

    score_ir = builder.compile_to_score_ir([timeline], positions)
    assert score_ir.semantic_contract_is_valid() is score_ir

    with tempfile.TemporaryDirectory() as tmpdir:
        out_gp = Path(tmpdir) / "test_out.gp"
        warnings = builder.write_gp_file(score_ir, out_gp)

        assert out_gp.exists()
        assert out_gp.stat().st_size > 0

        with zipfile.ZipFile(out_gp, "r") as z:
            names = set(z.namelist())
            assert "VERSION" in names
            assert "Content/score.gpif" in names


def test_compiler_reference_gp_isolation():
    compiler = ScoreIRCompiler()
    score_ir = compiler.compile([], [])
    assert score_ir is not None
    assert score_ir.semantic_contract_is_valid() is score_ir


def test_private_fixture_lesson6_gp_compilation():
    lesson6 = Path("fixtures/private/Lesson-6.pdf")
    if not lesson6.exists():
        pytest.skip("Private fixture Lesson-6.pdf not present")

    res = run_recognition_on_file(lesson6, assume_treble_clef=True)
    assert res is not None

    builder = GPIFBuilder()
    score_ir = builder.compile_to_score_ir(
        bar_timelines=res.get("timeline_preview", []),
        position_ownership=res.get("fretboard_position_ownership", []),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_gp = Path(tmpdir) / "lesson6_out.gp"
        builder.write_gp_file(score_ir, out_gp)
        assert out_gp.exists()
        assert out_gp.stat().st_size > 0
