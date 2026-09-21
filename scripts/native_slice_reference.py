#!/usr/bin/env python3
"""Independent Guitar Pro (GPIF) reference reader and comparator for the L3-NATIVE acceptance slice.

Standard library only. This module must never import ``score2gp``: it is the oracle side of the
acceptance harness and has to stay independent of the parser, writer and generation code it judges.

It expands reused GPIF records *by occurrence* (MasterBar -> Bar -> Voice -> Beat -> Note), validates
every id and link, normalises the result to exact rational quarter-note offsets, and compares two
normalised documents layer by layer. Every element or property outside the explicit allowlists below
raises ``ReferenceError`` instead of being skipped, so an unsupported musical feature can never be
silently ignored.

Commands::

    python scripts/native_slice_reference.py expand --gp <file.gp> --out <normalised.json>
    python scripts/native_slice_reference.py compare --expected <a.gp|a.json> --actual <b.gp|b.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "native-slice-reference.v0.1"
GPIF_MEMBER = "Content/score.gpif"
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_DIVERGENCES = 50

NOTE_VALUES = {
    "Whole": Fraction(4),
    "Half": Fraction(2),
    "Quarter": Fraction(1),
    "Eighth": Fraction(1, 2),
    "16th": Fraction(1, 4),
    "32nd": Fraction(1, 8),
    "64th": Fraction(1, 16),
    "128th": Fraction(1, 32),
}

# Supported fields. Anything else is an ``unsupported_feature`` error.
MASTERBAR_TAGS = {"Key", "Time", "Bars", "DoubleBar", "XProperties"}
KEY_TAGS = {"AccidentalCount", "Mode", "TransposeAs"}
BAR_TAGS = {"Clef", "Voices", "XProperties"}
VOICE_TAGS = {"Beats"}
BEAT_TAGS = {
    "Dynamic", "Rhythm", "TransposedPitchStemOrientation", "ConcertPitchStemOrientation",
    "FreeText", "Notes", "Properties", "XProperties", "Arpeggio",
}
BEAT_PROPERTY_NAMES = {"PrimaryPickupVolume", "PrimaryPickupTone"}
NOTE_TAGS = {"InstrumentArticulation", "Properties"}
NOTE_PROPERTY_NAMES = {"ConcertPitch", "Fret", "Midi", "String", "TransposedPitch"}
RHYTHM_TAGS = {"NoteValue", "AugmentationDot"}
HEADER_FIELDS = ("Title", "SubTitle", "Artist", "Album", "Words", "Music", "WordsAndMusic", "Tabber", "Copyright")

# Playback, layout and engraving-only data. They are not PDF-expressed musical facts and are
# deliberately excluded from the comparison rather than silently unread.
IGNORED_FIELDS = [
    "Beat.Dynamic", "Beat.*StemOrientation", "Beat.Properties.PrimaryPickup*",
    "MasterBar.XProperties", "Bar.XProperties", "Beat.XProperties", "Note.InstrumentArticulation",
]

LAYERS = ("header", "tempo", "structure", "events", "notes")


class ReferenceError(ValueError):
    """A fail-closed reference problem with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def frac(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def unfrac(text: str) -> Fraction:
    n, _, d = text.partition("/")
    return Fraction(int(n), int(d or 1))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(document: Any) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------- reading


def read_gpif(path: Path) -> ET.Element:
    """Parse a ``.gp`` package (or a bare ``.gpif``); fail closed on anything unexpected."""
    path = Path(path)
    if not path.is_file():
        raise ReferenceError("source_missing", f"not a file: {path.name}")
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as package:
                members = [n for n in package.namelist() if n == GPIF_MEMBER]
                if len(members) != 1:
                    raise ReferenceError("gpif_member_missing", f"expected exactly one {GPIF_MEMBER}")
                info = package.getinfo(GPIF_MEMBER)
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ReferenceError("gpif_member_too_large", str(info.file_size))
                raw = package.read(GPIF_MEMBER)
        else:
            raw = path.read_bytes()
            if len(raw) > MAX_MEMBER_BYTES:
                raise ReferenceError("gpif_member_too_large", str(len(raw)))
        root = ET.fromstring(raw)
    except (zipfile.BadZipFile, ET.ParseError) as error:
        raise ReferenceError("source_unreadable", type(error).__name__) from error
    if root.tag != "GPIF":
        raise ReferenceError("not_gpif", f"root element is {root.tag!r}")
    return root


def _check_tags(element: ET.Element, allowed: set[str], where: str) -> None:
    for child in element:
        if child.tag not in allowed:
            raise ReferenceError("unsupported_feature", f"{where} has unsupported child <{child.tag}>")


def _records(root: ET.Element, container: str, item: str) -> dict[str, ET.Element]:
    node = root.find(container)
    if node is None:
        raise ReferenceError("missing_container", container)
    records: dict[str, ET.Element] = {}
    for child in node:
        if child.tag != item:
            raise ReferenceError("unsupported_feature", f"{container} has unexpected child <{child.tag}>")
        record_id = child.get("id")
        if record_id is None:
            raise ReferenceError("missing_id", f"<{item}> without id in {container}")
        if record_id in records:
            raise ReferenceError("duplicate_id", f"{item} id {record_id}")
        records[record_id] = child
    return records


def _id_list(text: str | None, where: str) -> list[str]:
    tokens = (text or "").split()
    for token in tokens:
        if not (token.lstrip("-").isdigit()):
            raise ReferenceError("malformed_reference", f"{where}: {token!r}")
    return tokens


def _lookup(table: dict[str, ET.Element], key: str, kind: str, where: str, used: set[str]) -> ET.Element:
    if key not in table:
        raise ReferenceError("dangling_reference", f"{where} references missing {kind} {key}")
    used.add(key)
    return table[key]


def _pitch(prop: ET.Element) -> tuple[str, str, int]:
    pitch = prop.find("Pitch")
    if pitch is None or pitch.findtext("Step") is None or pitch.findtext("Octave") is None:
        raise ReferenceError("malformed_pitch", "Pitch without Step/Octave")
    return pitch.findtext("Step", ""), (pitch.findtext("Accidental") or "").strip(), int(pitch.findtext("Octave", ""))


def _tuning(root: ET.Element) -> list[int]:
    tunings = [
        [int(v) for v in (p.findtext("Pitches") or "").split()]
        for p in root.iterfind("Tracks/Track/Staves/Staff/Properties/Property")
        if p.get("name") == "Tuning"
    ]
    if len(tunings) != 1 or not tunings[0]:
        raise ReferenceError("tuning_unresolved", f"expected exactly one tuning, found {len(tunings)}")
    return tunings[0]


def _note(element: ET.Element, where: str, tuning: list[int]) -> dict[str, Any]:
    _check_tags(element, NOTE_TAGS, where)
    properties: dict[str, ET.Element] = {}
    for prop in element.iterfind("Properties/Property"):
        name = prop.get("name")
        if name not in NOTE_PROPERTY_NAMES:
            raise ReferenceError("unsupported_feature", f"{where} has unsupported note property {name!r}")
        if name in properties:
            raise ReferenceError("duplicate_property", f"{where} repeats note property {name!r}")
        properties[name] = prop
    missing = NOTE_PROPERTY_NAMES - set(properties)
    if missing:
        raise ReferenceError("incomplete_note", f"{where} lacks {sorted(missing)}")
    fret = int(properties["Fret"].findtext("Fret", ""))
    string = int(properties["String"].findtext("String", ""))
    midi = int(properties["Midi"].findtext("Number", ""))
    concert, written = _pitch(properties["ConcertPitch"]), _pitch(properties["TransposedPitch"])
    if not 0 <= string < len(tuning):
        raise ReferenceError("string_out_of_range", f"{where}: string {string}")
    if tuning[string] + fret != midi:
        raise ReferenceError("midi_tuning_mismatch", f"{where}: string {string} fret {fret} midi {midi}")
    if concert[:2] != written[:2] or written[2] - concert[2] != 1:
        raise ReferenceError("pitch_convention_inconsistent", f"{where}: written vs sounding differ unexpectedly")
    return {"string": string, "fret": fret, "midi": midi}


def _rhythm(element: ET.Element, where: str) -> tuple[Fraction, int]:
    _check_tags(element, RHYTHM_TAGS, where)
    value = element.findtext("NoteValue")
    if value not in NOTE_VALUES:
        raise ReferenceError("unsupported_feature", f"{where} has note value {value!r}")
    dots = 0
    dot = element.find("AugmentationDot")
    if dot is not None:
        dots = int(dot.get("count", "0"))
    duration = NOTE_VALUES[value] * (2 - Fraction(1, 2 ** dots))
    return duration, dots


def _beat(element: ET.Element, where: str, tables: dict[str, dict[str, ET.Element]], used: dict[str, set[str]],
          tuning: list[int]) -> dict[str, Any]:
    _check_tags(element, BEAT_TAGS, where)
    for prop in element.iterfind("Properties/Property"):
        if prop.get("name") not in BEAT_PROPERTY_NAMES:
            raise ReferenceError("unsupported_feature", f"{where} has unsupported beat property {prop.get('name')!r}")
    rhythm_ref = element.find("Rhythm")
    if rhythm_ref is None or rhythm_ref.get("ref") is None:
        raise ReferenceError("dangling_reference", f"{where} has no rhythm reference")
    rhythm = _lookup(tables["Rhythms"], rhythm_ref.get("ref", ""), "Rhythm", where, used["Rhythms"])
    duration, dots = _rhythm(rhythm, f"{where}/Rhythm")
    note_ids = _id_list(element.findtext("Notes"), f"{where}/Notes")
    notes = sorted(
        (_note(_lookup(tables["Notes"], nid, "Note", where, used["Notes"]), f"{where}/Note {nid}", tuning)
         for nid in note_ids),
        key=lambda n: (n["string"], n["fret"], n["midi"]),
    )
    seen = [(n["string"], n["fret"]) for n in notes]
    if len(set(seen)) != len(seen):
        raise ReferenceError("duplicate_chord_member", f"{where} repeats a string/fret in one chord")
    arpeggio = element.findtext("Arpeggio")
    text = element.findtext("FreeText")
    return {
        "kind": "note" if notes else "rest",
        "duration": frac(duration),
        "dots": dots,
        "arpeggio": arpeggio,
        "text": text.strip() if text and text.strip() else None,
        "notes": notes,
    }


def _tempo(root: ET.Element) -> list[dict[str, Any]]:
    tempos = []
    for auto in root.iterfind("MasterTrack/Automations/Automation"):
        if auto.findtext("Type") != "Tempo":
            raise ReferenceError("unsupported_feature", f"automation type {auto.findtext('Type')!r}")
        bpm, unit = (auto.findtext("Value") or "").split()
        tempos.append({"bar": int(auto.findtext("Bar", "0")), "position": auto.findtext("Position"), "bpm": int(bpm), "unit": int(unit)})
    return tempos


def expand(root: ET.Element) -> dict[str, Any]:
    """Expand a parsed GPIF tree into the normalised, occurrence-level document."""
    tables = {
        "Bars": _records(root, "Bars", "Bar"), "Voices": _records(root, "Voices", "Voice"),
        "Beats": _records(root, "Beats", "Beat"), "Notes": _records(root, "Notes", "Note"),
        "Rhythms": _records(root, "Rhythms", "Rhythm"),
    }
    used: dict[str, set[str]] = {name: set() for name in tables}
    tuning = _tuning(root)
    staff_count = len(root.findall("Tracks/Track/Staves/Staff"))
    master = root.find("MasterBars")
    if master is None or not len(master):
        raise ReferenceError("missing_container", "MasterBars")

    measures: list[dict[str, Any]] = []
    for m_index, master_bar in enumerate(master):
        where = f"MasterBar {m_index}"
        if master_bar.tag != "MasterBar":
            raise ReferenceError("unsupported_feature", f"MasterBars has unexpected child <{master_bar.tag}>")
        _check_tags(master_bar, MASTERBAR_TAGS, where)
        key_node = master_bar.find("Key")
        if key_node is None:
            raise ReferenceError("incomplete_measure", f"{where} has no key")
        _check_tags(key_node, KEY_TAGS, f"{where}/Key")
        try:
            numerator, denominator = (int(v) for v in (master_bar.findtext("Time") or "").split("/"))
        except ValueError as error:
            raise ReferenceError("malformed_time", where) from error
        capacity = Fraction(numerator * 4, denominator)
        bar_ids = _id_list(master_bar.findtext("Bars"), f"{where}/Bars")
        if len(bar_ids) != staff_count:
            raise ReferenceError("bar_count_mismatch", f"{where}: {len(bar_ids)} bars for {staff_count} staves")
        staves = []
        for s_index, bar_id in enumerate(bar_ids):
            bar = _lookup(tables["Bars"], bar_id, "Bar", where, used["Bars"])
            _check_tags(bar, BAR_TAGS, f"{where}/Bar {bar_id}")
            voices = []
            slots = _id_list(bar.findtext("Voices"), f"{where}/Bar {bar_id}/Voices")
            for v_index, voice_id in enumerate(slots):
                if voice_id == "-1":
                    continue
                voice = _lookup(tables["Voices"], voice_id, "Voice", where, used["Voices"])
                _check_tags(voice, VOICE_TAGS, f"{where}/Voice {voice_id}")
                beat_ids = _id_list(voice.findtext("Beats"), f"{where}/Voice {voice_id}/Beats")
                if not beat_ids:
                    raise ReferenceError("empty_voice", f"{where}: voice {voice_id} has no beats")
                events, onset = [], Fraction(0)
                for beat_id in beat_ids:
                    beat = _lookup(tables["Beats"], beat_id, "Beat", where, used["Beats"])
                    event = _beat(beat, f"{where}/Beat {beat_id}", tables, used, tuning)
                    event["onset"] = frac(onset)
                    onset += unfrac(event["duration"])
                    events.append(event)
                if onset != capacity:
                    raise ReferenceError("voice_duration_mismatch", f"{where}: voice sums to {frac(onset)}, bar is {frac(capacity)}")
                voices.append({"voice": v_index, "events": events})
            if not voices:
                raise ReferenceError("empty_bar", f"{where}: staff {s_index} has no voice")
            staves.append({"staff": s_index, "voices": voices})
        measures.append({
            "index": m_index,
            "time": [numerator, denominator],
            "key": {"accidentals": int(key_node.findtext("AccidentalCount", "0")), "mode": key_node.findtext("Mode"), "transpose_as": key_node.findtext("TransposeAs")},
            "double_bar": master_bar.find("DoubleBar") is not None,
            "staves": staves,
        })

    score = root.find("Score")
    header = {name: (score.findtext(name) or "").strip() for name in HEADER_FIELDS} if score is not None else {}
    stats = _stats(measures, tables, used)
    return {
        "schema": SCHEMA,
        "conventions": {
            "string_index_zero": "lowest_pitched_string",
            "tuning_low_to_high": tuning,
            "midi_is": "sounding_pitch",
            "written_octave_above_sounding": 1,
            "duration_unit": "quarter_note_rational",
            "ignored_fields": IGNORED_FIELDS,
        },
        "header": header,
        "tempo": _tempo(root),
        "measures": measures,
        "stats": stats,
    }


def _stats(measures: list[dict[str, Any]], tables: dict[str, dict[str, ET.Element]], used: dict[str, set[str]]) -> dict[str, Any]:
    beats = [e for m in measures for s in m["staves"] for v in s["voices"] for e in v["events"]]
    return {
        "measures": len(measures),
        "definitions": {name.lower(): len(table) for name, table in tables.items()},
        "unreferenced_definitions": {name.lower(): len(set(table) - used[name]) for name, table in tables.items()},
        "beat_occurrences": len(beats),
        "note_occurrences": sum(len(e["notes"]) for e in beats),
        "rest_occurrences": sum(1 for e in beats if e["kind"] == "rest"),
        "chord_occurrences": sum(1 for e in beats if len(e["notes"]) > 1),
        "dotted_occurrences": sum(1 for e in beats if e["dots"]),
        "arpeggio_occurrences": sum(1 for e in beats if e["arpeggio"]),
        "text_labels": sum(1 for e in beats if e["text"]),
        "double_bars": sum(1 for m in measures if m["double_bar"]),
    }


def load_document(path: Path) -> dict[str, Any]:
    """Load a normalised document from a ``.gp``/``.gpif`` source or a previously expanded JSON."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReferenceError("source_unreadable", type(error).__name__) from error
        if not isinstance(document, dict) or document.get("schema") != SCHEMA:
            raise ReferenceError("schema_mismatch", f"expected {SCHEMA}")
        return document
    return expand(read_gpif(path))


# ------------------------------------------------------------------------------------- comparing


def assert_distinct_sources(reference: Path, candidate: Path) -> None:
    """Refuse to let the expected and the actual side be the same file or the same bytes."""
    ref, cand = Path(reference), Path(candidate)
    if not ref.exists() or not cand.exists():
        raise ReferenceError("source_missing", "reference and candidate must both exist")
    if os.path.samefile(ref, cand) or file_sha256(ref) == file_sha256(cand):
        raise ReferenceError("reference_alias", "candidate is the reference (same file or identical bytes)")


def _flatten(document: dict[str, Any]) -> Iterable[tuple[tuple[int, int, int, int], dict[str, Any]]]:
    for measure in document["measures"]:
        for staff in measure["staves"]:
            for voice in staff["voices"]:
                for index, event in enumerate(voice["events"]):
                    yield (measure["index"], staff["staff"], voice["voice"], index), event


def _divergence(layer: str, where: dict[str, Any], expected: Any, actual: Any) -> dict[str, Any]:
    return {"layer": layer, **where, "expected": expected, "actual": actual}


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Compare two normalised documents. Identical musical semantics pass; any difference is reported."""
    found: list[dict[str, Any]] = []

    def note(entry: dict[str, Any]) -> None:
        if len(found) < MAX_DIVERGENCES:
            found.append(entry)

    for field in sorted(set(expected["header"]) | set(actual["header"])):
        if expected["header"].get(field) != actual["header"].get(field):
            note(_divergence("header", {"field": field}, expected["header"].get(field), actual["header"].get(field)))
    if expected["tempo"] != actual["tempo"]:
        note(_divergence("tempo", {"field": "automations"}, expected["tempo"], actual["tempo"]))
    if expected["conventions"]["tuning_low_to_high"] != actual["conventions"]["tuning_low_to_high"]:
        note(_divergence("structure", {"field": "tuning"}, expected["conventions"]["tuning_low_to_high"], actual["conventions"]["tuning_low_to_high"]))

    e_measures, a_measures = expected["measures"], actual["measures"]
    if len(e_measures) != len(a_measures):
        note(_divergence("structure", {"field": "measure_count"}, len(e_measures), len(a_measures)))
    for e_m, a_m in zip(e_measures, a_measures):
        for field, e_val, a_val in (("time", e_m["time"], a_m["time"]), ("key", e_m["key"], a_m["key"]),
                                    ("double_bar", e_m["double_bar"], a_m["double_bar"])):
            if e_val != a_val:
                note(_divergence("structure", {"measure": e_m["index"], "field": field}, e_val, a_val))

    e_events, a_events = dict(_flatten(expected)), dict(_flatten(actual))
    for position in sorted(set(e_events) | set(a_events)):
        where = dict(zip(("measure", "staff", "voice", "event"), position))
        if position not in e_events or position not in a_events:
            note(_divergence("events", {**where, "field": "presence"}, position in e_events, position in a_events))
            continue
        e_ev, a_ev = e_events[position], a_events[position]
        for field in ("kind", "onset", "duration", "dots", "arpeggio", "text"):
            if e_ev[field] != a_ev[field]:
                note(_divergence("events", {**where, "field": field}, e_ev[field], a_ev[field]))
        if e_ev["notes"] != a_ev["notes"]:
            note(_divergence("notes", {**where, "field": "chord_members"}, e_ev["notes"], a_ev["notes"]))

    layers = {layer: ("FAIL" if any(d["layer"] == layer for d in found) else "PASS") for layer in LAYERS}
    return {"equal": not found, "layers": layers, "first_divergence": found[0] if found else None, "divergences": found}


# ----------------------------------------------------------------------------------- manifest

MANIFEST_SCHEMA = "native-slice-manifest.v0.1"
ADJUDICATED = "first_system_adjudicated"


def _first_system_equivalence(reference: dict[str, Any], first_system: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare the source-read events of the first system with the reference expansion by occurrence."""
    problems: list[dict[str, Any]] = []
    tuning_size = len(reference["conventions"]["tuning_low_to_high"])
    for read in first_system["source_read"]:
        measure = read["measure"]
        if not 1 <= measure <= len(reference["measures"]):
            problems.append({"measure": measure, "field": "measure_missing"})
            continue
        events = reference["measures"][measure - 1]["staves"][0]["voices"][0]["events"]
        expected = [
            {"kind": e["kind"], "duration": e["duration"],
             "notes": sorted((tuning_size - n["string"], n["fret"]) for n in e["notes"])}
            for e in events
        ]
        observed = [
            {"kind": "note" if e["notes"] else "rest", "duration": e["duration"],
             "notes": sorted((s, f) for s, f in e["notes"])}
            for e in read["events"]
        ]
        if expected != observed:
            problems.append({"measure": measure, "field": "events", "expected_count": len(expected), "observed_count": len(observed)})
    return problems


STAFF_LINE_COVERAGE = 400.0   # points of horizontal ink for a y to count as a staff line
FULL_HEIGHT_TOLERANCE = 1.5   # points: how close a stroke must come to the staff's top and bottom lines
DOUBLE_STROKE_GAP = 4.0       # points: strokes closer than this form one double barline
BARLINE_X_TOLERANCE = 0.6


def _staff_clusters(coverage: dict[float, float]) -> list[list[float]]:
    ys = sorted(y for y, ink in coverage.items() if ink > STAFF_LINE_COVERAGE)
    clusters: list[list[float]] = [[ys[0]]] if ys else []
    for y in ys[1:]:
        if y - clusters[-1][-1] > 10:
            clusters.append([y])
        else:
            clusters[-1].append(y)
    return clusters


def _page_strokes(page: Any) -> tuple[dict[float, float], list[tuple[float, float, float]]]:
    """Horizontal ink per y (for staff lines) and vertical strokes as (x, top, bottom)."""
    coverage: dict[float, float] = {}
    vertical: list[tuple[float, float, float]] = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l" and abs(item[1].y - item[2].y) < 0.01:
                y = round(item[1].y, 2)
                coverage[y] = coverage.get(y, 0.0) + abs(item[1].x - item[2].x)
            elif item[0] == "l" and abs(item[1].x - item[2].x) < 0.01 and abs(item[1].y - item[2].y) > 3:
                vertical.append((item[1].x, min(item[1].y, item[2].y), max(item[1].y, item[2].y)))
            elif item[0] == "re" and item[1].height < 1.5 and item[1].width > 3:
                y = round((item[1].y0 + item[1].y1) / 2, 2)
                coverage[y] = coverage.get(y, 0.0) + item[1].width
            elif item[0] == "re" and item[1].width < 3 and item[1].height > 3:
                vertical.append(((item[1].x0 + item[1].x1) / 2, item[1].y0, item[1].y1))
    return coverage, vertical


def _spans(staff: list[float], stroke: tuple[float, float, float]) -> bool:
    return stroke[1] <= staff[0] + FULL_HEIGHT_TOLERANCE and stroke[2] >= staff[-1] - FULL_HEIGHT_TOLERANCE


def _system_topology(notation: list[float], tab: list[float], vertical: list[tuple[float, float, float]],
                     page_number: int, system_number: int) -> dict[str, Any]:
    notation_xs = sorted({round(s[0], 2) for s in vertical if _spans(notation, s)})
    tab_xs = sorted({round(s[0], 2) for s in vertical if _spans(tab, s)})
    paired = [x for x in notation_xs if any(abs(x - other) < BARLINE_X_TOLERANCE for other in tab_xs)]
    boundaries: list[float] = []
    secondary: list[float] = []
    for x in paired:
        if boundaries and x - boundaries[-1] < DOUBLE_STROKE_GAP:
            secondary.append(boundaries[-1])
            boundaries[-1] = x
        else:
            boundaries.append(x)
    start = min(paired) if paired else None
    interior = [x for x in boundaries if start is not None and x > start + 3]
    return {
        "page": page_number, "system": system_number, "measures": len(interior),
        "notation_staff_y": [notation[0], notation[-1]], "tab_staff_y": [tab[0], tab[-1]],
        "barline_xs": ([start] if start is not None else []) + interior,
        "double_barline_secondary_xs": secondary,
        "notation_full_height_stem_xs": [x for x in notation_xs if x not in paired],
    }


def source_topology(pdf_path: Path) -> dict[str, Any]:
    """Measure the printed measure topology from PDF vectors alone (no reference, no product code).

    Rule under test: in a paired notation/TAB system a barline is a full-height stroke on BOTH the
    five-line notation staff and the six-line TAB staff at one x. Note stems can span the notation
    staff but have no TAB counterpart, so they never qualify. Requires PyMuPDF (imported lazily so the
    rest of this module stays standard-library only).
    """
    import fitz  # noqa: PLC0415  (deliberately lazy: only the topology probe needs a PDF library)

    per_page: list[int] = []
    systems: list[dict[str, Any]] = []
    for page_number, page in enumerate(fitz.open(str(pdf_path)), 1):
        coverage, vertical = _page_strokes(page)
        clusters = _staff_clusters(coverage)
        page_measures, system_number, index = 0, 0, 0
        while index < len(clusters) - 1:
            if len(clusters[index]) == 5 and len(clusters[index + 1]) == 6:
                system_number += 1
                system = _system_topology(clusters[index], clusters[index + 1], vertical, page_number, system_number)
                page_measures += system["measures"]
                systems.append(system)
                index += 2
            else:
                index += 1
        per_page.append(page_measures)
    return {
        "method": "paired-staff rule: a barline is a full-height stroke on BOTH the notation and TAB staff at one x; near-coincident double strokes merge",
        "pages": len(per_page), "measures_per_page": per_page, "systems_total": len(systems),
        "measures_total": sum(per_page), "systems": systems, "independent_of_reference": True,
    }


def build_manifest(reference: dict[str, Any], pdf_sha256: str, gp_sha256: str, adjudication: dict[str, Any],
                   topology: dict[str, Any]) -> dict[str, Any]:
    """Bind source hashes, the occurrence-level reference, PDF-measured topology and human adjudication.

    The human input carries only what cannot be measured (the transcription read off the printed page).
    Geometry comes from ``source_topology``. Source/reference equivalence of the adjudicated system and
    the printed-measure count are re-derived here. A disagreement does not raise: it is preserved as an
    explicit blocker, because a disagreement must never be hidden.
    """
    if adjudication.get("status") != ADJUDICATED:
        raise ReferenceError("adjudication_incomplete", f"status must be {ADJUDICATED!r}")
    for key in ("first_system", "unadjudicated"):
        if key not in adjudication:
            raise ReferenceError("adjudication_incomplete", f"missing {key!r}")
    chosen = adjudication["first_system"]
    for key in ("page", "system", "printed_measures", "source_read"):
        if key not in chosen:
            raise ReferenceError("adjudication_incomplete", f"first_system missing {key!r}")
    measured = next((s for s in topology["systems"] if s["page"] == chosen["page"] and s["system"] == chosen["system"]), None)
    if measured is None:
        raise ReferenceError("adjudication_incomplete", "adjudicated system not found in the measured topology")
    first = {**chosen, **{k: v for k, v in measured.items() if k not in ("page", "system", "measures")},
             "barline_x_tolerance": BARLINE_X_TOLERANCE}
    blockers = [{"code": "source_reference_disagreement", **p} for p in _first_system_equivalence(reference, first)]
    blockers += [{"code": "unresolved_disagreement", "detail": d} for d in adjudication.get("disagreements", [])]
    if len(chosen["printed_measures"]) != measured["measures"]:
        blockers.append({"code": "printed_measure_count_disagreement",
                         "adjudicated": len(chosen["printed_measures"]), "measured": measured["measures"]})
    if topology["measures_total"] != len(reference["measures"]):
        blockers.append({"code": "topology_measure_count_disagreement",
                         "source": topology["measures_total"], "reference": len(reference["measures"])})
    return {
        "schema": MANIFEST_SCHEMA,
        "source": {"pdf_sha256": pdf_sha256, "gp_sha256": gp_sha256, "pages": topology["pages"]},
        "reference": reference,
        "reference_fingerprint": fingerprint(reference),
        "adjudication": {**adjudication, "topology": {k: v for k, v in topology.items() if k != "systems"}, "first_system": first},
        "blockers": blockers,
    }


def validate_manifest(manifest: Any) -> None:
    """Fail closed on a malformed, tampered or unresolved manifest."""
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ReferenceError("manifest_schema_mismatch", f"expected {MANIFEST_SCHEMA}")
    for key in ("source", "reference", "reference_fingerprint", "adjudication", "blockers"):
        if key not in manifest:
            raise ReferenceError("manifest_incomplete", f"missing {key!r}")
    if manifest["reference"].get("schema") != SCHEMA:
        raise ReferenceError("manifest_reference_schema", f"expected {SCHEMA}")
    if fingerprint(manifest["reference"]) != manifest["reference_fingerprint"]:
        raise ReferenceError("manifest_tampered", "reference fingerprint does not match its content")
    if manifest["adjudication"].get("status") != ADJUDICATED:
        raise ReferenceError("adjudication_incomplete", f"status must be {ADJUDICATED!r}")
    if manifest["blockers"]:
        raise ReferenceError("manifest_has_blockers", f"{len(manifest['blockers'])} unresolved blocker(s)")


# ------------------------------------------------------------------------------------------ CLI


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent GPIF reference reader and comparator.")
    sub = parser.add_subparsers(dest="command", required=True)
    expand_cmd = sub.add_parser("expand", help="expand a .gp/.gpif file into the normalised occurrence-level document")
    expand_cmd.add_argument("--gp", type=Path, required=True)
    expand_cmd.add_argument("--out", type=Path, required=True)
    manifest_cmd = sub.add_parser("build-manifest", help="bind source hashes, the reference and an adjudication into a private manifest")
    manifest_cmd.add_argument("--gp", type=Path, required=True)
    manifest_cmd.add_argument("--pdf", type=Path, required=True)
    manifest_cmd.add_argument("--adjudication", type=Path, required=True)
    manifest_cmd.add_argument("--out", type=Path, required=True)
    compare_cmd = sub.add_parser("compare", help="compare two .gp/.gpif/.json documents")
    compare_cmd.add_argument("--expected", type=Path, required=True)
    compare_cmd.add_argument("--actual", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "expand":
            document = expand(read_gpif(args.gp))
            args.out.write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")
            print(json.dumps({"status": "EXPANDED", "fingerprint": fingerprint(document), "stats": document["stats"]}))
            return 0
        if args.command == "build-manifest":
            if args.out.exists():
                raise ReferenceError("output_exists", "refusing to overwrite an existing manifest")
            adjudication = json.loads(args.adjudication.read_text(encoding="utf-8"))
            manifest = build_manifest(expand(read_gpif(args.gp)), file_sha256(args.pdf), file_sha256(args.gp), adjudication,
                                      source_topology(args.pdf))
            args.out.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
            print(json.dumps({"status": "MANIFEST_WRITTEN", "blockers": len(manifest["blockers"]),
                              "reference_fingerprint": manifest["reference_fingerprint"]}))
            return 0 if not manifest["blockers"] else 3
        assert_distinct_sources(args.expected, args.actual)
        result = compare(load_document(args.expected), load_document(args.actual))
        divergence = result["first_divergence"]
        # Only layer/field/location are printed: values may be private musical content.
        print(json.dumps({"equal": result["equal"], "layers": result["layers"],
                          "first_divergence": divergence and {k: v for k, v in divergence.items() if k not in ("expected", "actual")}}))
        return 0 if result["equal"] else 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "REFUSED", "code": "input_unreadable", "error": type(error).__name__}), file=sys.stderr)
        return 2
    except ReferenceError as error:
        print(json.dumps({"status": "REFUSED", "code": error.code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_cli())
