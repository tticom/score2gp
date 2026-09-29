"""DUR-02 independent comparator: a produced Guitar Pro file against the ground-truth file, per event.

Standard library only; it never imports score2gp, so it cannot share a defect with the writer it
judges. Both files are read by the same reader straight from their GPIF records. Per bar it compares,
each field on its own: the time signature, then per event the kind (note or rest), the written note
value (``NoteValue``), dots (``AugmentationDot``), the tuplet ratio (``PrimaryTuplet``), the tie
(origin, destination) and the chord's (string, fret) positions. A bar the product refused is written
empty (no beats, no invented rest); it counts against coverage and is never compared as if it were
written.

The tests below are negative controls: each mutates one field of a synthetic GPIF and requires the
comparator to report exactly that difference, located by bar and event index.
"""

from __future__ import annotations

import io
import html
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

WRITTEN = {"Whole": "whole", "Half": "half", "Quarter": "quarter", "Eighth": "eighth",
           "16th": "16th", "32nd": "32nd", "64th": "64th"}
RHYTHM_TAGS = {"NoteValue", "AugmentationDot", "PrimaryTuplet"}
TECHNIQUE_FIELDS = ("hopo_origin", "hopo_destination", "slide", "vibrato", "palm_mute", "let_ring")
EVENT_FIELDS = ("kind", "written", "dots", "tuplet", "tie", "positions", *TECHNIQUE_FIELDS)


class OracleRefusal(Exception):
    """The reader met a GPIF element it does not read; it refuses rather than skipping it."""


def read_gp_metadata(gp: Path | bytes) -> dict[str, object]:
    """Read final GPIF score fields without importing production code."""
    data = gp if isinstance(gp, bytes) else Path(gp).read_bytes()
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("Content/score.gpif"))
    score = root.find("Score")
    if score is None:
        raise OracleRefusal("Score absent")
    fields: dict[str, object] = {}
    for name in ("Title", "Music", "Copyright"):
        fields[name] = score.findtext(name) or ""
    for name in ("FirstPageHeader", "FirstPageFooter", "PageHeader", "PageFooter"):
        value = score.findtext(name) or ""
        fields[name] = tuple(re.findall(r"%[A-Za-z&]+%", value))
        if name == "PageHeader" and value.strip():
            fields[name] = ("LITERAL_PAGE_HEADER",) + fields[name]
    return fields


def compare_gp_metadata(truth: Path | bytes, produced: Path | bytes) -> dict[str, tuple[object, object]]:
    expected, actual = read_gp_metadata(truth), read_gp_metadata(produced)
    return {name: (expected[name], actual[name]) for name in expected if expected[name] != actual[name]}


def read_gp_template_text(gp: Path | bytes) -> dict[str, str]:
    data = gp if isinstance(gp, bytes) else Path(gp).read_bytes()
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("Content/score.gpif"))
    score = root.find("Score")
    if score is None:
        raise OracleRefusal("Score absent")
    return {name: html.unescape(score.findtext(name) or "") for name in
            ("FirstPageHeader", "FirstPageFooter", "PageHeader", "PageFooter")}


