"""GPIF builder and binary .gp package compiler seam."""

from pathlib import Path
from typing import Any
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp
from score2gp.scoreir_compiler import ScoreIRCompiler


class GPIFBuilder:
    """Builds GPIF XML structures and compiles ScoreIR models into valid .gp binaries."""

    def __init__(self, compiler: ScoreIRCompiler | None = None) -> None:
        self.compiler = compiler or ScoreIRCompiler()

    def compile_to_score_ir(
        self,
        bar_timelines: list[Any],
        position_ownership: list[Any],
        time_signature: tuple[int, int] = (4, 4),
        bpm: int = 120,
    ) -> ScoreIR:
        return self.compiler.compile(
            bar_timelines=bar_timelines,
            position_ownership=position_ownership,
            time_signature=time_signature,
            bpm=bpm,
        )

    def write_gp_file(
        self,
        score: ScoreIR,
        out_path: str | Path,
        template: str | Path | None = None,
    ) -> list[str]:
        """
        Assembles compiled ScoreIR model into a valid .gp binary package.
        Returns any warnings generated during binary package packaging.
        """
        return write_gp(score, out_path=out_path, template=template)
