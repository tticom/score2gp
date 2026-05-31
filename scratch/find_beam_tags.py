import xml.etree.ElementTree as ET

def main():
    path = 'work/verification/relational_comparisons/lesson_3/original.gpif'
    tree = ET.parse(path)
    root = tree.getroot()
    
    tags = set()
    for el in root.iter():
        tags.add(el.tag)
        
    print("=== UNIQUE TAGS ===")
    for t in sorted(tags):
        if "beam" in t.lower() or "group" in t.lower() or "split" in t.lower() or "rhythm" in t.lower():
            print(t)
            
    print("\n=== SEARCHING PROPERTY NAMES ===")
    prop_names = set()
    for el in root.findall('.//Property'):
        prop_names.add(el.get('name'))
    for n in sorted(prop_names):
        if "beam" in n.lower() or "group" in n.lower() or "split" in n.lower() or "rhythm" in n.lower():
            print(f"Property name: {n}")
            
    print("\n=== SEARCHING BEAT CHILDREN ===")
    beat_children = set()
    for b in root.findall('.//Beats/Beat'):
        for child in b:
            beat_children.add(child.tag)
    print(sorted(beat_children))

if __name__ == '__main__':
    main()
