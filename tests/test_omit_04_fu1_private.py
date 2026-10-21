"""PDF-only acceptance: independent source-ledger digests, never a reference GP.

The ledger was transcribed from the approved PDF's rendered notation and TAB.
Only counts, indices, codes and SHA-256 digests are retained here. Detailed
source readings stay in ignored work/omit04fu1/independent-source-ledger.json.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pytest

from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
LEDGER = {
    3: (10, "bdc5e3676e2a0f57efe37b0978a3fe74f082d5b95229a335552ddd944780b21d"),
    5: (9, "70deda7fa8f2266dcb64bd621cd6e38cbe3074cfb5e2227a606e19a36c1eaf5b"),
    7: (10, "bdc5e3676e2a0f57efe37b0978a3fe74f082d5b95229a335552ddd944780b21d"),
    9: (2, "a95c4c17aa74a480563ea8c9bb7880c73aa8ff908f4b23e9d2d999d3b05dc04f"),
}


@pytest.fixture(scope="module")
def converted():
    source = ROOT / "fixtures/private/G-Am-C-Lick.pdf"
    assert source.is_file(), "required approved private PDF missing"
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omit04fu1-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        run = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
            "--pdf-only-tab", "--out", str(output), "--work-dir", str(folder / "build"),
        ], capture_output=True, text=True)
        assert run.returncode == 0
        route = json.loads((folder / "build/note-type-route.json").read_text())
        yield route, read_gp_bars(output), output


def test_written_bars_match_independent_printed_notation_and_tab_ledger(converted):
    """Reject equal-count/spacing rhythm guesses and changed string/fret output."""
    route, bars, output = converted
    assert [b["output_bar_index"] for b in route["bars"] if b["status"] == "written"] == list(LEDGER)
    for number, (count, digest) in LEDGER.items():
        events = bars[number - 1]["events"]
        assert len(events) == count, (number, "event_count")
        actual = []
        for event in events:
            # Native GPIF strings count from the bottom. A muted string has no
            # printed fret; its writer-only storage fret is checked separately.
            strikes = sorted(6 - string for string in event.get("percussive_strikes", []))
            actual.append({
                "kind": event["kind"], "written": event["written"], "dots": event["dots"],
                "tuplet": event["tuplet"], "tie": list(event["tie"]), "percussive_strikes": strikes,
                "positions": sorted([[6 - string, None if 6 - string in strikes else fret]
                                     for string, fret in event["positions"]]),
            })
        encoded = json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(encoded).hexdigest() == digest, (number, "source_ledger_mismatch")
    # Exact base bytes protect every native strike property and its storage
    # position as well as ties, slides and the remaining package fields.
    with zipfile.ZipFile(output) as package:
        assert hashlib.sha256(package.read("Content/score.gpif")).hexdigest() == (
            "15c8978d144517410cfad95db4cbf83828bccd54033972665325fc795291b52b")


def test_refused_bars_keep_measured_located_causes_and_no_written_beats(converted):
    """Reject dropped refusal evidence, old unmeasured reports and unsafe writes."""
    route, bars, _ = converted
    expected = {
        1: (0, 7, "note_duration_event_unread", "unsupported_overlapping_form", "unread_symbol"),
        2: (0, 8, "notehead_digit_count_mismatch", None, "notation_tab_column"),
        4: (1, 7, "note_duration_event_unread", "rest_glyph_beside_note", "note_duration_record"),
        6: (1, 8, "notehead_digit_count_mismatch", None, "notation_tab_column"),
        8: (2, 7, "note_duration_event_unread", "rest_glyph_beside_note", "note_duration_record"),
    }
    assert route["summary"]["refused_bars"] == len(expected)
    for number, (system, event, reason, detail, source) in expected.items():
        entry = route["bars"][number - 1]
        assert bars[number - 1]["events"] is None, (number, "unsafe_write")
        assert (entry["status"], entry["reason"], entry["detail"]) == ("refused", reason, detail)
        assert entry["location"] == dict(page_index=0, system_index=system,
                                         bar_index=number - 1, event_index=event)
        evidence = entry["refusal_evidence"]
        assert evidence["source"] == source
        bbox = evidence["bbox"]
        assert len(bbox) == 4 and bbox[0] < bbox[2] and bbox[1] < bbox[3]
        if source == "notation_tab_column":
            assert (evidence["notation_head_count"], evidence["tab_candidate_count"],
                    evidence["distinct_tab_strings"]) == (2, 1, 1)
            assert len(evidence["tab_candidate_ids"]) == 1
            assert evidence["dx_spaces"] == 0.0
        else:
            assert evidence["cause"] == detail
