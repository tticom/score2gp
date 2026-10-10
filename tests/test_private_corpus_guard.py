"""Synthetic skips prove pytest infrastructure only, never musical/domain acceptance.

No private inputs are read or converted here. Real-source acceptance belongs to
the unchanged SCALE-01 assertion and the mounted-corpus CI run.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest


# Independent census examples: do not derive these from the guard's match list.
CORPUS_REASONS = [
    "private source is not mounted",
    "private Lesson-3 corpus not mounted",
    "private corpus not mounted: Lesson-4.pdf, Lesson-4.gp",
    "private corpus absent",
    "mounted private corpus is unavailable: Melodic Soloing Masterclass.pdf",
    "Lesson-7.pdf required for this private-fixture acceptance test.",
    "private lesson corpus absent",
    "private repeat corpus absent",
    "Lesson-5.pdf required for this private-fixture acceptance test.",
    "Lesson-6.pdf required for this private-fixture acceptance test.",
    "mounted private corpus is unavailable",
    "Lesson-6.pdf required to generate Lesson-6_unowned_artifact.json",
    "Lesson-6.pdf required to generate Lesson-6_invalid_artifact.json",
]


def run_skipped_test(tmp_path, source, required=True):
    (tmp_path / "test_probe.py").write_text(source, encoding="utf-8")
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("SCORE2GP_REQUIRE_PRIVATE_CORPUS", None)
    if required:
        env["SCORE2GP_REQUIRE_PRIVATE_CORPUS"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "private_corpus_guard", "-q", "-rs", str(tmp_path)],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )


@pytest.mark.parametrize("reason", CORPUS_REASONS)
def test_every_census_reason_fails_required_run_and_preserves_local_skip(tmp_path, reason):
    source = f"import pytest\ndef test_missing():\n    pytest.skip({reason!r})\n"
    required = run_skipped_test(tmp_path, source)
    assert required.returncode == 1, required.stdout + required.stderr
    assert "private-corpus skips: 1" in required.stdout
    assert "test_probe.py::test_missing" in required.stdout
    assert reason in required.stdout
    local = run_skipped_test(tmp_path, source, required=False)
    assert local.returncode == 0, local.stdout + local.stderr
    assert "1 skipped" in local.stdout


@pytest.mark.parametrize("source,expected_id", [
    ("import pytest\n@pytest.mark.skipif(True, reason='private corpus absent')\ndef test_missing(): pass\n", "test_probe.py::test_missing"),
    ("import pytest\n@pytest.fixture\ndef missing(): pytest.skip('private corpus absent')\ndef test_missing(missing): pass\n", "test_probe.py::test_missing"),
    ("import pytest\npytest.importorskip('fixture_guard_nonexistent_dependency', reason='private corpus absent')\n", "test_probe.py"),
])
def test_setup_and_collection_skips_also_fail(tmp_path, source, expected_id):
    result = run_skipped_test(tmp_path, source)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "private-corpus skips: 1" in result.stdout
    assert expected_id in result.stdout


@pytest.mark.parametrize("reason,classification", [
    ("requires the Windows provider", "legitimate"),
    ("windows-file-lock is the only provider; off-Windows the harness refuses (asserted in the test above)", "legitimate"),
    ("symlink privilege unavailable on Windows", "unrecognised"),
    ("a newly introduced reason", "unrecognised"),
    ("private adjudicated manifest is not mounted (local ignored artefact: build it with scripts/native_slice_reference.py build-manifest, or set SCORE2GP_L3_ORACLE); without it the harness refuses to run, which is asserted in test_native_slice_acceptance.py", "legitimate"),
])
def test_unrelated_skips_remain_allowed_and_are_reported(tmp_path, reason, classification):
    result = run_skipped_test(tmp_path, f"import pytest\ndef test_optional(): pytest.skip({reason!r})\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "private-corpus skips: 0" in result.stdout
    assert f"[{classification}] test_probe.py::test_optional: {reason}" in result.stdout


def test_xfail_is_not_a_corpus_skip(tmp_path):
    result = run_skipped_test(tmp_path, "import pytest\n@pytest.mark.xfail(reason='private corpus absent')\ndef test_known_failure(): assert False\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "private-corpus skips: 0" in result.stdout
    assert "1 xfailed" in result.stdout
