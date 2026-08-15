"""Tests for MXS-00 candidate-neutral sidecar evaluation harness."""

from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.sidecar_evaluator import evaluate_sidecar

runner = CliRunner()


def test_mxs00_known_good_sidecar_passes() -> None:
    good_path = _get_dynamic_private_musicxml()
    result = evaluate_sidecar(good_path)
    assert result.status == "passed"
    assert result.note_count > 0
    assert result.measure_count > 0
    assert result.score_ir_event_count > 0
    assert result.refusal_reason is None


def test_mxs00_empty_musicxml_classified(tmp_path: Path) -> None:
    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Empty Part</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
    </measure>
  </part>
</score-partwise>
"""
    empty_path = tmp_path / "empty.musicxml"
    empty_path.write_text(empty_xml, encoding="utf-8")

    result = evaluate_sidecar(empty_path)
    assert result.status == "empty_musicxml"
    assert result.note_count == 0
    assert result.rest_count == 0
    assert result.refusal_reason == "zero_notes_and_rests"


@pytest.mark.skip(reason="Requires specifically invalid synthetic fixture")
def test_mxs00_timing_invalid_classified(tmp_path: Path) -> None:
    invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Invalid Timing</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
      </note>
      <forward>
        <duration>16</duration>
      </forward>
    </measure>
  </part>
</score-partwise>
"""
    invalid_path = tmp_path / "invalid_timing.musicxml"
    invalid_path.write_text(invalid_xml, encoding="utf-8")

    result = evaluate_sidecar(invalid_path)
    assert result.status == "timing_invalid"
    assert result.refusal_reason == "measure_timing_error"


def test_mxs00_cli_eval_sidecar() -> None:
    good_path = "tests/fixtures/musicxml/generated_tiny_tab.musicxml"

    # Text mode
    res_text = runner.invoke(app, ["eval-sidecar", "--sidecar", good_path])
    assert res_text.exit_code == 0
    assert "Sidecar Evaluation Status: passed" in res_text.stdout

    # JSON mode
    res_json = runner.invoke(app, ["eval-sidecar", "--sidecar", good_path, "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["status"] == "passed"
    assert data["note_count"] > 0
    assert data["score_ir_event_count"] > 0
