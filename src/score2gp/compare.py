from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from .ir import ScoreIR, Bar, Event, Note, KeySignature, TimeSignature, Tempo


@dataclass
class NoteData:
    pitch: int | str | None = None
    string: int | None = None
    fret: int | None = None
    tie_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pitch": self.pitch,
            "string": self.string,
            "fret": self.fret,
            "tie_type": self.tie_type,
        }


@dataclass
class EventData:
    event_type: str  # "note", "rest", "chord"
    onset_beats: float
    duration_beats: float
    onset_ticks: int | None = None
    duration_ticks: int | None = None
    is_dotted: bool = False
    dots: int = 0
    is_tied: bool = False
    chord_membership: str | None = None
    notes: list[NoteData] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "onset_beats": round(self.onset_beats, 4),
            "duration_beats": round(self.duration_beats, 4),
            "onset_ticks": self.onset_ticks,
            "duration_ticks": self.duration_ticks,
            "is_dotted": self.is_dotted,
            "dots": self.dots,
            "is_tied": self.is_tied,
            "chord_membership": self.chord_membership,
            "notes": [n.to_dict() for n in self.notes],
        }


@dataclass
class BarData:
    bar_index: int
    time_signature: tuple[int, int] = (4, 4)
    key_signature: dict[str, Any] = field(default_factory=lambda: {"fifths": 0, "mode": "major"})
    tempo: float | None = 120.0
    barline: str = "normal"  # "normal", "double", "final", "regular", "end", etc.
    system_break: bool = False
    page_break: bool = False
    events: list[EventData] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_index": self.bar_index,
            "time_signature": list(self.time_signature),
            "key_signature": self.key_signature,
            "tempo": self.tempo,
            "barline": self.barline,
            "system_break": self.system_break,
            "page_break": self.page_break,
            "events": [e.to_dict() for e in self.events],
        }


def normalize_barline_style(style: str | None) -> str:
    if not style:
        return "normal"
    s = str(style).lower().strip()
    if s in ("regular", "normal", "standard", "hidden", "dashed"):
        return "normal"
    if s in ("end", "final"):
        return "final"
    if s in ("double", "section"):
        return "double"
    if "repeat" in s:
        return s
    return s


def compact_bar_summary(bar: BarData) -> dict[str, Any]:
    event_strs = []
    for ev in bar.events:
        type_code = "R" if ev.event_type == "rest" else ("C" if ev.event_type == "chord" or len(ev.notes) > 1 else "N")
        dur_str = f"{ev.duration_beats:g}"
        if ev.is_dotted:
            dur_str += f".d{ev.dots}" if ev.dots > 1 else "."
        if ev.is_tied:
            dur_str += "~"

        note_details = []
        for n in sorted(ev.notes, key=lambda x: (x.string or 0, x.pitch or 0)):
            n_info = []
            if n.pitch is not None:
                n_info.append(f"p={n.pitch}")
            if n.string is not None:
                n_info.append(f"s={n.string}")
            if n.fret is not None:
                n_info.append(f"f={n.fret}")
            if n_info:
                note_details.append("/".join(n_info))

        notes_str = f"[{','.join(note_details)}]" if note_details else ""
        chord_str = f"{{{ev.chord_membership}}}" if ev.chord_membership else ""
        event_strs.append(f"{type_code}:{ev.onset_beats:g}({dur_str}){chord_str}{notes_str}")

    return {
        "bar_index": bar.bar_index,
        "time_signature": list(bar.time_signature),
        "key_signature": bar.key_signature,
        "tempo": bar.tempo,
        "barline": bar.barline,
        "system_break": bar.system_break,
        "page_break": bar.page_break,
        "events_summary": " ".join(event_strs) if event_strs else "(empty)",
        "event_count": len(bar.events),
    }


