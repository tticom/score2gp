from __future__ import annotations

import pytest
from pydantic import ValidationError

from score2gp.ir import ScoreIR


def test_tiny_ir_fixture_valid() -> None:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    assert score.metadata.title == "Tiny Open-E Test"
    assert score.tracks[0].tuning.name == "Open E"
    assert score.bars[0].time_signature.numerator == 12


def test_ir_rejects_unknown_track() -> None:
    data = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json").model_dump()
    data["bars"][0]["events"][0]["track_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown tracks"):
        ScoreIR.model_validate(data)
