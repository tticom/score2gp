import xml.etree.ElementTree as ET

def get_child_tags_and_attrs(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    print(f"\nFile: {file_path}")
    print(f"Root tag: {root.tag}, attributes: {root.attrib}")
    children = list(root)
    print(f"Number of direct children: {len(children)}")
    tags = [child.tag for child in children]
    # Count unique tags
    unique_tags = {}
    for t in tags:
        unique_tags[t] = unique_tags.get(t, 0) + 1
    print("Direct children tag counts:")
    for t, count in unique_tags.items():
        print(f"  <{t}>: {count}")
    return root

root_orig = get_child_tags_and_attrs("scratch/original_lesson_3.gpif")
root_gen = get_child_tags_and_attrs("scratch/extracted_score.gpif")
