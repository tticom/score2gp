from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Add scripts to sys.path so we can import from it
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import artifact_audit


def test_artifact_audit_pass(monkeypatch) -> None:
    # Set up mock files that pass the audit rules
    mock_files = [
        "src/score2gp/notation_bridge.py",
        "tests/test_notation_bridge.py",
        "fixtures/private/.gitkeep",
        "fixtures/public/tiny_score.ir.json",
        "schemas/scoreir.v0.1.schema.json",
        ".gitignore",
        "pyproject.toml",
        ".antigravitycli/tool-definitions.json",
        "tests/fixtures/pdf/overlays/example.png",
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    # Calling main should succeed and not raise SystemExit with error
    try:
        artifact_audit.main()
    except SystemExit as e:
        assert e.code == 0


def test_artifact_audit_fails_private_fixture(monkeypatch) -> None:
    # Set up mock files with a violating private fixture
    mock_files = [
        "src/score2gp/notation_bridge.py",
        "fixtures/private/Lesson-3.pdf",  # Violator!
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    with pytest.raises(SystemExit) as exc_info:
        artifact_audit.main()
    assert exc_info.value.code == 1


def test_artifact_audit_fails_work_dir(monkeypatch) -> None:
    # Set up mock files with a tracked file in work/
    mock_files = [
        "src/score2gp/notation_bridge.py",
        "work/private/debug_report.json",  # Violator!
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    with pytest.raises(SystemExit) as exc_info:
        artifact_audit.main()
    assert exc_info.value.code == 1


def test_artifact_audit_fails_banned_root_artifact(monkeypatch) -> None:
    # Set up mock files with a root warnings.json
    mock_files = [
        "src/score2gp/notation_bridge.py",
        "warnings.json",  # Violator!
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    with pytest.raises(SystemExit) as exc_info:
        artifact_audit.main()
    assert exc_info.value.code == 1


def test_artifact_audit_fails_json_outside_allowlist(monkeypatch) -> None:
    # Set up mock files with a JSON file outside allowed paths
    mock_files = [
        "src/score2gp/notation_bridge.py",
        "src/some_other_folder/bad_config.json",  # Violator!
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    with pytest.raises(SystemExit) as exc_info:
        artifact_audit.main()
    assert exc_info.value.code == 1


@pytest.mark.parametrize("path", ["analysis.ir.json", "analysis.tabraw.json"])
def test_artifact_audit_fails_root_generated_score_json(monkeypatch, path: str) -> None:
    mock_files = [
        "src/score2gp/notation_bridge.py",
        path,
    ]

    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: mock_files)

    with pytest.raises(SystemExit) as exc_info:
        artifact_audit.main()
    assert exc_info.value.code == 1


@pytest.mark.parametrize("path", [
    "reference/tab-notation-reference-images/2026-06-09/Arpeggiated Chord.png",
    "reference/tab-notation-reference-images/2026-06-09/probe.PNG",  # extension case must not bypass the ban
    "reference/tab-notation-reference-images/2026-06-09/probe.Png",
])
def test_artifact_audit_rejects_third_party_reference_images(monkeypatch, path) -> None:
    # Third-party reference images belong in the private corpus, not this repository.
    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: ["fixtures/private/.gitkeep", path])
    with pytest.raises(SystemExit) as exc:
        artifact_audit.main()
    assert exc.value.code != 0


@pytest.mark.parametrize("path", [
    "diagnostics/report.HTML",
    "work2/out.JSON",
    "fixtures/private/Song.PDF",
    "fixtures/private/Song.GPX",
    "Result.IR.JSON",
])
def test_artifact_audit_extension_checks_ignore_case(monkeypatch, path) -> None:
    monkeypatch.setattr(artifact_audit, "run_cmd", lambda args: ["fixtures/private/.gitkeep", path])
    with pytest.raises(SystemExit) as exc:
        artifact_audit.main()
    assert exc.value.code != 0
