import xml.etree.ElementTree as ET

def get_detailed_paths(elem, current_path=""):
    paths = {}
    tag = elem.tag
    path = f"{current_path}/{tag}" if current_path else tag
    paths[path] = set(elem.attrib.keys())
    for child in elem:
        child_paths = get_detailed_paths(child, path)
        for cp, attrs in child_paths.items():
            if cp not in paths:
                paths[cp] = set()
            paths[cp].update(attrs)
    return paths

def main():
    orig_tree = ET.parse('work/verification/relational_comparisons/lesson_3/original.gpif')
    gen_tree = ET.parse('work/verification/relational_comparisons/lesson_3/generated.gpif')

    orig_paths = get_detailed_paths(orig_tree.getroot())
    gen_paths = get_detailed_paths(gen_tree.getroot())

    print("=== PATHS IN ORIGINAL BUT NOT IN GENERATED ===")
    orig_only = sorted([p for p in orig_paths if p not in gen_paths])
    for p in orig_only:
        print(f"  {p}")

    print("\n=== PATHS IN GENERATED BUT NOT IN ORIGINAL ===")
    gen_only = sorted([p for p in gen_paths if p not in orig_paths])
    for p in gen_only:
        print(f"  {p}")

    print("\n=== ATTRIBUTE DIFFERENCES FOR COMMON PATHS ===")
    for p in sorted(orig_paths.keys()):
        if p in gen_paths:
            orig_attrs = orig_paths[p]
            gen_attrs = gen_paths[p]
            if orig_attrs != gen_attrs:
                print(f"  {p}:")
                print(f"    Original attrs: {orig_attrs}")
                print(f"    Generated attrs: {gen_attrs}")

if __name__ == '__main__':
    main()
