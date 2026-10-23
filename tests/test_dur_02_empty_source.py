"""Real-source DUR-02-FU2 controls; private output stays in temporary work directories."""

import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest
from typer.testing import CliRunner

from score2gp.cli import app


def _private(name):
    path = Path("fixtures/private") / name
    if not path.exists():
        pytest.skip(f"private corpus not mounted: {name}")
    return path


def _gpif(path):
    with zipfile.ZipFile(path) as package:
        return ET.fromstring(package.read("Content/score.gpif"))


def _convert(pdf, work):
    out, report = work / "out.gp", work / "report.json"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                    "--out", str(out), "--work-dir", str(work / "route"),
                                    "--json-report", str(report)])
    return result, out, json.loads(report.read_text(encoding="utf-8"))


def test_private_empty_source_keeps_printed_bars_without_beats():
    """Reject old refusal, a guessed note/rest/rhythm, and a dropped bar.

    Independent oracle: visual inspection of No Notes.pdf gives three rows of three empty bars;
    independently opened reference has nine MasterBars and no beats. Neither feeds conversion.
    """
    pdf, reference = _private("No Notes.pdf"), _private("no-notes.gp")
    ref = _gpif(reference)
    assert len(ref.findall("./MasterBars/MasterBar")) == 9
    assert ref.findall("./Beats/Beat") == []
    work = Path("work")
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        result, out, report = _convert(pdf, Path(tmp))
        assert result.exit_code == 0, result.output
        assert report["status"] == "success"
        route = json.loads((Path(tmp) / "route/note-type-route.json").read_text(encoding="utf-8"))
        assert route["summary"]["source_bars"] == 9
        assert route["summary"]["written_bars"] == 9
        assert route["summary"]["refused_bars"] == 0
        assert all(bar["status"] == "written" and bar["events"] == [] for bar in route["bars"])
        root = _gpif(out)
        assert len(root.findall("./MasterBars/MasterBar")) == 9
        assert len(root.findall("./Bars/Bar")) == 9
        for master, bar in zip(root.findall("./MasterBars/MasterBar"), root.findall("./Bars/Bar")):
            assert master.findtext("Bars") == bar.get("id")
        assert root.findall("./Beats/Beat") == []
        assert root.findall("./Notes/Note") == []
        assert root.findall("./Rhythms/Rhythm") == []
        assert all(not (voice.findtext("Beats") or "").strip()
                   for voice in root.findall("./Voices/Voice"))


@pytest.mark.parametrize("name", [
    "12 Bar Blues Solo Guitar Jam.pdf",
    "5 MUST KNOW Pentatonic Licks In Em.pdf",
    "7_Grateful_Dead_Melodies.pdf",
    "Finger postition tips TAB.pdf",
])
def test_private_digits_without_notation_keep_specific_refusal(name):
    """Reject accepting rhythm-free digits or replacing the route reason with the generic guard."""
    pdf = _private(name)
    work = Path("work")
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        result, out, report = _convert(pdf, Path(tmp))
        assert result.exit_code != 0, result.output
        assert not out.exists()
        assert report["status"] == "refused"
        assert report["refusal_code"] == "pdf_only_tab_no_notation_bars"
        route = json.loads((Path(tmp) / "route/note-type-route.json").read_text(encoding="utf-8"))
        assert route["summary"]["source_bars"] == 0
        assert route["summary"]["tab_digits"] > 0
        assert len(route["unplaced_tab_digits"]) == route["summary"]["tab_digits"]
        assert all(digit["candidate_id"] and digit["page_index"] >= 0
                   for digit in route["unplaced_tab_digits"])
