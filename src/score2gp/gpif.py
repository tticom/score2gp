from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from .ir import Event, Note, ScoreIR, Technique

SUPPORTED_MINIMAL_TECHNIQUES = {"slide", "vibrato", "hammer-on", "pull-off", "tie", "slur", "bend", "let-ring", "palm-mute", "grace", "dead-note", "tremolo-bar", "tremolo-picking", "slap", "pop", "tapping", "trill"}


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
                    if tech.kind in ("hammer-on", "pull-off", "slur") and getattr(tech, "target_event_id", None):
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
        if score.layout.engraving_boundaries is not None:
            ps.set("engravingWidth", str(score.layout.engraving_boundaries.width))
            ps.set("engravingHeight", str(score.layout.engraving_boundaries.height))
        _text(ps, "Width", score.layout.page_setup.width)
        _text(ps, "Height", score.layout.page_setup.height)
        _text(ps, "MarginTop", score.layout.page_setup.margins.top)
        _text(ps, "MarginBottom", score.layout.page_setup.margins.bottom)
        _text(ps, "MarginLeft", score.layout.page_setup.margins.left)
        _text(ps, "MarginRight", score.layout.page_setup.margins.right)
        _text(ps, "Scale", score.layout.page_setup.scale)
        if score.layout.engraving_boundaries is not None:
            eb = ET.SubElement(ps, "EngravingBoundaries")
            _text(eb, "Width", score.layout.engraving_boundaries.width)
            _text(eb, "Height", score.layout.engraving_boundaries.height)


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

    # Score-level view modes
    if getattr(score, "layout", None) is not None and score.layout.view is not None:
        view_node = ET.SubElement(score_node, "View")
        _text(view_node, "Mode", score.layout.view.mode.capitalize())
        if score.layout.view.scroll_speed is not None:
            _text(view_node, "ScrollSpeed", score.layout.view.scroll_speed)

    # Score-level print layouts
    if getattr(score, "layout", None) is not None and score.layout.print_setup is not None:
        print_node = ET.SubElement(score_node, "Print")
        ps_cfg = score.layout.print_setup
        _text(print_node, "Title", "true" if ps_cfg.print_title else "false")
        _text(print_node, "Subtitle", "true" if ps_cfg.print_subtitle else "false")
        _text(print_node, "Artist", "true" if ps_cfg.print_artist else "false")
        _text(print_node, "Composer", "true" if ps_cfg.print_composer else "false")
        _text(print_node, "Transcriber", "true" if ps_cfg.print_transcriber else "false")
        _text(print_node, "Copyright", "true" if ps_cfg.print_copyright else "false")
        _text(print_node, "PageNumbering", "true" if ps_cfg.print_page_numbering else "false")
        _text(print_node, "MultiTrack", "true" if ps_cfg.print_multi_track else "false")

    # Score-level advanced Layout templates, margins, and bracing/bracket properties
    if getattr(score, "layout", None) is not None and (
        score.layout.system_page_margins is not None or score.layout.ensemble_brackets is not None
    ):
        layout_node = ET.SubElement(score_node, "Layout")
        if score.layout.system_page_margins is not None:
            spm = ET.SubElement(layout_node, "SystemPageMargins")
            _text(spm, "Top", score.layout.system_page_margins.top)
            _text(spm, "Bottom", score.layout.system_page_margins.bottom)
            _text(spm, "Left", score.layout.system_page_margins.left)
            _text(spm, "Right", score.layout.system_page_margins.right)
        if score.layout.ensemble_brackets is not None:
            bracing_node = ET.SubElement(layout_node, "Bracing")
            ensemble_brackets_node = ET.SubElement(layout_node, "EnsembleBrackets")
            for bracket in score.layout.ensemble_brackets:
                brace_node = ET.SubElement(bracing_node, "Brace", {"style": bracket.style})
                _text(brace_node, "Tracks", " ".join(bracket.track_ids))
                bracket_node = ET.SubElement(ensemble_brackets_node, "Bracket", {"style": bracket.style})
                _text(bracket_node, "Tracks", " ".join(bracket.track_ids))

    # Score-level custom font stylesheets and music typography parameters
    if getattr(score, "layout", None) is not None and score.layout.fonts is not None:
        fonts_cfg = score.layout.fonts
        _text(score_node, "MusicFont", fonts_cfg.music_font)
        _text(score_node, "SymbolFont", fonts_cfg.symbol_font)
        fonts_node = ET.SubElement(score_node, "Fonts")
        categories = {
            "Title": fonts_cfg.title,
            "Header": fonts_cfg.header,
            "Lyrics": fonts_cfg.lyrics,
            "Tablature": fonts_cfg.tab_annotations,
        }
        for cat_id, font_def in categories.items():
            if font_def is not None:
                ET.SubElement(fonts_node, "Font", {
                    "id": cat_id,
                    "name": font_def.family,
                    "size": str(font_def.size),
                    "bold": "true" if font_def.bold else "false",
                    "italic": "true" if font_def.italic else "false",
                })

    # Score-level custom stylesheet style collections
    if getattr(score, "layout", None) is not None and score.layout.style_collections is not None:
        sc_node = ET.SubElement(score_node, "StyleCollections")
        for sc in score.layout.style_collections:
            item = ET.SubElement(sc_node, "StyleCollection", {
                "id": sc.id,
                "name": sc.name,
            })
            if sc.description is not None:
                _text(item, "Description", sc.description)

    event_map = {}
    for bar in score.bars:
        for event in bar.events:
            event_map[event.id] = event

    _tracks(score_node, score, track_cd_maps)
    _master_bars(score_node, score)
    _bars(score_node, score, hopo_dests, let_ring_notes, palm_mute_notes, track_cd_maps, event_map)

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
            if getattr(track, "layout_preferences", None) is not None and track.layout_preferences.tab_only:
                layout_code = 2
            else:
                layout_code = 3 if track.tablature_enabled else 1
        _text(node, "SystemsDefautLayout", layout_code)
        _text(node, "SystemsLayout", layout_code)

        _text(node, "Instrument", track.instrument)
        _text(node, "Capo", track.capo)

        if getattr(track, "layout_preferences", None) is not None:
            if track.layout_preferences.tab_only:
                tab_node = ET.SubElement(node, "Tablature")
                _text(tab_node, "TabOnly", "true")

            if track.layout_preferences.view_mode:
                view_node = ET.SubElement(node, "View")
                _text(view_node, "Mode", track.layout_preferences.view_mode.capitalize())

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

        # Sounds
        if (
            getattr(track, "sound", None) is not None
            or getattr(track, "midi_program", None) is not None
            or getattr(track, "midi_channel", None) is not None
        ):
            sounds = ET.SubElement(node, "Sounds")
            sound = ET.SubElement(sounds, "Sound")

            # Name
            name_val = track.name
            if getattr(track, "sound", None) is not None and track.sound.name is not None:
                name_val = track.sound.name
            _text(sound, "Name", name_val)

            # Path
            if getattr(track, "sound", None) is not None and track.sound.path is not None:
                _text(sound, "Path", track.sound.path)

            # MidiConnection
            midi_conn = ET.SubElement(sound, "MidiConnection")

            port_val = 1
            if getattr(track, "sound", None) is not None:
                port_val = track.sound.midi_port
            _text(midi_conn, "Port", port_val)

            chan_val = 1
            if getattr(track, "sound", None) is not None and track.sound.midi_channel is not None:
                chan_val = track.sound.midi_channel
            elif getattr(track, "midi_channel", None) is not None:
                chan_val = track.midi_channel
            _text(midi_conn, "Channel", chan_val)

            prog_val = 24
            if getattr(track, "sound", None) is not None and track.sound.midi_program is not None:
                prog_val = track.sound.midi_program
            elif getattr(track, "midi_program", None) is not None:
                prog_val = track.midi_program
            _text(midi_conn, "Instrument", prog_val)

        # Staves, Staff and Properties (Tuning, FretCount, Capo, etc.)
        staves_node = ET.SubElement(node, "Staves")
        staff_node = ET.SubElement(staves_node, "Staff")
        properties_nodes = [
            ET.SubElement(staff_node, "Properties"),
            ET.SubElement(staff_node, "StaffProperties")
        ]

        # 1. CapoFret
        for p_node in properties_nodes:
            capo_prop = ET.SubElement(p_node, "Property", {"name": "CapoFret"})
            _text(capo_prop, "Fret", track.capo)

        # 2. FretCount
        for p_node in properties_nodes:
            fret_prop = ET.SubElement(p_node, "Property", {"name": "FretCount"})
            _text(fret_prop, "Number", 24)

        # 3. PartialCapoFret
        for p_node in properties_nodes:
            pcapo_prop = ET.SubElement(p_node, "Property", {"name": "PartialCapoFret"})
            _text(pcapo_prop, "Fret", 0)

        # 4. PartialCapoStringFlags
        for p_node in properties_nodes:
            flags_prop = ET.SubElement(p_node, "Property", {"name": "PartialCapoStringFlags"})
            _text(flags_prop, "Bitset", "0" * len(track.tuning.strings))

        # 5. Tuning
        sorted_strings = sorted(track.tuning.strings, key=lambda s: s.number, reverse=True)
        pitches_str = " ".join(str(string.pitch) for string in sorted_strings)
        inst_type = "Bass" if track.instrument.lower() == "bass" else "Guitar"
        has_balances = any(getattr(s, "volume_offset", None) is not None for s in sorted_strings)
        has_finetunes = any(getattr(s, "fine_tune", None) is not None for s in sorted_strings)

        for p_node in properties_nodes:
            tuning_prop = ET.SubElement(p_node, "Property", {"name": "Tuning"})
            _text(tuning_prop, "Pitches", pitches_str)
            _text(tuning_prop, "Instrument", inst_type)
            _text(tuning_prop, "Label", "None")
            _text(tuning_prop, "LabelVisible", "true")

            if has_balances:
                balances_str = " ".join(str(s.volume_offset if s.volume_offset is not None else 0.0) for s in sorted_strings)
                _text(tuning_prop, "Balance", balances_str)

            if has_finetunes:
                finetunes_str = " ".join(str(s.fine_tune if s.fine_tune is not None else 0.0) for s in sorted_strings)
                _text(tuning_prop, "FineTuning", finetunes_str)

        # Tablature layout preference
        if track.tablature_enabled:
            for p_node in properties_nodes:
                tab_prop = ET.SubElement(p_node, "Property", {"name": "Tablature"})
                _text(tab_prop, "Enable", "true")

        # Stem direction layout preference
        layout_prefs = getattr(track, "layout_preferences", None)
        if layout_prefs is not None:
            if layout_prefs.stem_direction:
                for p_node in properties_nodes:
                    stems_prop = ET.SubElement(p_node, "Property", {"name": "Stems"})
                    _text(stems_prop, "Enable", "true" if layout_prefs.stem_direction != "auto" else "false")
                    _text(stems_prop, "Direction", layout_prefs.stem_direction.capitalize())

            # Notation system line sizing constraints
            if layout_prefs.line_sizing:
                for p_node in properties_nodes:
                    ls_prop = ET.SubElement(p_node, "Property", {"name": "LineSizing"})
                    _text(ls_prop, "Size", layout_prefs.line_sizing.capitalize())

            # Track-level view mode property
            if layout_prefs.view_mode:
                for p_node in properties_nodes:
                    vm_prop = ET.SubElement(p_node, "Property", {"name": "ViewMode"})
                    _text(vm_prop, "Mode", layout_prefs.view_mode.capitalize())

            # Brackets visibility
            if layout_prefs.brackets_visible is not None:
                for p_node in properties_nodes:
                    b_prop = ET.SubElement(p_node, "Property", {"name": "Brackets"})
                    _text(b_prop, "Enable", "true" if layout_prefs.brackets_visible else "false")

            # Stem visibility
            if layout_prefs.stems_visible is not None:
                for p_node in properties_nodes:
                    sv_prop = ET.SubElement(p_node, "Property", {"name": "StemVisibility"})
                    _text(sv_prop, "Enable", "true" if layout_prefs.stems_visible else "false")

            # Line sizing per system
            if layout_prefs.line_sizing_per_system:
                for p_node in properties_nodes:
                    lsps_prop = ET.SubElement(p_node, "Property", {"name": "LineSizingPerSystem"})
                    _text(lsps_prop, "Size", layout_prefs.line_sizing_per_system.capitalize())

        # Collect chord diagrams for this track to construct staff properties
        tmap = track_cd_maps.get(track.id, {})
        if tmap:
            for p_node in properties_nodes:
                diag_coll_prop = ET.SubElement(p_node, "Property", {"name": "DiagramCollection"})
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

        if getattr(bar, "barline", None) is not None:
            barline_map = {
                "regular": "Simple",
                "double": "Double",
                "end": "End",
                "section": "Section",
                "repeat-start": "RepeatStart",
                "repeat-end": "RepeatEnd",
            }
            barline_val = barline_map.get(bar.barline, "Simple")
            _text(node, "Barline", barline_val)

            if bar.barline == "repeat-start":
                ET.SubElement(node, "RepeatStart")
            elif bar.barline == "repeat-end":
                repeat_count = getattr(bar, "repeat_count", None) or 2
                ET.SubElement(node, "Repeat", {"count": str(repeat_count)})


