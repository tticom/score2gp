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
            
            for track in root.findall(".//Track")[:1]:
                sdl = track.find("SystemsDefautLayout")
                sl = track.find("SystemsLayout")
                print(f"SystemsDefautLayout: {sdl.text if sdl is not None else 'N/A'}")
                print(f"SystemsLayout: {sl.text if sl is not None else 'N/A'}")

if __name__ == "__main__":
    main()
