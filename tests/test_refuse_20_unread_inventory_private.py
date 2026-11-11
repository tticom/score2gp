"""Real-source diagnostic regression; no recognition/coverage acceptance claim.

Oracle: the approved printed page has five TAB systems containing nine bars.
It prints no note rhythm. Counts and codes only are recorded here. Synthetic
fixtures carry zero acceptance weight. DROP_UNREAD_TAB_INVENTORY (omit writing
the fallback reader's diagnostic file) must fail this test.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from score2gp.cli import app


def test_cli_retains_every_unread_tab_bar_without_writing_music(tmp_path):
    """Reject losing all bar locations merely because no event was read."""
    source = Path("fixtures/private/5_Grateful_Dead_Intros.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_20_INVENTORY_SOURCE_MISSING"
    build = tmp_path / "build"
    output = tmp_path / "output.gp"
    report = tmp_path / "report.json"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab", "--out", str(output),
        "--work-dir", str(build), "--json-report", str(report),
    ])
    assert result.exit_code == 2, result.output
    assert not output.exists()
    assert json.loads(report.read_bytes())["refusal_code"] == "pdf_only_tab_no_notation_bars"
    inventory = json.loads((build / "tab-rhythm.json").read_bytes())
    assert len(inventory["systems"]) == 5
    assert inventory["summary"]["bars"] == 9
    assert inventory["summary"]["read_events"] == 0
    assert inventory["summary"]["unread_events"] == 52
    by_bar = {}
    for event in inventory["events"]:
        assert event["status"] == "unread"
        assert event["reason"] == "tab_column_without_rhythm_mark"
        assert event["duration_quarters"] is None and event["written"] is None
        location = event["location"]
        assert all(location[key] is not None for key in (
            "page_index", "system_index", "bar_index", "event_index", "bbox",
        ))
        assert location["bar_index"] == event["bar_index"]
        by_bar.setdefault(event["bar_index"], []).append(event)
    assert set(by_bar) == set(range(9))
    assert all(check["status"] == "incomplete" for check in inventory["bar_checks"])
