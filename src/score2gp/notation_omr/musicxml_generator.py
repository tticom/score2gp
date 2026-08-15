"""MusicXML generation from OMR timeline preview."""

from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from .timeline import build_staff_timeline_preview

KEY_FIFTHS = {
    "C Major": 0, "A Minor": 0,
    "G Major": 1, "E Minor": 1,
    "D Major": 2, "B Minor": 2,
    "A Major": 3, "F# Minor": 3,
    "E Major": 4, "C# Minor": 4,
    "B Major": 5, "G# Minor": 5,
    "F# Major": 6, "D# Minor": 6,
    "C# Major": 7, "A# Minor": 7,
    "F Major": -1, "D Minor": -1,
    "Bb Major": -2, "G Minor": -2,
    "Eb Major": -3, "C Minor": -3,
    "Ab Major": -4, "F Minor": -4,
    "Db Major": -5, "Bb Minor": -5,
    "Gb Major": -6, "Eb Minor": -6,
    "Cb Major": -7, "Ab Minor": -7,
}

TICK_TYPE_MAPPINGS = {
    3840: "whole",
    1920: "half",
    960: "quarter",
    480: "eighth",
    240: "16th",
    120: "32nd",
    60: "64th"
}

def get_note_type(duration_ticks: int) -> str:
    # Find closest match in TICK_TYPE_MAPPINGS
    for ticks, n_type in sorted(TICK_TYPE_MAPPINGS.items(), key=lambda x: abs(x[0] - duration_ticks)):
        return n_type
    return "quarter"

def parse_resolved_pitch(pitch_str: str | None) -> tuple[str, int | None, int] | None:
    if not pitch_str:
        return None
    try:
        step = pitch_str[0].upper()
        alter = None
        if len(pitch_str) == 3:
            alt_char = pitch_str[1]
            if alt_char == '#':
                alter = 1
            elif alt_char == 'b':
                alter = -1
            octave = int(pitch_str[2])
        elif len(pitch_str) == 2:
            octave = int(pitch_str[1])
        else:
            return None
        return step, alter, octave
    except Exception:
        return None

