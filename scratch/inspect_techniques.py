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
            
            # Find a few notes with Slide
            print("--- Slide Note Examples ---")
            slides = 0
            for note in root.findall(".//Note"):
                slide_prop = note.find(".//Property[@name='Slide']")
                if slide_prop is not None:
                    print(ET.tostring(note, encoding="utf-8").decode("utf-8").strip())
                    print("-" * 40)
                    slides += 1
                    if slides >= 3:
                        break
                        
            # Find a few notes with HopoOrigin/HopoDestination
            print("\n--- HO/PO Note Examples ---")
            hopos = 0
            for note in root.findall(".//Note"):
                hopo_org = note.find(".//Property[@name='HopoOrigin']")
                hopo_dst = note.find(".//Property[@name='HopoDestination']")
                if hopo_org is not None or hopo_dst is not None:
                    print(ET.tostring(note, encoding="utf-8").decode("utf-8").strip())
                    print("-" * 40)
                    hopos += 1
                    if hopos >= 3:
                        break

            # Find a few notes with Bend
            print("\n--- Bend Note Examples ---")
            bends = 0
            for note in root.findall(".//Note"):
                bend_prop = note.find(".//Property[@name='Bended']")
                if bend_prop is not None:
                    print(ET.tostring(note, encoding="utf-8").decode("utf-8").strip())
                    print("-" * 40)
                    bends += 1
                    if bends >= 3:
                        break

if __name__ == "__main__":
    main()
