"""Real-source writer acceptance; no reference musical data enters conversion.

Synthetic tests carry zero acceptance weight. These checks use every mounted
private PDF through the normal CLI, then the independent FND-03A reader.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
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


@pytest.fixture(scope='module')
def converted_corpus():
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fnd03b-test-', dir=ROOT / 'work') as name:
        yield convert_corpus(Path(name))


def test_every_converting_private_pdf_has_resolved_chord_links(converted_corpus):
    """Reject RAW_SYMBOL_AS_TARGET (the original writer) at real beat locations."""
    converted = attachments = 0
    for index, output, _ in converted_corpus:
        if output.exists():
            chords = assert_resolved(output, index)
            score = json.loads((output.parent / 'work/score.ir.json').read_bytes())
            expected = Counter()
            for bi, bar in enumerate(score['bars']):
                for event in bar['events']:
                    if event.get('chord_symbol') or event.get('chord_diagram'):
                        expected[bi] += 1
            if Counter(loc[0] for loc in chords) != expected:
                raise AssertionError(f'input {index}: CHORD_OCCURRENCES_CHANGED')
            attachments += len(chords)
            converted += 1
    assert converted > 0, 'CONVERTING_SOURCE_REQUIRED'
    assert attachments > 0, 'REAL_CHORD_ATTACHMENT_REQUIRED'


def test_wrong_staff_local_target_mutant_is_rejected(converted_corpus, tmp_path, monkeypatch):
    """Reject WRONG_STAFF_LOCAL_TARGET in the actual writer on real-source IR."""
    from score2gp import gpif
    from score2gp.gp_package import write_gp
    from score2gp.ir import ScoreIR

    for index, output, _ in converted_corpus:
        if not output.exists() or not assert_resolved(output, index):
            continue
        score = ScoreIR.model_validate_json((output.parent / 'work/score.ir.json').read_bytes())
        control = tmp_path / 'control.gp'
        write_gp(score, control)
        assert_resolved(control, index)
        original = gpif._text

        def wrong_target(parent, tag, value):
            if parent.tag == 'Beat' and tag == 'Chord':
                # This token cannot be any of the writer's numeric staff IDs.
                value = 'WRONG_STAFF_LOCAL_TARGET'
            return original(parent, tag, value)

        monkeypatch.setattr(gpif, '_text', wrong_target)
        mutant = tmp_path / 'mutant.gp'
        write_gp(score, mutant)
        with pytest.raises(AssertionError, match='CHORD: DANGLING_LINK'):
            assert_resolved(mutant, index)
        return
    raise AssertionError('REAL_CHORD_ATTACHMENT_REQUIRED')
