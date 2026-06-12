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
                        totals = gate_report.generate_report()

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
