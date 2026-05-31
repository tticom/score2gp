import xml.etree.ElementTree as ET
import zipfile

def main():
    with zipfile.ZipFile('/tmp/pytest-of-tticom/pytest-21/test_gpif_standard_guitar_pitc0/guitar_pitch_display.gp') as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        print("=== ZIP ROOT TAG ===")
        print(root.tag)
        print("\n=== ZIP ROOT CHILDREN ===")
        for child in root:
            print(f"  <{child.tag}>")
            
        print("\n=== ZIP NOTES SEARCH ===")
        notes = root.find(".//Notes")
        print(f"notes found via .//Notes: {notes}")
        notes_direct = root.find("Notes")
        print(f"notes found via Notes: {notes_direct}")

if __name__ == '__main__':
    main()