def _extract_bars_from_score_ir(score: ScoreIR) -> list[BarData]:
    bars_data: list[BarData] = []
    current_tempo = float(score.tempo.bpm) if getattr(score, "tempo", None) else 120.0

    for bar in sorted(score.bars, key=lambda b: b.index):
        ts = (bar.time_signature.numerator, bar.time_signature.denominator)
        ks = {"fifths": bar.key_signature.fifths, "mode": bar.key_signature.mode} if bar.key_signature else {"fifths": 0, "mode": "major"}
        if bar.tempo:
            current_tempo = float(bar.tempo.bpm)

        sys_break = bar.layout_break == "line"
        page_break = bar.layout_break == "page"
        bl_style = normalize_barline_style(bar.barline)

        events_list: list[EventData] = []
        for ev in bar.events:
            tpq = ev.timing.ticks_per_quarter if ev.timing.ticks_per_quarter > 0 else 960
            onset_beats = ev.timing.onset_ticks / tpq
            duration_beats = ev.timing.duration_ticks / tpq
            dots = ev.timing.notated_duration.dots if ev.timing.notated_duration else 0
            is_dotted = dots > 0

            is_tied = any(getattr(t, "kind", None) == "tie" for t in ev.techniques)
            notes_data: list[NoteData] = []
            for n in ev.notes:
                n_tied = any(getattr(t, "kind", None) == "tie" for t in n.techniques)
                if n_tied:
                    is_tied = True
                tie_state = None
                for t in n.techniques:
                    if getattr(t, "kind", None) == "tie":
                        tie_state = getattr(t, "state", "start")
                        break
                notes_data.append(NoteData(
                    pitch=n.pitch,
                    string=n.string,
                    fret=n.fret,
                    tie_type=tie_state,
                ))

            ev_type = "rest" if ev.is_rest else ("chord" if len(notes_data) > 1 or ev.chord_symbol else "note")

            events_list.append(EventData(
                event_type=ev_type,
                onset_beats=onset_beats,
                duration_beats=duration_beats,
                onset_ticks=ev.timing.onset_ticks,
                duration_ticks=ev.timing.duration_ticks,
                is_dotted=is_dotted,
                dots=dots,
                is_tied=is_tied,
                chord_membership=ev.chord_symbol,
                notes=notes_data,
            ))

        events_list.sort(key=lambda e: e.onset_beats)

        bars_data.append(BarData(
            bar_index=bar.index,
            time_signature=ts,
            key_signature=ks,
            tempo=current_tempo,
            barline=bl_style,
            system_break=sys_break,
            page_break=page_break,
            events=events_list,
        ))

    return bars_data


def _extract_bars_from_gp_xml(root: ET.Element) -> list[BarData]:
    bars_data: list[BarData] = []

    rhythms: dict[str, dict[str, Any]] = {}
    rhythms_node = root.find("Rhythms")
    if rhythms_node is not None:
        for r_elem in rhythms_node.findall("Rhythm"):
            r_id = r_elem.get("id")
            dur_name = r_elem.findtext("NoteValue", "Quarter")
            dots = 1 if r_elem.find("AugmentationDot") is not None else 0
            rhythms[r_id] = {"duration_name": dur_name, "dots": dots}

    mb_nodes = root.find("MasterBars")
    if mb_nodes is None:
        return bars_data

    cur_ts = (4, 4)
    cur_ks = {"fifths": 0, "mode": "major"}
    cur_tempo = 120.0

    master_bars = mb_nodes.findall("MasterBar")
    for idx, mb in enumerate(master_bars, start=1):
        ts_text = mb.findtext("Time")
        if ts_text and "/" in ts_text:
            parts = ts_text.split("/")
            try:
                cur_ts = (int(parts[0]), int(parts[1]))
            except ValueError:
                pass

        key_node = mb.find("Key")
        if key_node is not None:
            fifths = int(key_node.findtext("AccidentalCount", "0"))
            mode = key_node.findtext("Mode", "Major").lower()
            cur_ks = {"fifths": fifths, "mode": mode}

        tempo_node = mb.find("Tempo")
        if tempo_node is not None:
            cur_tempo = float(tempo_node.findtext("Value", "120"))

        bl_style = "normal"
        if mb.find("DoubleBar") is not None or mb.find("Section") is not None:
            bl_style = "double"

        sys_break = mb.find("Section") is not None or mb.find("Layout") is not None
        page_break = False

        bars_data.append(BarData(
            bar_index=idx,
            time_signature=cur_ts,
            key_signature=cur_ks,
            tempo=cur_tempo,
            barline=bl_style,
            system_break=sys_break,
            page_break=page_break,
            events=[],
        ))

    bar_nodes = root.find("Bars")
    if bar_nodes is not None:
        for b_elem in bar_nodes.findall("Bar"):
            b_id = b_elem.get("id")
            try:
                b_idx = int(b_id) + 1 if b_id is not None and b_id.isdigit() else len(bars_data)
            except ValueError:
                b_idx = len(bars_data)

            if b_idx <= len(bars_data):
                target_bar = bars_data[b_idx - 1]
                voices_node = b_elem.find("Voices")
                if voices_node is not None:
                    for v_elem in voices_node.findall("Voice"):
                        beats_node = v_elem.find("Beats")
                        if beats_node is None:
                            continue
                        cur_beat_onset = 0.0
                        for beat_elem in beats_node.findall("Beat"):
                            rhythm_ref = beat_elem.find("Rhythm")
                            r_info = rhythms.get(rhythm_ref.get("ref")) if rhythm_ref is not None else None

                            dur_name = r_info["duration_name"] if r_info else "Quarter"
                            dots = r_info["dots"] if r_info else 0

                            dur_map = {
                                "Whole": 4.0,
                                "Half": 2.0,
                                "Quarter": 1.0,
                                "Eighth": 0.5,
                                "16th": 0.25,
                                "32nd": 0.125,
                                "64th": 0.0625,
                            }
                            dur_beats = dur_map.get(dur_name, 1.0)
                            if dots > 0:
                                dur_beats *= 1.5

                            is_rest = beat_elem.find("Property[@name='Rest']") is not None
                            notes_data: list[NoteData] = []
                            notes_node = beat_elem.find("Notes")
                            if notes_node is not None:
                                for n_elem in notes_node.findall("Note"):
                                    props = {p.get("name"): p for p in n_elem.findall("Property")}
                                    string_val = int(props["String"].findtext("String", "1")) if "String" in props else 1
                                    fret_val = int(props["Fret"].findtext("Fret", "0")) if "Fret" in props else 0
                                    midi_val = int(props["Midi"].findtext("Number", "60")) if "Midi" in props else None

                                    tie_state = None
                                    if "Tie" in props:
                                        tie_state = props["Tie"].findtext("State", "Start").lower()

                                    notes_data.append(NoteData(
                                        pitch=midi_val,
                                        string=string_val,
                                        fret=fret_val,
                                        tie_type=tie_state,
                                    ))

                            ev_type = "rest" if is_rest else ("chord" if len(notes_data) > 1 else "note")
                            target_bar.events.append(EventData(
                                event_type=ev_type,
                                onset_beats=cur_beat_onset,
                                duration_beats=dur_beats,
                                is_dotted=dots > 0,
                                dots=dots,
                                is_tied=any(n.tie_type is not None for n in notes_data),
                                notes=notes_data,
                            ))
                            cur_beat_onset += dur_beats

    return bars_data


