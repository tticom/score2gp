import xml.etree.ElementTree as ET

def main():
    orig_tree = ET.parse('scratch/original_lesson_3.gpif')
    gen_tree = ET.parse('scratch/extracted_score.gpif')

    orig_score = orig_tree.find('.//Score')
    gen_score = gen_tree.find('.//Score')

    print("=== ORIGINAL SCORE CHILDREN ===")
    for child in orig_score:
        print(f"  <{child.tag}>")

    print("\n=== GENERATED SCORE CHILDREN ===")
    for child in gen_score:
        print(f"  <{child.tag}>")

if __name__ == '__main__':
    main()
