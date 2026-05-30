import xml.etree.ElementTree as ET

tree_orig = ET.parse("scratch/original_lesson_3.gpif")
root_orig = tree_orig.getroot()

notes_orig = root_orig.find("Notes")
strings = set()
frets = set()
midis = set()
for note in notes_orig:
    props = note.find("Properties")
    str_val = props.find("Property[@name='String']/String")
    fret_val = props.find("Property[@name='Fret']/Fret")
    midi_val = props.find("Property[@name='Midi']/Number")
    if str_val is not None: strings.add(str_val.text)
    if fret_val is not None: frets.add(fret_val.text)
    if midi_val is not None: midis.add(midi_val.text)

print("Original unique strings:", sorted(list(strings)))
print("Original unique frets:", sorted(list(frets), key=int))
print("Original unique midis:", sorted(list(midis), key=int))