def _extract_bars_from_gp_file(gp_path: Path) -> list[BarData]:
    with zipfile.ZipFile(gp_path, "r") as zf:
        if "Content/score.gpif" in zf.namelist():
            xml_data = zf.read("Content/score.gpif")
            root = ET.fromstring(xml_data)
            return _extract_bars_from_gp_xml(root)
    return []


def _extract_bars_from_musicxml_file(mxml_path: Path) -> list[BarData]:
    tree = ET.parse(mxml_path)
    root = tree.getroot()
    bars_data: list[BarData] = []

    cur_ts = (4, 4)
    cur_ks = {"fifths": 0, "mode": "major"}
    cur_tempo = 120.0
    divisions = 1

    part = root.find("part")
    measures = part.findall("measure") if part is not None else root.findall(".//measure")

    for idx, m_elem in enumerate(measures, start=1):
        m_num = m_elem.get("number")
        try:
            bar_idx = int(m_num) if m_num and m_num.isdigit() else idx
        except ValueError:
            bar_idx = idx

        attr = m_elem.find("attributes")
        if attr is not None:
            if attr.find("divisions") is not None:
                divisions = max(1, int(attr.findtext("divisions", "1")))
            time_elem = attr.find("time")
            if time_elem is not None:
                beats = int(time_elem.findtext("beats", "4"))
                beat_type = int(time_elem.findtext("beat-type", "4"))
                cur_ts = (beats, beat_type)
            key_elem = attr.find("key")
            if key_elem is not None:
                fifths = int(key_elem.findtext("fifths", "0"))
                mode = key_elem.findtext("mode", "major").lower()
                cur_ks = {"fifths": fifths, "mode": mode}

        sound_elem = m_elem.find(".//sound[@tempo]")
        if sound_elem is not None:
            try:
                cur_tempo = float(sound_elem.get("tempo", "120"))
            except ValueError:
                pass

        bl_elem = m_elem.find("barline")
        bl_style = "normal"
        if bl_elem is not None:
            style_text = bl_elem.findtext("bar-style", "").lower()
            if style_text in ("double", "heavy-light"):
                bl_style = "double"
            elif style_text in ("light-heavy", "final"):
                bl_style = "final"

        print_elem = m_elem.find("print")
        sys_break = print_elem is not None and print_elem.get("new-system") == "yes"
        page_break = print_elem is not None and print_elem.get("new-page") == "yes"

        events_list: list[EventData] = []
        cur_onset_divs = 0

        for note_elem in m_elem.findall("note"):
            if note_elem.find("chord") is not None and events_list:
                last_ev = events_list[-1]
                last_ev.event_type = "chord"
                pitch_elem = note_elem.find("pitch")
                if pitch_elem is not None:
                    step = pitch_elem.findtext("step", "C")
                    octave = int(pitch_elem.findtext("octave", "4"))
                    alter = int(pitch_elem.findtext("alter", "0"))
                    pitch_map = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
                    midi_pitch = (octave + 1) * 12 + pitch_map.get(step, 0) + alter
                    str_elem = note_elem.find(".//string")
                    fret_elem = note_elem.find(".//fret")
                    string_val = int(str_elem.text) if str_elem is not None and str_elem.text else None
                    fret_val = int(fret_elem.text) if fret_elem is not None and fret_elem.text else None
                    last_ev.notes.append(NoteData(pitch=midi_pitch, string=string_val, fret=fret_val))
                continue

            dur_text = note_elem.findtext("duration", "0")
            dur_divs = int(dur_text) if dur_text.isdigit() else 0
            dur_beats = dur_divs / divisions if divisions > 0 else 1.0
            onset_beats = cur_onset_divs / divisions if divisions > 0 else 0.0
            cur_onset_divs += dur_divs

            is_rest = note_elem.find("rest") is not None
            dots = len(note_elem.findall("dot"))
            is_dotted = dots > 0
            is_tied = note_elem.find("tie") is not None or note_elem.find(".//tied") is not None

            notes_data: list[NoteData] = []
            if not is_rest:
                pitch_elem = note_elem.find("pitch")
                if pitch_elem is not None:
                    step = pitch_elem.findtext("step", "C")
                    octave = int(pitch_elem.findtext("octave", "4"))
                    alter = int(pitch_elem.findtext("alter", "0"))
                    pitch_map = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
                    midi_pitch = (octave + 1) * 12 + pitch_map.get(step, 0) + alter
                    str_elem = note_elem.find(".//string")
                    fret_elem = note_elem.find(".//fret")
                    string_val = int(str_elem.text) if str_elem is not None and str_elem.text else None
                    fret_val = int(fret_elem.text) if fret_elem is not None and fret_elem.text else None
                    notes_data.append(NoteData(pitch=midi_pitch, string=string_val, fret=fret_val))

            events_list.append(EventData(
                event_type="rest" if is_rest else "note",
                onset_beats=onset_beats,
                duration_beats=dur_beats,
                is_dotted=is_dotted,
                dots=dots,
                is_tied=is_tied,
                notes=notes_data,
            ))

        bars_data.append(BarData(
            bar_index=bar_idx,
            time_signature=cur_ts,
            key_signature=cur_ks,
            tempo=cur_tempo,
            barline=bl_style,
            system_break=sys_break,
            page_break=page_break,
            events=events_list,
        ))

    return bars_data


