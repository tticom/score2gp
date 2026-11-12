"""Printed-page chord ownership; counts and indices only.

Design source: the first page of the approved chapter extract. Its fifth bar
has four events (quarter, half, eighth, eighth), nine heads, and three parallel
legato slides from the first chord to the second. Accidentals stagger to the
left of that chord; the slurs above and below it describe the same transition.
One head of the last chord slides into the following bar while another is tied.
DROP_STAGGERED_ACCIDENTALS, DROP_CHORD_SLUR_ENVELOPE and
DROP_LABELED_CHORD_DEPARTURE must fail this test.
Synthetic fixtures carry zero acceptance weight.
"""

import json
from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import pymupdf
from typer.testing import CliRunner

from score2gp.cli import app


def test_printed_staggered_chord_keeps_internal_and_departing_slides(tmp_path):
    source = Path("fixtures/private/Melodic_Expressions_Chap_19_.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_20_CHORD_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(source), "--pdf-only-tab",
        "--out", str(output), "--work-dir", str(build),
    ])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())
    assert route["bars"][4]["status"] == "written"
    durations = json.loads((build / "note-durations.json").read_bytes())
    chord = next(e for e in durations["events"] if e["bar_index"] == 4 and e["event_index"] == 0)
    accidentals = chord.get("accidentals", [])
    assert len(accidentals) == 3
    assert {a["direction"] for a in accidentals} == {"sharp"}
    assert len({a["head_staff_position_index"] for a in accidentals}) == 3
    score = json.loads((build / "score.ir.json").read_bytes())
    events = score["bars"][4]["events"]
    assert [e["timing"]["notated_duration"]["value"] for e in events] == [
        "quarter", "half", "eighth", "eighth",
    ]
    assert sum(e["timing"]["duration_ticks"] for e in events) == 3840
    assert [len(e["notes"]) for e in events] == [3, 3, 1, 2]
    slides = [t for n in events[0]["notes"] for t in n["techniques"] if t["kind"] == "slide"]
    assert len(slides) == 3
    assert all(t["style"] == "legato" for t in slides)
    departing = [t for n in events[3]["notes"] for t in n["techniques"] if t["kind"] == "slide"]
    assert len(departing) == 1
    assert departing[0]["style"] == "legato"
    assert departing[0]["target_event_id"] == score["bars"][5]["events"][0]["id"]
    with zipfile.ZipFile(output) as package:
        gpif = ET.fromstring(package.read("Content/score.gpif"))
    masters = gpif.findall("./MasterBars/MasterBar")
    bars = {n.get("id"): n for n in gpif.findall("./Bars/Bar")}
    voices = {n.get("id"): n for n in gpif.findall("./Voices/Voice")}
    beats = {n.get("id"): n for n in gpif.findall("./Beats/Beat")}
    notes = {n.get("id"): n for n in gpif.findall("./Notes/Note")}
    bar = bars[masters[4].findtext("Bars").split()[0]]
    voice = voices[bar.findtext("Voices").split()[0]]
    chord = beats[voice.findtext("Beats").split()[0]]
    written = [notes[i] for i in chord.findtext("Notes").split()]
    assert len(written) == 3
    assert all(n.findtext("./Properties/Property[@name='Slide']/Flags") == "2" for n in written)
    final = beats[voice.findtext("Beats").split()[-1]]
    departing = [notes[i] for i in final.findtext("Notes").split()]
    assert sum(n.findtext("./Properties/Property[@name='Slide']/Flags") == "2" for n in departing) == 1


def test_separate_source_staggered_chord_keeps_rhythm_and_arpeggio(tmp_path):
    """Regression of the frozen reader's positive separate-source application.

    The first application receipt predates this regression. The source had
    been inspected in previous rounds, so this is not a blind holdout.
    Printed-page oracle, not independently verified against a reference file.
    DROP_STAGGERED_ACCIDENTALS and DROP_SHARED_ARPEGGIO_READER reject this bar.
    """
    source = Path("fixtures/private/Melodic_Expressions.pdf")
    assert source.is_file(), "REQUIRED_REFUSE_20_SEPARATE_SOURCE_MISSING"
    build, output = tmp_path / "build", tmp_path / "output.gp"
    with pymupdf.open(source) as original, pymupdf.open() as page:
        page.insert_pdf(original, from_page=2, to_page=2)
        with tempfile.TemporaryDirectory(prefix="r20_") as neutral:
            pdf = Path(neutral) / "page.pdf"
            assert "test" not in str(pdf).lower(), "REAL_SOURCE_ROUTE_REQUIRED"
            page.save(pdf)
            result = CliRunner().invoke(app, [
                "convert", "--pdf", str(pdf), "--pdf-only-tab",
                "--out", str(output), "--work-dir", str(build),
            ])
    assert result.exit_code == 0, result.output
    route = json.loads((build / "note-type-route.json").read_bytes())
    assert route["summary"]["source_bars"] == 11
    assert [b["source_bar_index"] for b in route["bars"] if b["status"] == "refused"] == [0]
    assert route["bars"][0]["refusal_evidence"]["notation_head_count"] == 6
    assert route["bars"][0]["refusal_evidence"]["tab_candidate_count"] == 5
    score = json.loads((build / "score.ir.json").read_bytes())
    events = score["bars"][1]["events"]
    durations = json.loads((build / "note-durations.json").read_bytes())
    records = [e for e in durations["events"] if e["bar_index"] == 1]
    assert [len(e.get("accidentals", [])) for e in records] == [2, 5, 3, 0, 1]
    assert [e["timing"]["notated_duration"]["value"] for e in events] == [
        "16th", "16th", "eighth", "quarter", "half",
    ]
    assert sum(e["timing"]["duration_ticks"] for e in events) == 3840
    assert [len(e["notes"]) for e in events] == [5, 5, 5, 0, 6]
    assert [e["is_rest"] for e in events] == [False, False, False, True, False]
    assert all(e["timing"]["notated_duration"]["dots"] == 0 for e in events)
    assert events[4]["arpeggio"] == "down"
    with zipfile.ZipFile(output) as package:
        gpif = ET.fromstring(package.read("Content/score.gpif"))
    masters = gpif.findall("./MasterBars/MasterBar")
    bars = {n.get("id"): n for n in gpif.findall("./Bars/Bar")}
    voices = {n.get("id"): n for n in gpif.findall("./Voices/Voice")}
    beats = {n.get("id"): n for n in gpif.findall("./Beats/Beat")}
    bar = bars[masters[1].findtext("Bars").split()[0]]
    voice = voices[bar.findtext("Voices").split()[0]]
    written = [beats[i] for i in voice.findtext("Beats").split()]
    assert [len((b.findtext("Notes") or "").split()) for b in written] == [5, 5, 5, 0, 6]
    assert written[4].findtext("Arpeggio") == "Down"
