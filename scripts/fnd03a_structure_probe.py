"""Sanitized FND-03A census of all reference and fresh PDF-only GP files.

Run outside pytest: no writer patching, reference template or reference input
to conversion. Private inputs/outputs remain below ignored work/. The public
JSON contains input indices, hashes, counts, locations, codes and times only.
This is a diagnostic, never a conversion-success or playback-equivalence gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from gp_structure_oracle import StructureRefusal, compare_gp_structure, read_gp_structure


def census(path):
    result = read_gp_structure(path, kinds=('repeats', 'sections'))
    counts = {'generation': result['generation'],
            'bars': len(result['repeats']),
            'repeat_starts': sum(r['start'] for r in result['repeats'].values()),
            'repeat_ends': sum(r['end'] for r in result['repeats'].values()),
            'ending_markers': sum(bool(r['endings']) for r in result['repeats'].values()),
            'sections': sum(s is not None for s in result['sections'].values())}
    try:
        counts['chord_attachments'] = len(read_gp_structure(path, kinds=('chords',))['chords'])
    except StructureRefusal as exc:
        counts['chord_refusal'] = str(exc)
    return counts


def run(corpus, scratch, reuse=False):
    paths = sorted(corpus.glob('*.gp'))
    if not paths:
        raise SystemExit('REQUIRED_GP_CORPUS_MISSING')
    rows = []
    for index, reference in enumerate(paths, 1):
        folder = scratch / f'input-{index:02d}'
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'output.gp'
        row = {'input': index, 'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest()}
        try:
            row['reference'] = census(reference)
        except StructureRefusal as exc:
            row['reference_refusal'] = str(exc)
        if not reuse:
            pdf = reference.with_suffix('.pdf')
            if not pdf.exists():
                matches = [p for p in corpus.glob('*.pdf')
                           if p.stem.lower().replace(' ', '-') == reference.stem.lower()]
                if len(matches) != 1:
                    row['conversion_refusal'] = 'PDF_SOURCE_MISSING_OR_AMBIGUOUS'
                    rows.append(row)
                    continue
                pdf = matches[0]
            if output.exists():
                raise SystemExit('FRESH_OUTPUT_DIRECTORY_REQUIRED')
            command = [sys.executable, '-m', 'score2gp.cli', 'convert', '--pdf', str(pdf),
                       '--pdf-only-tab', '--out', str(output), '--work-dir', str(folder / 'work')]
            start = time.monotonic()
            try:
                done = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
                                      env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')})
                row['conversion_exit_code'] = done.returncode
                (folder / 'stdout.bin').write_bytes(done.stdout)
                (folder / 'stderr.bin').write_bytes(done.stderr)
            except subprocess.TimeoutExpired:
                row['conversion_refusal'] = 'TIMEOUT'
            row['seconds'] = round(time.monotonic() - start, 2)
        if output.is_file():
            row['generated_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
            try:
                row['generated'] = census(output)
                if 'reference' in row:
                    row['comparison'] = compare_gp_structure(reference, output)
            except StructureRefusal as exc:
                row['generated_refusal'] = str(exc)
        else:
            row['generated_refusal'] = 'NO_GP_WRITTEN'
        rows.append(row)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'fixtures/private')
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true', help='Reinspect existing outputs; no freshness claim')
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    if not scratch.is_relative_to((ROOT / 'work').resolve()):
        raise SystemExit('SCRATCH_MUST_BE_UNDER_IGNORED_WORK')
    print(json.dumps({'schema': 'fnd03a-structure-probe.v1',
                      'fresh_conversion': not args.reuse,
                      'rows': run(args.corpus, scratch, args.reuse)}, indent=2))