def _parse_single_bar_dict(d: dict[str, Any], default_index: int = 1) -> BarData:
    bar_idx = int(d.get("bar_index", d.get("index", default_index)))

    ts_raw = d.get("time_signature", (4, 4))
    if isinstance(ts_raw, dict):
        ts = (int(ts_raw.get("numerator", 4)), int(ts_raw.get("denominator", 4)))
    elif hasattr(ts_raw, "numerator") and hasattr(ts_raw, "denominator"):
        ts = (int(ts_raw.numerator), int(ts_raw.denominator))
    elif isinstance(ts_raw, (list, tuple)) and len(ts_raw) >= 2:
        ts = (int(ts_raw[0]), int(ts_raw[1]))
    else:
        ts = (4, 4)

    ks_raw = d.get("key_signature")
    if isinstance(ks_raw, dict):
        ks = {"fifths": int(ks_raw.get("fifths", 0)), "mode": str(ks_raw.get("mode", "major")).lower()}
    elif hasattr(ks_raw, "fifths"):
        ks = {"fifths": int(ks_raw.fifths), "mode": str(getattr(ks_raw, "mode", "major")).lower()}
    else:
        ks = {"fifths": 0, "mode": "major"}

    tempo_val = d.get("tempo")
    if isinstance(tempo_val, dict):
        tempo = float(tempo_val.get("bpm", 120.0))
    elif hasattr(tempo_val, "bpm"):
        tempo = float(tempo_val.bpm)
    elif tempo_val is not None:
        try:
            tempo = float(tempo_val)
        except (ValueError, TypeError):
            tempo = 120.0
    else:
        tempo = 120.0

    bl = normalize_barline_style(d.get("barline", "normal"))
    sb = bool(d.get("system_break", False)) or d.get("layout_break") == "line"
    pb = bool(d.get("page_break", False)) or d.get("layout_break") == "page"

    events: list[EventData] = []
    for ev_d in d.get("events", []):
        notes: list[NoteData] = []
        for n_d in ev_d.get("notes", []):
            notes.append(NoteData(
                pitch=n_d.get("pitch"),
                string=n_d.get("string"),
                fret=n_d.get("fret"),
                tie_type=n_d.get("tie_type"),
            ))

        timing_d = ev_d.get("timing")
        if timing_d and isinstance(timing_d, dict):
            tpq = timing_d.get("ticks_per_quarter", 960)
            onset_beats = timing_d.get("onset_ticks", 0) / tpq
            duration_beats = timing_d.get("duration_ticks", 960) / tpq
            notated_dur = timing_d.get("notated_duration")
            dots = notated_dur.get("dots", 0) if isinstance(notated_dur, dict) else 0
        else:
            onset_beats = float(ev_d.get("onset_beats", 0.0))
            duration_beats = float(ev_d.get("duration_beats", 1.0))
            dots = int(ev_d.get("dots", 0))

        events.append(EventData(
            event_type=ev_d.get("event_type", "rest" if ev_d.get("is_rest") else ("chord" if len(notes) > 1 else "note")),
            onset_beats=onset_beats,
            duration_beats=duration_beats,
            onset_ticks=ev_d.get("onset_ticks"),
            duration_ticks=ev_d.get("duration_ticks"),
            is_dotted=bool(ev_d.get("is_dotted", False)) or dots > 0,
            dots=dots,
            is_tied=bool(ev_d.get("is_tied", False)),
            chord_membership=ev_d.get("chord_membership", ev_d.get("chord_symbol")),
            notes=notes,
        ))

    return BarData(
        bar_index=bar_idx,
        time_signature=ts,
        key_signature=ks,
        tempo=tempo,
        barline=bl,
        system_break=sb,
        page_break=pb,
        events=events,
    )


