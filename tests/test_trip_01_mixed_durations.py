"""TRIP-01 real-source rhythm checks; committed evidence is counts only.

The target's bar groups have eighth bases. Its swing legend also illustrates
a quarter plus an eighth under a 3:2 bracket, outside the bars. Lesson-6
also exercises a quarter inside a mixed-value 3:2 bracket. No synthetic source
has acceptance weight. The target GP is unreadable: its oracle is the PDF,
and those observations are not independently verified.
"""
from collections import Counter
from fractions import Fraction
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

from score2gp.notation_omr import note_duration as nd
from test_dur_01_lessons_4_7 import _compare_module
from test_dur_02_oracle import read_gp_bars


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
TARGET = PRIVATE / "Mixing Lead & Rhythm pt1.pdf"


def _printed_counts():
    # Measured from all four printed pages, per bar (quarter, eighth, half,
    # triplet groups). Chords count once. No pitches or event sequences.
    counts = {bar: (0, 8, 0, 0) for bar in range(1, 46, 2)}
    counts[2] = (0, 8, 0, 0)
    counts.update({bar: (4, 0, 0, 0) for bar in (6, 8, 10, 12)})
    counts.update({bar: (2, 4, 0, 0) for bar in (14, 16, 18, 20, 22)})
    counts.update({bar: (1, 9, 0, 3) for bar in (26, 28, 30, 38)})
    counts.update({bar: (2, 6, 0, 2) for bar in (34, 40)})
    counts.update({24: (1, 7, 0, 1), 32: (1, 8, 0, 2),
                   36: (1, 7, 0, 1), 42: (1, 6, 0, 0),
                   44: (0, 9, 0, 1), 46: (1, 2, 1, 0)})
    return counts


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    assert TARGET.is_file(), "REQUIRED_TRIP_01_PDF_MISSING"
    scratch = tmp_path_factory.mktemp("trip01")
    output = scratch / "result.gp"
    build = scratch / "build"
    run = subprocess.run([
        sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(TARGET),
        "--pdf-only-tab", "--out", str(output), "--work-dir", str(build),
    ], cwd=ROOT, capture_output=True)
    # Keep raw private diagnostics out of assertion output.
    assert run.returncode == 0, f"TRIP_01_CONVERSION_EXIT_{run.returncode}"
    return (json.loads((build / "note-durations.json").read_bytes()),
            json.loads((build / "note-type-route.json").read_bytes()),
            read_gp_bars(output))


def _assert_target(records):
    assert records["summary"]["bars"] == 46
    for bar, (quarters, eighths, halves, groups) in _printed_counts().items():
        events = [e for e in records["events"] if e["bar_index"] == bar - 1]
        assert all(e["status"] == "read" for e in events), f"UNREAD_BAR_{bar}"
        assert Counter(e["written"] for e in events) == +Counter(
            quarter=quarters, eighth=eighths, half=halves), f"WRITTEN_TYPES_BAR_{bar}"
        tuplets = [e for e in events if e["tuplet"]]
        assert len({e["tuplet"]["group"] for e in tuplets}) == groups, f"GROUPS_BAR_{bar}"
        assert len(tuplets) == 3 * groups, f"MEMBERS_BAR_{bar}"
        for e in tuplets:
            assert e["written"] == "eighth", f"BASE_BAR_{bar}"
            assert (e["tuplet"]["actual"], e["tuplet"]["normal"]) == (3, 2)
            assert Fraction(e["duration_quarters"]) == Fraction(1, 3), f"DURATION_BAR_{bar}"


def test_printed_mixed_values_reach_packaged_gp(converted):
    """Reject dropped groups, eighth-to-quarter substitution and writer loss."""
    records, route, packaged = converted
    _assert_target(records)
    assert Counter(b["status"] for b in route["bars"]) == {"written": 45, "refused": 1}
    refused = [b for b in route["bars"] if b["status"] == "refused"]
    assert [(b["source_bar_index"], b["reason"], b["detail"]) for b in refused] == [
        (3, "note_duration_event_unread", "tuplet_number_unassociated")]
    assert packaged[3]["events"] is None
    # Independent package reader checks transport after the PDF count oracle.
    for bar in _printed_counts():
        observed = packaged[bar - 1]["events"]
        source = [e for e in records["events"] if e["bar_index"] == bar - 1]
        assert len(observed) == len(source), f"PACKAGED_COUNT_BAR_{bar}"
        assert [(e["written"], e["dots"], e["tuplet"]) for e in observed] == [
            (e["written"], e["dots"]["count"],
             (e["tuplet"]["actual"], e["tuplet"]["normal"]) if e["tuplet"] else None)
            for e in source], f"PACKAGED_RHYTHM_BAR_{bar}"


def _assert_quarter(records):
    compare = _compare_module()
    truth = compare.rhythm_ground_truth(PRIVATE / "Lesson-6.gp")
    summary = compare.compare(records, truth)["summary"]
    assert summary["mismatches"] == [], "LESSON_6_RHYTHM_MISMATCH"
    quarters = [e for e in records["events"] if e["tuplet"] and e["written"] == "quarter"]
    assert len(quarters) == 1, "QUARTER_TUPLET_WITNESS_REQUIRED"
    assert Fraction(quarters[0]["duration_quarters"]) == Fraction(2, 3)


def test_quarter_in_printed_mixed_tuplet_matches_readable_reference():
    """Reject treating the un-beamed quarter as an ordinary quarter."""
    assert (PRIVATE / "Lesson-6.pdf").is_file(), "REQUIRED_LESSON_6_PDF_MISSING"
    assert (PRIVATE / "Lesson-6.gp").is_file(), "REQUIRED_LESSON_6_GP_MISSING"
    _assert_quarter(nd.read_note_durations(PRIVATE / "Lesson-6.pdf"))


@pytest.mark.parametrize("base", ["quarter", "eighth"])
def test_drop_tuplet_scaling_mutant_is_killed(monkeypatch, base):
    """DROP_QUARTER_TRIPLET / DROP_EIGHTH_TRIPLET at the production seam.

    Mutate executable reader logic, not its output or oracle. Recognition still
    sees the genuine source shapes and grouping. Each control must pass first.
    """
    source = PRIVATE / "Lesson-6.pdf" if base == "quarter" else TARGET
    check = _assert_quarter if base == "quarter" else _assert_target
    check(nd.read_note_durations(source))
    original = inspect.getsource(nd._record)
    needle = 'if record["tuplet"] and not grace:'
    assert original.count(needle) == 1, "MUTATION_SEAM_CHANGED"
    mutated = original.replace(needle, needle[:-1] + f' and written != "{base}":')
    namespace = dict(vars(nd))
    exec(compile(mutated, "<trip01-drop-tuplet-scaling>", "exec"), namespace)
    monkeypatch.setattr(nd, "_record", namespace["_record"])
    failure = "LESSON_6_RHYTHM_MISMATCH" if base == "quarter" else "DURATION_BAR_"
    with pytest.raises(AssertionError, match=failure):
        check(nd.read_note_durations(source))
