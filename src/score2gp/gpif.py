from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from .ir import Event, Note, ScoreIR, Technique

SUPPORTED_MINIMAL_TECHNIQUES = {"slide", "vibrato", "hammer-on", "pull-off", "tie", "slur", "bend", "let-ring", "palm-mute", "grace", "dead-note", "tremolo-bar", "tremolo-picking", "slap", "pop", "tapping"}


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


def _page_setup(parent: ET.Element, score: ScoreIR) -> None:
    if getattr(score, "layout", None) is not None:
        ps = ET.SubElement(parent, "PageSetup")
        _text(ps, "Width", score.layout.page_setup.width)
        _text(ps, "Height", score.layout.page_setup.height)
        _text(ps, "MarginTop", score.layout.page_setup.margins.top)
        _text(ps, "MarginBottom", score.layout.page_setup.margins.bottom)
        _text(ps, "MarginLeft", score.layout.page_setup.margins.left)
        _text(ps, "MarginRight", score.layout.page_setup.margins.right)
        _text(ps, "Scale", score.layout.page_setup.scale)


def _master_track(parent: ET.Element, score: ScoreIR) -> None:
    track_order = []
    if getattr(score, "layout", None) is not None and score.layout.track_order:
        track_order = score.layout.track_order
    else:
        track_order = [t.id for t in score.tracks]

    if track_order:
        mt = ET.SubElement(parent, "MasterTrack")
        _text(mt, "Tracks", " ".join(track_order))


def build_gpif(score: ScoreIR) -> bytes:
    root = ET.Element("GPIF", {"version": "7", "generator": "score2gp"})
    score_node = ET.SubElement(root, "Score")

    hopo_dests = _find_hopo_destinations(score)
    let_ring_notes, palm_mute_notes = _find_span_notes(score)

    # Build unique chord diagrams map for each track to reference in Staves properties and Events
    track_cd_maps = {}
    for track in score.tracks:
        track_cds = []
        cd_seen = set()
        for bar in score.bars:
            for event in bar.events:
                if event.track_id == track.id and getattr(event, "chord_diagram", None) is not None:
                    dump = event.chord_diagram.model_dump_json()
                    if dump not in cd_seen:
                        cd_seen.add(dump)
                        track_cds.append(dump)
        track_cd_maps[track.id] = {dump: str(idx + 1) for idx, dump in enumerate(track_cds)}

    _metadata(score_node, score)
    _tempo(score_node, score)

    layout_systems = 4
    if getattr(score, "layout", None) is not None:
        _page_setup(score_node, score)
        _master_track(score_node, score)
        layout_systems = score.layout.score_systems_layout
    else:
        # Fallback if layout is None: write default PageSetup and MasterTrack
        ps = ET.SubElement(score_node, "PageSetup")
        _text(ps, "Width", 210.0)
        _text(ps, "Height", 297.0)
        _text(ps, "MarginTop", 15.0)
        _text(ps, "MarginBottom", 15.0)
        _text(ps, "MarginLeft", 15.0)
        _text(ps, "MarginRight", 15.0)
        _text(ps, "Scale", 1.0)
        _master_track(score_node, score)

    _text(score_node, "ScoreSystemsDefaultLayout", layout_systems)
    _text(score_node, "ScoreSystemsLayout", layout_systems)

    _tracks(score_node, score, track_cd_maps)
    _master_bars(score_node, score)
    _bars(score_node, score, hopo_dests, let_ring_notes, palm_mute_notes, track_cd_maps)

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


