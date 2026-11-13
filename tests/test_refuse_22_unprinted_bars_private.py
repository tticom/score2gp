"""Real-source bars with nothing printed in them; counts, indices and codes only.

Printed-page oracle (read by eye on the rendered pages, no reference file exists for any of these sources,
so every bar here is NOT independently verified): a bar whose staff and TAB lines carry no note, rest, sign,
number or mark between its barlines is a bar of silence. It is written empty, not refused.
Design sources: the Gloria and the 7_Grateful_Dead_Melodies PDFs. Holdout: the EXACT System PDF (two bars).
Bars the page does NOT show empty must stay refused: a two-bar repeat sign printed across a barline
(source 4 bar 56), TAB numbers the grouper never assigned (source 39 bar 30), and a system-first bar that
holds a clef and key signature (source 21 bar 9).
Mutants that must fail here: DROP_UNPRINTED_BARS (ENABLE_UNPRINTED_BARS = False refuses them all again),
and CENTRE_NOT_OVERLAP (testing a glyph's centre, not its extent, would write the two-bar-repeat bar).
Synthetic fixtures carry zero acceptance weight; none are used here.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app

CASES = {
    "Gloria.pdf": {"written": [2, 5, 8], "refused": [9]},
    "7_Grateful_Dead_Melodies.pdf": {"written": [16, 62, 66, 75], "refused": [46, 49, 55, 56]},
    "The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf": {"written": [42, 43], "refused": []},
    "PARANOID - BLACK SABBATH.pdf": {"written": [], "refused": [30]},
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_unprinted_bars_written_and_unsafe_ones_stay_refused(tmp_path, name):
    source = Path("fixtures/private") / name
    assert source.is_file(), "REQUIRED_REFUSE_22_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                      "--out", str(output), "--work-dir", str(build)])
    assert result.exit_code == 0, result.output
    bars = json.loads((build / "note-type-route.json").read_bytes())["bars"]
    for index in CASES[name]["written"]:
        assert bars[index]["status"] == "written" and bars[index].get("unprinted_bar") is True
        assert bars[index]["events"] == []
    for index in CASES[name]["refused"]:
        assert bars[index]["status"] == "refused"
        assert bars[index]["refusal_evidence"]["cause"] in {
            "bar_without_notation_or_tab_item", "tab_digits_without_notation_event"} or bars[index]["reason"]
    # No unprinted bar is ever a bar that holds an event.
    assert not [b for b in bars if b.get("unprinted_bar") and b["events"]]
