import xml.etree.ElementTree as ET

def main():
    path = 'work/verification/relational_comparisons/lesson_3/original.gpif'
    tree = ET.parse(path)
    root = tree.getroot()
    
    beats = root.findall('.//Beats/Beat')
    print("=== FIRST 16 BEAT XPROPERTIES ===")
    for b in beats[:16]:
        xps = []
        for xp in b.findall('.//XProperty'):
            xps.append(f"{xp.get('id')}={xp.find('Int').text if xp.find('Int') is not None else 'None'}")
        print(f"Beat id={b.get('id')}: {xps}")

if __name__ == '__main__':
    main()
