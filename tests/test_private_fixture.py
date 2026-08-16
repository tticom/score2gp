from __future__ import annotations

from pathlib import Path

from score2gp.gp_package import inspect_gp


PRIVATE_GP = Path(__file__).resolve().parent.parent.parent / "score2gp-private-fixtures" / "fixtures" / "private" / "Derek Trucks BB King.gp"


def test_private_gp_fixture_inspects() -> None:
    assert PRIVATE_GP.is_file(), (
        "mandatory real-source corpus is unavailable; CI must mount "
        "score2gp-private-fixtures before running tests"
    )
    summary = inspect_gp(PRIVATE_GP)
    assert summary["package"]["is_zip"] is True
    assert summary["package"]["xml_well_formed"] is True
    assert summary["tempo"] == "66"
    assert summary["time_signatures"] == ["12/8"]
    assert summary["tunings"][0]["name"] == "Open E"
    assert summary["bar_count"] >= 1
    assert summary["note_count"] >= 1
