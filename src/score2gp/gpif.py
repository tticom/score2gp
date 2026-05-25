from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from .ir import Event, Note, ScoreIR, Technique

SUPPORTED_MINIMAL_TECHNIQUES = {"slide", "vibrato", "hammer-on", "pull-off", "tie", "slur", "bend", "let-ring", "palm-mute", "grace"}


def _text(parent: ET.Element, tag: str, value: object | None) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def _find_hopo_destinations(score: ScoreIR) -> set[tuple[int, int, int]]:
    destinations = set()
    event_map = {}
    for bar in score.bars:
        for event in bar.events:
            event_map[event.id] = event

    for bar in score.bars:
        for event in bar.events:
            for note in event.notes:
                for tech in note.techniques:
                    if tech.kind in ("hammer-on", "pull-off") and getattr(tech, "target_event_id", None):
                        target_ev = event_map.get(tech.target_event_id)
                        if target_ev:
                            for target_note in target_ev.notes:
                                if target_note.string == note.string:
                                    destinations.add((target_ev.timing.bar_index, target_ev.timing.onset_ticks, target_note.string))
    return destinations


def _find_span_notes(score: ScoreIR) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    let_ring_notes = set()
    palm_mute_notes = set()

    # 1. Compute bar absolute start ticks
    bar_starts = {}
    current = 0
    for bar in sorted(score.bars, key=lambda b: b.index):
        bar_starts[bar.index] = current
        tpq = 960
        if bar.events:
            tpq = bar.events[0].timing.ticks_per_quarter
        bar_length = int(bar.time_signature.numerator * tpq * 4 / bar.time_signature.denominator)
        current += bar_length

    # 2. Build map of event_id -> (absolute_onset, bar_index, onset_ticks)
    event_info = {}
    for bar in score.bars:
        for event in bar.events:
            abs_onset = bar_starts[bar.index] + event.timing.onset_ticks
            event_info[event.id] = (abs_onset, bar.index, event.timing.onset_ticks)

    # 3. Collect all active spans
    spans = [] # list of (kind, string, start_abs, end_abs)
    for bar in score.bars:
        for event in bar.events:
            for note in event.notes:
                for tech in note.techniques:
                    if tech.kind in ("let-ring", "palm-mute") and getattr(tech, "end_event_id", None):
                        target_info = event_info.get(tech.end_event_id)
                        if target_info:
                            end_abs = target_info[0]
                            start_abs = bar_starts[bar.index] + event.timing.onset_ticks
                            spans.append((tech.kind, note.string, start_abs, end_abs))

    # 4. Filter all notes in the score against these spans
    for bar in score.bars:
        for event in bar.events:
            note_abs = bar_starts[bar.index] + event.timing.onset_ticks
            for note in event.notes:
                for kind, string, start_abs, end_abs in spans:
                    if note.string == string and start_abs <= note_abs <= end_abs:
                        if kind == "let-ring":
                            let_ring_notes.add((bar.index, event.timing.onset_ticks, note.string))
                        elif kind == "palm-mute":
                            palm_mute_notes.add((bar.index, event.timing.onset_ticks, note.string))

    return let_ring_notes, palm_mute_notes


def build_gpif(score: ScoreIR) -> bytes:
    root = ET.Element("GPIF", {"version": "7", "generator": "score2gp"})
    score_node = ET.SubElement(root, "Score")

    hopo_dests = _find_hopo_destinations(score)
    let_ring_notes, palm_mute_notes = _find_span_notes(score)

    _metadata(score_node, score)
    _tempo(score_node, score)
    _tracks(score_node, score)
    _master_bars(score_node, score)
    _bars(score_node, score, hopo_dests, let_ring_notes, palm_mute_notes)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _metadata(parent: ET.Element, score: ScoreIR) -> None:
    metadata = ET.SubElement(parent, "Metadata")
    _text(metadata, "Title", score.metadata.title)
    _text(metadata, "Artist", score.metadata.artist)
    _text(metadata, "Composer", score.metadata.composer)
    _text(metadata, "Album", score.metadata.album)
    _text(metadata, "Transcriber", score.metadata.transcriber)
    _text(metadata, "Copyright", score.metadata.copyright)


def _tempo(parent: ET.Element, score: ScoreIR) -> None:
    tempo = ET.SubElement(parent, "Tempo")
    _text(tempo, "Value", score.tempo.bpm)
    if score.tempo.text:
        _text(tempo, "Text", score.tempo.text)