def _bars(parent: ET.Element, score: ScoreIR, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]], track_cd_maps: dict[str, dict[str, str]], event_map: dict[str, Event]) -> None:
    bars = ET.SubElement(parent, "Bars")
    for bar in score.bars:
        bar_node = ET.SubElement(bars, "Bar", {"index": str(bar.index)})

        if getattr(bar, "anacrusis", False):
            props = ET.SubElement(bar_node, "Properties")
            anac_prop = ET.SubElement(props, "Property", {"name": "Anacrusis"})
            ET.SubElement(anac_prop, "Enable")

        events_by_voice = {}
        for event in bar.events:
            v_idx = event.timing.voice - 1
            events_by_voice.setdefault(v_idx, []).append(event)

        voices_node = ET.SubElement(bar_node, "Voices")
        for v_idx in sorted(events_by_voice.keys()):
            voice_node = ET.SubElement(voices_node, "Voice", {"id": str(v_idx)})
            for event in sorted(events_by_voice[v_idx], key=lambda item: item.timing.onset_ticks):
                _event(voice_node, event, hopo_dests, let_ring_notes, palm_mute_notes, track_cd_maps, event_map)


def _event(parent: ET.Element, event: Event, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]], track_cd_maps: dict[str, dict[str, str]], event_map: dict[str, Event]) -> None:
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

    if getattr(event, "hairpin", None) is not None:
        hairpin_map = {
            "crescendo": "Crescendo",
            "decrescendo": "Decrescendo",
            "diminuendo": "Decrescendo",
            "stop": "None",
            "none": "None",
        }
        hairpin_type = hairpin_map.get(event.hairpin, "None")
        hp_node = ET.SubElement(node, "Hairpin", {"type": hairpin_type})
        _text(hp_node, "Type", hairpin_type)

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

    # Fermata representation
    fermata_val = getattr(event, "fermata", None)
    if fermata_val is True:
        fermata_val = "standard"
    if fermata_val and fermata_val != "none":
        type_val = "Standard"
        if fermata_val == "short":
            type_val = "Short"
        elif fermata_val == "long":
            type_val = "Long"
        ferm_node = ET.SubElement(node, "Fermata")
        _text(ferm_node, "Type", type_val)

    # Brush & Arpeggio representation
    duration_map = {
        "whole": "Whole",
        "half": "Half",
        "quarter": "Quarter",
        "eighth": "Eighth",
        "16th": "Sixteenth",
        "32nd": "ThirtySecond",
        "64th": "SixtyFourth",
        "128th": "HundredTwentyEighth",
    }

    if getattr(event, "brush", None) in ("up", "down"):
        brush_dir = "Up" if event.brush == "up" else "Down"
        brush_dur = duration_map.get(getattr(event, "brush_duration", None) or "eighth", "Eighth")
        ET.SubElement(node, "Brush", {"direction": brush_dir, "duration": brush_dur})

    if getattr(event, "arpeggio", None) in ("up", "down"):
        arp_dir = "Up" if event.arpeggio == "up" else "Down"
        arp_dur = duration_map.get(getattr(event, "arpeggio_duration", None) or "eighth", "Eighth")
        ET.SubElement(node, "Arpeggio", {"direction": arp_dir, "duration": arp_dur})

    has_brush = getattr(event, "brush", None) in ("up", "down")
    has_arpeggio = getattr(event, "arpeggio", None) in ("up", "down")
    if has_brush or has_arpeggio:
        props_node = ET.SubElement(node, "Properties")
        if has_brush:
            brush_dir = "Up" if event.brush == "up" else "Down"
            brush_dur = duration_map.get(getattr(event, "brush_duration", None) or "eighth", "Eighth")
            prop_brush = ET.SubElement(props_node, "Property", {"name": "Brush"})
            _text(prop_brush, "Direction", brush_dir)
            _text(prop_brush, "Duration", brush_dur)
        if has_arpeggio:
            arp_dir = "Up" if event.arpeggio == "up" else "Down"
            arp_dur = duration_map.get(getattr(event, "arpeggio_duration", None) or "eighth", "Eighth")
            prop_arp = ET.SubElement(props_node, "Property", {"name": "Arpeggio"})
            _text(prop_arp, "Direction", arp_dir)
            _text(prop_arp, "Duration", arp_dur)

    if event.techniques:
        techniques = ET.SubElement(node, "Techniques")
        for technique in event.techniques:
            ET.SubElement(techniques, "Technique", {"name": technique.kind})
    for note in event.notes:
        _note(node, note, event.timing.bar_index, event.timing.onset_ticks, event.timing.duration_ticks, hopo_dests, let_ring_notes, palm_mute_notes, event_map)