def _tracks(parent: ET.Element, score: ScoreIR, track_cd_maps: dict[str, dict[str, str]]) -> None:
    tracks = ET.SubElement(parent, "Tracks")
    for track in score.tracks:
        node = ET.SubElement(tracks, "Track", {"id": track.id})
        _text(node, "Name", track.name)
        if getattr(track, "color", None) is not None:
            _text(node, "Color", track.color)

        layout_code = getattr(track, "systems_layout", None)
        if layout_code is None:
            layout_code = 3 if track.tablature_enabled else 1
        _text(node, "SystemsDefautLayout", layout_code)
        _text(node, "SystemsLayout", layout_code)

        _text(node, "Instrument", track.instrument)
        _text(node, "Capo", track.capo)

        if getattr(track, "mixer", None) is not None:
            mixer_node = ET.SubElement(node, "Mixer")
            _text(mixer_node, "Volume", int(track.mixer.volume * 100))
            _text(mixer_node, "Pan", int((track.mixer.pan + 1) * 50))
            _text(mixer_node, "Mute", str(track.mixer.mute).lower())
            _text(mixer_node, "Solo", str(track.mixer.solo).lower())

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

        # Staves, Staff and Properties (Tuning, FretCount, Capo, etc.)
        staves_node = ET.SubElement(node, "Staves")
        staff_node = ET.SubElement(staves_node, "Staff")
        properties_node = ET.SubElement(staff_node, "Properties")

        # 1. CapoFret
        capo_prop = ET.SubElement(properties_node, "Property", {"name": "CapoFret"})
        _text(capo_prop, "Fret", track.capo)

        # 2. FretCount
        fret_prop = ET.SubElement(properties_node, "Property", {"name": "FretCount"})
        _text(fret_prop, "Number", 24)

        # 3. PartialCapoFret
        pcapo_prop = ET.SubElement(properties_node, "Property", {"name": "PartialCapoFret"})
        _text(pcapo_prop, "Fret", 0)

        # 4. PartialCapoStringFlags
        flags_prop = ET.SubElement(properties_node, "Property", {"name": "PartialCapoStringFlags"})
        _text(flags_prop, "Bitset", "0" * len(track.tuning.strings))

        # 5. Tuning
        tuning_prop = ET.SubElement(properties_node, "Property", {"name": "Tuning"})
        pitches_str = " ".join(str(string.pitch) for string in sorted(track.tuning.strings, key=lambda s: s.number, reverse=True))
        _text(tuning_prop, "Pitches", pitches_str)
        inst_type = "Bass" if track.instrument.lower() == "bass" else "Guitar"
        _text(tuning_prop, "Instrument", inst_type)
        _text(tuning_prop, "Label", "None")
        _text(tuning_prop, "LabelVisible", "true")

        # Collect chord diagrams for this track to construct staff properties
        tmap = track_cd_maps.get(track.id, {})
        if tmap:
            diag_coll_prop = ET.SubElement(properties_node, "Property", {"name": "DiagramCollection"})
            items_node = ET.SubElement(diag_coll_prop, "Items")

            # Reconstruct the diagrams in ID order
            id_to_cd_dump = {v: k for k, v in tmap.items()}
            for idx in range(len(tmap)):
                cd_id = str(idx + 1)
                dump = id_to_cd_dump[cd_id]
                from .ir import ChordDiagram
                cd = ChordDiagram.model_validate_json(dump)

                item_node = ET.SubElement(items_node, "Item", {"id": cd_id, "name": cd.name})
                diag_node = ET.SubElement(item_node, "Diagram", {
                    "stringCount": str(cd.string_count),
                    "fretCount": str(cd.fret_count),
                    "baseFret": str(cd.base_fret),
                    "barsStates": "1 1 1 1 1",
                })
                for f in cd.frets:
                    ET.SubElement(diag_node, "Fret", {"string": str(f.string), "fret": str(f.fret)})

                fing_node = ET.SubElement(diag_node, "Fingering")
                for fg in cd.fingers:
                    ET.SubElement(fing_node, "Position", {
                        "finger": fg.finger,
                        "fret": str(fg.fret),
                        "string": str(fg.string),
                    })

                ET.SubElement(diag_node, "Property", {"name": "ShowName", "type": "bool", "value": "true"})
                ET.SubElement(diag_node, "Property", {"name": "ShowDiagram", "type": "bool", "value": "false"})
                ET.SubElement(diag_node, "Property", {"name": "ShowFingering", "type": "bool", "value": "false"})

                chord_node = ET.SubElement(item_node, "Chord")
                ET.SubElement(chord_node, "KeyNote", {"step": cd.key_note_step, "accidental": cd.key_note_accidental})
                ET.SubElement(chord_node, "BassNote", {"step": cd.bass_note_step, "accidental": cd.bass_note_accidental})



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

        if getattr(bar, "tempo", None) is not None:
            tempo_node = ET.SubElement(node, "Tempo")
            _text(tempo_node, "Value", bar.tempo.bpm)
            if bar.tempo.text:
                _text(tempo_node, "Text", bar.tempo.text)

        if getattr(bar, "layout_break", None) is not None:
            break_val = "Line" if bar.layout_break == "line" else ("Page" if bar.layout_break == "page" else "None")
            _text(node, "Break", break_val)


