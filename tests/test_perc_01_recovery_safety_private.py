"""Real-source disconfirmation for side effects of PERC recovery; hashes only."""
import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner
from score2gp.cli import app
from score2gp import pdf, pdf_grouping_evidence
from score2gp.notation_omr import note_duration
from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
LEDGER = {'Heartbreaker': {1: (14, 'b44dc1a11bbf8943c23ca2d71284a2add6360c825b004cc2aa49b8ca6106bea8'),
                  2: (16, '88f6d692cef9030915d90455c99bf5e8462d19e72745c8dbab4af717c310bf71'),
                  4: (9, '00c929d95dbcfed7d1b949300a77bac19e8dfa81dfba0d13ea7f5c4bcead202b'),
                  6: (7, '640882dc50d5a1b14bcfb3ff0fe0bd37569a77549f032c12330527cafdfdc73e')},
 'Back In Black': {7: (13, 'dd2651581c9ee3e906e0678c419eeb3f8709560b81ed920e4bc0bff7cc06f99b')},
 'Brown Sugar': {1: (4, 'fba59b99e2ac5a9b119749f5fd1eb1a4fe45c5a766759d5da37d52c8768a3a4d'),
                 2: (7, 'f655b787b0ed94165bf15129f9088b867203f3c74f0cdba6833a0399e7c4ba2b')}}


def assert_recovery_ledger(name, output):
    bars = read_gp_bars(output)
    assert {i + 1 for i, b in enumerate(bars) if b['events'] is not None} == set(LEDGER[name]), 'recovery_written_set'
    for number, (count, digest) in LEDGER[name].items():
        events = [dict(kind=e['kind'], written=e['written'], dots=e['dots'], tuplet=e['tuplet'],
                       tie=list(e['tie']), percussive_strikes=[],
                       positions=sorted([[6 - string, fret] for string, fret in e['positions']]))
                  for e in bars[number - 1]['events']]
        assert len(events) == count, 'recovery_event_count'
        actual = hashlib.sha256(json.dumps(events, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert actual == digest, (number, 'recovery_source_ledger')


def convert_source(name, folder):
    output = folder / 'out.gp'
    result = CliRunner().invoke(app, ['convert', '--pdf', str(ROOT / 'fixtures/private' / (name + '.pdf')),
                                   '--pdf-only-tab', '--out', str(output), '--work-dir', str(folder / 'build')])
    assert result.exit_code == 0, result.output
    return output


@pytest.fixture(scope='module')
def recovered(tmp_path_factory):
    return {name: convert_source(name, tmp_path_factory.mktemp('recovery')) for name in LEDGER}


@pytest.mark.parametrize('name', LEDGER)
def test_additional_recovered_bars_match_printed_source(recovered, name):
    """Reject wrong fret/string assignment, kinds, values, dots or ties."""
    assert_recovery_ledger(name, recovered[name])


def test_unclassified_same_position_arc_is_refused_with_its_owners(recovered):
    """Reject silent omission of a printed unsupported tie-shaped contour."""
    output = recovered['Brown Sugar']
    route = json.loads((output.parent / 'build/note-type-route.json').read_text())
    for number in (9, 10):
        bar = route['bars'][number - 1]
        assert bar['status'] == 'refused'
        assert bar['reason'] == 'note_duration_event_unread'
        assert bar['detail'] == 'unclassified_same_position_arc'
        assert bar['location']['bar_index'] == number - 1
    reading = json.loads((output.parent / 'build/note-durations.json').read_text())
    contours = reading['diagnostics']['unclassified_tie_contours']
    assert len(contours) == 1
    assert contours[0]['source'] and len(contours[0]['bbox']) == 4


@pytest.mark.parametrize('mutant', ['ending_bracket_as_string', 'drop_unread_tie_guard'])
def test_real_recovery_sources_reject_safety_mutants(recovered, monkeypatch, tmp_path, mutant):
    """Mutate production recovery/reader and require native source evidence to fail."""
    if mutant == 'ending_bracket_as_string':
        name = 'Heartbreaker'
        monkeypatch.setattr(pdf_grouping_evidence, 'common_ended_line_groups', pdf._tab_line_groups)
    else:
        name = 'Brown Sugar'
        monkeypatch.setattr(note_duration, '_unclassified_tie_contours', lambda *args: [])
    assert_recovery_ledger(name, recovered[name])
    output = convert_source(name, tmp_path)
    with pytest.raises(AssertionError, match='recovery_written_set|recovery_source_ledger'):
        assert_recovery_ledger(name, output)


@pytest.mark.parametrize('name', LEDGER)
def test_additional_ledgers_reject_wrong_native_values(recovered, name):
    """The independent source oracle must reject a wrong non-strike value."""
    with zipfile.ZipFile(recovered[name]) as package:
        root = ET.fromstring(package.read('Content/score.gpif'))
    fret = root.find("Notes/Note/Properties/Property[@name='Fret']/Fret")
    fret.text = str(int(fret.text) + 1)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        package.writestr('Content/score.gpif', ET.tostring(root))
    with pytest.raises(AssertionError, match='recovery_source_ledger'):
        assert_recovery_ledger(name, buffer.getvalue())