def read_gp_bars(gp: Path | bytes) -> list[dict[str, Any]]:
    """Per bar: its time signature and its events, or ``events=None`` for a bar with no beats."""
    data = gp if isinstance(gp, bytes) else Path(gp).read_bytes()
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("Content/score.gpif"))

    def table(container: str, item: str) -> dict[str, ET.Element]:
        node = root.find(container)
        return {} if node is None else {e.get("id"): e for e in node.findall(item)}

    bars, voices, beats = table("Bars", "Bar"), table("Voices", "Voice"), table("Beats", "Beat")
    rhythms, notes = table("Rhythms", "Rhythm"), table("Notes", "Note")
    out = []
    for index, master in enumerate(root.find("MasterBars").findall("MasterBar")):
        bar_ids = master.find("Bars").text.split()
        if len(bar_ids) != 1:
            raise OracleRefusal(f"bar {index}: {len(bar_ids)} staves")
        voice_ids = [v for v in (bars[bar_ids[0]].findtext("Voices") or "").split() if v != "-1"]
        voice_ids = [v for v in voice_ids if (voices[v].findtext("Beats") or "").split()]
        if len(voice_ids) > 1:
            raise OracleRefusal(f"bar {index}: {len(voice_ids)} voices")
        events = None
        if voice_ids:
            events = []
            for beat_id in voices[voice_ids[0]].findtext("Beats").split():
                beat = beats[beat_id]
                rhythm = rhythms[beat.find("Rhythm").get("ref")]
                unknown = sorted({child.tag for child in rhythm} - RHYTHM_TAGS)
                if unknown:
                    raise OracleRefusal(f"bar {index}: rhythm element {unknown}")
                value = rhythm.findtext("NoteValue")
                dot = rhythm.find("AugmentationDot")
                tuplet = rhythm.find("PrimaryTuplet")
                note_ids = (beat.findtext("Notes") or "").split()
                positions, origins, destinations = [], [], []
                techniques: dict[str, list[tuple[Any, ...]]] = {field: [] for field in TECHNIQUE_FIELDS}
                for nid in note_ids:
                    note = notes[nid]
                    props = {p.get("name"): p for p in note.iterfind("Properties/Property")}
                    position = (int(props["String"].findtext("String")), int(props["Fret"].findtext("Fret")))
                    positions.append(position)
                    for field, prop_name in (("hopo_origin", "HopoOrigin"),
                                             ("hopo_destination", "HopoDestination")):
                        if prop_name in props:
                            techniques[field].append(position)
                    if "Slide" in props or note.find("Slide") is not None:
                        flag = props["Slide"].findtext("Flags") if "Slide" in props else note.findtext("Slide")
                        techniques["slide"].append((*position, flag))
                    if "Vibrato" in props or note.find("Vibrato") is not None:
                        wave = props["Vibrato"].findtext("WaveSize") if "Vibrato" in props else note.findtext("Vibrato")
                        techniques["vibrato"].append((*position, wave))
                    for field, tag in (("palm_mute", "PalmMute"), ("let_ring", "LetRing")):
                        if note.find(tag) is not None or tag in props:
                            techniques[field].append(position)
                    tie = note.find("Tie")
                    origins.append(tie is not None and tie.get("origin") == "true")
                    destinations.append(tie is not None and tie.get("destination") == "true")
                events.append({
                    "kind": "note" if note_ids else "rest",
                    # A value Guitar Pro does not write is compared verbatim, so it shows as a difference.
                    "written": WRITTEN.get(value, f"unrecognised:{value}"),
                    "dots": int(dot.get("count")) if dot is not None else 0,
                    "tuplet": (int(tuplet.get("num")), int(tuplet.get("den"))) if tuplet is not None else None,
                    "tie": (any(origins), any(destinations)),
                    "positions": sorted(positions),
                    **{field: sorted(values) for field, values in techniques.items()},
                })
        key = master.find("Key")
        count = int(key.findtext("AccidentalCount")) if key is not None else None
        out.append({"time": master.findtext("Time"), "key_count": count,
                     "key_mode": key.findtext("Mode") if key is not None else None,
                    "double_bar": master.find("DoubleBar") is not None,
                    "repeat_start": master.find("RepeatStart") is not None,
                    "repeat_count": (int(master.find("Repeat").get("count"))
                                     if master.find("Repeat") is not None else None),
                    "events": events})
    return out


def compare_gp(truth: Path | bytes, produced: Path | bytes,
               mode_evidence: set[int] | None = None) -> dict[str, Any]:
    """Every difference between the produced file and the truth, by bar and event index."""
    want, have = read_gp_bars(truth), read_gp_bars(produced)
    differences: list[dict[str, Any]] = []
    written_bars = compared_events = equal_events = 0
    if len(want) != len(have):
        differences.append({"bar_index": None, "event_index": None, "field": "bar_count",
                            "expected": len(want), "actual": len(have)})
    for bar, (w, h) in enumerate(zip(want, have)):
        for field in ("double_bar", "repeat_start", "repeat_count"):
            if w[field] != h[field]:
                differences.append({"bar_index": bar, "event_index": None, "field": field,
                                    "expected": w[field], "actual": h[field]})
        if w["key_count"] != h["key_count"]:
            differences.append({"bar_index": bar, "event_index": None, "field": "key_accidental_count",
                                "expected": w["key_count"], "actual": h["key_count"]})
        if mode_evidence and bar in mode_evidence and w["key_mode"] != h["key_mode"]:
            differences.append({"bar_index": bar, "event_index": None, "field": "key_mode",
                                "expected": w["key_mode"], "actual": h["key_mode"]})
        if h["events"] is None:
            continue  # refused by the product: written empty, counted against coverage
        written_bars += 1
        if w["time"] != h["time"]:
            differences.append({"bar_index": bar, "event_index": None, "field": "time_signature",
                                "expected": w["time"], "actual": h["time"]})
        w_events = w["events"] or []
        for index in range(max(len(w_events), len(h["events"]))):
            if index >= len(w_events) or index >= len(h["events"]):
                differences.append({"bar_index": bar, "event_index": index, "field": "presence",
                                    "expected": index < len(w_events), "actual": index < len(h["events"])})
                continue
            compared_events += 1
            fields = [f for f in EVENT_FIELDS if w_events[index][f] != h["events"][index][f]]
            for f in fields:
                differences.append({"bar_index": bar, "event_index": index, "field": f,
                                    "expected": w_events[index][f], "actual": h["events"][index][f]})
            equal_events += not fields
    return {
        "source_bars": len(want),
        "written_bars": written_bars,
        "refused_bars": [bar for bar, h in enumerate(have) if h["events"] is None],
        "source_events": sum(len(w["events"] or []) for w in want),
        "compared_events": compared_events,
        "equal_events": equal_events,
        "differences": differences,
        "difference_counts": _counts(d["field"] for d in differences),
    }


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


