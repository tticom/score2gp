"""Real-source technique placement through the normal packaged CLI output."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
SOURCE = "Can't Find My Way Home (open chord shenanigans)"


def _oracle():
    spec = importlib.util.spec_from_file_location("fu5_oracle", ROOT / "tests/test_dur_02_oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_source_techniques_survive_notation_bar_placement():
    """Reject the old whole-TAB-system key mapping which drops every technique."""
    pdf = PRIVATE / (SOURCE + ".pdf")
    reference = PRIVATE / (SOURCE + ".gp")
    assert pdf.is_file() and reference.is_file()
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="dur02fu5-", dir=work) as directory:
        scratch = Path(directory)
        output = scratch / "result.gp"
        run = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
            "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
            "--work-dir", str(scratch / "build"),
        ], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        oracle = _oracle()
        result = oracle.compare_gp(reference, output)
        assert result["written_bars"] == 18
        assert result["refused_bars"] == [3, 6, 9]
        differences = [(d["bar_index"], d["event_index"], d["field"])
                       for d in result["differences"] if d["field"] in oracle.TECHNIQUE_FIELDS]
        assert differences == []
