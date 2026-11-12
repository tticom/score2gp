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
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pymupdf
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
        # The printed tie is between events 11 and 12 in both bars. In the
        # first bar three further events follow it; its last event is a single
        # note, not the tied chord. The original last-event oracle was wrong.
        origin, destination = events[11:13]
        assert destination["timing"]["notated_duration"]["value"] == ("16th" if index == 68 else "quarter")
        assert len(destination["notes"]) == heads
        assert [(n["string"], n["fret"]) for n in destination["notes"]] == [
            (n["string"], n["fret"]) for n in origin["notes"]
        ]
        assert all(any(t["kind"] == "tie" and t["state"] == "stop" for t in n["techniques"])
                   for n in destination["notes"])
        assert all(any(t["kind"] == "vibrato" for t in n["techniques"])
                   for e in (origin, destination) for n in e["notes"])
        expected_palms = {2, 3, 6, 7, 10, 13, 15} if index == 68 else {2, 3, 6, 7, 10}
        assert {i for i, e in enumerate(events) if any(t["kind"] == "palm-mute"
                for n in e["notes"] for t in n["techniques"])} == expected_palms
        if index == 68:
            assert [len(e["notes"]) for e in events[13:]] == [1, 2, 1]
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
        destination = [notes[i] for i in beats[beat_ids[12]].findtext("Notes").split()]
        predecessor = [notes[i] for i in beats[beat_ids[11]].findtext("Notes").split()]
        assert len(destination) == heads
        assert all(n.find("Tie").get("destination") == "true" for n in destination)
        assert all(n.find("Vibrato") is not None for n in predecessor + destination)
        def positions(items):
            return sorted((n.findtext("./Properties/Property[@name='String']/String"),
                           n.findtext("./Properties/Property[@name='Fret']/Fret")) for n in items)
        assert positions(destination) == positions(predecessor)


def test_tied_chord_reader_keeps_real_page_output_after_reextraction(tmp_path):
    """Reject DROP_TIED_TAB_PARENTHESES and DROP_TIED_CHORD_VIBRATO.

    This is an unchanged page extracted from the approved PDF, not generated
    music. No reference supplies reader inputs. The full-source test above
    independently checks that the normal CLI retains the complete inventory.
    """
    source = Path("fixtures/private/Melodic_Expressions.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_20_TIED_SOURCE_MISSING"
    with pymupdf.open(source) as original, pymupdf.open() as page:
        page.insert_pdf(original, from_page=6, to_page=6)
        with tempfile.TemporaryDirectory(prefix="r20_") as neutral:
            pdf = Path(neutral) / "page.pdf"
            assert "test" not in str(pdf).lower(), "REAL_SOURCE_ROUTE_REQUIRED"
            page.save(pdf)
            build, output = tmp_path / "build", tmp_path / "output.gp"
            result = CliRunner().invoke(app, [
                "convert", "--pdf", str(pdf), "--pdf-only-tab",
                "--out", str(output), "--work-dir", str(build),
            ])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())
    assert route["summary"]["source_bars"] == 11
    assert route["summary"]["written_bars"] == 9
    assert [b["source_bar_index"] for b in route["bars"] if b["status"] == "refused"] == [2, 5]
    ir = json.loads((build / "score.ir.json").read_bytes())
    for index, count, heads in [(3, 16, 2), (6, 13, 3)]:
        events = ir["bars"][index]["events"]
        assert len(events) == count
        assert sum(e["timing"]["duration_ticks"] for e in events) == 3840
        assert len(events[12]["notes"]) == heads
        assert all(any(t["kind"] == "tie" and t["state"] == "stop" for t in n["techniques"])
                   for n in events[12]["notes"])
        assert all(any(t["kind"] == "vibrato" for t in n["techniques"])
                   for e in events[11:13] for n in e["notes"])
