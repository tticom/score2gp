"""Real-source attachment placement; private musical values come only from the GP.

The output contract rejects dropping, moving to the preceding bar, and moving
to the first bar of a system. Only source indices and counts are stored here.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest
from chord_gpif import gpif_beats as _beats, gpif_chords as _chords, gpif_root as _root

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/private/Can't Find My Way Home (open chord shenanigans)"
# Printed chord labels, in page order; zero-based source bar/beat indices.
LABELS = [(0, 0), (0, 4), (1, 5), (2, 0), (2, 5), (3, 0),
          (4, 0), (4, 5), (5, 5), (6, 0), (6, 5), (7, 0),
          (8, 0), (8, 5), (9, 5), (10, 0), (10, 5), (11, 0),
          (12, 0), (12, 5), (13, 5), (14, 0), (14, 5), (15, 0),
          (16, 0), (16, 5), (17, 5), (18, 0), (18, 5), (19, 0)]
REFUSED = {3: "notehead_digit_count_mismatch", 6: "note_duration_event_unread",
           9: "notehead_digit_count_mismatch"}


def _assert_chords(root, reference):
    truth = _chords(reference)
    wanted = {loc: truth[loc] for loc in LABELS if loc[0] not in REFUSED}
    assert len(wanted) == 26
    assert _chords(root) == wanted


TECHNIQUES = {"pdf-p001-c0007": (1, 5, 0, "HopoOrigin"),
              "pdf-p001-c0118": (7, 8, 0, "HopoOrigin"),
              "pdf-p001-c0116": (7, 11, 0, "Slide")}


def _assert_techniques(score, output, reference):
    actual = {p["raw_token_id"]: (b["index"] - 1, ei, ni)
              for b in score["bars"] for ei, e in enumerate(b["events"])
              for ni, n in enumerate(e["notes"]) for p in n["provenance"]
              if p["raw_token_id"] in TECHNIQUES}
    assert actual == {ident: value[:3] for ident, value in TECHNIQUES.items()}
    output_notes = {n.get("id"): n for n in output.findall("Notes/Note")}
    strings = {(bi, ei, ni): output_notes[_beats(output)[bi, ei].findtext("Notes").split()[ni]].findtext(
        "Properties/Property[@name='String']/String") for bi, ei, ni, _ in TECHNIQUES.values()}
    properties = []
    for root in (output, reference):
        found = {}
        notes = {n.get("id"): n for n in root.findall("Notes/Note")}
        beats = _beats(root)
        for bi, ei, ni, prop in TECHNIQUES.values():
            owners = [notes[note_id] for note_id in beats[bi, ei].findtext("Notes").split()
                      if notes[note_id].findtext("Properties/Property[@name='String']/String") == strings[bi, ei, ni]]
            assert len(owners) == 1
            mark = owners[0].find(f"Properties/Property[@name='{prop}']")
            assert mark is not None, (bi, ei, ni, prop)
            found[bi, ei, ni] = [(child.tag, child.text, child.attrib) for child in mark]
        properties.append(found)
    assert properties[0] == properties[1]


def test_missing_and_preceding_system_technique_labels_keep_the_read_endpoints(converted):
    """Reject dropping upper labels or placing them on the preceding TAB row."""
    build, output, reference = converted
    score = json.loads((build / "score.ir.json").read_text())
    _assert_techniques(score, output, reference)


@pytest.mark.parametrize("mutant", ["previous_bar", "first_bar_of_system", "drop"])
def test_technique_owner_contract_rejects_placement_mutants(converted, mutant):
    build, output, reference = converted
    score = json.loads((build / "score.ir.json").read_text())
    _assert_techniques(score, output, reference)
    for bar in score["bars"]:
        for event in bar["events"]:
            for note in event["notes"]:
                for provenance in list(note["provenance"]):
                    if provenance["raw_token_id"] == "pdf-p001-c0007":
                        note["provenance"].remove(provenance)
                        if mutant != "drop":
                            target_beat = 5 if mutant == "previous_bar" else 0
                            destination = score["bars"][0]["events"][target_beat]["notes"][0]
                            provenance["bar_index"] = 1
                            destination["provenance"].append(provenance)
    with pytest.raises(AssertionError):
        _assert_techniques(score, output, reference)


@pytest.fixture(scope="module")
def converted():
    pdf, gp = SOURCE.with_suffix(".pdf"), SOURCE.with_suffix(".gp")
    assert pdf.is_file() and gp.is_file(), "required CFW-03 private inputs missing"
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfw03-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "written.gp"
        run = subprocess.run([sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
                              "--out", str(output), "--work-dir", str(folder / "build"),
                              "--pdf-only-tab", "--time-signature", "4/4", "--no-strict"],
                             text=True, capture_output=True)
        assert run.returncode == 0, run.stderr
        yield folder / "build", _root(output), _root(gp)


def test_all_printed_chords_reach_the_reference_bar_and_beat(converted):
    """Reject the old missing-system behaviour and each displaced/drop mutant."""
    _, output, reference = converted
    _assert_chords(output, reference)


@pytest.mark.parametrize("mutant", ["previous_bar", "first_bar_of_system", "drop"])
def test_chord_output_contract_rejects_placement_mutants(converted, mutant):
    _, output, reference = converted
    _assert_chords(output, reference)
    changed = copy.deepcopy(output)
    beats = _beats(changed)
    origin = beats[5, 5]  # second bar of a system: both displacement mutants differ
    mark = origin.find("Chord")
    assert mark is not None
    origin.remove(mark)
    if mutant != "drop":
        destination = beats[4, 5 if mutant == "previous_bar" else 0]
        existing = destination.find("Chord")
        if existing is not None:
            destination.remove(existing)
        destination.append(mark)
    with pytest.raises(AssertionError):
        _assert_chords(changed, reference)


def test_refused_bars_stay_empty_and_unplaced_marks_keep_located_reasons(converted):
    """Reject loosening either mismatch gate or silently dropping unresolved marks."""
    build, output, _ = converted
    route = json.loads((build / "note-type-route.json").read_text())
    assert len(route["bars"]) == 21
    assert {b["source_bar_index"]: b["reason"] for b in route["bars"]
            if b["status"] == "refused"} == REFUSED
    assert route["summary"]["written_bars"] == 18
    assert all(bar not in REFUSED for bar, _ in _beats(output))
    score = json.loads((build / "score.ir.json").read_text())
    unplaced = [w for w in score["warnings"] if w["code"] == "pdf_only_tab_attachment_bar_unplaced"]
    refused_marks = {"pdf-p001-c0039": 4, "pdf-p001-c0040": 4, "pdf-p001-c0043": 4,
                     "pdf-p001-c0112": 7, "pdf-p001-c0113": 7, "pdf-p001-c0115": 7,
                     "pdf-p001-c0117": 7, "pdf-p001-c0159": 10, "pdf-p001-c0160": 10,
                     "pdf-p001-c0161": 10}
    wanted = {ident: (bar, "annotation_bar_refused") for ident, bar in refused_marks.items()}
    wanted.update({"pdf-p001-c0005": (1, "annotation_technique_unsupported"),
                   "pdf-p001-c0006": (1, "annotation_technique_unsupported"),
                   "pdf-p001-c0119": (8, "annotation_per_head_target_unresolved"),
                   "pdf-p002-c0256": (16, "annotation_per_head_target_unresolved"),
                   "pdf-p002-c0259": (16, "annotation_per_head_target_unresolved"),
                   "pdf-p001-c0189": (None, "annotation_system_unresolved"),
                   "pdf-p002-c0361": (None, "annotation_system_unresolved")})
    assert len(unplaced) == 17
    assert {w["provenance"][0]["raw_token_id"]: (
        w["provenance"][0]["bar_index"], w["message"].split("reason=")[1].rstrip("."))
            for w in unplaced} == wanted
    assert all("reason=" in w["message"] and w["provenance"][0]["bbox"] for w in unplaced)
