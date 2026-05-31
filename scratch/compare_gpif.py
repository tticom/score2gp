import zipfile
from xml.etree import ElementTree as ET
from collections import Counter

def get_gpif_root(gp_path):
    with zipfile.ZipFile(gp_path, 'r') as z:
        xml_data = z.read('Content/score.gpif')
        return ET.fromstring(xml_data)

def count_tags(element):
    counts = Counter()
    for el in element.iter():
        counts[el.tag] += 1
    return counts

def print_element_structure(el, indent=0):
    children_tags = [child.tag for child in el]
    print("  " * indent + f"<{el.tag}> attrs={list(el.attrib.keys())} children={set(children_tags)}")
    for child in list(el)[:3]: # print first few children
        print_element_structure(child, indent + 1)
    if len(el) > 3:
        print("  " * (indent + 1) + f"... and {len(el) - 3} more children")

def compare_score_children(root_orig, root_gen):
    score_orig = root_orig.find('Score')
    score_gen = root_gen.find('Score')
    
    orig_tags = [c.tag for c in score_orig]
    gen_tags = [c.tag for c in score_gen]
    
    print("\n--- Compare <Score> children ---")
    print(f"Original: {orig_tags}")
    print(f"Generated: {gen_tags}")
    print(f"Original only: {set(orig_tags) - set(gen_tags)}")
    print(f"Generated only: {set(gen_tags) - set(orig_tags)}")

def compare_tracks(root_orig, root_gen):
    tracks_orig = root_orig.findall('.//Track')
    tracks_gen = root_gen.findall('.//Track')
    
    print(f"\n--- Compare Tracks count: Orig={len(tracks_orig)}, Gen={len(tracks_gen)} ---")
    if tracks_orig and tracks_gen:
        to = tracks_orig[0]
        tg = tracks_gen[0]
        to_tags = {c.tag for c in to.iter()}
        tg_tags = {c.tag for c in tg.iter()}
        print(f"Original Track sub-elements: {sorted(list(to_tags))}")
        print(f"Generated Track sub-elements: {sorted(list(tg_tags))}")
        print(f"Original Track unique tags: {to_tags - tg_tags}")
        print(f"Generated Track unique tags: {tg_tags - to_tags}")

def compare_bars(root_orig, root_gen):
    bars_orig = root_orig.findall('.//Bars/Bar')
    bars_gen = root_gen.findall('.//Bars/Bar')
    print(f"\n--- Compare Bars count: Orig={len(bars_orig)}, Gen={len(bars_gen)} ---")
    if bars_orig and bars_gen:
        bo = bars_orig[0]
        bg = bars_gen[0]
        bo_tags = {c.tag for c in bo.iter()}
        bg_tags = {c.tag for c in bg.iter()}
        print(f"Original Bar unique tags: {bo_tags - bg_tags}")
        print(f"Generated Bar unique tags: {bg_tags - bo_tags}")

def compare_events(root_orig, root_gen):
    events_orig = root_orig.findall('.//Event')
    events_gen = root_gen.findall('.//Event')
    print(f"\n--- Compare Events count: Orig={len(events_orig)}, Gen={len(events_gen)} ---")
    if events_orig and events_gen:
        eo = events_orig[0]
        eg = events_gen[0]
        eo_tags = {c.tag for c in eo.attrib.keys()}
        eg_tags = {c.tag for c in eg.attrib.keys()}
        print(f"Original Event attributes: {eo.attrib}")
        print(f"Generated Event attributes: {eg.attrib}")

def compare_notes(root_orig, root_gen):
    notes_orig = root_orig.findall('.//Note')
    notes_gen = root_gen.findall('.//Note')
    print(f"\n--- Compare Notes count: Orig={len(notes_orig)}, Gen={len(notes_gen)} ---")
    if notes_orig and notes_gen:
        no = notes_orig[0]
        ng = notes_gen[0]
        print(f"Original Note attributes: {no.attrib}")
        print(f"Generated Note attributes: {ng.attrib}")
        no_tags = {c.tag for c in no.iter()}
        ng_tags = {c.tag for c in ng.iter()}
        print(f"Original Note sub-elements: {sorted(list(no_tags))}")
        print(f"Generated Note sub-elements: {sorted(list(ng_tags))}")

def main():
    orig_path = 'fixtures/private/Lesson-3.gp'
    gen_path = 'work/private_e2e_smoke_v0_1/private_input_custom_lesson_3/smoke.gp'
    
    root_orig = get_gpif_root(orig_path)
    root_gen = get_gpif_root(gen_path)
    
    compare_score_children(root_orig, root_gen)
    compare_tracks(root_orig, root_gen)
    compare_bars(root_orig, root_gen)
    compare_events(root_orig, root_gen)
    compare_notes(root_orig, root_gen)

if __name__ == '__main__':
    main()
