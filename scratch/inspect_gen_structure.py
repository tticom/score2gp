import xml.etree.ElementTree as ET

def main():
    tree = ET.parse('scratch/extracted_score.gpif')
    root = tree.getroot()
    print("=== ROOT TAG ===")
    print(root.tag)
    print("\n=== ROOT CHILDREN ===")
    for child in root:
        print(f"  <{child.tag}> with {len(child)} children")

if __name__ == '__main__':
    main()
