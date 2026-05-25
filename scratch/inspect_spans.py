import zipfile
from xml.etree import ElementTree as ET
from pathlib import Path

def main():
    gp_path = Path(r"C:\Users\niall\src\Python\score2gp\fixtures\private\Derek Trucks BB King.gp")
    if not gp_path.exists():
        print(f"File not found: {gp_path}")
        return
        
    with zipfile.ZipFile(gp_path, "r") as z:
        if "Content/score.gpif" in z.namelist():
            gpif_bytes = z.read("Content/score.gpif")
            root = ET.fromstring(gpif_bytes)
            
            # Print GraceNotes beat example
            print("--- GraceNotes beat example ---")
            for beat in root.findall(".//Beat"):
                grace = beat.find("GraceNotes")
                if grace is not None:
                    print(ET.tostring(beat, encoding="utf-8").decode("utf-8").strip())
                    print("-" * 40)
                    break
                    
            # Print LetRing note example
            print("\n--- LetRing note example ---")
            for note in root.findall(".//Note"):
                lr = note.find("LetRing")
                if lr is not None:
                    print(ET.tostring(note, encoding="utf-8").decode("utf-8").strip())
                    print("-" * 40)
                    break
                    
            # Print PalmMute tracks / beat examples
            print("\n--- PalmMute tracks / other examples ---")
            pms = root.findall(".//PalmMute")
            for pm in pms[:3]:
                # Find parent
                parent_map = {c: p for p in root.iter() for c in p}
                p = parent_map.get(pm)
                print(f"PalmMute parent tag: {p.tag}")
                print(ET.tostring(pm, encoding="utf-8").decode("utf-8").strip())
                print("-" * 40)
                
            # Search for any properties of LetRing / PalmMute under Note or Event/Beat
            print("\n--- Any other LetRing/PalmMute references ---")
            for elem in root.iter():
                if "letring" in elem.tag.lower() or "palmmute" in elem.tag.lower():
                    print(f"Found element: {elem.tag}, Attrs: {elem.attrib}")

if __name__ == "__main__":
    main()
