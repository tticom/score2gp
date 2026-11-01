"""Real-source multi-note slurs; printed rhythm counts, never reference-derived rules.

Oracle: visual inspection of the printed notation. These sources have no GP
reference and are not independently verified. Synthetic tests have no acceptance
weight. Mutants:
  DROP_END_POINT_RULE  `_arc_end_ys` returns None, so a slur over several notes
                       is located as an unread overlap again (bars refused).
  DROP_SLUR_READER     no slur is read at all (also rejects the prior behaviour).
Each must fail the real-source assertions below.
"""
from collections import Counter
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd
from test_dur_02_oracle import read_gp_bars


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/private/Crossroads.pdf"
# Zero-based source bar indices: printed counts of quarter, eighth, sixteenth
# beats (a rest counts under its printed value) and rests. Chords count once. No musical event sequences are stored.
SLUR_BARS = {16: (1, 4, 4, 0), 19: (1, 1, 10, 1), 35: (1, 0, 12, 0)}


def _located_bars():
    assert SOURCE.is_file(), "REQUIRED_REFUSE_02_PDF_MISSING"
    result = nd.read_note_durations(SOURCE)
    return {u["location"]["bar_index"] for u in result["diagnostics"].get("unread_symbols", [])
            if u["class"] == "unsupported_overlapping_form"}


def test_multi_note_slurs_are_no_longer_located_unread():
    assert not _located_bars() & set(SLUR_BARS), "SLUR_STILL_LOCATED_UNREAD"


@pytest.mark.parametrize("mutant", ["end_point", "no_slurs"])
def test_mutants_leave_slurs_located_on_real_source(monkeypatch, mutant):
    """Rejects the implementation that does not read multi-note slurs."""
    if mutant == "end_point":
        monkeypatch.setattr(nd, "_arc_end_ys", lambda glyph: None)
    else:
        monkeypatch.setattr(nd, "_slanted_slur_ids", lambda glyphs, events, space: set())
    with pytest.raises(AssertionError):
        assert not _located_bars() & set(SLUR_BARS), "SLUR_STILL_LOCATED_UNREAD"


def test_slurred_bars_write_only_printed_rhythms(tmp_path):
    """Rejects a wrong duration, a refused bar and a lost GPIF beat."""
    assert SOURCE.is_file(), "REQUIRED_REFUSE_02_PDF_MISSING"
    output, build = tmp_path / "output.gp", tmp_path / "build"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(SOURCE), "--pdf-only-tab", "--out", str(output),
        "--work-dir", str(build),
    ])
    assert result.exit_code == 0, f"REFUSE_02_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    records = json.loads((build / "note-durations.json").read_bytes())
    packaged = read_gp_bars(output)
    for bar, (quarters, eighths, sixteenths, rests) in SLUR_BARS.items():
        entry = next(b for b in route["bars"] if b["source_bar_index"] == bar)
        assert entry["status"] == "written", f"SLUR_BAR_REFUSED_{bar}"
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