def _note(parent: ET.Element, note: Note, bar_index: int, onset_ticks: int, duration_ticks: int, hopo_dests: set[tuple[int, int, int]], let_ring_notes: set[tuple[int, int, int]], palm_mute_notes: set[tuple[int, int, int]], event_map: dict[str, Event]) -> None:
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

    articulations = getattr(note, "articulations", [])
    if "staccato" in articulations:
        ET.SubElement(note_node, "Staccato")
    if "tenuto" in articulations:
        ET.SubElement(note_node, "Tenuto")
    if "accent" in articulations:
        _text(note_node, "Accent", 1)
    if "marcato" in articulations:
        _text(note_node, "Accent", 2)
        ET.SubElement(note_node, "HeavyAccent")

    has_slide = False
    slide_flags = 2
    has_glissando = False
    has_bend = False
    has_hopo_origin = False
    bend_semitones = 1.0
    max_bend_semitones = 1.0
    has_slap = False
    has_pop = False
    has_tapping = False
    has_trill = False
    trill_fret = None
    trill_interval = None
    has_tremolo_bar = False
    has_hammer_on = False
    has_pull_off = False
    has_slur = False
    ho_style = None
    ho_flags = None
    ho_legato = None
    po_style = None
    po_flags = None
    po_legato = None
    legato_val = None
    flags_val = None

    for technique in note.techniques:
        if technique.kind == "tie":
            note_node.set("tie", technique.state)
            origin_val = "true" if technique.state in ("start", "continue") else "false"
            dest_val = "true" if technique.state in ("stop", "continue") else "false"
            ET.SubElement(note_node, "Tie", {"origin": origin_val, "destination": dest_val})
        if technique.kind == "slur":
            note_node.set("slur", technique.state)
            has_slur = True
            target_id = getattr(technique, "target_event_id", None)
            if target_id:
                target_ev = event_map.get(target_id)
                if target_ev:
                    target_note = next((n for n in target_ev.notes if n.string == note.string), None)
                    if target_note:
                        if target_note.pitch > note.pitch:
                            has_hammer_on = True
                            has_hopo_origin = True
                        elif target_note.pitch < note.pitch:
                            has_pull_off = True
                            has_hopo_origin = True
        if technique.kind == "slide":
            has_slide = True
            ET.SubElement(note_node, "Slide")
            style = getattr(technique, "style", "unknown")
            direction = getattr(technique, "direction", "unknown")
            if style == "glissando" or getattr(technique, "glissando", False):
                has_glissando = True
                ET.SubElement(note_node, "Glissando")
            
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
            elif style == "glissando":
                slide_flags = 64
            elif style == "grace":
                slide_flags = 128
            else:
                slide_flags = 2

            if getattr(technique, "flags", None) is not None:
                slide_flags = technique.flags
        if technique.kind == "bend":
            has_bend = True
            bend_semitones = technique.semitones if technique.semitones is not None else 1.0
            max_bend_semitones = bend_semitones
            if getattr(technique, "points", None):
                max_bend_semitones = max(pt.semitones for pt in technique.points)
            
            bend_node = ET.SubElement(note_node, "Bend")
            if getattr(technique, "points", None):
                for pt in technique.points:
                    off_pct = (pt.offset_ticks / max(1, duration_ticks)) * 100.0
                    val_gp = pt.semitones * 50.0
                    ET.SubElement(
                        bend_node,
                        "Point",
                        {
                            "offset": f"{off_pct:.6f}",
                            "value": f"{val_gp:.6f}",
                        }
                    )
            else:
                ET.SubElement(bend_node, "Point", {"offset": "0.000000", "value": "0.000000"})
                ET.SubElement(bend_node, "Point", {"offset": "50.000000", "value": f"{bend_semitones * 50.0:.6f}"})
                ET.SubElement(bend_node, "Point", {"offset": "100.000000", "value": f"{bend_semitones * 50.0:.6f}"})
        if technique.kind == "hammer-on":
            has_hopo_origin = True
            has_hammer_on = True
            ho_style = getattr(technique, "style", None)
            ho_flags = getattr(technique, "flags", None)
            ho_legato = getattr(technique, "legato", None)
            if ho_flags is not None:
                flags_val = ho_flags
            if ho_legato is not None:
                legato_val = ho_legato
            ET.SubElement(note_node, "HO")
            if ho_style == "slur":
                note_node.set("slur", "start")
                has_slur = True

        if technique.kind == "pull-off":
            has_hopo_origin = True
            has_pull_off = True
            po_style = getattr(technique, "style", None)
            po_flags = getattr(technique, "flags", None)
            po_legato = getattr(technique, "legato", None)
            if po_flags is not None:
                flags_val = po_flags
            if po_legato is not None:
                legato_val = po_legato
            ET.SubElement(note_node, "PO")
            if po_style == "slur":
                note_node.set("slur", "start")
                has_slur = True
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
            has_tremolo_bar = True
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
        if technique.kind == "trill":
            has_trill = True
            ET.SubElement(note_node, "Trill")
            trill_fret = getattr(technique, "fret", None)
            trill_interval = getattr(technique, "interval", None)

    if has_hammer_on and not any(ch.tag == "HO" for ch in note_node):
        ET.SubElement(note_node, "HO")
    if has_pull_off and not any(ch.tag == "PO" for ch in note_node):
        ET.SubElement(note_node, "PO")

    has_articulation = bool(articulations)
    lh_val = getattr(note, "left_hand_fingering", None)
    rh_val = getattr(note, "right_hand_fingering", None)
    if has_slide or has_bend or has_hopo_origin or is_hopo_dest or has_slap or has_pop or has_tapping or has_trill or has_tremolo_bar or has_glissando or has_articulation or has_hammer_on or has_pull_off or has_slur or lh_val or rh_val:
        properties_node = ET.SubElement(note_node, "Properties")

        fret_prop = ET.SubElement(properties_node, "Property", {"name": "Fret"})
        _text(fret_prop, "Fret", note.fret)

        string_prop = ET.SubElement(properties_node, "Property", {"name": "String"})
        _text(string_prop, "String", note.string)

        midi_prop = ET.SubElement(properties_node, "Property", {"name": "Midi"})
        _text(midi_prop, "Number", note.pitch)

        if lh_val:
            lh_map = {
                "0": "Open",
                "open": "Open",
                "t": "Thumb",
                "thumb": "Thumb",
                "1": "Index",
                "index": "Index",
                "2": "Middle",
                "middle": "Middle",
                "3": "Ring",
                "ring": "Ring",
                "4": "Little",
                "little": "Little"
            }
            mapped_lh = lh_map.get(str(lh_val).lower(), str(lh_val).capitalize())
            lh_prop = ET.SubElement(properties_node, "Property", {"name": "LeftHandFingering"})
            _text(lh_prop, "Fingering", mapped_lh)

        if rh_val:
            rh_map = {
                "p": "Thumb",
                "thumb": "Thumb",
                "i": "Index",
                "index": "Index",
                "m": "Middle",
                "middle": "Middle",
                "a": "Ring",
                "ring": "Ring",
                "c": "Little",
                "little": "Little"
            }
            mapped_rh = rh_map.get(str(rh_val).lower(), str(rh_val).capitalize())
            rh_prop = ET.SubElement(properties_node, "Property", {"name": "RightHandFingering"})
            _text(rh_prop, "Fingering", mapped_rh)

        if "accent" in articulations:
            acc_prop = ET.SubElement(properties_node, "Property", {"name": "Accentuation"})
            _text(acc_prop, "Value", "Accent")
        elif "marcato" in articulations:
            acc_prop = ET.SubElement(properties_node, "Property", {"name": "Accentuation"})
            _text(acc_prop, "Value", "Marcato")
        elif "tenuto" in articulations:
            acc_prop = ET.SubElement(properties_node, "Property", {"name": "Accentuation"})
            _text(acc_prop, "Value", "Tenuto")

        if has_slide:
            slide_prop = ET.SubElement(properties_node, "Property", {"name": "Slide"})
            _text(slide_prop, "Flags", slide_flags)

        if has_hopo_origin:
            hopo_prop = ET.SubElement(properties_node, "Property", {"name": "HopoOrigin"})
            ET.SubElement(hopo_prop, "Enable")

        if is_hopo_dest:
            hopo_dest_prop = ET.SubElement(properties_node, "Property", {"name": "HopoDestination"})
            ET.SubElement(hopo_dest_prop, "Enable")
            note_node.set("slur", "stop")

        if has_hammer_on:
            ho_prop = ET.SubElement(properties_node, "Property", {"name": "HammerOn"})
            ET.SubElement(ho_prop, "Enable")
            if ho_style is not None:
                _text(ho_prop, "Style", ho_style)
            if ho_flags is not None:
                _text(ho_prop, "Flags", ho_flags)
            if ho_legato is not None:
                _text(ho_prop, "Legato", str(ho_legato).lower())

        if has_pull_off:
            po_prop = ET.SubElement(properties_node, "Property", {"name": "PullOff"})
            ET.SubElement(po_prop, "Enable")
            if po_style is not None:
                _text(po_prop, "Style", po_style)
            if po_flags is not None:
                _text(po_prop, "Flags", po_flags)
            if po_legato is not None:
                _text(po_prop, "Legato", str(po_legato).lower())

        if legato_val is not None or flags_val is not None:
            legato_prop = ET.SubElement(properties_node, "Property", {"name": "Legato"})
            ET.SubElement(legato_prop, "Enable")
            if flags_val is not None:
                _text(legato_prop, "Flags", flags_val)
            if legato_val is not None:
                _text(legato_prop, "Legato", str(legato_val).lower())

        if has_slur:
            slur_prop = ET.SubElement(properties_node, "Property", {"name": "Slur"})
            ET.SubElement(slur_prop, "Enable")

        if has_bend:
            bended_prop = ET.SubElement(properties_node, "Property", {"name": "Bended"})
            ET.SubElement(bended_prop, "Enable")

            dest_offset = ET.SubElement(properties_node, "Property", {"name": "BendDestinationOffset"})
            _text(dest_offset, "Float", "100.000000")

            dest_val = ET.SubElement(properties_node, "Property", {"name": "BendDestinationValue"})
            _text(dest_val, "Float", f"{max_bend_semitones * 50.0:.6f}")

            mid_off1 = ET.SubElement(properties_node, "Property", {"name": "BendMiddleOffset1"})
            _text(mid_off1, "Float", "12.000000")

            mid_off2 = ET.SubElement(properties_node, "Property", {"name": "BendMiddleOffset2"})
            _text(mid_off2, "Float", "12.000000")

            mid_val = ET.SubElement(properties_node, "Property", {"name": "BendMiddleValue"})
            _text(mid_val, "Float", f"{max_bend_semitones * 25.0:.6f}")

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

        if has_trill:
            trill_prop = ET.SubElement(properties_node, "Property", {"name": "Trill"})
            if trill_fret is not None:
                _text(trill_prop, "Fret", trill_fret)
            if trill_interval is not None:
                _text(trill_prop, "Interval", trill_interval)

        if has_tremolo_bar:
            trem_prop = ET.SubElement(properties_node, "Property", {"name": "TremoloBar"})
            ET.SubElement(trem_prop, "Enable")

        if has_glissando:
            gliss_prop = ET.SubElement(properties_node, "Property", {"name": "Glissando"})
            ET.SubElement(gliss_prop, "Enable")

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
