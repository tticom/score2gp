import xml.etree.ElementTree as ET

def main():
    path = 'fixtures/private/Lesson-3.xml'
    tree = ET.parse(path)
    root = tree.getroot()
    
    measures = root.findall('.//part/measure')
    print(f"Total measures: {len(measures)}")
    
    measure1 = measures[0]
    print("=== MEASURE 1 XML ===")
    for child in measure1:
        if child.tag == 'note':
            pitch = child.find('pitch')
            step = pitch.find('step').text if pitch is not None else "Rest"
            octave = pitch.find('octave').text if pitch is not None else ""
            voice = child.find('voice').text if child.find('voice') is not None else "None"
            staff = child.find('staff').text if child.find('staff') is not None else "None"
            dur = child.find('duration').text if child.find('duration') is not None else "None"
            chord = child.find('chord') is not None
            print(f"  Note: pitch={step}{octave}, voice={voice}, staff={staff}, duration={dur}, chord={chord}")

if __name__ == '__main__':
    main()
