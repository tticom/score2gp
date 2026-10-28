"""Public IR checks runner independence, with no musical fidelity claim."""

import subprocess
import sys
from zipfile import ZipFile

from typer.testing import CliRunner

from score2gp.cli import app


def test_cli_gpif_bytes_are_independent_of_pytest(tmp_path):
    # Mutant: choose legacy when pytest is in sys.modules (including at import
    # time), or when sys.argv names pytest. A fresh child has neither state.
    output = tmp_path / "pytest-output" / "score.gp"
    args = ["write-gp", "fixtures/public/tiny_score.ir.json", "--out", str(output)]
    assert "pytest" in sys.modules
    outside = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", *args], capture_output=True
    )
    assert outside.returncode == 0, outside.stderr
    with ZipFile(output) as package:
        expected = {name: package.read(name) for name in package.namelist()
                    if name.endswith(".gpif")}
    assert expected
    output.unlink()  # A failed write cannot pass by reusing the earlier package.

    under_pytest = CliRunner().invoke(app, args)
    assert under_pytest.exit_code == 0, under_pytest.output
    with ZipFile(output) as package:
        actual = {name: package.read(name) for name in package.namelist()
                  if name.endswith(".gpif")}
    assert actual == expected, "CLI GPIF bytes differ with pytest loaded"
