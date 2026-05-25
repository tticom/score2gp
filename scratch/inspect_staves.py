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
            
            # Print everything inside Staves for the first track
            for track in root.findall(".//Track")[:1]:
                staves = track.find("Staves")
                if staves is not None:
                    print(ET.tostring(staves, encoding="utf-8").decode("utf-8")[:1000])

if __name__ == "__main__":
    main()
