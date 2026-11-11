"""Real-source tied TAB continuation; counts/indices/codes only.

Printed-page oracle: page 7 has eleven bars. The second bar of its second
system and the second bar of its third system contain parenthesized tied
chords. The former has sixteen sixteenths; the latter twelve sixteenths and
a quarter. The tied destinations have two and three heads respectively.
No reference supplies conversion values. Synthetic tests carry no acceptance
weight. DROP_TIED_TAB_PARENTHESES must leave these bars refused.
"""

import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from typer.testing import CliRunner

from score2gp.cli import app


def test_printed_tied_tab_parentheses_keep_the_chord_and_rhythm(tmp_path):
    source = Path("fixtures/private/Melodic_Expressions.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_20_TIED_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab",
        "--out", str(output), "--work-dir", str(build),
    ])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())
    assert route["summary"]["source_bars"] == 594
    durations = json.loads((build / "note-durations.json").read_bytes())
    systems = [s for s in durations["systems"] if s["page_index"] == 6]
    indices = [s["first_bar_index"] + i for s in systems for i in range(s["bar_count"])]
    page = [route["bars"][i] for i in indices]
    assert len(page) == 11
    assert sum(b["status"] == "written" for b in page) == 9
    assert [b["source_bar_index"] for b in page if b["status"] == "refused"] == [67, 70]
    score = json.loads((build / "score.ir.json").read_bytes())
    for index, heads, expected in [(68, 2, {"16th": 16}), (71, 3, {"16th": 12, "quarter": 1})]:
        assert route["bars"][index]["status"] == "written"
        events = score["bars"][index]["events"]
        assert dict(Counter(e["timing"]["notated_duration"]["value"] for e in events)) == expected
        assert sum(e["timing"]["duration_ticks"] for e in events) == 3840
        assert all(not e["is_rest"] and e["timing"]["notated_duration"]["dots"] == 0 for e in events)
        assert events[-1]["timing"]["notated_duration"]["value"] == ("16th" if index == 68 else "quarter")
        assert len(events[-1]["notes"]) == heads
        assert [(n["string"], n["fret"]) for n in events[-1]["notes"]] == [
            (n["string"], n["fret"]) for n in events[-2]["notes"]
        ]
        assert all(any(t["kind"] == "tie" and t["state"] == "stop" for t in n["techniques"])
                   for n in events[-1]["notes"])
        # A prototype that accepted the tie but dropped the printed wave failed
        # this requirement. Presence alone does not prove its per-head owner.
        assert any(t["kind"] == "vibrato" for e in events[-2:] for n in e["notes"] for t in n["techniques"])
    with zipfile.ZipFile(output) as package:
        gpif = ET.fromstring(package.read("Content/score.gpif"))
    assert len(gpif.findall("./MasterBars/MasterBar")) == 594
    # The final output must actually contain the newly read tied destinations.
    bars = {n.get("id"): n for n in gpif.findall("./Bars/Bar")}
    voices = {n.get("id"): n for n in gpif.findall("./Voices/Voice")}
    beats = {n.get("id"): n for n in gpif.findall("./Beats/Beat")}
    notes = {n.get("id"): n for n in gpif.findall("./Notes/Note")}
    masters = gpif.findall("./MasterBars/MasterBar")
    for index, heads in [(68, 2), (71, 3)]:
        bar = bars[masters[index].findtext("Bars").split()[0]]
        voice = voices[bar.findtext("Voices").split()[0]]
        beat_ids = voice.findtext("Beats").split()
        destination = [notes[i] for i in beats[beat_ids[-1]].findtext("Notes").split()]
        predecessor = [notes[i] for i in beats[beat_ids[-2]].findtext("Notes").split()]
        assert len(destination) == heads
        assert all(n.find("Tie").get("destination") == "true" for n in destination)
        assert any(n.find("Vibrato") is not None for n in predecessor + destination)
        def positions(items):
            return sorted((n.findtext("./Properties/Property[@name='String']/String"),
                           n.findtext("./Properties/Property[@name='Fret']/Fret")) for n in items)
        assert positions(destination) == positions(predecessor)
