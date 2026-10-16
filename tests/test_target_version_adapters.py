"""OUT-01 containment. Public IR tests cover selection plumbing, not fidelity.

Real-source output is audited in a fresh interpreter: the legacy serializer
selects different XML under pytest, so in-process writer tests cannot prove it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.batch import run_batch_pipeline, run_single_payload
from score2gp.gp_package import write_gp
from score2gp.ir import validate_score_ir_file
from score2gp.version_adapter import adapt_gpif, get_version_file_content

ROOT = Path(__file__).resolve().parents[1]
IR = ROOT / 'fixtures/public/tiny_score.ir.json'


@pytest.mark.parametrize('target', ['GP6', 'gp6', 'GP8', 'gp8', 'unknown', '', 'GP5'])
def test_unsupported_target_refuses_at_every_writer_boundary(target, tmp_path):
    # Mutant: silently turn unknown targets into GP7, or permit GP6/GP8.
    score, errors = validate_score_ir_file(IR)
    assert not errors
    out = tmp_path / 'uncreated' / 'output.gp'
    for action in [
        lambda: write_gp(score, out, target_version=target),
        lambda: adapt_gpif(b'<GPIF/>', target),
        lambda: get_version_file_content(target),
    ]:
        with pytest.raises(ValueError) as exc:
            action()
        assert repr(target) in str(exc.value)
        assert 'target_version' in str(exc.value)
        assert 'GP7' in str(exc.value)
        assert not out.parent.exists()


@pytest.mark.parametrize('target', ['GP6', 'GP8', 'unknown', ''])
@pytest.mark.parametrize('command', ['write-gp', 'convert'])
def test_cli_refuses_target_before_input_processing(target, command, tmp_path):
    # Mutant: remove the CLI gate; a missing input must not mask selection.
    out = tmp_path / 'uncreated' / 'output.gp'
    args = ['write-gp', str(IR), '--out', str(out)] if command == 'write-gp' else [
        'convert', '--pdf', str(tmp_path / 'absent.pdf'), '--out', str(out),
        '--work-dir', str(tmp_path / 'uncreated')]
    result = CliRunner().invoke(app, args + ['--target', target])
    assert result.exit_code != 0
    assert '--target' in result.output
    assert target in result.output
    assert 'unsupported' in result.output.lower()
    assert not out.parent.exists()


def test_batch_manifest_refuses_fabricated_targets(tmp_path):
    # Mutant: restore the previous three-success manifest behavior.
    result = run_batch_pipeline(ROOT / 'fixtures/public/test_version_adapters_manifest.json', tmp_path)
    assert result['total_payloads'] == 3
    assert result['success_count'] == 1
    assert result['failure_count'] == 2
    rows = {row['id']: row for row in result['results']}
    for target in ['GP6', 'GP8']:
        row = rows['payload_' + target.lower()]
        assert row['status'] == 'failed'
        assert target in row['error'] and 'target_version' in row['error']
        assert not Path(row['output_path']).exists()
    with ZipFile(rows['payload_gp7']['output_path']) as package:
        assert package.read('VERSION').strip() == b'7.0'
        assert ET.fromstring(package.read('Content/score.gpif')).attrib['version'] == '7'


@pytest.mark.parametrize('target', ['GP6', 'GP8', 'unknown'])
def test_batch_refuses_unknown_target_before_cache_or_build(target, tmp_path):
    # Mutant: validate only in write_gp, allowing a stale cached artifact through.
    class ForbiddenCache:
        def get_cached_artifact(self, *args):
            pytest.fail('unsupported target reached cache')
    row = run_single_payload({
        'id': 'unsupported', 'target_version': target,
        'musicxml': str(ROOT / 'tests/fixtures/musicxml/tiny_single_bar.musicxml'),
        'tabraw': str(ROOT / 'tests/fixtures/tabraw/tiny_single_bar_tabraw.json'),
    }, tmp_path, ForbiddenCache())
    assert row['status'] == 'failed'
    assert target in row['error'] and 'target_version' in row['error']
    assert not Path(row['output_path']).exists()


def test_invalid_gpif_is_refused_instead_of_passed_through():
    # Mutant: restore the adapter's invalid-XML pass-through.
    with pytest.raises(ET.ParseError):
        adapt_gpif(b'not xml', 'GP7')


@pytest.mark.parametrize('name', ['Lesson-6.pdf', 'Melodic_Expressions_Chap_19_.pdf'])
def test_written_gpif_has_only_real_reference_tags_and_stamps(name):
    # Mutant: inject StyleCollections (or any absent adapter tag), or fabricate a stamp.
    private = ROOT / 'fixtures/private'
    required = ['Ex 2 Hands Up.gp', 'Lesson-3.gp', 'Lesson-4.gp', 'Lesson-5.gp',
                'Lesson-6.gp', 'Lesson-7.gp', "Can't Find My Way Home (open chord shenanigans).gp", name]
    assert all((private / entry).is_file() for entry in required), 'required private corpus absent'
    tags = set()
    stamps = set()
    readable = 0
    for reference in private.glob('*.gp'):
        with ZipFile(reference) as package:
            data = package.read('Content/score.gpif')
            # One approved package has an encrypted GPIF; it supplies no XML
            # evidence. Every XML reference must parse, rather than being skipped.
            if not data.startswith(b'<?xml'):
                assert reference.name == 'Mixing Lead & Rhythm pt1.gp'
                continue
            root = ET.fromstring(data)
            tags.update(node.tag for node in root.iter())
            rev = root.find('GPRevision')
            stamps.add((root.findtext('GPVersion'), rev.text, tuple(sorted(rev.attrib.items())),
                        package.read('VERSION').strip()))
            readable += 1
    assert readable >= 10
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='out01-audit-', dir=work) as directory:
        scratch = Path(directory)
        # Observe the base writer's bytes before adaptation, in the production
        # interpreter. Base-writer tags (OMIT-02-FU1) are outside OUT-01; they
        # must not be removed to make an adapter audit pass.
        probe = '''
import runpy, sys
from pathlib import Path
import score2gp.gp_package as package
original = package.adapt_gpif
directory = Path(sys.argv[1])
calls = []
def capture(data, target):
    (directory / ('writer-' + str(len(calls)) + '.xml')).write_bytes(data)
    calls.append(target)
    return original(data, target)
package.adapt_gpif = capture
sys.argv = ['score2gp', *sys.argv[2:]]
runpy.run_module('score2gp.cli', run_name='__main__')
'''
        result = subprocess.run([
            sys.executable, '-c', probe, str(scratch), 'convert', '--pdf', str(private / name),
            '--pdf-only-tab', '--time-signature', '4/4', '--out', str(scratch / 'out.gp'),
            '--work-dir', str(scratch / 'build'), '--json-report', str(scratch / 'report.json'),
        ], env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr[-1000:]
        assert json.loads((scratch / 'report.json').read_text())['output_written']
        writer_xml = (scratch / 'writer-0.xml').read_bytes()
        writer_tags = {node.tag for node in ET.fromstring(writer_xml).iter()}
        with ZipFile(scratch / 'out.gp') as package:
            output_xml = package.read('Content/score.gpif')
            root = ET.fromstring(output_xml)
            assert ({node.tag for node in root.iter()} - writer_tags) <= tags
            rev = root.find('GPRevision')
            assert (root.findtext('GPVersion'), rev.text, tuple(sorted(rev.attrib.items())),
                    package.read('VERSION').strip()) in stamps
        # Exercise every remaining adapter selection path with the real writer
        # input. A case alias must neither invent tags nor change the output.
        for target in ['GP7', 'gp7']:
            adapted = adapt_gpif(writer_xml, target)
            assert ({node.tag for node in ET.fromstring(adapted).iter()} - writer_tags) <= tags
            assert adapted == output_xml
