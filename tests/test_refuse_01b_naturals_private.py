"""Real-source natural signs; printed rhythm counts, never reference-derived rules.

Oracle: visual inspection of the printed notation. These sources have no GP
reference and are not independently verified. Synthetic tests have no acceptance
weight. Mutant DROP_NATURAL_RULE disables the natural contour reader and must
fail the written-bar assertion through the normal CLI.
"""
from collections import Counter
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from test_dur_02_oracle import read_gp_bars


ROOT = Path(__file__).resolve().parents[1]
# Zero-based source indices; counts of printed quarter, eighth, sixteenth beats
# and rests. Chords count once. No musical event sequences are stored here.
CASES = [
    ("Back In Black", {0: (1, 2, 8, 0), 2: (1, 1, 10, 1), 5: (0, 2, 12, 0)}),
    ("Brown Sugar", {5: (0, 0, 16, 0)}),
    ("Crossroads", {4: (1, 1, 10, 0), 8: (2, 0, 8, 0),
                    12: (1, 2, 8, 1), 17: (1, 0, 12, 0),
                    30: (0, 2, 12, 0), 34: (0, 2, 12, 0)}),
]


@pytest.mark.parametrize("name,printed", CASES)
def test_naturals_release_only_printed_rhythms(name, printed, tmp_path):
    """Reject DROP_NATURAL_RULE, changed written values and lost GPIF beats."""
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "REQUIRED_REFUSE_01B_PDF_MISSING"
    output, build = tmp_path / "output.gp", tmp_path / "build"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab", "--out", str(output),
        "--work-dir", str(build),
    ])
    assert result.exit_code == 0, f"REFUSE_01B_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    records = json.loads((build / "note-durations.json").read_bytes())
    packaged = read_gp_bars(output)
    for bar, (quarters, eighths, sixteenths, rests) in printed.items():
        entry = next(b for b in route["bars"] if b["source_bar_index"] == bar)
        assert entry["status"] == "written", f"NATURAL_BAR_REFUSED_{bar}"
        events = packaged[entry["output_bar_index"] - 1]["events"]
        assert events is not None, f"GPIF_BAR_EMPTY_{bar}"
        assert Counter(e["written"] for e in events) == +Counter(
            quarter=quarters, eighth=eighths, **{"16th": sixteenths}), f"PRINTED_TYPES_{bar}"
        assert sum(e["kind"] == "rest" for e in events) == rests, f"PRINTED_RESTS_{bar}"
        assert all(e["dots"] == 0 and e["tuplet"] is None for e in events), f"PRINTED_MODIFIERS_{bar}"
        source_events = [e for e in records["events"] if e["bar_index"] == bar]
        assert [(e["written"], e["dots"], e["tuplet"]) for e in events] == [
            (e["written"], e["dots"]["count"], None) for e in source_events
        ], f"GPIF_RHYTHM_TRANSPORT_{bar}"
