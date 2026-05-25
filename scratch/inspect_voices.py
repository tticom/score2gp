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
            
            print("--- Searching globally for Event, Beat, and Note tags ---")
            events = root.findall(".//Event")
            beats = root.findall(".//Beat")
            notes = root.findall(".//Note")
            print(f"Global counts: Event={len(events)}, Beat={len(beats)}, Note={len(notes)}")
            
            if beats:
                beat = beats[0]
                # Find its ancestors/parent
                for p in root.iter():
                    if beat in list(p):
                        print(f"Beat 0 parent: {p.tag}, attrs={p.attrib}")
                        break
                # Print beat's children
                print(f"Beat children count: {len(beat)}")
                for child in beat:
                    print(f"  Child tag: {child.tag}, attrs: {child.attrib}")
            
            if events:
                event = events[0]
                for p in root.iter():
                    if event in list(p):
                        print(f"Event 0 parent: {p.tag}, attrs={p.attrib}")
                        break

if __name__ == "__main__":
    main()






