"""Real-reference rules; no private musical values are stored in this file.

Each assertion is checked against the approved package, not a product writer.
Names in the docstrings identify the reader mutants rejected by the test.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

import gp_structure_oracle as oracle

PRIVATE = Path(__file__).resolve().parents[1] / 'fixtures/private'


def sources():
    paths = sorted(PRIVATE.glob('*.gp'))
    assert paths, 'REQUIRED_GP_CORPUS_MISSING'
    readable = []
    for path in paths:
        with zipfile.ZipFile(path) as package:
            try:
                root = ET.fromstring(package.read('Content/score.gpif'))
            except ET.ParseError:
                with pytest.raises(oracle.StructureRefusal, match='GPIF_UNREADABLE'):
                    oracle.read_gp_structure(path)
                continue
        readable.append((path, root))
    assert readable, 'NO_READABLE_REFERENCES'
    return readable


def equal(actual, expected, code):
    # Failure reports must not disclose private chord names, frets or text.
    if actual != expected:
        raise AssertionError(code)


def test_repeat_flags_and_counts_from_native_references():
    """Reject REPEAT_COUNT_ZERO and REPEAT_START_DROPPED."""
    seen = 0
    for path, root in sources():
        rows = oracle.read_gp_structure(path)['repeats']
        for bi, master in enumerate(root.findall('MasterBars/MasterBar')):
            repeat = master.find('Repeat')
            start = repeat is not None and repeat.get('start') == 'true'
            end = repeat is not None and repeat.get('end') == 'true'
            equal(rows[bi]['start'], start, f'bar {bi}: REPEAT_START')
            equal(rows[bi]['end'], end, f'bar {bi}: REPEAT_END')
            equal(rows[bi]['count'], int(repeat.get('count')) if end else None,
                  f'bar {bi}: REPEAT_COUNT')
            seen += end
    assert seen > 0, 'REPEAT_REFERENCE_REQUIRED'


def test_alternate_endings_from_native_references():
    """Reject ALTERNATE_ENDINGS_DROPPED (including on non-repeat bars)."""
    seen = 0
    for path, root in sources():
        rows = oracle.read_gp_structure(path)['repeats']
        for bi, master in enumerate(root.findall('MasterBars/MasterBar')):
            expected = tuple(sorted({int(x) for x in (master.findtext('AlternateEndings') or '').split()}))
            equal(rows[bi]['endings'], expected, f'bar {bi}: ENDINGS')
            seen += bool(expected)
    assert seen > 0, 'ENDING_REFERENCE_REQUIRED'


def test_section_letter_and_text_from_native_references():
    """Reject SECTION_DROPPED, SECTION_LETTER_DROPPED, SECTION_TEXT_DROPPED."""
    seen = 0
    for path, root in sources():
        rows = oracle.read_gp_structure(path)['sections']
        for bi, master in enumerate(root.findall('MasterBars/MasterBar')):
            node = master.find('Section')
            expected = None if node is None else (node.findtext('Letter') or '', node.findtext('Text') or '')
            equal(rows[bi], expected, f'bar {bi}: SECTION')
            seen += node is not None
    assert seen > 0, 'SECTION_REFERENCE_REQUIRED'


def _xml_facts(node, path=()):
    """Flatten an independently read XML infoset for comparison without IDs."""
    facts = {(path, 'tag'): node.tag}
    facts.update({(path, key): value for key, value in node.attrib.items()
                  if not (node.tag == 'Item' and key == 'id')})
    facts[path, 'text'] = node.text if node.text and node.text.strip() else ''
    for index, child in enumerate(node):
        facts.update(_xml_facts(child, (*path, index)))
    return facts


def _read_facts(value, path=()):
    tag, attrs, text, children = value
    facts = {(path, 'tag'): tag, (path, 'text'): text}
    facts.update({(path, k): v for k, v in attrs})
    for index, child in enumerate(children):
        facts.update(_read_facts(child, (*path, index)))
    return facts


def test_staff_local_diagram_links_and_complete_geometry_from_native_references():
    """Reject CHORDS_DROPPED, DIAGRAM_FRET_DROPPED and GLOBAL_CHORD_IDS."""
    seen = 0
    for path, root in sources():
        rows = oracle.read_gp_structure(path)['chords']
        tracks = {t.get('id'): t for t in root.findall('Tracks/Track')}
        staves = [s for tid in root.findtext('MasterTrack/Tracks').split()
                  for s in tracks[tid].findall('Staves/Staff')]
        tables = {tag: {e.get('id'): e for e in root.findall(f'{tag}s/{tag}')}
                  for tag in ('Bar', 'Voice', 'Beat')}
        expected_locations = set()
        for si, staff in enumerate(staves):
            items = {i.get('id'): i for i in staff.findall(
                'Properties/Property[@name="DiagramCollection"]/Items/Item')}
            for bi, master in enumerate(root.findall('MasterBars/MasterBar')):
                bar = tables['Bar'][master.findtext('Bars').split()[si]]
                for vi, vid in enumerate(bar.findtext('Voices').split()):
                    if vid == '-1':
                        continue
                    for ei, bid in enumerate((tables['Voice'][vid].findtext('Beats') or '').split()):
                        cid = tables['Beat'][bid].findtext('Chord')
                        if cid is None:
                            continue
                        loc = bi, si, vi, ei
                        expected_locations.add(loc)
                        if loc not in rows:
                            raise AssertionError(f'{loc}: CHORD_ATTACHMENT')
                        equal(_read_facts(rows[loc]), _xml_facts(items[cid]), f'{loc}: DIAGRAM_FACTS')
                        seen += 1
        equal(set(rows), expected_locations, 'CHORD_OCCURRENCES')
    assert seen > 0, 'DIAGRAM_REFERENCE_REQUIRED'


def test_structural_comparator_locates_a_real_removed_section(tmp_path):
    """Reject COMPARATOR_IGNORES_SECTIONS; mutate only a local copy."""
    import io

    for path, root in sources():
        for bi, master in enumerate(root.findall('MasterBars/MasterBar')):
            section = master.find('Section')
            if section is None:
                continue
            master.remove(section)
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as package:
                package.writestr('Content/score.gpif', ET.tostring(root))
            result = oracle.compare_gp_structure(path, data.getvalue())
            equal(result['sections']['differences'], [{'location': bi, 'fields': ['presence']}],
                  'SECTION_DIFFERENCE_NOT_LOCATED')
            assert not result['repeats']['differences']
            assert not result['chords']['differences']
            return
    raise AssertionError('SECTION_REFERENCE_REQUIRED')
