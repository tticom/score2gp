"""Real-source labelled upward bends; counts, indices and notation codes only.

Printed-page oracle: two bars of the design source carry quarter-tone bends;
one also carries a half-step bend on the sounding head of a struck chord.
Each is fixed by a curved shaft, upward arrowhead and explicit amount label. The
shaft is not another event. Release curves are outside this bounded reader.
No reference file exists: these bars are not independently verified.
DROP_SIMPLE_BEND_READER (leave the shaft as an unread event) must fail this
test, as must DROP_BEND_DESTINATION (retain only the former GPIF flag) and
QUARTER_AS_SEMITONE (misread the quarter-tone label as a quarter semitone).
DROP_COMPLETE_BAR_BENDS loses the earlier half-step bend; DROP_FERMATA_GUARD
silently enables an untargeted continuation without its printed hold sign.
Synthetic fixtures carry zero acceptance weight; none are used here.
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from typer.testing import CliRunner

from score2gp.cli import app


def test_labelled_bend_shaft_is_owned_and_reaches_gpif(tmp_path):
    source = Path("fixtures/private/Crossroads.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_21_DESIGN_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab",
        "--out", str(output), "--work-dir", str(build),
    ])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())
    score = json.loads((build / "score.ir.json").read_bytes())
    for index, count, owner in [(13, 6, 5), (36, 14, 12)]:
        assert route["bars"][index]["status"] == "written"
        events = score["bars"][index]["events"]
        assert len(events) == count
        assert sum(e["timing"]["duration_ticks"] for e in events) == 3840
        bends = [(i, t) for i, e in enumerate(events) for n in e["notes"]
                 for t in n["techniques"] if t["kind"] == "bend"]
        assert [(i, b["semitones"]) for i, b in bends] == (
            [(1, 1.0), (owner, 0.5)] if index == 13 else [(owner, 0.5)])
    with ZipFile(output) as package:
        gpif = ET.fromstring(package.read("Content/score.gpif"))
    bends = gpif.findall("./Notes/Note/Bend")
    assert len(bends) == 3
    assert sorted(max(float(p.get("value")) for p in b.findall("Point")) for b in bends) == [25, 25, 50]
    native = gpif.findall("./Notes/Note/Properties/Property[@name='BendDestinationValue']/Float")
    assert len(native) == 3 and sorted(float(n.text) for n in native) == [25, 25, 50]
    masters = gpif.findall("./MasterBars/MasterBar")
    bars = {n.get("id"): n for n in gpif.findall("./Bars/Bar")}
    voices = {n.get("id"): n for n in gpif.findall("./Voices/Voice")}
    beats = {n.get("id"): n for n in gpif.findall("./Beats/Beat")}
    notes = {n.get("id"): n for n in gpif.findall("./Notes/Note")}
    for index, owner in [(13, 5), (36, 12)]:
        bar = bars[masters[index].findtext("Bars").split()[0]]
        voice = voices[bar.findtext("Voices").split()[0]]
        written = [beats[i] for i in voice.findtext("Beats").split()]
        assert [i for i, beat in enumerate(written) if any(
            notes[n].find("Bend") is not None for n in (beat.findtext("Notes") or "").split()
        )] == ([1, owner] if index == 13 else [owner])
    # The full-tone bend/release is not turned into a simple upward bend.
    assert route["bars"][18]["status"] == "refused"
    # Its new predecessor must not silently enable a whole chord whose
    # printed fermata is not represented by this reader.
    assert route["bars"][37]["status"] == "refused"
    assert route["bars"][37]["detail"] == "fermata_unrepresented"
