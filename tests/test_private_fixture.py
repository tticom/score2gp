from __future__ import annotations

from pathlib import Path

import pytest

from score2gp.gp_package import inspect_gp


PRIVATE_GP = Path("fixtures/private/Derek Trucks BB King.gp")


@pytest.mark.skipif(not PRIVATE_GP.exists(), reason="private fixture not present")
def test_private_gp_fixture_inspects() -> None:
    summary = inspect_gp(PRIVATE_GP)
    assert summary["package"]["is_zip"] is True
    assert summary["package"]["xml_well_formed"] is True
    assert summary["tempo"] == "66"
    assert summary["time_signatures"] == ["12/8"]
    assert summary["tunings"][0]["name"] == "Open E"
    assert summary["bar_count"] >= 1
    assert summary["note_count"] >= 1