# --- negative controls ---------------------------------------------------------------------------

def _gp(bars: list[list[dict[str, Any]] | None],
        keys: list[tuple[int, str] | None] | None = None,
        barlines: list[tuple[bool, bool, int | None]] | None = None) -> bytes:
    """A minimal GPIF package. Each event: kind, written, dots, tuplet, tie, positions."""
    root = ET.Element("GPIF")
    masters, bar_db, voice_db, beat_db = (ET.SubElement(root, n) for n in ("MasterBars", "Bars", "Voices", "Beats"))
    note_db, rhythm_db = ET.SubElement(root, "Notes"), ET.SubElement(root, "Rhythms")
    names = {"whole": "Whole", "half": "Half", "quarter": "Quarter", "eighth": "Eighth",
             "16th": "16th", "32nd": "32nd", "64th": "64th"}
    counters = {"voice": 0, "beat": 0, "note": 0, "rhythm": 0}
    for index, events in enumerate(bars):
        master = ET.SubElement(masters, "MasterBar")
        if barlines is not None:
            double, repeat_start, repeat_count = barlines[index]
            if double:
                ET.SubElement(master, "DoubleBar")
            if repeat_start:
                ET.SubElement(master, "RepeatStart")
            if repeat_count is not None:
                ET.SubElement(master, "Repeat", {"count": str(repeat_count)})
        if keys is not None and keys[index] is not None:
            fifths, mode = keys[index]
            key = ET.SubElement(master, "Key")
            ET.SubElement(key, "AccidentalCount").text = str(fifths)
            ET.SubElement(key, "Mode").text = mode
            ET.SubElement(key, "TransposeAs").text = "Flats" if fifths < 0 else "Sharps"
        ET.SubElement(master, "Time").text = "4/4"
        ET.SubElement(master, "Bars").text = str(index)
        bar = ET.SubElement(bar_db, "Bar", {"id": str(index)})
        if events is None:
            ET.SubElement(bar, "Voices").text = "-1 -1 -1 -1"
            continue
        voice_id = str(counters["voice"])
        counters["voice"] += 1
        ET.SubElement(bar, "Voices").text = f"{voice_id} -1 -1 -1"
        beat_ids = []
        for event in events:
            rhythm_id = str(counters["rhythm"])
            counters["rhythm"] += 1
            rhythm = ET.SubElement(rhythm_db, "Rhythm", {"id": rhythm_id})
            ET.SubElement(rhythm, "NoteValue").text = names[event["written"]]
            if event.get("dots"):
                ET.SubElement(rhythm, "AugmentationDot", {"count": str(event["dots"])})
            if event.get("tuplet"):
                ET.SubElement(rhythm, "PrimaryTuplet", {"num": str(event["tuplet"][0]), "den": str(event["tuplet"][1])})
            beat_id = str(counters["beat"])
            counters["beat"] += 1
            beat_ids.append(beat_id)
            beat = ET.SubElement(beat_db, "Beat", {"id": beat_id})
            ET.SubElement(beat, "Rhythm", {"ref": rhythm_id})
            note_ids = []
            for string, fret in event.get("positions", []):
                note_id = str(counters["note"])
                counters["note"] += 1
                note_ids.append(note_id)
                note = ET.SubElement(note_db, "Note", {"id": note_id})
                start, stop = event.get("tie", (False, False))
                if start or stop:
                    ET.SubElement(note, "Tie", {"origin": str(start).lower(), "destination": str(stop).lower()})
                props = ET.SubElement(note, "Properties")
                for name, tag, value in (("String", "String", string), ("Fret", "Fret", fret)):
                    prop = ET.SubElement(props, "Property", {"name": name})
                    ET.SubElement(prop, tag).text = str(value)
                for field, prop_name in (("hopo_origin", "HopoOrigin"),
                                         ("hopo_destination", "HopoDestination"),
                                         ("slide", "Slide"), ("vibrato", "Vibrato")):
                    for item in event.get(field, []):
                        if item[:2] == (string, fret):
                            prop = ET.SubElement(props, "Property", {"name": prop_name})
                            if field.startswith("hopo"):
                                ET.SubElement(prop, "Enable")
                            else:
                                ET.SubElement(prop, "Flags" if field == "slide" else "WaveSize").text = item[2]
                for field, tag in (("palm_mute", "PalmMute"), ("let_ring", "LetRing")):
                    if (string, fret) in event.get(field, []):
                        ET.SubElement(note, tag)
            if note_ids:
                ET.SubElement(beat, "Notes").text = " ".join(note_ids)
        voice = ET.SubElement(voice_db, "Voice", {"id": voice_id})
        ET.SubElement(voice, "Beats").text = " ".join(beat_ids)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("Content/score.gpif", ET.tostring(root))
    return buffer.getvalue()


