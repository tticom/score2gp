"""Real-source text labels through the PDF-only conversion route."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile

import pytest

from test_dur_02_oracle import compare_gp_free_text


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


@pytest.mark.parametrize("number", range(3, 8))
def test_lesson_free_text(number: int) -> None:
    source = PRIVATE / f"Lesson-{number}.pdf"
    reference = PRIVATE / f"Lesson-{number}.gp"
    if not source.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        output = Path(directory) / "written.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(Path(directory) / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        differences = compare_gp_free_text(reference, output)
        if number == 3:
            assert differences == []
