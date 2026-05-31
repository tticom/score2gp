import xml.etree.ElementTree as ET

def main():
    for name in ['original', 'generated']:
        path = f'work/verification/relational_comparisons/lesson_3/{name}.gpif'
        tree = ET.parse(path)
        root = tree.getroot()
        voices = root.findall('.//Voices/Voice')
        print(f"=== {name.upper()} VOICES (first 5) ===")
        for v in voices[:5]:
            print(ET.tostring(v).decode().strip())
            
        print(f"=== {name.upper()} BARS (first 5) ===")
        bars = root.findall('.//Bars/Bar')
        for b in bars[:5]:
            print(ET.tostring(b).decode().strip())

if __name__ == '__main__':
    main()
