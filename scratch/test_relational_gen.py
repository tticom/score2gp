import json
from xml.etree import ElementTree as ET
from fractions import Fraction
from score2gp.ir import ScoreIR

def _text(parent, tag, value):
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child

def build_relational_gpif(score):
    root = ET.Element("GPIF")
    _text(root, "GPVersion", "8.1.0")
    
    rev = ET.SubElement(root, "GPRevision", {"required": "12024", "recommended": "13000"})
    rev.text = "13006"
    
    enc = ET.SubElement(root, "Encoding")
    _text(enc, "EncodingDescription", "GP8")
    
    # 1. Score element (Metadata and layout)
    score_node = ET.SubElement(root, "Score")
    _text(score_node, "Title", score.metadata.title or "")
    _text(score_node, "SubTitle", "")
    _text(score_node, "Artist", score.metadata.artist or "")
    _text(score_node, "Album", score.metadata.album or "")
    _text(score_node, "Words", "")
    _text(score_node, "Music", score.metadata.composer or "")
    _text(score_node, "WordsAndMusic", "")
    _text(score_node, "Copyright", score.metadata.copyright or "")
    _text(score_node, "Tabber", score.metadata.transcriber or "")
    _text(score_node, "Instructions", "")
    _text(score_node, "Notices", "")
    _text(score_node, "FirstPageHeader", "")
    _text(score_node, "FirstPageFooter", "")
    _text(score_node, "PageHeader", "")
    _text(score_node, "PageFooter", "")
    _text(score_node, "ScoreSystemsDefaultLayout", "4")
    _text(score_node, "ScoreSystemsLayout", "4")
    _text(score_node, "ScoreZoomPolicy", "Value")
    _text(score_node, "ScoreZoom", "1")
    _text(score_node, "MultiVoice", "0")
    
    # 2. MasterTrack (automations, mixing)
    mt = ET.SubElement(root, "MasterTrack")
    _text(mt, "Tracks", "0") # we map first track to id 0
    automations = ET.SubElement(mt, "Automations")
    auto = ET.SubElement(automations, "Automation")
    _text(auto, "Type", "Tempo")
    _text(auto, "Linear", "false")
    _text(auto, "Bar", "0")
    _text(auto, "Position", "0")
    _text(auto, "Visible", "true")
    # Value format is "[BPM] [unit]" (e.g. "120 2" where 2 is quarter note)
    bpm_val = score.tempo.bpm if score.tempo else 120
    _text(auto, "Value", f"{bpm_val} 2")
    
    # 3. Tracks
    tracks_node = ET.SubElement(root, "Tracks")
    for idx, track in enumerate(score.tracks):
        track_id = str(idx)
        track_node = ET.SubElement(tracks_node, "Track", {"id": track_id})
        _text(track_node, "Name", track.name or "Guitar")
        _text(track_node, "ShortName", (track.name or "Gtr")[:6])
        _text(track_node, "Color", "235 152 125")
        _text(track_node, "SystemsDefautLayout", "3")
        _text(track_node, "SystemsLayout", "3 " * len(score.bars))
        
        # Tuning & Staves
        staves = ET.SubElement(track_node, "Staves")
        staff = ET.SubElement(staves, "Staff")
        props = ET.SubElement(staff, "Properties")
        
        capo_prop = ET.SubElement(props, "Property", {"name": "CapoFret"})
        _text(capo_prop, "Fret", track.capo or 0)
        
        fret_prop = ET.SubElement(props, "Property", {"name": "FretCount"})
        _text(fret_prop, "Number", 24)
        
        tuning_prop = ET.SubElement(props, "Property", {"name": "Tuning"})
        sorted_strings = sorted(track.tuning.strings, key=lambda s: s.number, reverse=True)
        pitches_str = " ".join(str(string.pitch) for string in sorted_strings)
        _text(tuning_prop, "Pitches", pitches_str)
        _text(tuning_prop, "Instrument", "Guitar")
        _text(tuning_prop, "Label", "None")
        _text(tuning_prop, "LabelVisible", "true")
    
    # 4. MasterBars
    mb_node = ET.SubElement(root, "MasterBars")
    for bar in score.bars:
        mb = ET.SubElement(mb_node, "MasterBar", {"index": str(bar.index)})
        _text(mb, "Time", f"{bar.time_signature.numerator}/{bar.time_signature.denominator}")
    
    # Decoupled Databases
    rhythms_db = ET.SubElement(root, "Rhythms")
    notes_db = ET.SubElement(root, "Notes")
    beats_db = ET.SubElement(root, "Beats")
    voices_db = ET.SubElement(root, "Voices")
    bars_db = ET.SubElement(root, "Bars")
    
    rhythms_map = {} # (value, dots) -> id
    notes_count = 0
    beats_count = 0
    voices_count = 0
    
    # For each bar
    for bar_idx, bar in enumerate(score.bars):
        # We need to map voices for this bar. Guitar Pro expects exactly 4 voices per bar.
        # Let's group events by voice in this bar.
        events_by_voice = {}
        for event in bar.events:
            v_idx = event.timing.voice - 1
            events_by_voice.setdefault(v_idx, []).append(event)
            
        voice_refs = []
        for v_idx in range(4):
            events = events_by_voice.get(v_idx, [])
            if not events:
                voice_refs.append("-1")
                continue
                
            # Create a Voice element
            voice_id = str(voices_count)
            voices_count += 1
            voice_node = ET.SubElement(voices_db, "Voice", {"id": voice_id})
            
            beat_refs = []
            for event in sorted(events, key=lambda e: e.timing.onset_ticks):
                beat_id = str(beats_count)
                beats_count += 1
                beat_node = ET.SubElement(beats_db, "Beat", {"id": beat_id})
                
                # Dynamic
                _text(beat_node, "Dynamic", event.dynamic.upper() if event.dynamic else "MF")
                
                # Rhythm
                # Find or create rhythm in database
                nd_val = event.timing.notated_duration.value if event.timing.notated_duration else "quarter"
                dots = event.timing.notated_duration.dots if event.timing.notated_duration else 0
                
                # Map duration value to GP standard
                val_map = {
                    "whole": "Whole",
                    "half": "Half",
                    "quarter": "Quarter",
                    "eighth": "Eighth",
                    "16th": "Sixteenth",
                    "32nd": "ThirtySecond",
                    "64th": "SixtyFourth",
                }
                gp_dur = val_map.get(nd_val.lower(), "Quarter")
                rhythm_key = (gp_dur, dots)
                
                if rhythm_key not in rhythms_map:
                    r_id = str(len(rhythms_map))
                    rhythms_map[rhythm_key] = r_id
                    r_node = ET.SubElement(rhythms_db, "Rhythm", {"id": r_id})
                    _text(r_node, "NoteValue", gp_dur)
                    if dots > 0:
                        ET.SubElement(r_node, "AugmentationDot", {"count": str(dots)})
                
                rhythm_ref = rhythms_map[rhythm_key]
                ET.SubElement(beat_node, "Rhythm", {"ref": rhythm_ref})
                
                # If it's a rest, mark it on beat
                if event.is_rest:
                    _text(beat_node, "Rest", "")
                
                # Notes
                note_refs = []
                for note in event.notes:
                    note_id = str(notes_count)
                    notes_count += 1
                    note_node = ET.SubElement(notes_db, "Note", {"id": note_id})
                    
                    props = ET.SubElement(note_node, "Properties")
                    
                    fret_prop = ET.SubElement(props, "Property", {"name": "Fret"})
                    _text(fret_prop, "Fret", note.fret)
                    
                    string_prop = ET.SubElement(props, "Property", {"name": "String"})
                    # In GP8/7, strings are 0-indexed starting from the 1st string (high E) being index 0!
                    # Wait, in original Lesson-3.gp: "String 0" is high E (string 1 in ScoreIR), and "String 5" is low E (string 6 in ScoreIR).
                    # So GP string index = string_number - 1!
                    _text(string_prop, "String", note.string - 1)
                    
                    midi_prop = ET.SubElement(props, "Property", {"name": "Midi"})
                    _text(midi_prop, "Number", note.pitch)
                    
                    # Concert pitch & Transposed pitch
                    # Let's map pitch to note steps
                    pitch_map = {
                        0: ("C", ""), 1: ("C", "Sharp"), 2: ("D", ""), 3: ("D", "Sharp"),
                        4: ("E", ""), 5: ("F", ""), 6: ("F", "Sharp"), 7: ("G", ""),
                        8: ("G", "Sharp"), 9: ("A", ""), 10: ("A", "Sharp"), 11: ("B", "")
                    }
                    step, accidental = pitch_map[note.pitch % 12]
                    octave = (note.pitch // 12) - 1 # MIDI octave
                    
                    cp_prop = ET.SubElement(props, "Property", {"name": "ConcertPitch"})
                    pitch_node = ET.SubElement(cp_prop, "Pitch")
                    _text(pitch_node, "Step", step)
                    _text(pitch_node, "Accidental", accidental)
                    _text(pitch_node, "Octave", octave)
                    
                    # For standard guitar, transposed pitch is 1 octave higher on staff
                    tp_prop = ET.SubElement(props, "Property", {"name": "TransposedPitch"})
                    tpitch_node = ET.SubElement(tp_prop, "Pitch")
                    _text(tpitch_node, "Step", step)
                    _text(tpitch_node, "Accidental", accidental)
                    _text(tpitch_node, "Octave", octave + 1)
                    
                    note_refs.append(note_id)
                
                if note_refs:
                    _text(beat_node, "Notes", " ".join(note_refs))
                    
                beat_refs.append(beat_id)
                
            _text(voice_node, "Beats", " ".join(beat_refs))
            voice_refs.append(voice_id)
            
        bar_node = ET.SubElement(bars_db, "Bar", {"id": str(bar_idx)})
        _text(bar_node, "Clef", "G2")
        _text(bar_node, "Voices", " ".join(voice_refs))
        
    # ET indent
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8")

def main():
    score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
    xml_data = build_relational_gpif(score)
    print(xml_data[:3000].decode('utf-8'))

if __name__ == '__main__':
    main()