def _tracks(parent: ET.Element, score: ScoreIR) -> None:
    tracks = ET.SubElement(parent, "Tracks")
    for track in score.tracks:
        node = ET.SubElement(tracks, "Track", {"id": track.id})
        _text(node, "Name", track.name)
        _text(node, "Instrument", track.instrument)
        _text(node, "Capo", track.capo)
        tuning = ET.SubElement(node, "Tuning", {"name": track.tuning.name})
        for string in sorted(track.tuning.strings, key=lambda item: item.number):
            ET.SubElement(
                tuning,
                "String",
                {
                    "number": str(string.number),
                    "pitch": str(string.pitch),
                    "name": string.name,
                },
            )


def _master_bars(parent: ET.Element, score: ScoreIR) -> None:
    master_bars = ET.SubElement(parent, "MasterBars")
    for bar in score.bars:
        node = ET.SubElement(master_bars, "MasterBar", {"index": str(bar.index)})
        _text(
            node,
            "Time",
            f"{bar.time_signature.numerator}/{bar.time_signature.denominator}",
        )
        if bar.key_signature is not None:
            key = ET.SubElement(node, "Key")
            _text(key, "Fifths", bar.key_signature.fifths)
            _text(key, "Mode", bar.key_signature.mode)


def _bars(parent: ET.Element, score: ScoreIR, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]]) -> None:
    bars = ET.SubElement(parent, "Bars")
    for bar in score.bars:
        bar_node = ET.SubElement(bars, "Bar", {"index": str(bar.index)})
        for event in sorted(bar.events, key=lambda item: item.timing.onset_ticks):
            _event(bar_node, event, hopo_dests, let_ring_notes, palm_mute_notes)


def _event(parent: ET.Element, event: Event, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]]) -> None:
    attrs = {
        "id": event.id,
        "track": event.track_id,
        "voice": str(event.timing.voice),
        "position": _ticks_to_fraction(event.timing.onset_ticks, event.timing.ticks_per_quarter),
        "duration": _ticks_to_fraction(event.timing.duration_ticks, event.timing.ticks_per_quarter),
        "confidence": f"{event.confidence:.3f}",
    }
    if event.is_rest:
        attrs["rest"] = "true"
    node = ET.SubElement(parent, "Event", attrs)

    if event.timing.notated_duration is not None or event.timing.tuplet is not None:
        rhythm_node = ET.SubElement(node, "Rhythm")
        if event.timing.notated_duration is not None:
            val_map = {
                "whole": "Whole",
                "half": "Half",
                "quarter": "Quarter",
                "eighth": "Eighth",
                "16th": "16th",
                "32nd": "32nd",
                "64th": "64th",
                "128th": "128th",
            }
            val_str = val_map.get(event.timing.notated_duration.value, event.timing.notated_duration.value.capitalize())
            _text(rhythm_node, "NoteValue", val_str)
            if event.timing.notated_duration.dots > 0:
                ET.SubElement(rhythm_node, "AugmentationDot", {"count": str(event.timing.notated_duration.dots)})
        if event.timing.tuplet is not None:
            ET.SubElement(
                rhythm_node,
                "PrimaryTuplet",
                {
                    "num": str(event.timing.tuplet.actual_notes),
                    "den": str(event.timing.tuplet.normal_notes),
                },
            )

    grace_timing = event.timing.grace
    if not grace_timing:
        for note in event.notes:
            for tech in note.techniques:
                if tech.kind == "grace":
                    grace_timing = tech.timing
                    break
    if grace_timing is not None:
        val = "OnBeat" if grace_timing.position == "on-beat" else "BeforeBeat"
        _text(node, "GraceNotes", val)

    if event.chord_symbol:
        _text(node, "Chord", event.chord_symbol)
    if event.techniques:
        techniques = ET.SubElement(node, "Techniques")
        for technique in event.techniques:
            ET.SubElement(techniques, "Technique", {"name": technique.kind})
    for note in event.notes:
        _note(node, note, event.timing.bar_index, event.timing.onset_ticks, hopo_dests, let_ring_notes, palm_mute_notes)


