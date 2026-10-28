"""Independent, stdlib-only FND-03A GPIF structural reader.

Field provenance: native approved GP7/8 references, cross-checked against
CoderLine/alphaTab packages/alphatab/src/importer/GpifParser.ts, methods
_parseMasterBar, _parseDiagramCollectionForStaff and _parseDiagramItem.
No official GPIF specification was available. This is a storage-structure
comparison, not a playback oracle. In particular, repeat counts retain their
GP generation; no GP6/7 multiplier is inferred from one pair of scores.

Chord IDs are staff-local and resolved per occurrence, through every voice.
The complete attached Item (except its local ID) is retained, including fret,
fingering, barre/display properties and chord spelling. These private values
must never be printed or persisted in public evidence.
"""
from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


class StructureRefusal(ValueError):
    """Located refusal; messages contain indices/codes, never musical values."""


def _root(gp: Path | bytes) -> ET.Element:
    try:
        data = gp if isinstance(gp, bytes) else Path(gp).read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            if package.namelist().count('Content/score.gpif') != 1:
                raise StructureRefusal('GPIF_MEMBER_COUNT')
            root = ET.fromstring(package.read('Content/score.gpif'))
    except (ET.ParseError, zipfile.BadZipFile, KeyError) as exc:
        raise StructureRefusal('GPIF_UNREADABLE') from exc
    if root.tag != 'GPIF' or root.find('MasterBars') is None:
        raise StructureRefusal('GPIF_TOPOLOGY')
    return root


def _table(root: ET.Element, container: str, tag: str) -> dict:
    result = {}
    for node in root.findall(f'{container}/{tag}'):
        ident = node.get('id')
        if ident is None or ident in result:
            raise StructureRefusal(f'{container}: RECORD_ID')
        result[ident] = node
    return result


def _linked(table: dict, ident: str, where: str) -> ET.Element:
    if ident not in table:
        raise StructureRefusal(f'{where}: DANGLING_LINK')
    return table[ident]


def _one(node: ET.Element, tag: str, where: str) -> ET.Element | None:
    found = node.findall(tag)
    if len(found) > 1:
        raise StructureRefusal(f'{where}: DUPLICATE_{tag.upper()}')
    return found[0] if found else None


def _repeat(master: ET.Element, where: str) -> dict:
    node = _one(master, 'Repeat', where)
    start = master.find('RepeatStart') is not None  # legacy extension
    end, count = False, None
    if node is not None:
        if set(node.attrib) - {'start', 'end', 'count'} or len(node):
            raise StructureRefusal(f'{where}: REPEAT_SHAPE')
        for flag in ('start', 'end'):
            if node.get(flag, 'false') not in {'true', 'false'}:
                raise StructureRefusal(f'{where}: REPEAT_BOOLEAN')
        start |= node.get('start') == 'true'
        # A count-only Repeat is the existing comparator's legacy extension.
        end = node.get('end', 'true' if 'start' not in node.attrib else 'false') == 'true'
        if end:
            try:
                count = int(node.attrib['count'])
            except (ValueError, KeyError) as exc:
                raise StructureRefusal(f'{where}: REPEAT_COUNT') from exc
            if count < 1:
                raise StructureRefusal(f'{where}: REPEAT_COUNT')
    endings = _one(master, 'AlternateEndings', where)
    try:
        passes = tuple(sorted(set(int(x) for x in (endings.text or '').split()))) if endings is not None else ()
    except ValueError as exc:
        raise StructureRefusal(f'{where}: ENDING_NUMBER') from exc
    if endings is not None and (endings.attrib or len(endings) or not passes or min(passes) < 1):
        raise StructureRefusal(f'{where}: ENDING_SHAPE')
    return {'start': start, 'end': end, 'count': count, 'endings': passes}


def _section(master: ET.Element, where: str) -> tuple | None:
    node = _one(master, 'Section', where)
    if node is None:
        return None
    if node.attrib or any(x.tag not in {'Letter', 'Text'} or x.attrib or len(x) for x in node):
        raise StructureRefusal(f'{where}: SECTION_SHAPE')
    for tag in ('Letter', 'Text'):
        _one(node, tag, where)
    return (node.findtext('Letter') or '', node.findtext('Text') or '')


def _item(node: ET.Element) -> tuple:
    """Canonical XML infoset: discard local Item ID and indentation only.

    Preserve all diagram information, rather than treating a matching chord
    name as proof that its geometry/fingering matches. Child ordering is kept
    conservatively; no undocumented equivalences are assumed.
    """
    attrs = tuple(sorted((k, v) for k, v in node.attrib.items()
                         if not (node.tag == 'Item' and k == 'id')))
    text = node.text if node.text and node.text.strip() else ''
    return node.tag, attrs, text, tuple(_item(child) for child in node)


