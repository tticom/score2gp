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
            
            # Parent mapping
            elem_to_parent = {c: p for p in root.iter() for c in p}
            def get_path(elem):
                path = [elem.tag]
                curr = elem
                while curr in elem_to_parent:
                    curr = elem_to_parent[curr]
                    if curr is not None:
                        path.append(curr.tag)
                return " -> ".join(reversed(path))
            
            print("--- Search for Mixer or Volume/Pan/Mute/Solo tags ---")
            mixer_related = set()
            for elem in root.iter():
                lower_tag = elem.tag.lower()
                if any(x in lower_tag for x in ("mixer", "volume", "pan", "mute", "solo")):
                    mixer_related.add(elem.tag)
            print(f"Found mixer-related tags: {mixer_related}")
            
            for tag in mixer_related:
                matches = root.findall(f".//{tag}")
                print(f"\nTag <{tag}> matches: {len(matches)}")
                for idx, m in enumerate(matches[:3]):
                    print(f"  Path: {get_path(m)}")
                    print(f"  Attrs: {m.attrib}, Text: {m.text}")
                    for child in m:
                        print(f"    Child: <{child.tag}> attrs={child.attrib} text={child.text}")

            print("\n--- Search for Tempo in MasterBars/Bars/timeline ---")
            # We want to see if MasterBar or Bar has Tempo child
            tempos = root.findall(".//MasterBar//Tempo") + root.findall(".//Bar//Tempo")
            print(f"Found {len(tempos)} Tempo elements under MasterBar/Bar.")
            for idx, t in enumerate(tempos[:5]):
                print(f"  Path: {get_path(t)}")
                print(f"  Attrs: {t.attrib}, Text: {t.text}")
                for child in t:
                    print(f"    Child: <{child.tag}> attrs={child.attrib} text={child.text}")

if __name__ == "__main__":
    main()
