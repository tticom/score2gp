import sys
from pathlib import Path
from unittest.mock import patch

# To import the script, we can execute its logic directly or import it if the sys.path is set.
# A simple way to test is to mock run_diagnostics_on_file and test the report aggregation.

import importlib.util

def load_script():
    script_path = Path(__file__).parent.parent / "scripts" / "raster_diagnostics_gate_report.py"
    spec = importlib.util.spec_from_file_location("gate_report", script_path)
    gate_report = importlib.util.module_from_spec(spec)
    sys.modules["gate_report"] = gate_report
    spec.loader.exec_module(gate_report)
    return gate_report


def test_gate_report_aggregation(capsys):
    gate_report = load_script()

    # Mock the return values for run_diagnostics_on_file
    # We pretend there are some fixtures and one returns false positives, one returns false negative, etc.
    
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
        "treble-staff-paper.pdf": {
            "staff_count": 10,
            "treble_clef_candidate": 0, # Fake false negative
            "unknown": 10,
            "pages": 1,
        },
        "FlashCardsValues.pdf": {
            "staff_count": 1,
            "treble_clef_candidate": 1,
            "unknown": 0,
            "pages": 11,
        },
    }

    def mock_run(path: Path):
        return mock_returns.get(path.name)

    with patch("gate_report.run_diagnostics_on_file", side_effect=mock_run):
        # We need to also patch Path.exists to return True so the manifest loop runs
        with patch("pathlib.Path.exists", return_value=True):
            totals = gate_report.generate_report()

    # Check totals
    assert totals["false_positives"] == 1
    assert totals["false_negatives"] == 1
    assert totals["total_cases_inspected"] == 5
    assert totals["total_pages"] == 15
    assert totals["total_staves"] == 12
    assert totals["unknowns"] == 11
    
    # Check stdout
    captured = capsys.readouterr()
    assert "False Positives: 1" in captured.out
    assert "False Negatives: 1" in captured.out
