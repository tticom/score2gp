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
            
            print("--- Track Colors ---")
            for track in root.findall(".//Track"):
                color = track.find("Color")
                if color is not None:
                    print(f"Track ID: {track.get('id')}, Name: {track.find('Name').text if track.find('Name') is not None else 'N/A'}")
                    print(f"  Color Text/Attribs: {color.text}, {color.attrib}")
                    for child in color:
                        print(f"    Child: <{child.tag}> text={child.text} attrib={child.attrib}")
                else:
                    print(f"Track ID: {track.get('id')} has no Color tag")
                    
            print("\n--- Track Properties / Pitches ---")
            for prop in root.findall(".//Track//Property"):
                name = prop.get("name")
                if name in ("Tuning", "Pitches", "Strings", "TuningStrings"):
                    print(f"Property Name: {name}")
                    print(f"  Attribs: {prop.attrib}, Text: {prop.text}")
                    for child in prop:
                        print(f"    Child: <{child.tag}> text={child.text} attrib={child.attrib}")
                        for subchild in child:
                            print(f"      Subchild: <{subchild.tag}> text={subchild.text} attrib={subchild.attrib}")

if __name__ == "__main__":
    main()
