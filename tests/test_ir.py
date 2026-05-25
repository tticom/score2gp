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


def test_defensive_preflight_sanitization_and_clamping() -> None:
    # 1. Load the malformed clamping test fixture
    _, errors = validate_score_ir_file("fixtures/public/test_malformed_input_clamping.ir.json")
    joined_errors = "\n".join(errors)

    # 2. Verify that original Pydantic range/type errors are NOT present
    # (because they were cleanly clamped/rounded by before validators)
    assert "Input should be less than or equal to 12" not in joined_errors  # string 15 clamped to 12
    assert "Input should be greater than or equal to 0" not in joined_errors  # fret -5 clamped to 0
    assert "Input should be less than or equal to 127" not in joined_errors  # pitch 150 clamped to 127
    assert "Input should be less than or equal to 8" not in joined_errors  # voice 9 clamped to 8
    assert "Input should be a valid integer" not in joined_errors  # fractional ticks rounded to integer

    # 3. Verify that the semantic warnings reflect the clamped values
    # (specifically string 12 and pitch 127)
    assert "event 'e1' uses string 12" in joined_errors

    # 4. Directly test Pydantic model instantiation with raw dict
    from score2gp.ir import Timing, Note
    t = Timing.model_validate({
        "bar_index": 1,
        "onset_ticks": 120.6,
        "duration_ticks": 960.2,
        "ticks_per_quarter": 960,
        "voice": 12.3  # should clamp to 8
    })
    assert t.onset_ticks == 121
    assert t.duration_ticks == 960
    assert t.voice == 8

    n = Note.model_validate({
        "string": 15,  # clamp to 12
        "fret": -3,  # clamp to 0
        "pitch": 140  # clamp to 127
    })
    assert n.string == 12
    assert n.fret == 0
    assert n.pitch == 127


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
