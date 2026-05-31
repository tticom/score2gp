import xml.etree.ElementTree as ET

def main():
    tree = ET.parse('work/verification/relational_comparisons/lesson_3/generated.gpif')
    root = tree.getroot()

    # Collect all defined IDs
    rhythms = {r.get('id') for r in root.findall('.//Rhythms/Rhythm')}
    notes = {n.get('id') for n in root.findall('.//Notes/Note')}
    beats = {b.get('id') for b in root.findall('.//Beats/Beat')}
    voices = {v.get('id') for v in root.findall('.//Voices/Voice')}
    bars = {b.get('id') for b in root.findall('.//Bars/Bar')}

    print(f"Defined Counts:")
    print(f"  Rhythms: {len(rhythms)}")
    print(f"  Notes: {len(notes)}")
    print(f"  Beats: {len(beats)}")
    print(f"  Voices: {len(voices)}")
    print(f"  Bars: {len(bars)}")

    errors = []

    # 1. Verify Beats -> Rhythm & Notes
    for beat_node in root.findall('.//Beats/Beat'):
        beat_id = beat_node.get('id')
        
        # Rhythm ref
        rhythm_ref = beat_node.find('Rhythm')
        if rhythm_ref is not None:
            ref = rhythm_ref.get('ref')
            if ref not in rhythms:
                errors.append(f"Beat '{beat_id}' references undefined Rhythm '{ref}'")
        else:
            errors.append(f"Beat '{beat_id}' is missing `<Rhythm>` child element")
            
        # Notes ref
        notes_elem = beat_node.find('Notes')
        if notes_elem is not None and notes_elem.text:
            note_refs = notes_elem.text.split()
            for n_ref in note_refs:
                if n_ref not in notes:
                    errors.append(f"Beat '{beat_id}' references undefined Note '{n_ref}'")

    # 2. Verify Voices -> Beats
    for voice_node in root.findall('.//Voices/Voice'):
        voice_id = voice_node.get('id')
        beats_elem = voice_node.find('Beats')
        if beats_elem is not None and beats_elem.text:
            beat_refs = beats_elem.text.split()
            for b_ref in beat_refs:
                if b_ref not in beats:
                    errors.append(f"Voice '{voice_id}' references undefined Beat '{b_ref}'")

    # 3. Verify Bars -> Voices
    for bar_node in root.findall('.//Bars/Bar'):
        bar_id = bar_node.get('id')
        voices_elem = bar_node.find('Voices')
        if voices_elem is not None and voices_elem.text:
            voice_refs = voices_elem.text.split()
            for v_ref in voice_refs:
                if v_ref != "-1" and v_ref not in voices:
                    errors.append(f"Bar '{bar_id}' references undefined Voice '{v_ref}'")

    # 4. Verify MasterBars -> Bars
    for mb_node in root.findall('.//MasterBars/MasterBar'):
        mb_idx = mb_node.get('index') or "?"
        bars_elem = mb_node.find('Bars')
        if bars_elem is not None and bars_elem.text:
            bar_refs = bars_elem.text.split()
            for b_ref in bar_refs:
                if b_ref not in bars:
                    errors.append(f"MasterBar index '{mb_idx}' references undefined Bar '{b_ref}'")

    # Print validation result
    print(f"\nValidation Result:")
    if errors:
        print(f"  FAILED with {len(errors)} errors:")
        for err in errors[:20]:
            print(f"    - {err}")
        if len(errors) > 20:
            print(f"    - ... and {len(errors) - 20} more errors")
    else:
        print("  PASSED! All relational reference integrity checks are clean.")

if __name__ == '__main__':
    main()
