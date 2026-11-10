"""REFUSE-19: a positively read key signature is not an extra rest.

Real approved sources only; synthetic tests carry no acceptance weight.
DROP_BAR_KEY_GLYPH_RULE must fail the newly-written-bar assertion below.
The source has no reference GP: musical output is checked against its printed
page in local ignored evidence, and is not independently verified.
Only counts, indices and diagnostic codes are retained here.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as reader


PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"
SOURCE = "The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf"
NEW_BARS = (21, 48)


def _convert(tmp_path, source=SOURCE):
    path = PRIVATE / source
    assert path.is_file(), "REQUIRED_REFUSE_19_SOURCE_MISSING"
    work = tmp_path / "build"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(path), "--pdf-only-tab",
        "--out", str(tmp_path / "output.gp"), "--work-dir", str(work),
    ])
    assert result.exit_code == 0, f"REFUSE_19_CLI_EXIT_{result.exit_code}"
    route = json.loads((work / "note-type-route.json").read_bytes())
    reading = json.loads((work / "note-durations.json").read_bytes())
    ir = json.loads((work / "score.ir.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, reading, ir


def _check_written(tmp_path):
    route, reading, ir = _convert(tmp_path)
    output = {b["index"]: b for b in ir["bars"]}
    for index in NEW_BARS:
        bar = route[index]
        assert bar["status"] == "written", f"BAR_{index}_STILL_REFUSED"
        key = reading["diagnostics"]["bar_key_signatures"][str(index)]
        assert key["status"] == "read" and key["sources"], "SIGNATURE_NOT_POSITIVELY_READ"
        assert output[bar["output_bar_index"]]["key_signature"]["fifths"] == key["fifths"]
        events = output[bar["output_bar_index"]]["events"]
        assert len(events) == 1 and events[0]["is_rest"] and not events[0]["notes"], "PRINTED_REST_CHANGED"
        assert not any(e.get("rest", {}).get("source") in key["sources"]
                       for e in reading["events"] if e.get("rest")), "SIGNATURE_ALSO_EMITTED_AS_REST"
    return route


def test_read_bar_key_glyphs_do_not_refuse_their_bars(tmp_path):
    """Reject DROP_BAR_KEY_GLYPH_RULE: both real-source bars must be written."""
    _check_written(tmp_path)


def test_drop_bar_key_glyph_rule_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, "_consume_bar_key_glyphs", lambda records, *args: records)
    with pytest.raises(AssertionError, match="STILL_REFUSED"):
        _check_written(tmp_path)
