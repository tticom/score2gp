"""X percussive strikes in TAB that has no notation staff (PERCX-01).

Real source: 5_Grateful_Dead_Intros (one TAB-only page, five systems, no printed rhythm; six X strikes on string 5
in system 4, bar 6, each in a chord voicing). Before this task the CLI refused it with
``percussive_strike_without_owning_note`` because a strike had no notation note to own it. The strike is owned by
its own TAB column now and the refusal is the one the source really earns: it prints no rhythm.

Oracle: the printed page (viewed: six X marks on the 5th string of one bar, in chord columns), counts and codes only.
Mutants:
  DROP_TAB_COLUMN_OWNER  restore the ``percussive_strike_without_owning_note`` raise in ``build_ir`` when no bar was
                         read: the first test fails on the category.
  DROP_STRIKE_READ       read only fret digits in ``read_tab_rhythm``: the second test fails (no cross head, digit
                         left unplaced).
The second test flips one real fret digit to an X in memory. That is infrastructure only: it carries no acceptance
weight (no private source has an X strike under rhythm-marked staffless TAB).
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.cli import app
from score2gp.pdf_tab_rhythm import read_tab_rhythm
from score2gp.tabraw import TabRaw

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def test_tab_only_source_with_x_strikes_is_refused_for_its_missing_rhythm(tmp_path):
    """Rejects: refusing the source because a strike has no notation owner (the pre-PERCX-01 category)."""
    pdf = PRIVATE / "5_Grateful_Dead_Intros.pdf"
    assert pdf.is_file(), "REQUIRED_PERCX_01_SOURCE_MISSING"
    build = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(tmp_path / "o.gp"), "--work-dir", str(build)])
    assert result.exit_code != 0
    assert not (tmp_path / "o.gp").exists()
    diagnostics = json.loads((build / "diagnostics.json").read_bytes())
    assert diagnostics["category"] == "pdf_only_tab_no_notation_bars"
    route = diagnostics["details"]["note_type_route"]
    assert route["summary"]["written_bars"] == 0
    strikes = route["tab_column_strikes"]
    assert len(strikes) == 6
    assert all(s["owner"] == "tab_column" and s["location"]["string"] == 5 and s["location"]["bar_index"] == 6
               and s["location"]["system_index"] == 4 for s in strikes)


@pytest.mark.parametrize("name", ["Finger postition tips TAB"])
def test_x_strike_under_printed_rhythm_is_a_dead_note_owned_by_its_tab_column(name):
    """Rejects: a strike left unplaced (bar refused), or turned into a fret or a pitched note."""
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_PERCX_01_SOURCE_MISSING"
    from score2gp.pdf import _extract_pdf_text_candidates
    from collections import defaultdict
    tab = TabRaw.model_validate({"candidates": _extract_pdf_text_candidates(pdf, [], defaultdict(int))})
    first = next(c for c in tab.candidates if c.kind == "fret")
    flipped = type(first).model_validate({**first.model_dump(), "kind": "percussive-strike",
                                          "parsed_fret": None, "raw_text": "X"})
    tab.candidates[tab.candidates.index(first)] = flipped
    reading = read_tab_rhythm(pdf, tab)
    assert not reading["diagnostics"]["tab_rhythm"]["unplaced_digits"]
    owned = [e for e in reading["events"] if (e.get("notehead") or {}).get("heads")]
    assert len(owned) == 1 and owned[0]["notehead"]["heads"][0]["source"] == flipped.id
    digits = [c for c in tab.candidates if (c.kind == "fret" and c.parsed_fret is not None) or c.kind == "percussive-strike"]
    bars, route = assembler.assemble_note_type_bars(digits, reading, track_id="guitar")
    assert route["summary"]["refused_bars"] == 0
    notes = [n for b in bars for e in b.events for n in e.notes]
    dead = [n for n in notes if n.is_dead]
    assert len(dead) == 1 and dead[0].pitch is None
