import xml.etree.ElementTree as ET

def main():
    path = 'work/verification/relational_comparisons/lesson_3/original.gpif'
    tree = ET.parse(path)
    root = tree.getroot()
    
    beats = root.findall('.//Beats/Beat')
    print("=== ORIGINAL FIRST 8 BEATS ===")
    for b in beats[:8]:
        beat_id = b.get('id')
        notes_elem = b.find('Notes')
        notes_text = notes_elem.text if notes_elem is not None else "None"
        rhythm_ref = b.find('Rhythm').get('ref')
        print(f"Beat id={beat_id}: rhythm={rhythm_ref}, notes={notes_text}")
        
    print("=== ORIGINAL FIRST 8 NOTES ===")
    notes = root.findall('.//Notes/Note')
    for n in notes[:8]:
        note_id = n.get('id')
        fret = n.find('.//Property[@name="Fret"]/Fret').text
        string = n.find('.//Property[@name="String"]/String').text
        pitch = n.find('.//Property[@name="Midi"]/Number').text
        print(f"Note id={note_id}: string={string}, fret={fret}, pitch={pitch}")

if __name__ == '__main__':
    main()
