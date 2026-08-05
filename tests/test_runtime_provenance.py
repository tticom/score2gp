import pytest

from pydantic import ValidationError

from score2gp.runtime_provenance import RuntimeProvenanceRecord



def test_runtime_provenance_schema_valid():

    record = RuntimeProvenanceRecord(

        product_sha="abcd123",

        is_dirty=False,

        cli_executable_path="/usr/bin/score2gp",
        child_python_executable_path="/usr/bin/python3",
        python_import_path="/usr/lib/python3.10/site-packages/score2gp",

        exact_command=["score2gp", "convert", "input.pdf"],

        input_classification="pdf-tab-musicxml",

        exit_status=0,

        output_written=True,

        stage="completed",

        structural_counts={"bars": 10, "events": 42}

    )

    assert record.product_sha == "abcd123"

    assert record.is_uncontrolled_runtime is False

    assert record.structural_counts["bars"] == 10



def test_runtime_provenance_is_uncontrolled():

    record = RuntimeProvenanceRecord(

        product_sha="abcd123",

        is_dirty=True,

        cli_executable_path="/usr/bin/score2gp",
        child_python_executable_path="/usr/bin/python3",
        python_import_path="/usr/lib/python3.10/site-packages/score2gp",

        exact_command=["score2gp", "convert", "input.pdf"],

        input_classification="pdf-tab-only",

        exit_status=0,

        output_written=True,

        stage="completed",

    )

    assert record.is_uncontrolled_runtime is True



def test_runtime_provenance_missing_required_fields():

    with pytest.raises(ValidationError):

        RuntimeProvenanceRecord(

            product_sha="abcd123",

            is_dirty=False,

            # missing cli_executable_path
            child_python_executable_path="/usr/bin/python3",
            python_import_path="/usr/lib/python3.10/site-packages/score2gp",

            exact_command=["score2gp", "convert", "input.pdf"],

            input_classification="pdf-tab-musicxml",

            exit_status=0,

            output_written=True,

            stage="completed"

        )



def test_runtime_provenance_mismatch_src_directory():

    record = RuntimeProvenanceRecord(

        product_sha="abcd123",

        is_dirty=False,

        cli_executable_path="/usr/bin/score2gp",
        child_python_executable_path="/usr/bin/python3",
        python_import_path="/home/user/repo/src/score2gp",

        exact_command=["score2gp", "convert", "input.pdf"],

        input_classification="pdf-tab-only",

        exit_status=0,

        output_written=True,

        stage="completed",

    )

    assert record.is_uncontrolled_runtime is True



def test_runtime_provenance_mismatch_different_trees():

    record = RuntimeProvenanceRecord(

        product_sha="abcd123",

        is_dirty=False,

        cli_executable_path="/usr/local/bin/score2gp",
        child_python_executable_path="/opt/custom_env/bin/python3",
        python_import_path="/opt/custom_env/lib/python3.10/site-packages/score2gp",

        exact_command=["score2gp", "convert", "input.pdf"],

        input_classification="pdf-tab-only",

        exit_status=0,

        output_written=True,

        stage="completed",

    )

    assert record.is_uncontrolled_runtime is True

def test_runtime_provenance_clean_source_checkout():
    import score2gp.cli
    from pathlib import Path
    expected_path = str(Path(score2gp.cli.__file__).parent.resolve())

    record = RuntimeProvenanceRecord(
        product_sha="abcd123",
        is_dirty=False,
        cli_executable_path="python3",
        child_python_executable_path="/usr/bin/python3",
        python_import_path=expected_path,
        exact_command=["python3", "-m", "score2gp", "convert", "input.pdf"],
        input_classification="pdf-tab-only",
        exit_status=0,
        output_written=True,
        stage="completed",
    )
    assert record.is_uncontrolled_runtime is False

def test_runtime_provenance_missing_report_fallback():
    record = RuntimeProvenanceRecord(
        product_sha="abcd123",
        is_dirty=False,
        cli_executable_path="python3",
        child_python_executable_path="unknown",
        python_import_path="unknown",
        exact_command=["python3", "-m", "score2gp", "convert", "input.pdf"],
        input_classification="pdf-tab-only",
        exit_status=1,
        output_written=False,
        stage="runtime_probe_failed",
    )
    assert record.is_uncontrolled_runtime is True


def test_sanitize_exact_command():
    from score2gp.runtime_provenance import sanitize_exact_command

    raw_cmd = [
        "python3",
        "scripts/private_e2e_smoke.py",
        "--pdf",
        "/home/tticom/fixtures/private/secret_song.pdf",
        "--musicxml",
        "/home/tticom/fixtures/private/secret_song.mxl",
        "--out",
        "/home/tticom/work/private_output",
    ]
    sanitized = sanitize_exact_command(raw_cmd)
    assert sanitized == [
        "python3",
        "scripts/private_e2e_smoke.py",
        "--pdf",
        "[PRIVATE_INPUT_PATH]",
        "--musicxml",
        "[PRIVATE_INPUT_PATH]",
        "--out",
        "[PRIVATE_OUTPUT_PATH]",
    ]


def test_get_git_info_failsafe(tmp_path):
    from score2gp.runtime_provenance import get_git_info

    # Non-existent directory returns ("unknown", True) without throwing exception
    non_repo = tmp_path / "non_existent_dir"
    non_repo.mkdir()
    sha, is_dirty = get_git_info(repo_root=non_repo)
    assert sha == "unknown"
    assert is_dirty is True


def test_runtime_provenance_versioned_python_interpreter():
    import score2gp.cli
    from pathlib import Path

    expected_path = str(Path(score2gp.cli.__file__).parent.resolve())

    # Versioned Python interpreters like python3.12 or python3.10
    record = RuntimeProvenanceRecord(
        product_sha="abcd123",
        is_dirty=False,
        cli_executable_path="/usr/bin/python3.12",
        child_python_executable_path="/usr/bin/python3.12",
        python_import_path=expected_path,
        exact_command=["python3.12", "-m", "score2gp", "convert", "[PRIVATE_INPUT_PATH]"],
        input_classification="pdf-tab-only",
        exit_status=0,
        output_written=True,
        stage="completed",
    )
    assert record.is_uncontrolled_runtime is False


def test_create_runtime_provenance_record_helper():
    from score2gp.runtime_provenance import create_runtime_provenance_record

    raw_cmd = ["python3", "scripts/private_diagnostic_smoke.py", "--pdf", "/tmp/private/my_score.pdf"]
    rec = create_runtime_provenance_record(
        exact_command=raw_cmd,
        input_classification="pdf-tab-only",
        output_report_path="work/diagnostics.json",
        exit_status=0,
        output_written=True,
        stage="completed",
    )

    assert rec.exact_command == ["python3", "scripts/private_diagnostic_smoke.py", "--pdf", "[PRIVATE_INPUT_PATH]"]
    assert rec.input_classification == "pdf-tab-only"
    assert isinstance(rec.is_dirty, bool)
    assert isinstance(rec.product_sha, str)
