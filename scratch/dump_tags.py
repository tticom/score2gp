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
            
            paths = set()
            elem_to_parent = {c: p for p in root.iter() for c in p}
            
            for elem in root.iter():
                path = [elem.tag]
                curr = elem
                while curr in elem_to_parent:
                    curr = elem_to_parent[curr]
                    if curr is not None:
                        path.append(curr.tag)
                paths.add(" -> ".join(reversed(path)))
                
            print("Unique Paths matching color/tuning/properties:")
            for p in sorted(paths):
                if any(x in p.lower() for x in ("color", "colour", "tuning", "properties")):
                    print(p)

if __name__ == "__main__":
    main()
