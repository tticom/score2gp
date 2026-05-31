import xml.etree.ElementTree as ET

tree_orig = ET.parse("scratch/original_lesson_3.gpif")
tree_gen = ET.parse("scratch/extracted_score.gpif")

root_orig = tree_orig.getroot()
root_gen = tree_gen.getroot()

def summarize_children(elem):
    if elem is None:
        return "None"
    return [(child.tag, child.attrib, child.text.strip() if child.text else "") for child in elem]

# Compare Score
print("Score comparison:")
print("Orig:", summarize_children(root_orig.find("Score"))[:10])
print("Gen :", summarize_children(root_gen.find("Score"))[:10])

# Compare MasterTrack
print("\nMasterTrack comparison:")
print("Orig:", summarize_children(root_orig.find("MasterTrack")))
print("Gen :", summarize_children(root_gen.find("MasterTrack")))

# Compare Tracks
print("\nTracks comparison:")
print("Orig:", summarize_children(root_orig.find("Tracks")))
print("Gen :", summarize_children(root_gen.find("Tracks")))

# Let's inspect Track child elements
track_orig = root_orig.find("Tracks/Track")
track_gen = root_gen.find("Tracks/Track")
print("Track Orig children:")
for child in track_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")
    if child.tag == "Staves":
        print("    Staves count:", len(child))
print("Track Gen children:")
for child in track_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")
    if child.tag == "Staves":
        print("    Staves count:", len(child))

# Let's inspect first MasterBar
mb_orig = root_orig.find("MasterBars/MasterBar")
mb_gen = root_gen.find("MasterBars/MasterBar")
print("\nMasterBar comparison:")
print("Orig first MasterBar:")
for child in mb_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")
print("Gen first MasterBar:")
for child in mb_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")

# Let's inspect first Bar
b_orig = root_orig.find("Bars/Bar")
b_gen = root_gen.find("Bars/Bar")
print("\nBar comparison:")
print("Orig first Bar:")
for child in b_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")
print("Gen first Bar:")
for child in b_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")

# Let's inspect first Voice
v_orig = root_orig.find("Voices/Voice")
v_gen = root_gen.find("Voices/Voice")
print("\nVoice comparison:")
print("Orig first Voice:")
for child in v_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")
print("Gen first Voice:")
for child in v_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''}")

# Let's inspect first Beat
bt_orig = root_orig.find("Beats/Beat")
bt_gen = root_gen.find("Beats/Beat")
print("\nBeat comparison:")
print("Orig first Beat:")
for child in bt_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")
print("Gen first Beat:")
for child in bt_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")

# Let's inspect first Note
nt_orig = root_orig.find("Notes/Note")
nt_gen = root_gen.find("Notes/Note")
print("\nNote comparison:")
print("Orig first Note:")
for child in nt_orig:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")
    if child.tag == "Properties":
        for prop in child:
            print(f"    <Property name={prop.attrib.get('name')}>")
            for sub in prop:
                print(f"      <{sub.tag}>: {sub.text}")
print("Gen first Note:")
for child in nt_gen:
    print(f"  <{child.tag}>: {child.text.strip() if child.text else ''} {child.attrib}")
    if child.tag == "Properties":
        for prop in child:
            print(f"    <Property name={prop.attrib.get('name')}>")
            for sub in prop:
                print(f"      <{sub.tag}>: {sub.text}")
