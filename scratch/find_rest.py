import xml.etree.ElementTree as ET

def main():
    tree = ET.parse('work/verification/relational_comparisons/lesson_3/original.gpif')
    root = tree.getroot()
    beats = root.findall('.//Beats/Beat')
    for b in beats:
        if b.find('Notes') is None:
            print("FOUND BEAT WITH NO NOTES:")
            ET.indent(b, space="  ")
            print(ET.tostring(b, encoding="utf-8").decode("utf-8"))

if __name__ == '__main__':
    main()
