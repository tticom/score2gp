import zipfile
import xml.etree.ElementTree as ET

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif')
            root = ET.fromstring(xml_content)
            
            seen_accent_tags = set()
            for note in root.findall(".//Note"):
                for child in note:
                    if 'accent' in child.tag.lower():
                        tag_str = f"<{child.tag}> = {child.text}"
                        if tag_str not in seen_accent_tags:
                            seen_accent_tags.add(tag_str)
                            print(f"Note child tag: {tag_str}")
                            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
