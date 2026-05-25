import zipfile
import xml.etree.ElementTree as ET

def search_nodes(node, path=''):
    curr_path = f"{path}/{node.tag}"
    tag_lower = node.tag.lower()
    
    keywords = ['anacrusis', 'barline', 'repeat', 'bar', 'measure']
    match = any(k in tag_lower for k in keywords)
    
    # Check attributes
    for k, v in node.attrib.items():
        if any(kw in k.lower() or kw in v.lower() for kw in keywords):
            match = True
            
    # Check text if short
    text_val = node.text.strip() if node.text else ""
    if len(text_val) < 100 and any(kw in text_val.lower() for kw in keywords):
        match = True
        
    if match:
        val_str = text_val
        print(f"{curr_path} -> text: {val_str}, attrs: {node.attrib}")
        
    for child in node:
        search_nodes(child, curr_path)

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif')
            root = ET.fromstring(xml_content)
            search_nodes(root)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