def _bars(parent: ET.Element, score: ScoreIR, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]], track_cd_maps: dict[str, dict[str, str]]) -> None:
    bars = ET.SubElement(parent, "Bars")
    for bar in score.bars:
        bar_node = ET.SubElement(bars, "Bar", {"index": str(bar.index)})

        events_by_voice = {}
        for event in bar.events:
            v_idx = event.timing.voice - 1
            events_by_voice.setdefault(v_idx, []).append(event)

        voices_node = ET.SubElement(bar_node, "Voices")
        for v_idx in sorted(events_by_voice.keys()):
            voice_node = ET.SubElement(voices_node, "Voice", {"id": str(v_idx)})
            for event in sorted(events_by_voice[v_idx], key=lambda item: item.timing.onset_ticks):
                _event(voice_node, event, hopo_dests, let_ring_notes, palm_mute_notes, track_cd_maps)


def _event(parent: ET.Element, event: Event, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]], track_cd_maps: dict[str, dict[str, str]]) -> None:
    attrs = {
        "id": event.id,
        "track": event.track_id,
        "voice": str(event.timing.voice - 1),
        "position": _ticks_to_fraction(event.timing.onset_ticks, event.timing.ticks_per_quarter),
        "duration": _ticks_to_fraction(event.timing.duration_ticks, event.timing.ticks_per_quarter),
        "confidence": f"{event.confidence:.3f}",
    }
    if event.is_rest:
        attrs["rest"] = "true"
    node = ET.SubElement(parent, "Event", attrs)

    if event.dynamic:
        _text(node, "Dynamic", event.dynamic.upper())

    if event.text:
        _text(node, "FreeText", event.text)
        _text(node, "Direction", event.text)
        _text(node, "Text", event.text)

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

    if getattr(event, "chord_diagram", None) is not None:
        tmap = track_cd_maps.get(event.track_id, {})
        dump = event.chord_diagram.model_dump_json()
        cd_id = tmap.get(dump)
        if cd_id:
            _text(node, "Chord", cd_id)

        cd = event.chord_diagram
        cd_node = ET.SubElement(node, "ChordDiagram", {
            "name": cd.name,
            "stringCount": str(cd.string_count),
            "fretCount": str(cd.fret_count),
            "baseFret": str(cd.base_fret),
        })
        for f in cd.frets:
            ET.SubElement(cd_node, "Fret", {"string": str(f.string), "fret": str(f.fret)})
        if cd.fingers:
            fing_node = ET.SubElement(cd_node, "Fingering")
            for fg in cd.fingers:
                ET.SubElement(fing_node, "Position", {
                    "finger": fg.finger,
                    "fret": str(fg.fret),
                    "string": str(fg.string),
                })
        ET.SubElement(cd_node, "KeyNote", {"step": cd.key_note_step, "accidental": cd.key_note_accidental})
        ET.SubElement(cd_node, "BassNote", {"step": cd.bass_note_step, "accidental": cd.bass_note_accidental})
    elif event.chord_symbol:
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
    if getattr(note, "is_dead", False):
        ET.SubElement(note_node, "DeadNote")

    has_slide = False
    slide_flags = 2
    has_bend = False
    has_hopo_origin = False
    bend_semitones = 1.0
    has_slap = False
    has_pop = False
    has_tapping = False

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
            style = getattr(technique, "style", "unknown")
            direction = getattr(technique, "direction", "unknown")
            if style == "shift":
                slide_flags = 1
            elif style == "legato":
                slide_flags = 2
            elif style == "slide-in":
                if direction == "up":
                    slide_flags = 16
                elif direction == "down":
                    slide_flags = 32
                else:
                    slide_flags = 16
            elif style == "slide-out":
                if direction == "up":
                    slide_flags = 8
                elif direction == "down":
                    slide_flags = 4
                else:
                    slide_flags = 4
            else:
                slide_flags = 2
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
        if technique.kind == "vibrato":
            _text(note_node, "Vibrato", "Wide" if getattr(technique, "width", "unknown") == "wide" else "Slight")
            curve = getattr(technique, "curve", None)
            if curve is not None:
                curve_node = ET.SubElement(note_node, "VibratoCurve")
                for pt in curve.points:
                    ET.SubElement(
                        curve_node,
                        "Point",
                        {
                            "offset": f"{pt.offset * 100:.6f}",
                            "value": f"{pt.value * 100:.6f}",
                            "speed": pt.speed,
                        }
                    )
        if technique.kind == "tremolo-bar":
            tremolo_node = ET.SubElement(note_node, "TremoloBar")
            for pt in getattr(technique, "points", []):
                ET.SubElement(
                    tremolo_node,
                    "Point",
                    {
                        "offset": f"{pt.offset * 100:.6f}",
                        "value": f"{pt.value * 50:.6f}",
                    }
                )
        if technique.kind == "tremolo-picking":
            duration_map = {
                "eighth": "Eighth",
                "16th": "Sixteenth",
                "32nd": "ThirtySecond",
                "64th": "SixtyFourth",
            }
            dur_val = duration_map.get(getattr(technique, "duration", "16th"), "Sixteenth")
            ET.SubElement(note_node, "TremoloPicking", {"duration": dur_val})
        if technique.kind == "slap":
            has_slap = True
            ET.SubElement(note_node, "Slapped")
        if technique.kind == "pop":
            has_pop = True
            ET.SubElement(note_node, "Popped")
        if technique.kind == "tapping":
            has_tapping = True
            ET.SubElement(note_node, "Tapped")

    if has_slide or has_bend or has_hopo_origin or is_hopo_dest or has_slap or has_pop or has_tapping:
        properties_node = ET.SubElement(note_node, "Properties")

        fret_prop = ET.SubElement(properties_node, "Property", {"name": "Fret"})
        _text(fret_prop, "Fret", note.fret)

        string_prop = ET.SubElement(properties_node, "Property", {"name": "String"})
        _text(string_prop, "String", note.string)

        midi_prop = ET.SubElement(properties_node, "Property", {"name": "Midi"})
        _text(midi_prop, "Number", note.pitch)

        if has_slide:
            slide_prop = ET.SubElement(properties_node, "Property", {"name": "Slide"})
            _text(slide_prop, "Flags", slide_flags)

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

        if has_slap:
            slap_prop = ET.SubElement(properties_node, "Property", {"name": "Slapped"})
            ET.SubElement(slap_prop, "Enable")

        if has_pop:
            pop_prop = ET.SubElement(properties_node, "Property", {"name": "Popped"})
            ET.SubElement(pop_prop, "Enable")

        if has_tapping:
            tapping_prop = ET.SubElement(properties_node, "Property", {"name": "Tapped"})
            ET.SubElement(tapping_prop, "Enable")

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
