import zipfile
import xml.etree.ElementTree as ET

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif')
            root = ET.fromstring(xml_content)
            
            # Search under MasterBars
            print("Searching in MasterBars...")
            for mb in root.findall(".//MasterBars/MasterBar"):
                props = mb.find(".//Property")
                if props is not None:
                    print(f"Found Property in MasterBar {mb.get('index')}:")
                    print(ET.tostring(mb, encoding='utf-8').decode('utf-8')[:500])
                    break
            else:
                print("No Property found in MasterBars.")
                
            # Search under Bars
            print("\nSearching in Bars...")
            for b in root.findall(".//Bars/Bar"):
                props = b.find(".//Property")
                if props is not None:
                    print(f"Found Property in Bar {b.get('id')}:")
                    print(ET.tostring(b, encoding='utf-8').decode('utf-8')[:500])
                    break
            else:
                print("No Property found in Bars.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
