"""Real-source text labels through the PDF-only conversion route."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import pytest

from test_dur_02_oracle import compare_gp_free_text, read_gp_free_text


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# Exact position-set oracles are digests so private bar/beat positions stay untracked.
EMPTY_POSITIONS = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
EXPECTED_MISSING_DIGEST = {
    3: EMPTY_POSITIONS,
    4: "80b90ec3799c6da1781fdf74743b91bfdac44231a7d17a667c7f4a852cfcc178",
    5: EMPTY_POSITIONS,
    6: EMPTY_POSITIONS,
    7: EMPTY_POSITIONS,
}
EXPECTED_COUNTS = {3: (12, 12, 0), 4: (18, 17, 1), 5: (7, 7, 0),
                   6: (26, 26, 0), 7: (25, 25, 0)}


def _position_digest(positions: set[tuple[int, int]]) -> str:
    payload = json.dumps(sorted(positions), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


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
        expected = {(bar, beat): text for bar, beat, text in read_gp_free_text(reference)}
        actual = {(bar, beat): text for bar, beat, text in read_gp_free_text(output)}
        missing, extra = set(expected) - set(actual), set(actual) - set(expected)
        assert (len(expected), len(actual), len(missing)) == EXPECTED_COUNTS[number]
        assert _position_digest(missing) == EXPECTED_MISSING_DIGEST[number]
        assert _position_digest(extra) == EMPTY_POSITIONS
        assert all(expected[position] == actual[position] for position in set(expected) & set(actual))
        if number == 3:
            assert compare_gp_free_text(reference, output) == []
