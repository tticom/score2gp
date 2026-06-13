import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import importlib.util

def load_script():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    spec = importlib.util.spec_from_file_location("gate_report", script_path)
    gate_report = importlib.util.module_from_spec(spec)
    sys.modules["gate_report"] = gate_report
    spec.loader.exec_module(gate_report)
    return gate_report

def test_manifest_schema_and_safety():
    manifest_path = Path(__file__).parent / "fixtures" / "raster_diagnostics_false_negative_manifest.json"
    assert manifest_path.exists(), "Manifest file must exist"

    with open(manifest_path, "r") as f:
        text = f.read()

    # Check for unsafe strings in the entire JSON text
    unsafe_strings = [
        ".pdf", "fixtures/private", "screenshot", ".gp", ".jpg", ".png", "output"
    ]
    for unsafe in unsafe_strings:
        assert unsafe not in text.lower(), f"Unsafe string '{unsafe}' found in manifest"

    data = json.loads(text)

    # Check top-level fields
    assert "schema_version" in data
    assert "source" in data
    assert "false_negative_cases" in data

    cases = data["false_negative_cases"]
    assert len(cases) > 0

    seen_ids = set()
    for case in cases:
        case_id = case["case_id"]
        assert case_id not in seen_ids, f"Duplicate case_id: {case_id}"
        seen_ids.add(case_id)
        assert "file_sha256" in case

def test_classify_case_result():
    gate_report = load_script()
    helper = gate_report.classify_case_result

    # Expected positive cases
    assert helper(expected_positive=True, known_false_negative=False, candidates=1) == "true_positive"
    assert helper(expected_positive=True, known_false_negative=True, candidates=1) == "true_positive"
    assert helper(expected_positive=True, known_false_negative=True, candidates=0) == "known_false_negative"
    assert helper(expected_positive=True, known_false_negative=False, candidates=0) == "unexpected_false_negative"

    # Expected negative cases
    assert helper(expected_positive=False, known_false_negative=False, candidates=0) == "true_negative"
    assert helper(expected_positive=False, known_false_negative=False, candidates=1) == "false_positive"