def _note(parent: ET.Element, note: Note, bar_index: int, onset_ticks: int, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]]) -> None:
    note_node = ET.SubElement(
        parent,
        "Note",
        {
            "string": str(note.string),
            "fret": str(note.fret),
            "pitch": str(note.pitch),
            "confidence": f"{note.confidence:.3f}",
        },
    )

    is_hopo_dest = (bar_index, onset_ticks, note.string) in hopo_dests
    is_let_ring = (bar_index, onset_ticks, note.string) in let_ring_notes
    is_palm_mute = (bar_index, onset_ticks, note.string) in palm_mute_notes

    if is_let_ring:
        ET.SubElement(note_node, "LetRing")
    if is_palm_mute:
        ET.SubElement(note_node, "PalmMute")

    has_slide = False
    has_bend = False
    has_hopo_origin = False
    bend_semitones = 1.0

    for technique in note.techniques:
        if technique.kind == "tie":
            note_node.set("tie", technique.state)
            origin_val = "true" if technique.state in ("start", "continue") else "false"
            dest_val = "true" if technique.state in ("stop", "continue") else "false"
            ET.SubElement(note_node, "Tie", {"origin": origin_val, "destination": dest_val})
        if technique.kind == "slur":
            note_node.set("slur", technique.state)
        if technique.kind == "slide":
            has_slide = True
            ET.SubElement(note_node, "Slide")
        if technique.kind == "bend":
            has_bend = True
            bend_semitones = technique.semitones if technique.semitones is not None else 1.0
            ET.SubElement(note_node, "Bend")
        if technique.kind == "hammer-on":
            has_hopo_origin = True
            ET.SubElement(note_node, "HO")
        if technique.kind == "pull-off":
            has_hopo_origin = True
            ET.SubElement(note_node, "PO")

    if has_slide or has_bend or has_hopo_origin or is_hopo_dest:
        properties_node = ET.SubElement(note_node, "Properties")

        fret_prop = ET.SubElement(properties_node, "Property", {"name": "Fret"})
        _text(fret_prop, "Fret", note.fret)

        string_prop = ET.SubElement(properties_node, "Property", {"name": "String"})
        _text(string_prop, "String", note.string)

        midi_prop = ET.SubElement(properties_node, "Property", {"name": "Midi"})
        _text(midi_prop, "Number", note.pitch)

        if has_slide:
            slide_prop = ET.SubElement(properties_node, "Property", {"name": "Slide"})
            _text(slide_prop, "Flags", 2)

        if has_hopo_origin:
            hopo_prop = ET.SubElement(properties_node, "Property", {"name": "HopoOrigin"})
            ET.SubElement(hopo_prop, "Enable")

        if is_hopo_dest:
            hopo_dest_prop = ET.SubElement(properties_node, "Property", {"name": "HopoDestination"})
            ET.SubElement(hopo_dest_prop, "Enable")

        if has_bend:
            bended_prop = ET.SubElement(properties_node, "Property", {"name": "Bended"})
            ET.SubElement(bended_prop, "Enable")

            dest_offset = ET.SubElement(properties_node, "Property", {"name": "BendDestinationOffset"})
            _text(dest_offset, "Float", "100.000000")

            dest_val = ET.SubElement(properties_node, "Property", {"name": "BendDestinationValue"})
            _text(dest_val, "Float", f"{bend_semitones * 50.0:.6f}")

            mid_off1 = ET.SubElement(properties_node, "Property", {"name": "BendMiddleOffset1"})
            _text(mid_off1, "Float", "12.000000")

            mid_off2 = ET.SubElement(properties_node, "Property", {"name": "BendMiddleOffset2"})
            _text(mid_off2, "Float", "12.000000")

            mid_val = ET.SubElement(properties_node, "Property", {"name": "BendMiddleValue"})
            _text(mid_val, "Float", f"{bend_semitones * 25.0:.6f}")

            orig_off = ET.SubElement(properties_node, "Property", {"name": "BendOriginOffset"})
            _text(orig_off, "Float", "0.000000")

            orig_val = ET.SubElement(properties_node, "Property", {"name": "BendOriginValue"})
            _text(orig_val, "Float", "0.000000")

    if note.techniques:
        techniques = ET.SubElement(note_node, "Techniques")
        for technique in note.techniques:
            ET.SubElement(techniques, "Technique", {"name": technique.kind})


def _ticks_to_fraction(ticks: int, ticks_per_quarter: int) -> str:
    return str(Fraction(ticks, ticks_per_quarter * 4))


def gpif_warnings(score: ScoreIR) -> list[str]:
    warnings: list[str] = []
    for track in score.tracks:
        if not track.tablature_enabled:
            warnings.append(f"track '{track.id}' tablature_enabled=false is not represented in the minimal GPIF writer")
        if track.staff_count != 1:
            warnings.append(f"track '{track.id}' staff_count={track.staff_count} is not represented in the minimal GPIF writer")
        if track.midi_program is not None or track.midi_channel is not None:
            warnings.append(f"track '{track.id}' MIDI program/channel is not represented in the minimal GPIF writer")
    for bar in score.bars:
        for event in bar.events:
            _technique_warnings(warnings, f"event '{event.id}'", event.techniques)
            for note in event.notes:
                _technique_warnings(warnings, f"event '{event.id}' note string {note.string}", note.techniques)
    return warnings


def _technique_warnings(warnings: list[str], owner: str, techniques: list[Technique]) -> None:
    for technique in techniques:
        if technique.kind not in SUPPORTED_MINIMAL_TECHNIQUES:
            warnings.append(f"{owner} technique '{technique.kind}' is not represented in the minimal GPIF writer")
