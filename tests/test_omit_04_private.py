"""OMIT-04 reference comparison through the independent GPIF reader."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest

from score2gp.gp_package import extract_score_ir_from_gp

from test_dur_02_oracle import read_gp_arpeggios, read_gp_bars


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("number,expected", [(3, 2), (4, 1), (5, 0), (6, 0), (7, 0)])
def test_lesson_arpeggios(number: int, expected: int) -> None:
    reference = ROOT / "fixtures/private" / f"Lesson-{number}.gp"
    source = ROOT / "fixtures/private" / f"Lesson-{number}.pdf"
    if not reference.is_file() or not source.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        produced = Path(directory) / "written.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(produced),
             "--work-dir", str(Path(directory) / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        truth, written = read_gp_arpeggios(reference), read_gp_arpeggios(produced)
        assert len(truth) == expected
        assert written == truth


@pytest.fixture(scope="module")
def cfw_arpeggio_conversion():
    name = "Can't Find My Way Home (open chord shenanigans)"
    source = ROOT / "fixtures/private" / f"{name}.pdf"
    reference = ROOT / "fixtures/private" / f"{name}.gp"
    if not source.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "written.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert run.returncode == 0, run.stderr[-1200:]
        yield scratch, output, reference


def test_other_reference_arpeggios_have_located_refusals(cfw_arpeggio_conversion) -> None:
    scratch, output, reference = cfw_arpeggio_conversion
    expected = [(2, 6, "Down"), (6, 6, "Down"), (18, 6, "Down"), (19, 6, "Down")]
    truth = read_gp_arpeggios(reference)
    assert truth == [(2, 6, "Down"), (6, 6, "Down"), (7, 6, "Down"),
                     (18, 6, "Down"), (19, 6, "Down")]
    assert read_gp_arpeggios(output) == expected
    report = json.loads((scratch / "build/arpeggios.json").read_text())
    assert report["counts_by_reason"] == {
        "pdf_arpeggio_attached": 4, "pdf_arpeggio_beat_unavailable": 1,
        "pdf_arpeggio_tab_duplicate": 5,
    }
    attached = [item for item in report["decisions"]
                if item["code"] == "pdf_arpeggio_attached"]
    assert [(item["bar_index"], item["beat_index"], item["direction"])
            for item in attached] == [(bar, beat, direction.lower())
                                       for bar, beat, direction in expected]
    durations = json.loads((scratch / "build/note-durations.json").read_text())
    for item in attached:
        x0, y0, x1, y1 = item["bbox"]
        chord = [event for event in durations["events"]
                 if event["bar_index"] == item["bar_index"] - 1
                 and event["event_index"] == item["beat_index"] - 1]
        assert len(chord) == 1 and chord[0]["kind"] == "chord"
        bx0, by0, _, by1 = chord[0]["location"]["bbox"]
        assert 0 <= bx0 - x1 <= 12
        assert min(by1, y1) - max(by0, y0) >= 0.6 * (by1 - by0)
        # A mark must identify one source chord, never a nearby second chord.
        neighbors = [event for event in durations["events"]
                     if event["bar_index"] == item["bar_index"] - 1
                     and event["kind"] == "chord"
                     and 0 <= event["location"]["bbox"][0] - x1 <= 12
                     and min(event["location"]["bbox"][3], y1)
                     - max(event["location"]["bbox"][1], y0)
                     >= 0.6 * (event["location"]["bbox"][3]
                                - event["location"]["bbox"][1])]
        assert neighbors == chord
    refusals = [item for item in report["decisions"]
                if item["code"] == "pdf_arpeggio_beat_unavailable"]
    assert len(refusals) == 1
    assert all(item["page_index"] >= 0 and item["stroke_indices"] for item in refusals)
    duplicates = [item for item in report["decisions"]
                  if item["code"] == "pdf_arpeggio_tab_duplicate"]
    assert len(duplicates) == 5
    assert all(item["page_index"] >= 0 and item["stroke_indices"] for item in duplicates)


def test_cfw_five_source_arpeggios_follow_written_bar_status(cfw_arpeggio_conversion) -> None:
    """Reject wrong-beat, flipped-direction, dropped-mark and unsafe-write mutants.

    PDF inspection establishes the five upward-pointing engraving arrows (the
    guitar downstroke direction). Reference GP is an independent output oracle,
    supplied only after the PDF-only conversion has finished.
    """
    scratch, output, reference = cfw_arpeggio_conversion
    route = json.loads((scratch / "build/note-type-route.json").read_text())
    report = json.loads((scratch / "build/arpeggios.json").read_text())
    durations = json.loads((scratch / "build/note-durations.json").read_text())
    generated_bars = read_gp_bars(output, include_grace=True)
    target_bars = (2, 6, 7, 18, 19)
    written_bars = (2, 6, 18, 19)
    assert route["summary"]["source_bars"] == 21
    assert route["summary"]["written_bars"] == 18
    assert route["summary"]["refused_bars"] == 3
    for number in target_bars:
        written = number in written_bars
        assert route["bars"][number - 1]["status"] == ("written" if written else "refused")
        assert (generated_bars[number - 1]["events"] is not None) == written

    # Check the final package, independently of the attachment report. This
    # exact sequence rejects displacement, inversion, deletion and extra rolls.
    expected = [(number, 6, "Down") for number in written_bars]
    assert read_gp_arpeggios(output) == expected
    assert [mark for mark in read_gp_arpeggios(reference) if mark[0] in written_bars] == expected

    bar = route["bars"][6]
    assert bar["reason"] == "note_duration_event_unread"
    assert bar["detail"] == "unsupported_overlapping_form"
    assert bar["location"] == {
        "page_index": 0, "system_index": 3, "bar_index": 6, "event_index": 5,
    }
    marks = [item for item in report["decisions"] if item["code"] != "pdf_arpeggio_tab_duplicate"]
    assert len(marks) == 5
    assert [item["direction"] for item in marks] == ["down"] * 5
    attached = [item for item in marks if item["code"] == "pdf_arpeggio_attached"]
    assert [(item["bar_index"], item["beat_index"], item["direction"]) for item in attached] == [
        (number, 6, "down") for number in written_bars
    ]
    refused = [item for item in marks if item["code"] == "pdf_arpeggio_beat_unavailable"]
    assert len(refused) == 1
    mark = refused[0]
    assert mark["page_index"] == bar["location"]["page_index"]
    assert len(mark["bbox"]) == 4 and mark["stroke_indices"]
    # A page-only refusal could silently drift to a different bar. Locate the
    # actual source mark inside bar 7's measured system/bar boundaries.
    system = next(system for system in durations["systems"]
                  if system["page_index"] == mark["page_index"]
                  and system["system_index"] == bar["location"]["system_index"])
    local = bar["location"]["bar_index"] - system["first_bar_index"]
    left, right = system["bars"][local]
    assert left < mark["bbox"][0] < mark["bbox"][2] < right
    # Rolled chords may extend below the staff onto ledger lines.
    assert mark["bbox"][1] < system["staff"]["bottom"]
    assert mark["bbox"][3] > system["staff"]["top"]
    ir = json.loads((scratch / "build/score.ir.json").read_text())
    warnings = [warning for warning in ir["warnings"] if warning["code"] == mark["code"]]
    assert len(warnings) == 1
    provenance = warnings[0]["provenance"][0]
    assert provenance["page"] == mark["page_index"] + 1
    assert provenance["raw"]["bbox"] == mark["bbox"]
    assert provenance["raw"]["stroke_indices"] == mark["stroke_indices"]


def test_lesson_3_reference_arpeggios_read_back_as_written() -> None:
    reference = ROOT / "fixtures/private/Lesson-3.gp"
    if not reference.is_file():
        pytest.skip("private corpus absent")
    truth = read_gp_arpeggios(reference)
    assert len(truth) == 2
    scratch_root = ROOT / "work"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        # The reference holds two beats with neither notes nor a Rest element, which the reader
        # refuses for its own, separate reason; mark them as rests so only arpeggios are under test.
        patched = Path(directory) / "lesson3_rests.gp"
        with zipfile.ZipFile(reference) as zin, zipfile.ZipFile(patched, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "Content/score.gpif":
                    root = ET.fromstring(data)
                    for beat in root.find("Beats").findall("Beat"):
                        if beat.find("Notes") is None and beat.find("Rest") is None:
                            ET.SubElement(beat, "Rest")
                    data = ET.tostring(root, encoding="utf-8")
                zout.writestr(item, data)
        score = extract_score_ir_from_gp(patched)
    read = [event.arpeggio for bar in score.bars for event in bar.events if event.arpeggio]
    assert read == [direction.lower() for _bar, _beat, direction in truth]
