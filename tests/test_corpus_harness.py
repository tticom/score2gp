import json

from pathlib import Path

from unittest.mock import patch, MagicMock

import pytest

import shutil

import sys



from scripts.corpus_harness import run_pipeline_for_input, resolve_score2gp_cmd, anonymize_name



def test_resolve_score2gp_cmd():
    with patch("pathlib.Path.exists") as mock_exists:
        # Test Priority 1: .venv/bin/score2gp
        mock_exists.return_value = True
        cmd = resolve_score2gp_cmd()
        assert cmd[1] == "convert"
        assert "score2gp" in cmd[0]

        # Test Priority 2: shutil.which fallback
        mock_exists.return_value = False
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/mock/bin/score2gp"
            cmd = resolve_score2gp_cmd()
            assert cmd == ["/mock/bin/score2gp", "convert"]

def test_real_invocation_smoke():
    """Real invocation smoke test verifying the CLI entrypoint can execute successfully."""
    cmd = resolve_score2gp_cmd()

    # We replace 'convert' with '--help' to ensure we do a clean fast-exit test
    # instead of a conversion run.
    smoke_cmd = [cmd[0], "convert", "--help"]
    import subprocess
    result = subprocess.run(
        smoke_cmd,
        capture_output=True,
        text=True,
        check=False
    )

    # Assert successful invocation
    assert result.returncode == 0
    import re
    clean_stdout = re.sub(r'\x1b\[.*?m', '', result.stdout)
    assert "convert" in clean_stdout.lower()

def test_anonymize_name_collision():
    """Ensure two different unknown inputs generate deterministic, collision-resistant labels."""
    paths = [
        Path("Derek Trucks BB King.pdf"),
        Path("Lick in All 5 CAGED Shapes start on the 5 _ guitar tab creator.pdf"),
        Path("Lesson-3.pdf"),
        Path("Lesson-4.pdf"),
        Path("Melodic Soloing Masterclass.pdf"),
        Path("unknown_input_a.pdf"),
        Path("unknown_input_b.pdf")
    ]

    labels = [anonymize_name(p) for p in paths]

    for label in labels:
        assert label.startswith("private_input_")

    assert len(labels) == len(set(labels))



@patch("subprocess.run")

def test_run_pipeline_for_input(mock_run, tmp_path):

    pdf_path = tmp_path / "test_input.pdf"

    pdf_path.touch()



    musicxml_path = tmp_path / "test_input.musicxml"

    musicxml_path.write_text("<score-partwise/>")



    output_base = tmp_path / "work"



    def side_effect(cmd, *args, **kwargs):

        # find work_dir from cmd

        work_dir = None

        for i, arg in enumerate(cmd):

            if arg == "--work-dir":

                work_dir = Path(cmd[i+1])

        if work_dir:

            work_dir.mkdir(parents=True, exist_ok=True)

            report_path = work_dir / "convert-report.json"

            report_path.write_text(json.dumps({

                "stage": "completed",

                "output_written": True,

                "cli_executable_path": "/mock/bin/score2gp",
                "child_python_executable_path": "/mock/bin/python3",
                "python_import_path": "/mock/lib/python3.10/site-packages/score2gp",

                "summary_counts": {

                    "bar_count": 10,

                    "event_count": 42,

                    "warning_count": 0

                },

                "musicxml_sidecar_info": {

                    "path": str(musicxml_path),

                    "sha256": "abcdef",

                    "generation_provenance": "supplied"

                }

            }))

        mock_res = MagicMock()

        mock_res.returncode = 0

        mock_res.stdout = "mock stdout"

        mock_res.stderr = "mock stderr"

        return mock_res



    mock_run.side_effect = side_effect



    summary = run_pipeline_for_input(pdf_path, musicxml_path, output_base)



    # Assert sidecar handling

    assert summary["exit_status"] == 0

    assert summary["output_written"] is True



    label = summary["input_label"]

    provenance_path = output_base / label / "provenance_record.json"

    assert provenance_path.exists()



    prov_data = json.loads(provenance_path.read_text())



    # Assert actual-runtime capture
    assert prov_data["child_python_executable_path"] == "/mock/bin/python3"
    assert prov_data["python_import_path"] == "/mock/lib/python3.10/site-packages/score2gp"



    # Assert output/report paths
    assert prov_data["output_report_path"] == str((output_base / label / "convert-report.json").resolve())
    assert prov_data["gp_output_path"] == str((output_base / label / "smoke.gp").resolve())



    # Assert unknown counts are correctly passed

    assert prov_data["structural_counts"]["source_rests"] == "unknown"

    assert prov_data["structural_counts"]["emitted_rests"] == "unknown"

    assert prov_data["structural_counts"]["bars"] == 10



    # Assert sidecar hashing/provenance from report

    assert prov_data["musicxml_sidecar_info"]["sha256"] == "abcdef"

    assert prov_data["musicxml_sidecar_info"]["generation_provenance"] == "supplied"



    # Verify command construction (ensure canonical command without skip-unboxed etc)

    score2gp_call = None

    for call in mock_run.call_args_list:

        if "--pdf" in call[0][0]:

            score2gp_call = call[0][0]

            break



    assert score2gp_call is not None

    assert "--pdf" in score2gp_call

    assert "--allow-remediation" not in score2gp_call
    assert "--allow-skip-unboxed-systems" not in score2gp_call

@patch("subprocess.run")
def test_run_pipeline_missing_report(mock_run, tmp_path):
    pdf_path = tmp_path / "test_input.pdf"
    pdf_path.touch()

    output_base = tmp_path / "work"

    def side_effect(cmd, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stdout = "mock stdout"
        mock_res.stderr = "Traceback ModuleNotFoundError"
        return mock_res

    mock_run.side_effect = side_effect

    summary = run_pipeline_for_input(pdf_path, None, output_base)

    label = summary["input_label"]
    provenance_path = output_base / label / "provenance_record.json"
    prov_data = json.loads(provenance_path.read_text())

    assert prov_data["cli_executable_path"] == resolve_score2gp_cmd()[0]
    assert prov_data["child_python_executable_path"] == "unknown"
    assert prov_data["python_import_path"] == "unknown"
    assert prov_data["stage"] == "runtime_probe_failed"
    assert prov_data["musicxml_sidecar_info"] == {"provenance": "absent"}