def _bar() -> list[dict[str, Any]]:
    return [
        {"kind": "note", "written": "quarter", "positions": [(3, 5)]},
        {"kind": "note", "written": "eighth", "tuplet": (3, 2), "positions": [(2, 7)]},
        {"kind": "note", "written": "eighth", "tuplet": (3, 2), "positions": [(2, 8)]},
        {"kind": "note", "written": "eighth", "tuplet": (3, 2), "tie": (True, False), "positions": [(2, 8)]},
        {"kind": "rest", "written": "quarter", "dots": 1},
        {"kind": "note", "written": "eighth", "tie": (False, True), "positions": [(1, 3), (2, 8)]},
    ]


def test_metadata_oracle_rejects_double_escaped_words_music_token():
    def package(template: str) -> bytes:
        root = ET.Element("GPIF")
        score = ET.SubElement(root, "Score")
        ET.SubElement(score, "FirstPageHeader").text = template
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Content/score.gpif", ET.tostring(root))
        return buffer.getvalue()

    assert read_gp_metadata(package("%WORDS&MUSIC%"))["FirstPageHeader"] == ("%WORDS&MUSIC%",)
    assert read_gp_metadata(package("%WORDS&amp;MUSIC%"))["FirstPageHeader"] == ()


def test_master_bar_double_and_repeats_are_independent_even_on_empty_bars():
    truth = _gp([None, _bar()], barlines=[(True, False, None), (False, True, 3)])
    produced = _gp([None, _bar()], barlines=[(False, False, None), (True, False, 2)])
    differences = compare_gp(truth, produced)["differences"]
    assert [(d["bar_index"], d["field"]) for d in differences] == [
        (0, "double_bar"), (1, "double_bar"), (1, "repeat_start"), (1, "repeat_count")]


def test_identical_files_have_no_difference():
    result = compare_gp(_gp([_bar(), _bar()]), _gp([_bar(), _bar()]))
    assert result["differences"] == [] and result["written_bars"] == 2 and result["equal_events"] == 12


def test_key_count_is_compared_on_every_bar_including_empty_bars():
    truth = _gp([_bar(), None, _bar()], keys=[(1, "Major"), (-2, "Major"), (0, "Major")])
    produced = _gp([_bar(), None, _bar()], keys=[(0, "Major"), None, (1, "Major")])
    result = compare_gp(truth, produced)
    assert [(d["bar_index"], d["field"]) for d in result["differences"]] == [
        (0, "key_accidental_count"), (1, "key_accidental_count"), (2, "key_accidental_count")]


def test_key_mode_is_compared_only_where_source_evidences_it():
    truth = _gp([_bar(), _bar()], keys=[(1, "Major"), (1, "Minor")])
    produced = _gp([_bar(), _bar()], keys=[(1, "Minor"), (1, "Major")])
    result = compare_gp(truth, produced, mode_evidence={1})
    assert [(d["bar_index"], d["field"]) for d in result["differences"]] == [(1, "key_mode")]


