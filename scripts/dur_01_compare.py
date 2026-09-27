#!/usr/bin/env python
"""Compare DUR-01 duration records for a PDF with its ground-truth Guitar Pro file, per event.

The ground truth is read by the independent GPIF reader ``scripts/native_slice_reference.py``
(standard library only; it never imports score2gp), not by the product's own model. Events are
compared by bar and event index. Each symbol-level field is compared on its own: kind (note or rest),
written note value, dots, tuplet ratio, sounding duration and tie, so an equal sounding duration can
never hide a wrong note type or grouping. A row's cause is its first differing field; ``differences``
lists them all.

Writes a full comparison (with locations) and a sanitised summary that holds counts, indices and
codes only. Keep both under ``work/`` for private sources; only the sanitised summary may be quoted.

Usage::

    python scripts/dur_01_compare.py --pdf fixtures/private/Lesson-3.pdf --gp fixtures/private/Lesson-3.gp \
        --out work/dur01/lesson3
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


@functools.cache
def load_oracle():
    spec = importlib.util.spec_from_file_location("native_slice_reference", HERE / "native_slice_reference.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


NOTE_VALUES = {"Whole": Fraction(4), "Half": Fraction(2), "Quarter": Fraction(1), "Eighth": Fraction(1, 2),
               "16th": Fraction(1, 4), "32nd": Fraction(1, 8), "64th": Fraction(1, 16)}
WRITTEN = {"Whole": "whole", "Half": "half", "Quarter": "quarter", "Eighth": "eighth",
           "16th": "16th", "32nd": "32nd", "64th": "64th"}  # GPIF NoteValue -> the reader's written value
RHYTHM_TAGS = {"NoteValue", "AugmentationDot", "PrimaryTuplet"}
FIELDS = ("kind", "written", "dots", "tuplet", "duration", "tie")  # compared in this order, each on its own


def rhythm_ground_truth(gp_path: Path) -> list[list[dict[str, Any]]]:
    """Per bar, each event's independent GPIF rhythm fields, read straight from the rhythm records.

    Standard library only, like the reference reader, but limited to rhythm, so it also reads
    tuplets and tied notes, which the reference reader refuses. Each event carries its written note
    value (NoteValue), dots (AugmentationDot), tuplet ratio (PrimaryTuplet num:den, or None), tie
    (starts, stops) and, separately, the sounding duration they imply. A bar with more than one
    voice, a note value outside the reader's range or any other rhythm element (a nested tuplet)
    raises rather than being guessed.
    """
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    import zipfile  # noqa: PLC0415

    root = ET.fromstring(zipfile.ZipFile(gp_path).read("Content/score.gpif"))

    def table(container: str, item: str) -> dict[str, Any]:
        return {e.get("id"): e for e in root.find(container).findall(item)}

    bars, voices, beats, rhythms = (table("Bars", "Bar"), table("Voices", "Voice"), table("Beats", "Beat"),
                                    table("Rhythms", "Rhythm"))
    note_table = table("Notes", "Note")
    out = []
    for index, master in enumerate(root.find("MasterBars").findall("MasterBar")):
        bar_ids = master.find("Bars").text.split()
        if len(bar_ids) != 1:
            raise SystemExit(f"bar {index}: {len(bar_ids)} staves; this comparison reads one")
        voice_ids = [v for v in bars[bar_ids[0]].find("Voices").text.split() if v != "-1"]
        voice_ids = [v for v in voice_ids if voices[v].find("Beats") is not None and voices[v].find("Beats").text]
        if len(voice_ids) != 1:
            raise SystemExit(f"bar {index}: {len(voice_ids)} voices; this comparison reads one")
        events = []
        for beat_id in voices[voice_ids[0]].find("Beats").text.split():
            beat = beats[beat_id]
            rhythm = rhythms[beat.find("Rhythm").get("ref")]
            unknown = sorted({child.tag for child in rhythm} - RHYTHM_TAGS)
            if unknown:
                raise SystemExit(f"bar {index}: rhythm element {', '.join(unknown)}; this comparison cannot read it")
            note_value = rhythm.find("NoteValue").text
            if note_value not in NOTE_VALUES:
                raise SystemExit(f"bar {index}: note value {note_value}; this comparison cannot read it")
            dot = rhythm.find("AugmentationDot")
            dots = int(dot.get("count")) if dot is not None else 0
            duration = NOTE_VALUES[note_value] * (2 - Fraction(1, 2 ** dots))
            tuplet_element = rhythm.find("PrimaryTuplet")
            tuplet = None
            if tuplet_element is not None:
                tuplet = (int(tuplet_element.get("num")), int(tuplet_element.get("den")))
                duration *= Fraction(tuplet[1], tuplet[0])
            note_ids = (beat.find("Notes").text or "").split() if beat.find("Notes") is not None else []
            ties = [note_table[n].find("Tie") for n in note_ids]
            events.append({"kind": "note" if note_ids else "rest", "written": WRITTEN[note_value], "dots": dots,
                           "tuplet": tuplet, "duration": duration,
                           "tie": (any(t is not None and t.get("origin") == "true" for t in ties),
                                   any(t is not None and t.get("destination") == "true" for t in ties))})
        out.append(events)
    return out


def ground_truth(gp_path: Path) -> list[list[dict[str, Any]]]:
    """Per bar, the events of the single notation voice, read by the independent reference reader.

    The reference reader admits only NoteValue and AugmentationDot in a rhythm and refuses tuplets and
    ties, so every event it returns is untupletted and untied. Its written note value is then the one
    value whose dotted length equals the duration; exactly one exists, and a duration with none raises.
    """
    oracle = load_oracle()
    document = oracle.expand(oracle.read_gpif(gp_path))
    bars = []
    for measure in document["measures"]:
        voices = [v for staff in measure["staves"] for v in staff["voices"] if v["events"]]
        if len(voices) != 1:
            raise SystemExit(f"bar {measure['index']}: {len(voices)} voices; this comparison reads one voice")
        events = []
        for e in voices[0]["events"]:
            dots, duration = int(e["dots"]), Fraction(e["duration"])
            written = [WRITTEN[v] for v, q in NOTE_VALUES.items() if q * (2 - Fraction(1, 2 ** dots)) == duration]
            if len(written) != 1:
                raise SystemExit(f"bar {measure['index']}: duration {duration} with {dots} dots names no note value")
            events.append({"kind": "rest" if e["kind"] == "rest" else "note", "written": written[0], "dots": dots,
                           "tuplet": None, "duration": duration, "tie": (False, False)})
        bars.append(events)
    return bars


def read_fields(event: dict[str, Any]) -> dict[str, Any]:
    """The same fields as the ground truth, taken from one read product record."""
    tuplet = event["tuplet"]
    return {"kind": "rest" if event["kind"] == "rest" else "note", "written": event["written"],
            "dots": event["dots"]["count"], "tuplet": (tuplet["actual"], tuplet["normal"]) if tuplet else None,
            "duration": Fraction(event["duration_quarters"]), "tie": (event["tie"]["start"], event["tie"]["stop"])}


def compare(records: dict[str, Any], truth: list[list[dict[str, Any]]]) -> dict[str, Any]:
    read_bars: dict[int, list[dict[str, Any]]] = {}
    for event in records["events"]:
        read_bars.setdefault(event["bar_index"], []).append(event)
    for events in read_bars.values():
        events.sort(key=lambda e: e["event_index"])
    bar_to_system = {}
    for system in records["systems"]:
        for b in range(system["first_bar_index"], system["first_bar_index"] + system["bar_count"]):
            bar_to_system[b] = system
    rows = []
    for bar, expected in enumerate(truth):
        got = read_bars.get(bar, [])
        system = bar_to_system.get(bar)
        for index in range(max(len(expected), len(got))):
            row = {"bar_index": bar, "event_index": index,
                   "page_index": system["page_index"] if system else None,
                   "system_index": system["system_index"] if system else None}
            want = expected[index] if index < len(expected) else None
            have = got[index] if index < len(got) else None
            if want is None:
                row["cause"] = "extra_event"
            elif have is None:
                row["cause"] = "missing_event"
            elif have["status"] != "read":
                row["cause"] = f"unread:{have['reason']}"
            else:
                read = read_fields(have)
                row["differences"] = [f for f in FIELDS if read[f] != want[f]]
                row["cause"] = f"{row['differences'][0]}_mismatch" if row["differences"] else None
            if have is not None:
                row["location"] = have["location"]
                row["read"] = {k: have[k] for k in ("kind", "status", "reason", "written", "value_quarters", "duration_quarters")}
                row["read"]["tuplet"] = [have["tuplet"]["actual"], have["tuplet"]["normal"]] if have["tuplet"] else None
            if want is not None:
                row["expected"] = {"kind": want["kind"], "written": want["written"], "dots": want["dots"],
                                   "tuplet": list(want["tuplet"]) if want["tuplet"] else None,
                                   "duration": str(want["duration"]), "tie": list(want["tie"])}
            rows.append(row)
    total = sum(len(b) for b in truth)
    read = sum(1 for r in rows if r.get("read", {}).get("status") == "read" and "expected" in r)
    matched = sum(1 for r in rows if r["cause"] is None)
    first = records["systems"][0] if records["systems"] else None
    first_bars = set(range(first["first_bar_index"], first["first_bar_index"] + first["bar_count"])) if first else set()
    first_rows = [r for r in rows if r["bar_index"] in first_bars]
    causes: dict[str, int] = {}
    for r in rows:
        if r["cause"]:
            causes[r["cause"]] = causes.get(r["cause"], 0) + 1
    compared = [r for r in rows if "differences" in r]
    fields = {f: {"compared": len(compared), "equal": sum(1 for r in compared if f not in r["differences"])}
              for f in FIELDS}
    return {
        "rows": rows,
        "summary": {
            "ground_truth_bars": len(truth), "read_bars": records["summary"]["bars"],
            "ground_truth_events": total, "read_events": read, "matched_events": matched,
            "ground_truth_tied_events": sum(1 for b in truth for e in b if any(e["tie"])),
            "ground_truth_tupletted_events": sum(1 for b in truth for e in b if e["tuplet"]),
            "fields": fields,
            "coverage": round(read / total, 4) if total else None,
            "match_rate": round(matched / total, 4) if total else None,
            "match_rate_of_read": round(matched / read, 4) if read else None,
            "first_system": {"bars": len(first_bars), "events": sum(1 for r in first_rows if "expected" in r),
                             "matched": sum(1 for r in first_rows if r["cause"] is None),
                             "all_read_and_equal": bool(first_rows) and all(r["cause"] is None for r in first_rows)},
            "causes": dict(sorted(causes.items())),
            "mismatches": [{"page_index": r["page_index"], "system_index": r["system_index"], "bar_index": r["bar_index"],
                            "event_index": r["event_index"], "cause": r["cause"],
                            "differences": r.get("differences", [])} for r in rows if r["cause"]],
            "bar_check_status": records["summary"]["bar_check_status"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--gp", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output directory (keep under work/ for private sources)")
    parser.add_argument("--time-signature", default=None, help="Caller-declared time signature for the bar check only")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(HERE.parent / "src"))
    from score2gp.notation_omr.note_duration import read_note_durations  # noqa: PLC0415

    declared = tuple(int(p) for p in args.time_signature.split("/")) if args.time_signature else None
    records = read_note_durations(args.pdf, time_signature=declared)
    oracle = load_oracle()
    try:
        truth, reader = ground_truth(args.gp), "native_slice_reference"
    except oracle.ReferenceError as exc:
        # The reference reader refuses features outside its allowlist (tuplets, ties).
        truth, reader = rhythm_ground_truth(args.gp), f"rhythm_only (reference refused: {exc.code})"
    result = compare(records, truth)
    result["summary"]["ground_truth_reader"] = reader
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "note-durations.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (args.out / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(result["summary"], indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(json.dumps({k: s[k] for k in ("ground_truth_reader", "ground_truth_events", "read_events", "matched_events",
                                         "coverage", "match_rate", "fields", "first_system", "causes")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