def test_gate_report_aggregation_and_privacy(capsys):
    import builtins
    gate_report = load_script()

    sha_known_fn = "hash_known_fn"
    sha_unexpected_fn = "hash_unexpected_fn"
    sha_true_pos = "hash_true_pos"

    mock_manifest_json = {
        "false_negative_cases": [
            {
                "case_id": "case_known_fn",
                "file_sha256": sha_known_fn,
                "expected_positive": True,
                "safe_category": "currently_verified_false_negative"
            },
            {
                "case_id": "case_unexpected_fn",
                "file_sha256": sha_unexpected_fn,
                "expected_positive": True,
                "safe_category": "currently_verified_true_positive"
            },
            {
                "case_id": "case_true_pos",
                "file_sha256": sha_true_pos,
                "expected_positive": True,
                "safe_category": "currently_verified_true_positive"
            },
            {
                "case_id": "case_skipped",
                "file_sha256": "hash_skipped",
                "expected_positive": True,
                "safe_category": "currently_verified_true_positive"
            }
        ]
    }

    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0, # TN
            "unknown": 1,
            "pages": 1,
        },
        "generated_standard_staff_negative_tab.pdf": {
            "staff_count": 0,
            "treble_clef_candidate": 0, # TN
            "unknown": 0,
            "pages": 1,
        },
        "generated_standard_staff_negative_noise.pdf": {
            "staff_count": 0,
            "treble_clef_candidate": 1, # Fake false positive
            "unknown": 0,
            "pages": 1,
        },
        "fake_known_fn.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0, # Known FN
            "unknown": 0,
            "pages": 1,
        },
        "fake_unexpected_fn.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0, # Unexpected FN!
            "unknown": 0,
            "pages": 1,
        },
        "fake_true_pos.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 1, # True Positive
            "unknown": 0,
            "pages": 1,
        },
        "extra_private_not_in_manifest.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0,
            "unknown": 0,
            "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    def mock_compute_sha256(path: Path):
        if path.name == "fake_known_fn.pdf": return sha_known_fn
        if path.name == "fake_unexpected_fn.pdf": return sha_unexpected_fn
        if path.name == "fake_true_pos.pdf": return sha_true_pos
        if path.name == "extra_private_not_in_manifest.pdf": return "dummy_hash"
        return "other_hash"

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster_diagnostics_false_negative_manifest.json": return True
        if self.name == "raster-treble-clef": return True
        if self.name in mock_returns: return True
        return orig_exists(self)

    orig_glob = Path.glob
    def custom_glob(self, pattern):
        if self.name == "raster-treble-clef":
            return [
                Path("fixtures/private/raster-treble-clef/fake_known_fn.pdf"),
                Path("fixtures/private/raster-treble-clef/fake_unexpected_fn.pdf"),
                Path("fixtures/private/raster-treble-clef/fake_true_pos.pdf"),
                Path("fixtures/private/raster-treble-clef/extra_private_not_in_manifest.pdf"),
            ]
        return orig_glob(self, pattern)

    import builtins
    orig_open = builtins.open
    def custom_open(file, *args, **kwargs):
        if str(file).endswith("raster_diagnostics_false_negative_manifest.json"):
            import io
            return io.StringIO(json.dumps(mock_manifest_json))
        return orig_open(file, *args, **kwargs)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch("gate_report.compute_sha256", side_effect=mock_compute_sha256):
            with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
                with patch.object(Path, "glob", autospec=True, side_effect=custom_glob):
                    with patch("builtins.open", side_effect=custom_open):
                        gate_status, totals = gate_report.generate_report()

    assert totals["false_positives"] == 1
    assert totals["known_false_negatives"] == 1
    assert totals["unexpected_false_negatives"] == 1
    assert totals["true_positives"] == 1
    assert totals["total_cases_inspected"] == 6
    assert totals["skipped_optional_private_fixtures"] == 1
    assert totals["negative_fixture_outcomes"] == 2

    captured = capsys.readouterr()

    # Check that anonymised case IDs are logged, not the raw filenames
    assert "fake_known_fn.pdf" not in captured.out
    assert "fake_unexpected_fn.pdf" not in captured.out
    assert "fake_true_pos.pdf" not in captured.out
    assert "extra_private_not_in_manifest.pdf" not in captured.out

    assert "MATCHED KNOWN FALSE NEGATIVE MANIFEST ENTRY: case_known_fn" in captured.out
    assert "UNEXPECTED FALSE NEGATIVE: case_unexpected_fn" in captured.out
    assert "Skipping missing optional private fixture: case_skipped" in captured.out
    assert "True Positives             : 1" in captured.out
    assert "Gate Status: REVIEW" in captured.out

def test_unreadable_private_fixture(capsys):
    gate_report = load_script()

    def mock_run(path: Path, display_label=None):
        # Trigger the internal failure logic to return None
        return None

    def mock_compute_sha256(path: Path):
        return "53785c550a699cab31aa973e4278c086050ac7ac8b030a8edcbc00aa3942300e"

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster-treble-clef": return True
        if self.name == "unreadable_private.pdf": return True
        return orig_exists(self)

    orig_glob = Path.glob
    def custom_glob(self, pattern):
        if self.name == "raster-treble-clef":
            return [
                Path("fixtures/private/raster-treble-clef/unreadable_private.pdf"),
            ]
        return orig_glob(self, pattern)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch("gate_report.compute_sha256", side_effect=mock_compute_sha256):
            with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
                with patch.object(Path, "glob", autospec=True, side_effect=custom_glob):
                    gate_report.generate_report()

    captured = capsys.readouterr()

    # unreadable_private.pdf shouldn't be printed anywhere
    assert "unreadable_private.pdf" not in captured.err
    assert "unreadable_private.pdf" not in captured.out
    assert "Error processing fn_private_positive_001" in captured.err

