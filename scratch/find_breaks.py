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
            
            breaks = root.findall(".//Break")
            print(f"Found {len(breaks)} Break elements:")
            for b in breaks[:5]:
                # Print parent path
                path = [b.tag]
                curr = b
                # Parent mapping
                elem_to_parent = {c: p for p in root.iter() for c in p}
                while curr in elem_to_parent:
                    curr = elem_to_parent[curr]
                    if curr is not None:
                        path.append(curr.tag)
                print(" -> ".join(reversed(path)))
                print(f"  Attrs: {b.attrib}, Text: {b.text}")
                for child in b:
                    print(f"    Child: <{child.tag}> text={child.text} attrib={child.attrib}")

if __name__ == "__main__":
    main()