def generate_musicxml_from_omr(
    outcomes: list[dict],
    semantic_candidates: list[dict] | None = None,
    all_staff_geometries: list[dict] | None = None
) -> str:
    """Compile OMR recognition outcomes into a valid MusicXML string."""

    # 1. Build the timeline preview
    previews = build_staff_timeline_preview(outcomes, semantic_candidates, all_staff_geometries)
    if not previews:
        return ""

    # For now, generate a single partwise score from the first staff preview
    preview = previews[0]

    # Resolve global attributes from semantic candidates
    fifths = 0
    clef_sign = "G"
    clef_line = 2
    beats_val = 4
    beat_type_val = 4

    if semantic_candidates:
        sc = semantic_candidates[0]
        # Resolve key fifths
        logical_ks = sc.get("logical_key_signature")
        if logical_ks and logical_ks.get("key_name"):
            fifths = KEY_FIFTHS.get(logical_ks["key_name"], 0)

        # Resolve clef
        logical_clef = sc.get("logical_clef")
        if logical_clef:
            kind = logical_clef.get("clef_kind")
            if kind == "bass":
                clef_sign = "F"
                clef_line = 4
            elif kind == "alto":
                clef_sign = "C"
                clef_line = 3

        # Resolve time signature
        for cand in semantic_candidates:
            ts = cand.get("time_signature") or cand.get("logical_time_signature") or cand.get("meter")
            if isinstance(ts, dict):
                b = ts.get("beats") or ts.get("num") or ts.get("numerator")
                bt = ts.get("beat_type") or ts.get("den") or ts.get("denominator")
                if b and bt and int(bt) > 0:
                    beats_val = int(b)
                    beat_type_val = int(bt)
                    break
            elif "beats" in cand and "beat_type" in cand and int(cand["beat_type"]) > 0:
                beats_val = int(cand["beats"])
                beat_type_val = int(cand["beat_type"])
                break
            elif "time_signature_num" in cand and "time_signature_den" in cand and int(cand["time_signature_den"]) > 0:
                beats_val = int(cand["time_signature_num"])
                beat_type_val = int(cand["time_signature_den"])
                break

    # Build standard XML skeleton
    score = ET.Element("score-partwise", version="4.0")

    part_list = ET.SubElement(score, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    part_name = ET.SubElement(score_part, "part-name")
    part_name.text = "Guitar"

    part = ET.SubElement(score, "part", id="P1")

    # Generate measures
    for m_data in preview["measures"]:
        # We don't raise ValueError here if capacity is invalid,
        # we still generate the measure so downstream diagnostics can report it.
        
        m_idx = m_data["measure_index"]
        measure = ET.SubElement(part, "measure", number=str(m_idx))

        # Write attributes on the first measure
        if m_idx == 1:
            attrs = ET.SubElement(measure, "attributes")
            divisions = ET.SubElement(attrs, "divisions")
            divisions.text = "8"

            key = ET.SubElement(attrs, "key")
            fifths_el = ET.SubElement(key, "fifths")
            fifths_el.text = str(fifths)

            time = ET.SubElement(attrs, "time")
            beats = ET.SubElement(time, "beats")
            beats.text = str(beats_val)
            beat_type = ET.SubElement(time, "beat-type")
            beat_type.text = str(beat_type_val)

            clef = ET.SubElement(attrs, "clef")
            sign = ET.SubElement(clef, "sign")
            sign.text = clef_sign
            line = ET.SubElement(clef, "line")
            line.text = str(clef_line)

        # Group events by voice
        events = m_data.get("events", [])
        v1_events = sorted([e for e in events if e.get("voice") == 1], key=lambda e: e["start_tick"])
        v2_events = sorted([e for e in events if e.get("voice") == 2], key=lambda e: e["start_tick"])

        # Only write Voice 2 if it contains actual musical events (not just padding rests)
        v2_has_music = any(e.get("symbol_type") != "padding_rest" for e in v2_events)

        # Write Voice 1
        xml_cursor = 0
        last_written_pitch_start_tick = -1
        for i, ev in enumerate(v1_events):
            pitch_data = parse_resolved_pitch(ev.get("resolved_pitch"))
            is_note = "note" in ev.get("symbol_type", "")
            
            if is_note and pitch_data is None:
                continue

            is_chord = False
            if pitch_data is not None:
                if ev["start_tick"] == last_written_pitch_start_tick:
                    is_chord = True
                else:
                    last_written_pitch_start_tick = ev["start_tick"]

            if not is_chord and ev["start_tick"] > xml_cursor:
                # Write a rest to fill the gap
                gap_ticks = ev["start_tick"] - xml_cursor
                rest_node = ET.SubElement(measure, "note")
                ET.SubElement(rest_node, "rest")
                dur = ET.SubElement(rest_node, "duration")
                dur.text = str(max(1, gap_ticks // 120))
                voice_el = ET.SubElement(rest_node, "voice")
                voice_el.text = "1"
                type_el = ET.SubElement(rest_node, "type")
                type_el.text = get_note_type(gap_ticks)
                xml_cursor = ev["start_tick"]

            note = ET.SubElement(measure, "note")
            if is_chord:
                ET.SubElement(note, "chord")

            if pitch_data:
                step, alter, octave = pitch_data
                pitch = ET.SubElement(note, "pitch")
                s = ET.SubElement(pitch, "step")
                s.text = step
                if alter is not None:
                    alt = ET.SubElement(pitch, "alter")
                    alt.text = str(alter)
                oct_el = ET.SubElement(pitch, "octave")
                oct_el.text = str(octave)
            else:
                ET.SubElement(note, "rest")

            dur_ticks = ev.get("duration_ticks", 960)
            dur_val = max(1, dur_ticks // 120)
            dur = ET.SubElement(note, "duration")
            dur.text = str(dur_val)

            voice_el = ET.SubElement(note, "voice")
            voice_el.text = "1"

            type_el = ET.SubElement(note, "type")
            type_el.text = get_note_type(dur_ticks)

            if not is_chord:
                xml_cursor += dur_ticks

        # Write Voice 2 if present and has musical content
        if v2_events and v2_has_music:
            # Backup to the beginning of the measure (or final xml_cursor)
            backup = ET.SubElement(measure, "backup")
            duration_el = ET.SubElement(backup, "duration")
            duration_el.text = str(max(1, xml_cursor // 120))

            xml_cursor = 0
            last_written_pitch_start_tick = -1
            for i, ev in enumerate(v2_events):
                pitch_data = parse_resolved_pitch(ev.get("resolved_pitch"))
                is_note = "note" in ev.get("symbol_type", "")
                
                if is_note and pitch_data is None:
                    continue

                is_chord = False
                if pitch_data is not None:
                    if ev["start_tick"] == last_written_pitch_start_tick:
                        is_chord = True
                    else:
                        last_written_pitch_start_tick = ev["start_tick"]

                if not is_chord and ev["start_tick"] > xml_cursor:
                    gap_ticks = ev["start_tick"] - xml_cursor
                    rest_node = ET.SubElement(measure, "note")
                    ET.SubElement(rest_node, "rest")
                    dur = ET.SubElement(rest_node, "duration")
                    dur.text = str(max(1, gap_ticks // 120))
                    voice_el = ET.SubElement(rest_node, "voice")
                    voice_el.text = "2"
                    type_el = ET.SubElement(rest_node, "type")
                    type_el.text = get_note_type(gap_ticks)
                    xml_cursor = ev["start_tick"]

                note = ET.SubElement(measure, "note")
                if is_chord:
                    ET.SubElement(note, "chord")

                if pitch_data:
                    step, alter, octave = pitch_data
                    pitch = ET.SubElement(note, "pitch")
                    s = ET.SubElement(pitch, "step")
                    s.text = step
                    if alter is not None:
                        alt = ET.SubElement(pitch, "alter")
                        alt.text = str(alter)
                    oct_el = ET.SubElement(pitch, "octave")
                    oct_el.text = str(octave)
                else:
                    ET.SubElement(note, "rest")

                dur_ticks = ev.get("duration_ticks", 960)
                dur_val = max(1, dur_ticks // 120)
                dur = ET.SubElement(note, "duration")
                dur.text = str(dur_val)

                voice_el = ET.SubElement(note, "voice")
                voice_el.text = "2"

                type_el = ET.SubElement(note, "type")
                type_el.text = get_note_type(dur_ticks)

                if not is_chord:
                    xml_cursor += dur_ticks

    # Generate pretty formatted string
    xml_str = ET.tostring(score, encoding="utf-8")
    parsed = minidom.parseString(xml_str)

    # Return XML string with standard declarations
    doc_str = parsed.toprettyxml(indent="  ")
    # Replace single line xml tags if needed, clean up formatting
    return doc_str