def test_run_diagnostics_on_file_privacy(capsys):
    gate_report = load_script()
    import fitz

    def mock_open(*args, **kwargs):
        raise Exception("cannot open fixtures/private/raster-treble-clef/secret_path.pdf")

    with patch.object(fitz, "open", side_effect=mock_open):
        with patch.object(Path, "exists", return_value=True):
            p = Path("fixtures/private/raster-treble-clef/secret_path.pdf")
            gate_report.run_diagnostics_on_file(p, display_label="safe_label")

    captured = capsys.readouterr()
    assert "fixtures/private/raster-treble-clef/secret_path.pdf" not in captured.err
    assert "secret_path.pdf" not in captured.err
    assert "safe_label" in captured.err

def test_gate_status_pass(capsys):
    gate_report = load_script()

    # Create a perfectly clean scenario
    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_tab.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_noise.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_whole_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 1, "whole_note_candidate_summary": {"total_count": 1}, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_half_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 0, "whole_note_candidate_summary": {"total_count": 0}, "unknown": 0, "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    orig_exists = Path.exists
    def custom_exists(self):
        # Prevent picking up real private fixtures
        if self.name == "raster-treble-clef": return False
        if self.name == "raster_diagnostics_false_negative_manifest.json": return False
        if self.name in mock_returns: return True
        return orig_exists(self)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
            gate_report.generate_report()

    captured = capsys.readouterr()
    assert "Gate Status: PASS" in captured.out
    assert "Whole-note fixture outcome summary" in captured.out
    assert "Whole-note detection status: pass" in captured.out
    assert "Whole-note detection status reasons: positive_candidates_complete, no_false_positive_candidates" in captured.out
    assert "Positive whole-note fixtures evaluated: 1" in captured.out
    assert "Positive fixtures with candidates: 1" in captured.out
    assert "Half-note fixtures evaluated: 1" in captured.out
    assert "Half-note fixtures with false-positive whole-note candidates: 0" in captured.out

def test_classify_whole_note_outcome():
    gate_report = load_script()
    helper = gate_report.classify_whole_note_outcome

    # Positive
    assert helper("positive_whole_note", "file.pdf", 1) == "whole_note_true_positive"
    assert helper("positive_whole_note", "file.pdf", 0) == "whole_note_false_negative"
    assert helper("other_category", "whole_note_file.pdf", 1) == "whole_note_true_positive"

    # Half note
    assert helper("half_note", "file.pdf", 0) == "whole_note_true_negative"
    assert helper("half_note", "file.pdf", 1) == "whole_note_false_positive"
    assert helper("other_category", "half_note_file.pdf", 0) == "whole_note_true_negative"

    # Negative/noise
    assert helper("negative_blank", "file.pdf", 0) == "whole_note_true_negative"
    assert helper("negative_noise", "file.pdf", 1) == "whole_note_false_positive"

    # Not applicable
    assert helper("positive_private", "file.pdf", 1) == "whole_note_not_applicable"
    assert helper("positive_private", "file.pdf", 0) == "whole_note_not_applicable"



