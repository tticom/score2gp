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