def test_each_technique_placement_is_compared_by_bar_and_event():
    reference = _bar()
    reference[0] = {**reference[0], "hopo_origin": [(3, 5)], "slide": [(3, 5, "1")],
                    "vibrato": [(3, 5, "Wide")], "palm_mute": [(3, 5)], "let_ring": [(3, 5)]}
    reference[1] = {**reference[1], "hopo_destination": [(2, 7)]}
    for field in TECHNIQUE_FIELDS:
        changed = [dict(event) for event in reference]
        index = 1 if field == "hopo_destination" else 0
        changed[index].pop(field)
        result = compare_gp(_gp([reference]), _gp([changed]))
        assert [(d["bar_index"], d["event_index"], d["field"]) for d in result["differences"]] == [(0, index, field)]


def test_word_spellings_of_short_note_values_are_reported_as_differences():
    for source_name, alternate_name in ((b"16th", b"Sixteenth"),
                                        (b"32nd", b"ThirtySecond"),
                                        (b"64th", b"SixtyFourth")):
        truth = _gp([[{"kind": "note", "written": source_name.decode(), "positions": [(3, 5)]}]])
        truth_gpif = zipfile.ZipFile(io.BytesIO(truth)).read("Content/score.gpif")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as package:
            package.writestr("Content/score.gpif", truth_gpif.replace(
                b"<NoteValue>" + source_name + b"</NoteValue>",
                b"<NoteValue>" + alternate_name + b"</NoteValue>"))
        assert [(d["bar_index"], d["event_index"], d["field"], d["actual"])
                for d in compare_gp(truth, buffer.getvalue())["differences"]] == [
                    (0, 0, "written", f"unrecognised:{alternate_name.decode()}")]


def _mutated(event_index: int, field: str, value: Any) -> bytes:
    bar = _bar()
    bar[event_index] = {**bar[event_index], field: value}
    return _gp([_bar(), bar])


def test_each_field_is_compared_on_its_own_and_located():
    cases = [
        (0, "written", "eighth", "written"),
        (4, "dots", 0, "dots"),
        (1, "tuplet", None, "tuplet"),
        (3, "tie", (False, False), "tie"),
        (0, "positions", [(3, 6)], "positions"),
        (5, "positions", [(1, 3)], "positions"),
    ]
    for event_index, key, value, field in cases:
        result = compare_gp(_gp([_bar(), _bar()]), _mutated(event_index, key, value))
        assert [(d["bar_index"], d["event_index"], d["field"]) for d in result["differences"]] == [(1, event_index, field)]


def test_a_rest_written_as_a_note_is_a_kind_difference():
    result = compare_gp(_gp([_bar()]), _gp([[{**e, "kind": "note", "positions": [(1, 0)]} if e["kind"] == "rest" else e
                                             for e in _bar()]]))
    assert {(d["event_index"], d["field"]) for d in result["differences"]} == {(4, "kind"), (4, "positions")}


def test_a_refused_bar_counts_against_coverage_and_is_not_compared():
    result = compare_gp(_gp([_bar(), _bar()]), _gp([None, _bar()]))
    assert result["written_bars"] == 1 and result["refused_bars"] == [0] and result["differences"] == []


def test_a_note_value_guitar_pro_does_not_write_is_a_difference():
    gpif = zipfile.ZipFile(io.BytesIO(_gp([_bar()]))).read("Content/score.gpif")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("Content/score.gpif", gpif.replace(b"<NoteValue>Quarter</NoteValue>", b"<NoteValue>Crotchet</NoteValue>"))
    produced = buffer.getvalue()
    result = compare_gp(_gp([_bar()]), produced)
    assert {(d["event_index"], d["field"], d["actual"]) for d in result["differences"]} == {(0, "written", "unrecognised:Crotchet"), (4, "written", "unrecognised:Crotchet")}


def test_a_missing_event_is_located():
    result = compare_gp(_gp([_bar()]), _gp([_bar()[:-1]]))
    assert [(d["bar_index"], d["event_index"], d["field"]) for d in result["differences"]] == [(0, 5, "presence")]


def test_the_oracle_never_imports_score2gp():
    source = Path(__file__).read_text(encoding="utf-8")
    assert "import " + "score2gp" not in source and "from " + "score2gp" not in source