def test_gate_status_json_mode(capsys):
    gate_report = load_script()
    import json

    # Create a perfectly clean scenario
    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_tab.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_noise.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_whole_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 1, "whole_note_candidate_summary": {"total_count": 1}, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_half_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 0, "whole_note_candidate_summary": {"total_count": 0}, "unknown": 0, "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster-treble-clef": return False
        if self.name == "raster_diagnostics_false_negative_manifest.json": return False
        if self.name in mock_returns: return True
        return orig_exists(self)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
            gate_report.generate_report(json_mode=True)

    captured = capsys.readouterr()
    assert "Gate Status: PASS" not in captured.out
    assert "Raster Diagnostics Gate Report" not in captured.out

    # Verify it is parseable JSON
    output_json = json.loads(captured.out)
    assert output_json["schema_version"] == 1
    assert output_json["gate_status"] == "PASS"
    assert "totals" in output_json
    assert "categories" in output_json
    assert "cases" in output_json
    assert "whole_note_detection_status" in output_json
    assert output_json["whole_note_detection_status"] == "pass"
    assert "whole_note_detection_status_reasons" in output_json
    assert output_json["whole_note_detection_status_reasons"] == ["positive_candidates_complete", "no_false_positive_candidates"]

    assert output_json["totals"]["false_positives"] == 0
    assert output_json["totals"]["unexpected_false_negatives"] == 0
    assert len(output_json["cases"]) == 5

    assert "whole_note_fixture_outcome_summary" in output_json
    wn_summary = output_json["whole_note_fixture_outcome_summary"]
    assert wn_summary["negative_noise_fixtures_evaluated"] == 3
    assert wn_summary["negative_noise_fixtures_with_false_positive_candidates"] == 0
    assert wn_summary["positive_fixtures_evaluated"] == 1
    assert wn_summary["positive_fixtures_with_candidates"] == 1
    assert wn_summary["half_note_fixtures_evaluated"] == 1
    assert wn_summary["half_note_fixtures_with_false_positive_candidates"] == 0

    for case in output_json["cases"]:
        assert "case_id" in case
        assert "whole_note_candidate" in case
        assert "pdf" in case["case_id"] # for standard negative tests, it's the filename

def test_gate_status_json_mode_review_and_privacy(capsys):
    gate_report = load_script()
    import json

    mock_manifest_json = {
        "schema_version": 1,
        "false_negative_cases": [
            {
                "case_id": "case_known_fn",
                "file_sha256": "sha_known_fn",
                "safe_category": "currently_verified_false_negative",
                "expected_positive": True
            },
            {
                "case_id": "case_unexpected_fn",
                "file_sha256": "sha_unexpected_fn",
                "safe_category": "unrelated",
                "expected_positive": True
            }
        ]
    }

    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_tab.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_negative_noise.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "fake_known_fn.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "fake_unexpected_fn.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    def mock_compute_sha256(path: Path):
        if path.name == "fake_known_fn.pdf": return "sha_known_fn"
        if path.name == "fake_unexpected_fn.pdf": return "sha_unexpected_fn"
        return "other_hash"

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster_diagnostics_false_negative_manifest.json": return True
        if self.name == "raster-treble-clef": return True
        if self.name in mock_returns: return True
        return orig_exists(self)

    orig_glob = Path.glob
    def custom_glob(self, pattern):
        if self.name == "raster-treble-clef":
            return [
                Path("fixtures/private/raster-treble-clef/fake_known_fn.pdf"),
                Path("fixtures/private/raster-treble-clef/fake_unexpected_fn.pdf"),
            ]
        return orig_glob(self, pattern)

    import builtins
    orig_open = builtins.open
    def custom_open(file, *args, **kwargs):
        if str(file).endswith("raster_diagnostics_false_negative_manifest.json"):
            import io
            return io.StringIO(json.dumps(mock_manifest_json))
        return orig_open(file, *args, **kwargs)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch("gate_report.compute_sha256", side_effect=mock_compute_sha256):
            with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
                with patch.object(Path, "glob", autospec=True, side_effect=custom_glob):
                    with patch("builtins.open", side_effect=custom_open):
                        gate_report.generate_report(json_mode=True)

    captured = capsys.readouterr()
    output_json = json.loads(captured.out)

    assert output_json["gate_status"] == "REVIEW"
    assert output_json["totals"]["known_false_negatives"] == 1
    assert output_json["totals"]["unexpected_false_negatives"] == 1

    # Verify privacy
    raw_str = captured.out
    assert "fake_known_fn.pdf" not in raw_str
    assert "fake_unexpected_fn.pdf" not in raw_str
    assert "raster-treble-clef" not in raw_str

    # Check that case_id is an anonymized string or case_id
    case_ids = [c["case_id"] for c in output_json["cases"]]
    assert "case_known_fn" in case_ids
    assert "whole_note_candidate" in output_json["cases"][0]