def _extract_bars_from_dict(d: dict[str, Any]) -> list[BarData]:
    bars_list = d.get("bars", [])
    result: list[BarData] = []
    for i, b_d in enumerate(bars_list, start=1):
        if isinstance(b_d, BarData):
            result.append(b_d)
        elif isinstance(b_d, dict):
            result.append(_parse_single_bar_dict(b_d, default_index=i))
    return result


def load_bar_data(source: Any) -> list[BarData]:
    if source is None:
        return []

    if isinstance(source, list) and all(isinstance(x, BarData) for x in source):
        return source

    if isinstance(source, ScoreIR):
        return _extract_bars_from_score_ir(source)

    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        suffix = p.suffix.lower()
        if suffix == ".gp":
            return _extract_bars_from_gp_file(p)
        elif suffix in (".musicxml", ".xml"):
            return _extract_bars_from_musicxml_file(p)
        elif suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            return load_bar_data(data)

    if isinstance(source, dict):
        if "bars" in source:
            try:
                score = ScoreIR.model_validate(source)
                return _extract_bars_from_score_ir(score)
            except Exception:
                pass
            return _extract_bars_from_dict(source)
        elif "events" in source or "bar_index" in source or "index" in source:
            return [_parse_single_bar_dict(source)]

    if isinstance(source, list):
        bars = []
        for i, item in enumerate(source, start=1):
            if isinstance(item, BarData):
                bars.append(item)
            elif isinstance(item, dict):
                b = _parse_single_bar_dict(item, default_index=i)
                bars.append(b)
        return bars

    raise TypeError(f"Unsupported score representation source type: {type(source)}")


