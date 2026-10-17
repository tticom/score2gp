"""Independent native chord reader and byte-preserving attachment normalization.

Private musical values are read from approved packages, never stored here.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


def gpif_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as package:
        return ET.fromstring(package.read("Content/score.gpif"))


def gpif_beats(root: ET.Element) -> dict[tuple[int, int], ET.Element]:
    tables = {name: {x.get("id"): x for x in root.findall(f"{name}s/{name}")}
              for name in ("Bar", "Voice", "Beat")}
    result = {}
    for bi, master in enumerate(root.findall("MasterBars/MasterBar")):
        bar_ids = master.findtext("Bars").split()
        assert len(bar_ids) == 1
        bar = tables["Bar"][bar_ids[0]]
        voices = [x for x in bar.findtext("Voices").split() if x != "-1"]
        for voice in voices:
            for ei, beat in enumerate(tables["Voice"][voice].findtext("Beats").split()):
                result[bi, ei] = tables["Beat"][beat]
    return result


def gpif_chords(root: ET.Element) -> dict[tuple[int, int], str]:
    items = {x.get("id"): x.get("name") for x in root.findall(
        './/Staves/Staff/Properties/Property[@name="DiagramCollection"]/Items/Item')}
    result = {}
    for location, beat in gpif_beats(root).items():
        chord = beat.findtext("Chord")
        if chord is not None:
            assert chord in items, location
            result[location] = items[chord]
    return result


def without_verified_chord_additions(data: bytes, reference: Path, *, count: int) -> bytes:
    """Remove exactly the independently verified additions before frozen digests.

    The caller names a source whose baseline has no chord annotations. Reject
    missing, displaced, dangling, or wrong-name additions before touching bytes.
    Every other byte remains subject to both existing whole-file digests.
    """
    actual = gpif_chords(ET.fromstring(data))
    expected = gpif_chords(gpif_root(reference))
    assert len(actual) == len(expected) == count
    assert actual == expected
    stripped, removed = re.subn(rb"(?m)^      <Chord>[^<]*</Chord>\r?\n", b"", data)
    assert removed == count
    def restore_empty_collection(match):
        indent = match.group(1)
        return (indent + b'<Property name="DiagramCollection">\n' +
                indent + b'  <Items />\n' + indent + b'</Property>\n')

    stripped, collections = re.subn(
        rb'(?m)^([ \t]*)<Property name="DiagramCollection">(?s:.*?)^\1</Property>\r?\n',
        b"", stripped)
    assert collections == 1
    # The native writer appends its empty collection defaults after explicit
    # properties. Restore the empty DiagramCollection at that baseline slot.
    stripped, slots = re.subn(
        rb'(?m)^([ \t]*)<Property name="ChordWorkingSet">\r?\n\1  <Items />\r?\n\1</Property>\r?\n',
        lambda match: match.group() + restore_empty_collection(match), stripped)
    assert slots == 1
    return stripped