def read_gp_structure(gp: Path | bytes, *, kinds=('repeats', 'sections', 'chords')) -> dict:
    if not kinds or set(kinds) - {'repeats', 'sections', 'chords'}:
        raise ValueError('unknown structural kind')
    root = _root(gp)
    generation = (root.findtext('GPVersion') or '').split('.')[0]
    if generation not in {'7', '8'}:
        raise StructureRefusal('GP_GENERATION_UNPROVEN')
    masters = root.findall('MasterBars/MasterBar')
    result = {'generation': generation, 'repeats': {}, 'sections': {}, 'chords': {}}
    for bi, master in enumerate(masters):
        if 'repeats' in kinds:
            result['repeats'][bi] = _repeat(master, f'bar {bi}')
        if 'sections' in kinds:
            result['sections'][bi] = _section(master, f'bar {bi}')
    if 'chords' not in kinds:
        return result
    tracks = _table(root, 'Tracks', 'Track')
    order = (root.findtext('MasterTrack/Tracks') or '').split()
    if len(order) != len(set(order)) or set(order) != set(tracks):
        raise StructureRefusal('TRACK_ORDER')
    staves = [staff for ident in order for staff in tracks[ident].findall('Staves/Staff')]
    bars, voices, beats = (_table(root, c, t) for c, t in
                           [('Bars', 'Bar'), ('Voices', 'Voice'), ('Beats', 'Beat')])
    for si, staff in enumerate(staves):
        items = {}
        collections = staff.findall('Properties/Property[@name="DiagramCollection"]')
        if len(collections) > 1:
            raise StructureRefusal(f'staff {si}: DUPLICATE_COLLECTION')
        for collection in collections:
            items = _table(collection, 'Items', 'Item')
        for bi, master in enumerate(masters):
            where = f'bar {bi}, staff {si}'
            ids = (master.findtext('Bars') or '').split()
            if len(ids) != len(staves):
                raise StructureRefusal(f'{where}: STAFF_TOPOLOGY')
            bar = _linked(bars, ids[si], where)
            for vi, vid in enumerate((bar.findtext('Voices') or '').split()):
                if vid == '-1':
                    continue
                voice = _linked(voices, vid, where)
                for ei, bid in enumerate((voice.findtext('Beats') or '').split()):
                    location = (bi, si, vi, ei)
                    beat = _linked(beats, bid, f'{location}')
                    chord = _one(beat, 'Chord', f'{location}')
                    if chord is not None:
                        if chord.attrib or len(chord):
                            raise StructureRefusal(f'{location}: CHORD_LINK_SHAPE')
                        item = _linked(items, (chord.text or '').strip(), f'{location}: CHORD')
                        if len(item.findall('Diagram')) != 1:
                            raise StructureRefusal(f'{location}: DIAGRAM_COUNT')
                        result['chords'][location] = _item(item)
    return result


def compare_gp_structure(truth: Path | bytes, produced: Path | bytes) -> dict:
    """Compare every structural occurrence; publish only counts and locations.

    Repeat counts are compared within GP7/8 only. GP6 refuses in the reader;
    this API makes no version-neutral playback claim.
    """
    result = {}
    for kind in ('repeats', 'sections', 'chords'):
        try:
            want = read_gp_structure(truth, kinds=(kind,))
        except StructureRefusal as exc:
            result[kind] = {'reference_refusal': str(exc)}
            continue
        try:
            have = read_gp_structure(produced, kinds=(kind,))
        except StructureRefusal as exc:
            result[kind] = {'generated_refusal': str(exc)}
            continue
        expected, actual = want[kind], have[kind]
        differences = []
        agreements = 0
        for loc in sorted(set(expected) | set(actual)):
            if loc in expected and loc in actual and expected[loc] == actual[loc]:
                agreements += 1
            else:
                fields = ['presence']
                if kind == 'repeats' and loc in expected and loc in actual:
                    fields = [k for k in expected[loc] if expected[loc][k] != actual[loc][k]]
                elif kind == 'sections' and expected.get(loc) is not None and actual.get(loc) is not None:
                    fields = [name for index, name in enumerate(('letter', 'text'))
                              if expected[loc][index] != actual[loc][index]]
                elif kind == 'chords' and loc in expected and loc in actual:
                    fields = ['diagram_infoset']
                differences.append({'location': loc, 'fields': fields})
        result[kind] = {'expected_occurrences': len(expected), 'actual_occurrences': len(actual),
                        'agreements': agreements, 'differences': differences}
    return result
