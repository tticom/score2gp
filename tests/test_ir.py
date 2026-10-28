from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from score2gp.ir import ScoreIR, export_scoreir_schema, validate_score_ir_file


def test_tiny_ir_fixture_valid() -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    assert score.metadata.title == "Tiny Open-E Test"
    assert score.tracks[0].tuning.name == "Open E"
    assert score.bars[0].time_signature.numerator == 12
    assert score.bars[0].events[0].timing.onset_ticks == 0
    assert score.bars[0].events[1].techniques[0].kind == "slide"


def test_ir_rejects_unknown_track() -> None:
    data = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json").model_dump()
    data["bars"][0]["events"][0]["track_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown track"):
        ScoreIR.model_validate(data)


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("unknown_track.ir.json", "unknown track"),
        ("bad_bbox.ir.json", "bbox must use ordered"),
        ("pitch_mismatch.ir.json", "expected 62 from tuning"),
        ("overlapping_voice_events.ir.json", "overlap"),
        ("invalid_string.ir.json", "tuning does not define"),
        ("malformed_technique.ir.json", "less than or equal to 12"),
        ("impossible_guitar_pitch_low.ir.json", "physically playable pitch range of a standard guitar"),
        ("impossible_guitar_pitch_high.ir.json", "physically playable pitch range of a standard guitar"),
    ],
)
def test_invalid_ir_fixtures_fail_with_readable_messages(fixture_name: str, expected: str) -> None:
    _, errors = validate_score_ir_file(Path("fixtures/public/invalid") / fixture_name)
    joined = "\n".join(errors)
    assert expected in joined


def test_exported_schema_matches_committed_schema(tmp_path) -> None:
    generated_path = export_scoreir_schema(tmp_path)
    generated = json.loads(generated_path.read_text(encoding="utf-8"))
    committed = json.loads(Path("schemas/scoreir.v0.1.schema.json").read_text(encoding="utf-8"))
    assert generated == committed


def test_defensive_preflight_rejects_malformed_values_without_clamping() -> None:
    # FND-02 replaces the old assertions requiring silent repairs. This public
    # malformed input tests validation infrastructure, not musical fidelity.
    _, errors = validate_score_ir_file("fixtures/public/test_malformed_input_clamping.ir.json")
    joined_errors = "\n".join(errors)
    # Kills RESTORE_IR_SANITIZERS: exact paths and stable Pydantic reason codes
    # must reach the public file-validation channel, with no repaired values.
    assert "bars.0.events.0.notes.0.fret: [greater_than_equal]" in joined_errors
    assert "bars.0.events.0.notes.0.pitch: [less_than_equal]" in joined_errors
    assert "bars.0.events.0.timing.onset_ticks: [int_from_float]" in joined_errors
    assert "bars.0.events.0.timing.duration_ticks: [int_from_float]" in joined_errors
    assert "bars.0.events.0.timing.bar_index: [int_from_float]" in joined_errors


def test_malformed_structural_arrays_raise_targeted_failures() -> None:
    data = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json").model_dump()

    # 1. Malformed events (should raise custom ValueError "events must be a valid JSON array")
    data_bad_events = json.loads(json.dumps(data))
    data_bad_events["bars"][0]["events"] = {"not": "a list"}
    with pytest.raises(ValidationError, match="events must be a valid JSON array"):
        ScoreIR.model_validate(data_bad_events)

    # 2. Malformed tracks (should raise custom ValueError "tracks must be a valid JSON array")
    data_bad_tracks = json.loads(json.dumps(data))
    data_bad_tracks["tracks"] = {"gtr-1": "not a list"}
    with pytest.raises(ValidationError, match="tracks must be a valid JSON array"):
        ScoreIR.model_validate(data_bad_tracks)
