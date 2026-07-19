import pytest

from pydantic import ValidationError

from score2gp.runtime_provenance import RuntimeProvenanceRecord



def test_runtime_provenance_schema_valid():

    record = RuntimeProvenanceRecord(

        product_sha="abcd123",

        is_dirty=False,

        cli_executable_path="/usr/bin/score2gp",

        python_import_path="/usr/lib/python3.10/site-packages/score2gp",

        exact_command="score2gp convert input.pdf",

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

        python_import_path="/usr/lib/python3.10/site-packages/score2gp",

        exact_command="score2gp convert input.pdf",

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

            python_import_path="/usr/lib/python3.10/site-packages/score2gp",

            exact_command="score2gp convert input.pdf",

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

        python_import_path="/home/user/repo/src/score2gp",

        exact_command="score2gp convert input.pdf",

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

        python_import_path="/opt/custom_env/lib/python3.10/site-packages/score2gp",

        exact_command="score2gp convert input.pdf",

        input_classification="pdf-tab-only",

        exit_status=0,

        output_written=True,

        stage="completed",

    )

    assert record.is_uncontrolled_runtime is True