def compare_bar_scores(actual_source: Any, expected_source: Any | None = None) -> dict[str, Any]:
    actual_bars = load_bar_data(actual_source)

    # Invariant checker mode when expected_source is None
    if expected_source is None:
        mismatches: list[dict[str, Any]] = []
        for i, b in enumerate(actual_bars, start=1):
            if b.bar_index != i:
                mismatches.append({
                    "bar_index": b.bar_index,
                    "field": "bar_index",
                    "actual": b.bar_index,
                    "expected": i,
                    "message": f"Bar index invariant failed: expected {i}, got {b.bar_index}",
                })
            num, den = b.time_signature
            if num <= 0 or (den & (den - 1)) != 0 or den <= 0:
                mismatches.append({
                    "bar_index": b.bar_index,
                    "field": "time_signature",
                    "actual": b.time_signature,
                    "expected": "valid (num>0, den power of 2)",
                    "message": f"Bar {b.bar_index} invalid time signature: {b.time_signature}",
                })
            prev_onset = -0.0001
            for ev_idx, ev in enumerate(b.events):
                if ev.onset_beats < prev_onset:
                    mismatches.append({
                        "bar_index": b.bar_index,
                        "field": f"events[{ev_idx}].onset_beats",
                        "actual": ev.onset_beats,
                        "expected": f">= {prev_onset}",
                        "message": f"Bar {b.bar_index} event {ev_idx} onset out of order: {ev.onset_beats} < {prev_onset}",
                    })
                prev_onset = ev.onset_beats
                if ev.duration_beats < 0:
                    mismatches.append({
                        "bar_index": b.bar_index,
                        "field": f"events[{ev_idx}].duration_beats",
                        "actual": ev.duration_beats,
                        "expected": ">= 0.0",
                        "message": f"Bar {b.bar_index} event {ev_idx} negative duration: {ev.duration_beats}",
                    })
                for n_idx, n in enumerate(ev.notes):
                    if n.string is not None and not (1 <= n.string <= 12):
                        mismatches.append({
                            "bar_index": b.bar_index,
                            "field": f"events[{ev_idx}].notes[{n_idx}].string",
                            "actual": n.string,
                            "expected": "1..12",
                            "message": f"Bar {b.bar_index} note {n_idx} invalid string: {n.string}",
                        })
                    if n.fret is not None and n.fret < 0:
                        mismatches.append({
                            "bar_index": b.bar_index,
                            "field": f"events[{ev_idx}].notes[{n_idx}].fret",
                            "actual": n.fret,
                            "expected": ">= 0",
                            "message": f"Bar {b.bar_index} note {n_idx} invalid fret: {n.fret}",
                        })
                    if n.pitch is not None and isinstance(n.pitch, int) and not (0 <= n.pitch <= 127):
                        mismatches.append({
                            "bar_index": b.bar_index,
                            "field": f"events[{ev_idx}].notes[{n_idx}].pitch",
                            "actual": n.pitch,
                            "expected": "0..127",
                            "message": f"Bar {b.bar_index} note {n_idx} invalid pitch: {n.pitch}",
                        })

        summary = [compact_bar_summary(b) for b in actual_bars]
        return {
            "matches": len(mismatches) == 0,
            "mode": "invariant_check",
            "total_bars_actual": len(actual_bars),
            "total_bars_expected": None,
            "first_mismatch": mismatches[0] if mismatches else None,
            "mismatches": mismatches,
            "bar_summary": summary,
        }

    # Diagnostic comparison mode when expected_source is provided
    expected_bars = load_bar_data(expected_source)
    mismatches: list[dict[str, Any]] = []

    if len(actual_bars) != len(expected_bars):
        mismatches.append({
            "bar_index": 0,
            "field": "bar_count",
            "actual": len(actual_bars),
            "expected": len(expected_bars),
            "message": f"Total bar count mismatch: actual={len(actual_bars)}, expected={len(expected_bars)}",
        })

    max_bars = max(len(actual_bars), len(expected_bars))
    for i in range(max_bars):
        if i >= len(actual_bars):
            mismatches.append({
                "bar_index": i + 1,
                "field": "missing_bar",
                "actual": None,
                "expected": compact_bar_summary(expected_bars[i]),
                "message": f"Bar {i + 1} missing in actual output",
            })
            continue
        if i >= len(expected_bars):
            mismatches.append({
                "bar_index": i + 1,
                "field": "extra_bar",
                "actual": compact_bar_summary(actual_bars[i]),
                "expected": None,
                "message": f"Bar {i + 1} extra in actual output",
            })
            continue

        act_b = actual_bars[i]
        exp_b = expected_bars[i]
        b_idx = act_b.bar_index

        if act_b.time_signature != exp_b.time_signature:
            mismatches.append({
                "bar_index": b_idx,
                "field": "time_signature",
                "actual": list(act_b.time_signature),
                "expected": list(exp_b.time_signature),
                "message": f"Bar {b_idx} time_signature mismatch: actual={act_b.time_signature}, expected={exp_b.time_signature}",
            })

        if act_b.key_signature != exp_b.key_signature:
            mismatches.append({
                "bar_index": b_idx,
                "field": "key_signature",
                "actual": act_b.key_signature,
                "expected": exp_b.key_signature,
                "message": f"Bar {b_idx} key_signature mismatch: actual={act_b.key_signature}, expected={exp_b.key_signature}",
            })

        if act_b.tempo is not None and exp_b.tempo is not None and abs(act_b.tempo - exp_b.tempo) > 0.01:
            mismatches.append({
                "bar_index": b_idx,
                "field": "tempo",
                "actual": act_b.tempo,
                "expected": exp_b.tempo,
                "message": f"Bar {b_idx} tempo mismatch: actual={act_b.tempo}, expected={exp_b.tempo}",
            })

        if normalize_barline_style(act_b.barline) != normalize_barline_style(exp_b.barline):
            mismatches.append({
                "bar_index": b_idx,
                "field": "barline",
                "actual": act_b.barline,
                "expected": exp_b.barline,
                "message": f"Bar {b_idx} barline style mismatch: actual={act_b.barline}, expected={exp_b.barline}",
            })

        if act_b.system_break != exp_b.system_break:
            mismatches.append({
                "bar_index": b_idx,
                "field": "system_break",
                "actual": act_b.system_break,
                "expected": exp_b.system_break,
                "message": f"Bar {b_idx} system_break mismatch: actual={act_b.system_break}, expected={exp_b.system_break}",
            })

        if act_b.page_break != exp_b.page_break:
            mismatches.append({
                "bar_index": b_idx,
                "field": "page_break",
                "actual": act_b.page_break,
                "expected": exp_b.page_break,
                "message": f"Bar {b_idx} page_break mismatch: actual={act_b.page_break}, expected={exp_b.page_break}",
            })

        if len(act_b.events) != len(exp_b.events):
            mismatches.append({
                "bar_index": b_idx,
                "field": "event_count",
                "actual": len(act_b.events),
                "expected": len(exp_b.events),
                "message": f"Bar {b_idx} event count mismatch: actual={len(act_b.events)}, expected={len(exp_b.events)}",
            })

        min_evs = min(len(act_b.events), len(exp_b.events))
        for ev_i in range(min_evs):
            act_e = act_b.events[ev_i]
            exp_e = exp_b.events[ev_i]

            if act_e.event_type != exp_e.event_type:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].event_type",
                    "actual": act_e.event_type,
                    "expected": exp_e.event_type,
                    "message": f"Bar {b_idx} event {ev_i} type mismatch: actual={act_e.event_type}, expected={exp_e.event_type}",
                })

            if abs(act_e.onset_beats - exp_e.onset_beats) > 0.01:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].onset_beats",
                    "actual": round(act_e.onset_beats, 4),
                    "expected": round(exp_e.onset_beats, 4),
                    "message": f"Bar {b_idx} event {ev_i} onset mismatch: actual={act_e.onset_beats}, expected={exp_e.onset_beats}",
                })

            if abs(act_e.duration_beats - exp_e.duration_beats) > 0.01:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].duration_beats",
                    "actual": round(act_e.duration_beats, 4),
                    "expected": round(exp_e.duration_beats, 4),
                    "message": f"Bar {b_idx} event {ev_i} duration mismatch: actual={act_e.duration_beats}, expected={exp_e.duration_beats}",
                })

            if act_e.is_dotted != exp_e.is_dotted or act_e.dots != exp_e.dots:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].is_dotted",
                    "actual": {"dotted": act_e.is_dotted, "dots": act_e.dots},
                    "expected": {"dotted": exp_e.is_dotted, "dots": exp_e.dots},
                    "message": f"Bar {b_idx} event {ev_i} dotted state mismatch: actual={act_e.dots} dots, expected={exp_e.dots} dots",
                })

            if act_e.is_tied != exp_e.is_tied:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].is_tied",
                    "actual": act_e.is_tied,
                    "expected": exp_e.is_tied,
                    "message": f"Bar {b_idx} event {ev_i} tie state mismatch: actual={act_e.is_tied}, expected={exp_e.is_tied}",
                })

            if act_e.chord_membership != exp_e.chord_membership:
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].chord_membership",
                    "actual": act_e.chord_membership,
                    "expected": exp_e.chord_membership,
                    "message": f"Bar {b_idx} event {ev_i} chord membership mismatch: actual={act_e.chord_membership}, expected={exp_e.chord_membership}",
                })

            if len(act_e.notes) != len(exp_e.notes):
                mismatches.append({
                    "bar_index": b_idx,
                    "field": f"events[{ev_i}].notes_count",
                    "actual": len(act_e.notes),
                    "expected": len(exp_e.notes),
                    "message": f"Bar {b_idx} event {ev_i} note count mismatch: actual={len(act_e.notes)}, expected={len(exp_e.notes)}",
                })

            act_notes_sorted = sorted(act_e.notes, key=lambda n: (n.string or 0, n.pitch or 0))
            exp_notes_sorted = sorted(exp_e.notes, key=lambda n: (n.string or 0, n.pitch or 0))
            min_notes = min(len(act_notes_sorted), len(exp_notes_sorted))

            for n_i in range(min_notes):
                an = act_notes_sorted[n_i]
                en = exp_notes_sorted[n_i]

                if an.pitch is not None and en.pitch is not None and an.pitch != en.pitch:
                    mismatches.append({
                        "bar_index": b_idx,
                        "field": f"events[{ev_i}].notes[{n_i}].pitch",
                        "actual": an.pitch,
                        "expected": en.pitch,
                        "message": f"Bar {b_idx} event {ev_i} note {n_i} pitch mismatch: actual={an.pitch}, expected={en.pitch}",
                    })

                if an.string is not None and en.string is not None and an.string != en.string:
                    mismatches.append({
                        "bar_index": b_idx,
                        "field": f"events[{ev_i}].notes[{n_i}].string",
                        "actual": an.string,
                        "expected": en.string,
                        "message": f"Bar {b_idx} event {ev_i} note {n_i} string mismatch: actual={an.string}, expected={en.string}",
                    })

                if an.fret is not None and en.fret is not None and an.fret != en.fret:
                    mismatches.append({
                        "bar_index": b_idx,
                        "field": f"events[{ev_i}].notes[{n_i}].fret",
                        "actual": an.fret,
                        "expected": en.fret,
                        "message": f"Bar {b_idx} event {ev_i} note {n_i} fret mismatch: actual={an.fret}, expected={en.fret}",
                    })

    summary = [compact_bar_summary(b) for b in actual_bars]
    return {
        "matches": len(mismatches) == 0,
        "mode": "diagnostic_comparison",
        "total_bars_actual": len(actual_bars),
        "total_bars_expected": len(expected_bars),
        "first_mismatch": mismatches[0] if mismatches else None,
        "mismatches": mismatches,
        "bar_summary": summary,
    }


