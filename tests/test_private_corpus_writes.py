"""Filesystem infrastructure probes; synthetic bytes make no musical claims."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("operation", [
    "target.write_text('artifact')",
    "target.write_bytes(b'original')",  # even an identical overwrite is forbidden
    "target.open('a').close()",
    "os.close(os.open(target, os.O_WRONLY))",
    "target.unlink()",
    "target.rename(corpus / 'renamed')",
    "(corpus / 'new-directory').mkdir()",
    "(corpus / '..' / 'corpus' / 'input').write_text('artifact')",
    "exec(\"try:\\n    target.write_bytes(b'original')\\nexcept PermissionError:\\n    pass\")",
    "Path('outside').write_text('incoming'); os.replace('outside', target)",
    "subprocess.run([sys.executable, '-c', "
    "\"from pathlib import Path; Path('corpus/input').write_text('child')\"], check=True)",
])
def test_private_corpus_write_fails_pytest(tmp_path, operation):
    """Reject the mutant that removes write enforcement, including child writes."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "input").write_bytes(b"original")
    (tmp_path / "test_probe.py").write_text(
        "import os, subprocess, sys\nfrom pathlib import Path\n"
        "def test_write():\n    corpus = Path('corpus')\n"
        "    target = corpus / 'input'\n    " + operation + "\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "private_corpus_guard", "-q",
         "-o", f"private_corpus_roots={corpus}", "test_probe.py"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "private-corpus writes:" in result.stdout
    if operation.startswith("subprocess.run"):
        assert "1 files changed" in result.stdout
    else:
        assert "test_probe.py::test_write" in result.stdout


def test_compiler_artifacts_use_requested_scratch_directory(tmp_path, monkeypatch):
    """Reject restoring _ensure_fixture's old corpus output destination.

    Stub recognition only: this checks artifact placement, not recognition.
    Existing real Lesson-6 tests retain all their domain assertions.
    """
    from test_scoreir_gpif_compiler_refactor import _ensure_fixture

    monkeypatch.setattr("score2gp.notation_omr.pipeline.run_recognition_on_file", lambda *a, **k: {})
    for name in ("Lesson-6_unowned_artifact.json", "Lesson-6_invalid_artifact.json"):
        result = _ensure_fixture(name, tmp_path)
        assert result == tmp_path / name
        assert result.is_file()
