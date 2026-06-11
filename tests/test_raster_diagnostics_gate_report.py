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

def test_gate_report_aggregation_and_privacy(capsys):
    gate_report = load_script()

    # The actual SHA256 of the two verified private fixtures
    sha1 = "53785c550a699cab31aa973e4278c086050ac7ac8b030a8edcbc00aa3942300e"
    sha2 = "f2326734f47ab5483691b504aa2e6827970d10d6d97b5a8eb691db9a0897ab8e"

    mock_returns = {
        "generated_standard_staff_negative_blank.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0,
            "unknown": 1,
            "pages": 1,
        },
        "generated_standard_staff_negative_tab.pdf": {
            "staff_count": 0,
            "treble_clef_candidate": 0,
            "unknown": 0,
            "pages": 1,
        },
        "generated_standard_staff_negative_noise.pdf": {
            "staff_count": 0,
            "treble_clef_candidate": 1, # Fake false positive
            "unknown": 0,
            "pages": 1,
        },
        "fake_private_1.pdf": {
            "staff_count": 10,
            "treble_clef_candidate": 0, # Fake false negative for sha1
            "unknown": 10,
            "pages": 1,
        },
        "fake_private_2.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 1, # Fake true positive for sha2
            "unknown": 0,
            "pages": 11,
        },
        "extra_private_not_in_manifest.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 0, # FN but not in manifest
            "unknown": 0,
            "pages": 1,
        }
    }

    def mock_run(path: Path, display_label=None):
        return mock_returns.get(path.name)

    def mock_compute_sha256(path: Path):
        if path.name == "fake_private_1.pdf": return sha1
        if path.name == "fake_private_2.pdf": return sha2
        if path.name == "extra_private_not_in_manifest.pdf": return "dummy_hash"
        return "other_hash"

    orig_exists = Path.exists
    def custom_exists(self):
        if self.name == "raster-treble-clef": return True
        if self.name in mock_returns: return True
        return orig_exists(self)

    orig_glob = Path.glob
    def custom_glob(self, pattern):
        if self.name == "raster-treble-clef":
            return [
                Path("fixtures/private/raster-treble-clef/fake_private_1.pdf"),
                Path("fixtures/private/raster-treble-clef/fake_private_2.pdf"),
                Path("fixtures/private/raster-treble-clef/extra_private_not_in_manifest.pdf"),
            ]
        return orig_glob(self, pattern)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        with patch("gate_report.compute_sha256", side_effect=mock_compute_sha256):
            with patch.object(Path, "exists", autospec=True, side_effect=custom_exists):
                with patch.object(Path, "glob", autospec=True, side_effect=custom_glob):
                    totals = gate_report.generate_report()

    # We expect cases_inspected = 5 (the 3 negative + 2 mapped private fixtures).
    # The extra_private_not_in_manifest.pdf should NOT be in the manifest so it won't be run by the gate report!
    assert totals["false_positives"] == 1
    assert totals["false_negatives"] == 1
    assert totals["total_cases_inspected"] == 5
    assert totals["total_pages"] == 15
    assert totals["total_staves"] == 12
    assert totals["unknowns"] == 11

    captured = capsys.readouterr()

    # Check that anonymised case IDs are logged, not the raw filenames
    assert "fake_private_1.pdf" not in captured.out
    assert "fake_private_2.pdf" not in captured.out
    assert "extra_private_not_in_manifest.pdf" not in captured.out

    # The extra private fixture should not be processed at all
    assert "UNEXPECTED FALSE NEGATIVE" not in captured.out

    assert "MATCHED KNOWN FALSE NEGATIVE MANIFEST ENTRY: fn_private_positive_001" in captured.out

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