def test_cli_check_mode_pass(monkeypatch, capsys):
    gate_report = load_script()

    # Create a clean scenario
    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_whole_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 1, "whole_note_candidate_summary": {"total_count": 1}, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_half_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 0, "whole_note_candidate_summary": {"total_count": 0}, "unknown": 0, "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster-treble-clef": return False
        if self.name == "raster_diagnostics_false_negative_manifest.json": return False
        if self.name in mock_returns: return True
        return orig_exists(self)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
            # Test --check when status is PASS
            monkeypatch.setattr(sys, "argv", ["raster_diagnostics_gate_report.py", "--check"])
            with patch("sys.exit") as mock_exit:
                # We need to execute the __main__ block logic, so we just run the script module
                # But since it's already loaded, we can run the logic manually or reload.
                # It's easier to simulate the parsing.
                parser = gate_report.argparse.ArgumentParser()
                parser.add_argument("--json", action="store_true")
                parser.add_argument("--check", action="store_true")
                args = parser.parse_args(["--check"])

                status, totals = gate_report.generate_report(json_mode=args.json)
                if args.check:
                    mock_exit(0 if status == "PASS" else 1)

                mock_exit.assert_called_once_with(0)


def test_cli_check_mode_review(monkeypatch, capsys):
    gate_report = load_script()

    # Create a failure scenario
    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1, "treble_clef_candidate": 1, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_whole_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 1, "whole_note_candidate_summary": {"total_count": 1}, "unknown": 0, "pages": 1,
        },
        "generated_standard_staff_half_note.pdf": {
            "staff_count": 1, "treble_clef_candidate": 0, "whole_note_candidate": 0, "whole_note_candidate_summary": {"total_count": 0}, "unknown": 0, "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster-treble-clef": return False
        if self.name == "raster_diagnostics_false_negative_manifest.json": return False
        if self.name in mock_returns: return True
        return orig_exists(self)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
            # Test --check when status is REVIEW
            parser = gate_report.argparse.ArgumentParser()
            parser.add_argument("--json", action="store_true")
            parser.add_argument("--check", action="store_true")
            args = parser.parse_args(["--check", "--json"])

            with patch("sys.exit") as mock_exit:
                status, totals = gate_report.generate_report(json_mode=args.json)
                if args.check:
                    mock_exit(0 if status == "PASS" else 1)

                mock_exit.assert_called_once_with(1)

            # Ensure parseable JSON and no raw paths
            captured = capsys.readouterr()
            output_json = json.loads(captured.out)
            assert output_json["gate_status"] == "REVIEW"
            assert output_json["totals"]["false_positives"] == 1

import subprocess

def test_subprocess_human_mode_pass():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Gate Status: PASS" in result.stdout
    assert "Raster Diagnostics Gate Report" in result.stdout
    assert "Whole-note fixture outcome summary" in result.stdout
    assert "Whole-note detection status: pass" in result.stdout
    assert "Whole-note detection status reasons: positive_candidates_complete, no_false_positive_candidates" in result.stdout
    assert "Positive whole-note fixtures evaluated: 1" in result.stdout
    assert "Half-note fixtures evaluated: 1" in result.stdout

def test_subprocess_json_mode_pass():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--json"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    # Should be valid JSON
    data = json.loads(result.stdout)
    assert data["gate_status"] == "PASS"
    assert data["schema_version"] == 1
    assert "Raster Diagnostics Gate Report" not in result.stdout

def test_subprocess_check_mode_pass():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--check"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Gate Status: PASS" in result.stdout

def test_subprocess_json_check_mode_pass():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--json", "--check"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    # Should be valid JSON
    data = json.loads(result.stdout)
    assert data["gate_status"] == "PASS"


def test_subprocess_check_mode_review_with_test_manifest(tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    manifest_data = [
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_blank.pdf",
            "category": "test_category",
            "expected_positive": True,
            "known_false_negative": False,
            "case_id": "test_unexpected_fn"
        }
    ]
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    result = subprocess.run(
        [sys.executable, str(script_path), "--check", "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1
    assert "Gate Status: REVIEW" in result.stdout
    # Verify no raw paths
    assert "pytest-of" not in result.stdout
    assert str(tmp_path) not in result.stdout
    assert "test_unexpected_fn" in result.stdout


def test_subprocess_json_check_mode_review_with_test_manifest(tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    manifest_data = [
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_blank.pdf",
            "category": "test_category",
            "expected_positive": True,
            "known_false_negative": False,
            "case_id": "test_unexpected_fn"
        }
    ]
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    result = subprocess.run(
        [sys.executable, str(script_path), "--json", "--check", "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1

    # Should be valid JSON
    data = json.loads(result.stdout)
    assert data["gate_status"] == "REVIEW"
    assert data["totals"]["unexpected_false_negatives"] == 1

    assert "pytest-of" not in result.stdout
    assert str(tmp_path) not in result.stdout


def test_subprocess_test_manifest_rejects_private_without_leaking(tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    private_path = "fixtures/private/some_secret.pdf"
    manifest_data = [
        {
            "path": private_path,
            "category": "test_category",
            "expected_positive": True,
            "known_false_negative": False,
            "case_id": "test_private"
        }
    ]
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    result = subprocess.run(
        [sys.executable, str(script_path), "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert "Warning: Rejecting unsafe test manifest path" in result.stderr
    assert private_path not in result.stderr
    assert private_path not in result.stdout

def test_subprocess_test_manifest_rejects_absolute_without_leaking(tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    abs_path = "/etc/passwd"
    manifest_data = [
        {
            "path": abs_path,
            "category": "test_category",
            "expected_positive": True,
            "known_false_negative": False,
            "case_id": "test_abs"
        }
    ]
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    result = subprocess.run(
        [sys.executable, str(script_path), "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert "Warning: Rejecting unsafe test manifest path" in result.stderr
    assert abs_path not in result.stderr
    assert abs_path not in result.stdout

def test_subprocess_test_manifest_bad_json_without_leaking(tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    with open(manifest_path, "w") as f:
        f.write("{ bad json }")

    result = subprocess.run(
        [sys.executable, str(script_path), "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1
    assert "Error loading test manifest: Invalid or missing manifest" in result.stderr
    assert str(manifest_path) not in result.stderr

def test_whole_note_fixture_outcome_summary_json(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"

    manifest_path = tmp_path / "test_manifest.json"
    manifest_data = [
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_whole_note.pdf",
            "category": "positive_whole_note",
            "expected_positive": False,
            "known_false_negative": False,
            "case_id": "generated_standard_staff_whole_note.pdf"
        },
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_half_note.pdf",
            "category": "half_note",
            "expected_positive": False,
            "known_false_negative": False,
            "case_id": "generated_standard_staff_half_note.pdf"
        },
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf",
            "category": "negative_noise",
            "expected_positive": False,
            "known_false_negative": False,
            "case_id": "generated_standard_staff_negative_noise.pdf"
        }
    ]
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    result = subprocess.run(
        [sys.executable, str(script_path), "--json", "--test-manifest", str(manifest_path)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "whole_note_fixture_outcome_summary" in data
    summary = data["whole_note_fixture_outcome_summary"]

    assert summary["positive_fixtures_evaluated"] == 1
    assert summary["positive_fixtures_with_candidates"] == 1
    assert summary["positive_fixtures_without_candidates"] == 0

    assert summary["half_note_fixtures_evaluated"] == 1
    assert summary["half_note_fixtures_with_false_positive_candidates"] == 0

    assert summary["negative_noise_fixtures_evaluated"] == 1
    assert summary["negative_noise_fixtures_with_false_positive_candidates"] == 0

    cases = {c["case_id"]: c for c in summary["cases"]}

    assert cases["generated_standard_staff_whole_note.pdf"]["whole_note_outcome"] == "whole_note_true_positive"
    assert cases["generated_standard_staff_half_note.pdf"]["whole_note_outcome"] == "whole_note_true_negative"
    assert cases["generated_standard_staff_negative_noise.pdf"]["whole_note_outcome"] == "whole_note_true_negative"

    raw_cases = {c["case_id"]: c for c in data["cases"]}
    for case_id, raw_case in raw_cases.items():
        wn_summary = raw_case.get("whole_note_candidate_summary", {})
        total_count = wn_summary.get("total_count", 0)
        assert cases[case_id]["whole_note_candidate_summary_total_count"] == total_count

    json_str = result.stdout.lower()
    assert "scoreir" not in json_str
    assert "gp_output" not in json_str
    assert "guitar_pro" not in json_str
    assert "pitch" not in json_str
    assert "duration" not in json_str
    assert "ocr" not in json_str
    assert "full_notation" not in json_str

    assert "whole_note_detection_status" in data
    assert data["whole_note_detection_status"] == "pass"
    assert "whole_note_detection_status_reasons" in data
    assert "positive_candidates_complete" in data["whole_note_detection_status_reasons"]
    assert "no_false_positive_candidates" in data["whole_note_detection_status_reasons"]

def test_summarize_whole_note_detection_status():
    gate_report = load_script()
    helper = gate_report.summarize_whole_note_detection_status

    # Empty summary
    status, reasons = helper({})
    assert status == "review"
    assert "summary_missing_or_incomplete" in reasons

    # Pass scenario
    status, reasons = helper({
        "positive_fixtures_evaluated": 2,
        "positive_fixtures_with_candidates": 2,
        "half_note_fixtures_with_false_positive_candidates": 0,
        "negative_noise_fixtures_with_false_positive_candidates": 0
    })
    assert status == "pass"
    assert "positive_candidates_complete" in reasons
    assert "no_false_positive_candidates" in reasons

    # Review scenario: positive fixtures missing
    status, reasons = helper({
        "positive_fixtures_evaluated": 0,
        "positive_fixtures_with_candidates": 0,
        "half_note_fixtures_with_false_positive_candidates": 0,
        "negative_noise_fixtures_with_false_positive_candidates": 0
    })
    assert status == "review"
    assert "positive_fixtures_missing" in reasons

    # Review scenario: positive candidates missing
    status, reasons = helper({
        "positive_fixtures_evaluated": 2,
        "positive_fixtures_with_candidates": 1,
        "half_note_fixtures_with_false_positive_candidates": 0,
        "negative_noise_fixtures_with_false_positive_candidates": 0
    })
    assert status == "review"
    assert "positive_candidates_missing" in reasons

    # Fail scenario: half note false positives
    status, reasons = helper({
        "positive_fixtures_evaluated": 2,
        "positive_fixtures_with_candidates": 2,
        "half_note_fixtures_with_false_positive_candidates": 1,
        "negative_noise_fixtures_with_false_positive_candidates": 0
    })
    assert status == "fail"
    assert "half_note_false_positives_present" in reasons

    # Fail scenario: negative noise false positives
    status, reasons = helper({
        "positive_fixtures_evaluated": 2,
        "positive_fixtures_with_candidates": 2,
        "half_note_fixtures_with_false_positive_candidates": 0,
        "negative_noise_fixtures_with_false_positive_candidates": 1
    })
    assert status == "fail"
    assert "negative_noise_false_positives_present" in reasons
