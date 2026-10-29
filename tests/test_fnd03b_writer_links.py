"""Real-source writer acceptance; no reference musical data enters conversion.

Synthetic tests carry zero acceptance weight. These checks use every mounted
private PDF through the normal CLI, then the independent FND-03A reader.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from gp_structure_oracle import StructureRefusal, read_gp_structure

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'fixtures/private'


def corpus_sources():
    """Keep FND-03A's numbered pairs first, then cover the remaining PDFs too."""
    pdfs = sorted(PRIVATE.glob('*.pdf'))
    if not pdfs:
        raise AssertionError('REQUIRED_PDF_CORPUS_MISSING')
    paired = []
    for reference in sorted(PRIVATE.glob('*.gp')):
        matches = [p for p in pdfs if p.stem == reference.stem]
        if not matches:
            matches = [p for p in pdfs
                       if p.stem.lower().replace(' ', '-') == reference.stem.lower()]
        if len(matches) != 1:
            raise AssertionError('REQUIRED_PAIRED_PDF_MISSING_OR_AMBIGUOUS')
        paired.append(matches[0])
    return paired + [p for p in pdfs if p not in paired]


def convert_corpus(folder):
    sources = corpus_sources()  # Verify the complete inventory before converting.

    def convert(row):
        index, pdf = row
        destination = folder / f'input-{index:02d}'
        destination.mkdir(parents=True)
        output = destination / 'output.gp'
        command = [sys.executable, '-m', 'score2gp.cli', 'convert', '--pdf', str(pdf),
                   '--pdf-only-tab', '--out', str(output),
                   '--work-dir', str(destination / 'work')]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
        # Raw diagnostics remain private in scratch, never in assertion output.
        (destination / 'stdout.bin').write_bytes(result.stdout)
        (destination / 'stderr.bin').write_bytes(result.stderr)
        return index, output, result.returncode

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(convert, enumerate(sources, 1)))


def assert_resolved(output, index):
    try:
        return read_gp_structure(output, kinds=('chords',))['chords']
    except StructureRefusal as exc:
        raise AssertionError(f'input {index}: {exc}') from None


def assert_chord_attachments(output, index, score):
    """Check identity and full occurrence location, not just target existence.

    The expected names come from the real conversion IR, without consulting the
    writer's ID map or a reference GP. The independent reader supplies the Item
    actually selected by each final Beat/Chord. Never print private names.
    """
    chords = assert_resolved(output, index)
    expected = {}
    staff_offset = 0
    for track in score['tracks']:
        for bi, bar in enumerate(score['bars']):
            voices = defaultdict(list)
            for event in bar['events']:
                if event['track_id'] == track['id']:
                    voices[event['timing']['voice'] - 1].append(event)
            for voice, events in voices.items():
                ordered = sorted(events, key=lambda e: (
                    e['timing']['onset_ticks'], 0 if e['timing'].get('grace') else 1))
                for ei, event in enumerate(ordered):
                    diagram = event.get('chord_diagram')
                    name = diagram['name'] if diagram else event.get('chord_symbol')
                    if diagram or name:
                        expected[bi, staff_offset + voice // 4, voice % 4, ei] = name
        staff_offset += track.get('staff_count') or 1
    if set(chords) != set(expected):
        locations = sorted(set(chords) ^ set(expected))
        raise AssertionError(f'input {index}: CHORD_LOCATIONS_CHANGED {locations}')
    for location, item in chords.items():
        if dict(item[1]).get('name') != expected[location]:
            raise AssertionError(f'input {index}: CHORD_TARGET_CHANGED {location}')
    return chords


@pytest.fixture(scope='module')
def converted_corpus():
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fnd03b-test-', dir=ROOT / 'work') as name:
        yield convert_corpus(Path(name))


def test_every_converting_private_pdf_has_resolved_chord_links(converted_corpus):
    """Reject RAW_SYMBOL_AS_TARGET and WRONG_EXISTING_TARGET at real locations."""
    converted = attachments = 0
    for index, output, _ in converted_corpus:
        if output.exists():
            score = json.loads((output.parent / 'work/score.ir.json').read_bytes())
            chords = assert_chord_attachments(output, index, score)
            attachments += len(chords)
            converted += 1
    assert converted > 0, 'CONVERTING_SOURCE_REQUIRED'
    assert attachments > 0, 'REAL_CHORD_ATTACHMENT_REQUIRED'


@pytest.mark.parametrize('mutation', ['DANGLING_TARGET', 'WRONG_EXISTING_TARGET'])
def test_wrong_staff_local_target_mutant_is_rejected(
        converted_corpus, tmp_path, monkeypatch, mutation):
    """Kill both an unresolved token and a resolvable but incorrect diagram ID."""
    from score2gp import gpif
    from score2gp.gp_package import write_gp
    from score2gp.ir import ScoreIR

    cases = 0
    for index, output, _ in converted_corpus:
        if not output.exists():
            continue
        ir = json.loads((output.parent / 'work/score.ir.json').read_bytes())
        chords = assert_chord_attachments(output, index, ir)
        if not chords:
            continue
        if mutation == 'WRONG_EXISTING_TARGET':
            # This corpus case must contain different diagrams in one staff.
            # ID 1 exists in that staff; the oracle below proves it resolves.
            if (len(ir['tracks']) != 1 or (ir['tracks'][0].get('staff_count') or 1) != 1
                    or len({dict(item[1]).get('name') for item in chords.values()}) < 2):
                continue
        score = ScoreIR.model_validate(ir)
        control = tmp_path / 'control.gp'
        write_gp(score, control)
        assert_chord_attachments(control, index, ir)
        original = gpif._text

        def wrong_target(parent, tag, value):
            if parent.tag == 'Beat' and tag == 'Chord':
                value = '1' if mutation == 'WRONG_EXISTING_TARGET' else mutation
            return original(parent, tag, value)

        mutant = tmp_path / 'mutant.gp'
        with monkeypatch.context() as patch:
            patch.setattr(gpif, '_text', wrong_target)
            write_gp(score, mutant)
        if mutation == 'WRONG_EXISTING_TARGET':
            resolved = assert_resolved(mutant, index)
            assert set(resolved) == set(chords), 'MUTANT_MUST_PRESERVE_LOCATIONS'
            assert resolved != chords, 'MUTANT_MUST_CHANGE_SELECTED_DIAGRAM'
            reason = 'CHORD_TARGET_CHANGED'
        else:
            reason = 'CHORD: DANGLING_LINK'
        with pytest.raises(AssertionError, match=reason):
            assert_chord_attachments(mutant, index, ir)
        cases += 1
    assert cases > 0, 'REAL_CHORD_ATTACHMENT_REQUIRED'
