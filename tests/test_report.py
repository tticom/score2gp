from __future__ import annotations

import json

from score2gp.report import write_conversion_report, write_warnings


def test_warning_and_report_files(tmp_path) -> None:
    warnings = [{"code": "unsupported-technique", "message": "Bend shape was not recognised."}]
    warnings_path = tmp_path / "warnings.json"
    report_path = tmp_path / "report.html"

    write_warnings(warnings_path, warnings)
    write_conversion_report(report_path, "Report", warnings, {"note_count": 2})

    assert json.loads(warnings_path.read_text()) == warnings
    report = report_path.read_text()
    assert "unsupported-technique" in report
    assert "note_count" in report
