"""Located reasons for the alignment and total refusals REFUSE-03 left unknown (REFUSE-04).

Real sources only (the private corpus; counts and codes, never content). Nothing here writes a bar:
REFUSE-04 settled that no remaining class is an honestly settleable reader gap, so each refusal stays
and now says which side of the notation/TAB disagreement has the extra item and why. Synthetic tests
carry no acceptance weight; none are used. Mutant:
  DROP_LOCATED_EVIDENCE  `_disagreement_evidence` returns no evidence (the old, unlocated refusal).
                         Every assertion below must fail.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _route(source: str, tmp_path, *, tab_only_ok: bool = True):
    pdf = PRIVATE / source
    assert pdf.is_file(), "REQUIRED_REFUSE_04_PDF_MISSING"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(tmp_path / "output.gp"), "--work-dir", str(tmp_path / "build")])
    assert result.exit_code == 0, f"REFUSE_04_CLI_EXIT_{result.exit_code}"
    return json.loads((tmp_path / "build" / "note-type-route.json").read_bytes())


def _check(route):
    bars = route["bars"]
    # Black Dog, bar 0: the printed bar totals less than the meter; bar 1 is a tied continuation of it.
    total = bars[0]
    assert (total["status"], total["reason"]) == ("refused", "bar_total_mismatch")
    evidence = total["refusal_evidence"]
    assert (evidence["cause"], evidence["total_quarters"], evidence["expected_quarters"]) == (
        "notation_total_below_meter", "15/4", "4")
    assert (evidence["notation_events"], evidence["tab_columns"]) == (1, 1)
    tie = bars[1]
    assert (tie["status"], tie["reason"]) == ("refused", "notation_note_without_tab_digit")
    assert tie["refusal_evidence"]["cause"] == "tie_stop_without_written_predecessor"
    assert tie["location"]["event_index"] == 0


def test_black_dog_refusals_are_located(tmp_path):
    """Rejects a refusal that does not say whether the bar total or the tie continuation is the cause."""
    _check(_route("Black Dog.pdf", tmp_path))


def test_tab_only_source_bar_without_event_says_where_the_rhythm_came_from(tmp_path):
    """Rejects an unlocated bar_without_notation_event for the source whose 'staff' is the TAB placeholder."""
    route = _route("7_Grateful_Dead_Melodies.pdf", tmp_path)
    bar = route["bars"][12]
    assert (bar["status"], bar["reason"]) == ("refused", "bar_without_notation_event")
    assert bar["refusal_evidence"]["rhythm_source"] == "tab_rhythm"
    assert bar["refusal_evidence"]["notation_events"] == 0


def test_mutant_without_located_evidence_fails(tmp_path, monkeypatch):
    """Rejects dropping the evidence: the real-source assertions must then fail."""
    monkeypatch.setattr(assembler, "_disagreement_evidence", lambda *a, **k: {"source": "notation_tab_bar_counts"})
    with pytest.raises((AssertionError, KeyError)):
        _check(_route("Black Dog.pdf", tmp_path))
