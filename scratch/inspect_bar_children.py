import zipfile
import xml.etree.ElementTree as ET

def dump_node(node, level=0):
    indent = "  " * level
    text = node.text.strip() if node.text else ""
    val_str = f" = {text}" if text else ""
    print(f"{indent}<{node.tag} {node.attrib}>{val_str}")
    for child in node:
        dump_node(child, level + 1)

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif')
            root = ET.fromstring(xml_content)
            
            # Print master bar children
            print("=== MasterBar 0 (index 1) ===")
            mb = root.find(".//MasterBar")
            if mb is not None:
                dump_node(mb)
                
            print("\n=== Bar 0 ===")
            b = root.find(".//Bars/Bar")
            if b is not None:
                dump_node(b)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
