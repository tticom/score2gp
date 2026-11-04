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
                  # REFUSE-02 pin (multi-note slur): rhythm checked against the printed notation.
                  3: (15, 'e3d5fd31f34c59f0fe2934808cdba7225f6d234009471f5e059d5970bc93ab35'),
                  4: (9, '00c929d95dbcfed7d1b949300a77bac19e8dfa81dfba0d13ea7f5c4bcead202b'),
                  # REFUSE-05 pin (dotted half painted as a stroked point): rhythm checked against the
                  # printed notation page; strings/frets are a regression pin. Not independently verified.
                  5: (3, '94d288f78f970008bf5095c26edd3060f218f7fbff5f7a2c2d5f62994d318dd0'),
                  6: (7, '640882dc50d5a1b14bcfb3ff0fe0bd37569a77549f032c12330527cafdfdc73e'),
                  # REFUSE-10 pins (long tie crescents read as ties: half note to whole note over a barline).
                  # Rhythm and ties checked against the printed notation page; strings/frets are a regression
                  # pin. No reference GP exists: not independently verified.
                  7: (5, 'ddb318b210d6cd551ec078f8a766ea09c88899079d89f7a9b4ac977a60b24895'),
                  8: (1, '2d398cb644865f066f19a245236570de917389a3e46506a3b1bd5714eda749e7')},
 'Back In Black': {1: (11, '33935bb5b04df01f9fa3d9eb7ec92790aea54acdd642af6270b101cbc0a43341'),
                   3: (12, '822c984d144bd21c18b80b248a46ce526e00b285ac5c65d66c8f5a803ce1e3b1'),
                   # REFUSE-10 pins (vibrato line; stem-side slur over three heads): checked against the
                   # printed page and bar totals; strings/frets are a regression pin. Not independently verified.
                   2: (15, '39da5756c418ca678685f239d8e09a14495bd1456bfdc3dbe930817c287220f8'),
                   4: (21, 'c29824c60debbd42d7c3405a6c74717e9be26e6ff050bbed47d665218fbda158'),
                   # REFUSE-11 pin (first note tied over the system break; the TAB prints an empty "( )"):
                   # rhythm and tie checked against the printed page and bar total; strings/frets are
                   # inherited from the previous system's tied note, a regression pin. Not independently verified.
                   5: (13, '7b3c1158fac3b83132b09e850df994a77f7f36e742ea3ba9c14d84bee4f4f16f'),
                   6: (14, '317fb90d5e1f5077a3314049d7ca5fecf452b4da9f1f8919b57011ef53d765b8'),  # REFUSE-01B pins
                   7: (13, 'dd2651581c9ee3e906e0678c419eeb3f8709560b81ed920e4bc0bff7cc06f99b')},
 'Brown Sugar': {# REFUSE-10 pins (vibrato lines; long tie crescent across a barline to a whole note, whose
                 # TAB prints no digit): checked against the printed page and bar totals; strings/frets are
                 # a regression pin. No reference GP exists: not independently verified.
                 3: (8, '0b312f726ead567d1136078691dc08fa7a857f68766451627f1586d30cbabbcf'),
                 4: (7, '7d7cf1b7be4e285e74eeb68f3aba7d294f0d0c85e8d911addfa9f320783b18ae'),
                 # REFUSE-11 pin (first note tied over the system break; the TAB prints an empty "( )"):
                 # checked against the printed page and bar total; strings/frets are inherited from the
                 # previous system's tied note, a regression pin. Not independently verified.
                 5: (11, '939d0b13e3906476ec953a9f2acfcf70ea712ee3ada6333678dd57249381e90d'),
                 9: (12, 'd24b8169f083858384bddbfc061d1f6b36370f71add2ea588908a352f67b20ac'),
                 10: (1, '9aa7d608152d4a72af17d844adea4c3a875a249fc4099716be44659a5ba738bf'),
                 6: (16, '05aa46b1d415fdff96fc92c7f6022bffef20a9afb7f3e8cb263a58c6106fd044'),  # REFUSE-01B pin
                 1: (4, 'fba59b99e2ac5a9b119749f5fd1eb1a4fe45c5a766759d5da37d52c8768a3a4d'),
                 2: (7, 'f655b787b0ed94165bf15129f9088b867203f3c74f0cdba6833a0399e7c4ba2b'),
                 # REFUSE-08 pin (sixteenth rest read as 16th, not eighth): bar total 4/4 checked, rest value
                 # checked against the printed page; strings/frets are a regression pin. Not independently verified.
                 7: (18, '6210d095ba11ae14f0c8b1f1f2b7f645aa840c160f5660a1d4bcbb818620d153')}}


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


def test_long_tie_crescent_is_read_as_a_tie_with_its_owners(recovered):
    """REFUSE-10 supersedes the earlier refusal: reject a tall tie crescent left refused, or its tie lost."""
    output = recovered['Brown Sugar']
    route = json.loads((output.parent / 'build/note-type-route.json').read_text())
    for number in (9, 10):
        bar = route['bars'][number - 1]
        assert bar['status'] == 'written', number
    reading = json.loads((output.parent / 'build/note-durations.json').read_text())
    assert not reading['diagnostics'].get('unclassified_tie_contours')
    bars = read_gp_bars(output)
    assert bars[8]['events'][-1]['tie'][0] and bars[9]['events'][0]['tie'][1]


@pytest.mark.parametrize('mutant', ['ending_bracket_as_string', 'drop_crescent_ties'])
def test_real_recovery_sources_reject_safety_mutants(recovered, monkeypatch, tmp_path, mutant):
    """Mutate production recovery/reader and require native source evidence to fail."""
    if mutant == 'ending_bracket_as_string':
        name = 'Heartbreaker'
        monkeypatch.setattr(pdf_grouping_evidence, 'common_ended_line_groups', pdf._tab_line_groups)
    else:
        name = 'Brown Sugar'
        monkeypatch.setattr(note_duration, '_shallow_crescent_ties', lambda *args: [])
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
