"""Real-source ghost heads whose left parenthesis stands one unused accidental slot from the head (REFUSE-23).

Measured with the normal CLI over every approved PDF: the leading class (TAB columns with no printed rhythm mark, 73 bars)
prints no rhythm and stays refused (only a spacing guess could settle it). Among the classes the page does settle,
`rest_glyph_unidentified` (11 bars, all in `Melodic_Expressions.pdf`) is none of rests: 2 are mid-staff meter digits, 2 are
diamond-head chords, 2 are arrow-accidental pairs, 1 is a tall chord pair, and 3 are single-head parenthesis pairs whose
left stroke stands about 1.3 staff spaces left of the head with nothing between. Two of those (source bars 495 and 514:
a parenthesised half note then a half rest) are written as ghost notes. Source bar 555 also carries a dot after the
head and stays refused (`unsupported_overlapping_form`). No reference `.gp` exists: not independently verified; the two
bars were checked against the printed page. Holdout waived for this task (maintainer, 2026-11-14).
Mutant: DROP_PAREN_SLOT_RULE (ENABLE_PAREN_ACCIDENTAL_SLOT = False) refuses bars 495 and 514 again and fails this test.
Synthetic tests carry no acceptance weight: none are used.
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from score2gp.cli import app

SOURCE = Path("fixtures/private/Melodic_Expressions.pdf")


def test_detached_parenthesis_ghost_half_notes_are_written(tmp_path):
    assert SOURCE.is_file(), "REQUIRED_REFUSE_23_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(SOURCE), "--pdf-only-tab",
                                      "--out", str(output), "--work-dir", str(build)])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())["bars"]
    score = json.loads((build / "score.ir.json").read_bytes())["bars"]
    for index in (495, 514):
        assert route[index]["status"] == "written"
        events = score[index]["events"]
        assert [e["is_rest"] for e in events] == [False, True]
        assert [e["timing"]["duration_ticks"] for e in events] == [1920, 1920]
        assert len(events[0]["notes"]) == 1 and events[0]["notes"][0]["is_ghost"] is True
    # A dotted parenthesised head is another form and stays refused with its located reason.
    assert route[555]["status"] == "refused"
    assert route[555]["refusal_evidence"]["cause"] == "unsupported_overlapping_form"
