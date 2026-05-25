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
            
            # Print unique tag names in the entire XML
            tags = set()
            for elem in root.iter():
                tags.add(elem.tag)
            print("All unique tags:")
            print(sorted(list(tags)))
            
            print("\n--- Searching for beat-level directions or text ---")
            for beat in root.findall(".//Beat"):
                for child in beat:
                    # if child tag has text or direction, print it
                    if "text" in child.tag.lower() or "direction" in child.tag.lower() or child.tag in ("Direction", "Text", "FreeText"):
                        print(f"Beat id={beat.get('id')}: child tag={child.tag}, text={child.text}, attrs={child.attrib}")
                        
if __name__ == "__main__":
    main()
