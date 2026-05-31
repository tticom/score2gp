import xml.etree.ElementTree as ET

def inspect_gpif(filepath, name):
    print(f"=== {name}: {filepath} ===")
    tree = ET.parse(filepath)
    
    # Let's find all Note elements anywhere in the tree
    notes = list(tree.findall('.//Note'))
    print(f"Total Notes: {len(notes)}")
    
    # We want to see how the pitch step, accidental and octave are derived from Midi number
    for note in notes[:40]:
        note_id = note.get('id')
        props = note.find('Properties')
        if props is not None:
            midi_num = None
            fret = None
            string = None
            cp_step, cp_oct = None, None
            tp_step, tp_oct = None, None
            
            for prop in props.findall('Property'):
                p_name = prop.get('name')
                if p_name == 'Midi':
                    midi_num = int(prop.find('Number').text) if prop.find('Number') is not None else None
                elif p_name == 'Fret':
                    fret = int(prop.find('Fret').text) if prop.find('Fret') is not None else None
                elif p_name == 'String':
                    string = int(prop.find('String').text) if prop.find('String') is not None else None
                elif p_name == 'ConcertPitch':
                    pitch_node = prop.find('Pitch')
                    if pitch_node is not None:
                        cp_step = pitch_node.find('Step').text if pitch_node.find('Step') is not None else ''
                        cp_oct = int(pitch_node.find('Octave').text) if pitch_node.find('Octave') is not None else None
                elif p_name == 'TransposedPitch':
                    pitch_node = prop.find('Pitch')
                    if pitch_node is not None:
                        tp_step = pitch_node.find('Step').text if pitch_node.find('Step') is not None else ''
                        tp_oct = int(pitch_node.find('Octave').text) if pitch_node.find('Octave') is not None else None
            
            print(f"ID={note_id} String={string} Fret={fret} Midi={midi_num} | Concert={cp_step}{cp_oct} Transposed={tp_step}{tp_oct}")

inspect_gpif('scratch/original_lesson_3.gpif', 'ORIGINAL')
