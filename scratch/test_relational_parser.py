import zipfile
from xml.etree import ElementTree as ET
from fractions import Fraction

def parse_relational_gpif(gp_path):
    with zipfile.ZipFile(gp_path, 'r') as z:
        root = ET.fromstring(z.read('Content/score.gpif'))
    
    # 1. Parse Rhythms
    rhythms_node = root.find('Rhythms')
    rhythms = {}
    duration_ticks_map = {
        "Whole": 3840,
        "Half": 1920,
        "Quarter": 960,
        "Eighth": 480,
        "Sixteenth": 240,
        "ThirtySecond": 120,
        "SixtyFourth": 60,
    }
    
    for r in rhythms_node.findall('Rhythm'):
        r_id = r.get('id')
        val = r.find('NoteValue').text
        ticks = duration_ticks_map.get(val, 960)
        
        dots = r.find('AugmentationDot')
        if dots is not None:
            count = int(dots.get('count') or 1)
            factor = 1.0
            for i in range(count):
                factor += 1.0 / (2 ** (i + 1))
            ticks = int(ticks * factor)
            
        rhythms[r_id] = {
            "value": val,
            "ticks": ticks
        }
    
    # 2. Parse Notes
    notes_node = root.find('Notes')
    notes = {}
    for n in notes_node.findall('Note'):
        n_id = n.get('id')
        props = n.find('Properties')
        fret = int(props.find('.//Property[@name="Fret"]/Fret').text)
        string = int(props.find('.//Property[@name="String"]/String').text) + 1 # 1-indexed string
        pitch = int(props.find('.//Property[@name="Midi"]/Number').text)
        
        notes[n_id] = {
            "fret": fret,
            "string": string,
            "pitch": pitch
        }
        
    # 3. Parse Beats
    beats_node = root.find('Beats')
    beats = {}
    for b in beats_node.findall('Beat'):
        b_id = b.get('id')
        dyn = b.find('Dynamic')
        dyn_text = dyn.text if dyn is not None else "MF"
        
        rhythm_ref = b.find('Rhythm').get('ref')
        r_info = rhythms[rhythm_ref]
        
        rest = b.find('Rest') is not None
        
        notes_ref_text = b.find('Notes')
        notes_refs = notes_ref_text.text.split() if notes_ref_text is not None and notes_ref_text.text else []
        
        free_text = b.find('FreeText')
        text = free_text.text if free_text is not None else None
        
        beats[b_id] = {
            "dynamic": dyn_text,
            "duration_ticks": r_info["ticks"],
            "rest": rest,
            "notes": [notes[nid] for nid in notes_refs],
            "text": text
        }
        
    # 4. Parse Voices
    voices_node = root.find('Voices')
    voices = {}
    for v in voices_node.findall('Voice'):
        v_id = v.get('id')
        beats_ref_text = v.find('Beats')
        beat_refs = beats_ref_text.text.split() if beats_ref_text is not None and beats_ref_text.text else []
        voices[v_id] = beat_refs
        
    # 5. Parse Bars
    bars_node = root.find('Bars')
    print("Parsed Bars:")
    for bar in list(bars_node.findall('Bar'))[:5]: # print first 5 bars
        bar_id = bar.get('id')
        voice_refs = bar.find('Voices').text.split()
        print(f"Bar {bar_id}: Clef={bar.find('Clef').text}, Voice Refs={voice_refs}")
        
        # stepping through each voice to calculate beat positions
        for v_idx, v_id in enumerate(voice_refs):
            if v_id == "-1":
                continue
            print(f"  Voice {v_idx} (id {v_id}):")
            onset = 0
            for beat_id in voices[v_id]:
                b = beats[beat_id]
                print(f"    Beat {beat_id}: onset={onset}, duration={b['duration_ticks']}, rest={b['rest']}, notes={b['notes']}, text={b['text']}")
                onset += b['duration_ticks']

def main():
    parse_relational_gpif('fixtures/private/Lesson-3.gp')

if __name__ == '__main__':
    main()