def format_mismatch_report(result: dict[str, Any]) -> str:
    lines = []
    mode = result.get("mode", "comparison")
    matches = result.get("matches", False)
    header = "BAR-LEVEL COMPARISON REPORT" if mode == "diagnostic_comparison" else "BAR-LEVEL INVARIANT CHECK REPORT"

    lines.append("=" * 60)
    lines.append(header)
    lines.append("=" * 60)
    lines.append(f"Result Status : {'PASS (No Mismatches)' if matches else 'FAIL (Mismatches Detected)'}")
    lines.append(f"Actual Bars   : {result.get('total_bars_actual', 0)}")
    if mode == "diagnostic_comparison":
        lines.append(f"Expected Bars : {result.get('total_bars_expected', 0)}")
    lines.append(f"Total Issues  : {len(result.get('mismatches', []))}")
    lines.append("-" * 60)

    first_mismatch = result.get("first_mismatch")
    if first_mismatch:
        lines.append("FIRST MISMATCH:")
        lines.append(f"  Bar       : {first_mismatch.get('bar_index')}")
        lines.append(f"  Field     : {first_mismatch.get('field')}")
        lines.append(f"  Actual    : {first_mismatch.get('actual')}")
        lines.append(f"  Expected  : {first_mismatch.get('expected')}")
        lines.append(f"  Message   : {first_mismatch.get('message')}")
        lines.append("-" * 60)

    mismatches = result.get("mismatches", [])
    if mismatches:
        lines.append("ALL MISMATCHES:")
        for m in mismatches:
            lines.append(f"  [Bar {m.get('bar_index')}] {m.get('field')}: actual={m.get('actual')!r}, expected={m.get('expected')!r}")
            if "message" in m and m["message"]:
                lines.append(f"    -> {m['message']}")
        lines.append("-" * 60)

    bar_summary = result.get("bar_summary", [])
    if bar_summary:
        lines.append("COMPACT BAR EVENT SUMMARY:")
        for b in bar_summary:
            sb_flag = " [SYS_BREAK]" if b.get("system_break") else ""
            pb_flag = " [PAGE_BREAK]" if b.get("page_break") else ""
            bl_style = b.get("barline", "normal")
            bl_flag = f" [{str(bl_style).upper()}]" if bl_style not in ("normal", "regular") else ""
            ts = b.get("time_signature", [4, 4])
            ts_str = f"{ts[0]}/{ts[1]}"
            lines.append(f"  Bar {b.get('bar_index'):02d} ({ts_str}){bl_flag}{sb_flag}{pb_flag}: {b.get('events_summary')}")
        lines.append("-" * 60)

    return "\n".join(lines)
