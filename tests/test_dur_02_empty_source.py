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
    assert path.is_file(), (
        f"mandatory real-source input is unavailable: {name}; "
        "mount score2gp-private-fixtures before running tests"
    )
    return path


@pytest.mark.parametrize("name", ["No Notes.pdf", "no-notes.gp"])
def test_required_private_input_fails_when_missing(name, tmp_path, monkeypatch):
    """Infrastructure check: reject silently skipping a missing mandatory input."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(AssertionError, match=f"mandatory real-source input is unavailable: {name}"):
        try:
            _private(name)
        except pytest.skip.Exception:
            pytest.fail("missing mandatory input was skipped instead of failing")


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
    "7_Grateful_Dead_Melodies.pdf",
])
def test_private_digits_without_printed_rhythm_are_never_written(name):
    """Reject accepting rhythm-free digits (TABRHY-01 reads printed rhythm marks; this source prints none).

    The other no-notation sources this test used to cover (12 Bar Blues, 5 MUST KNOW, Finger position tips) print
    rhythm under the TAB and now convert; ``tests/test_tab_rhythm_real.py`` asserts that. This source prints a
    whole-rest glyph in some bars and no stem, beam or other rhythm mark anywhere: every digit column must stay
    unwritten and only the printed rests may be written.
    """
    pdf = _private(name)
    work = Path("work")
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        result, out, report = _convert(pdf, Path(tmp))
        route = json.loads((Path(tmp) / "route/note-type-route.json").read_text(encoding="utf-8"))
        durations = json.loads((Path(tmp) / "route/note-durations.json").read_text(encoding="utf-8"))
        assert route["summary"]["tab_digits"] > 0
        assert set(route["summary"]["match_kinds"]) <= {"rest"}
        assert "tab_column" not in route["summary"]["match_kinds"] and "tie_continuation" not in route["summary"]["match_kinds"]
        columns = [r for r in durations["events"] if r["reason"] == "tab_column_without_rhythm_mark"]
        assert columns and len(columns) <= route["summary"]["tab_digits"]
        root = _gpif(out) if out.exists() else None
        assert root is None or root.findall("./Notes/Note") == []
