"""FU5: source-count census and real-file disconfirmation; no reference GP.

The printed census was read from the PDF, independently of extraction. Only
counts, indices, reason codes and source-ledger digests are retained in Git.
"""
import hashlib
import copy
import io
import inspect
import json
import zipfile
import tempfile
from pathlib import Path
from fractions import Fraction
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.notation_omr import note_duration
from score2gp.tabraw import TabRaw
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp
from score2gp.pdf_tab_measure_timing import ticks_for_quarters

from test_dur_02_oracle import read_gp_bars
from test_omit_04_fu1_private import LEDGER, ROOT, converted


PRINTED_STRIKES = {1: 2, 2: 2, 3: 2, 4: 4, 5: 2, 6: 2, 7: 2, 8: 4, 9: 0}
STRIKE_EVENTS = {1: [(2, 1), (3, 1)], 2: [(3, 1), (4, 1)],
                 3: [(2, 1), (3, 1)], 4: [(2, 2), (3, 2)],
                 5: [(2, 1), (3, 1)], 6: [(3, 1), (4, 1)],
                 7: [(2, 1), (3, 1)], 8: [(2, 2), (3, 2)], 9: []}
SOURCE_LEDGER = {**LEDGER, 1: (9, '70deda7fa8f2266dcb64bd621cd6e38cbe3074cfb5e2227a606e19a36c1eaf5b')}


def assert_source_ledger(bars):
    for number, (count, digest) in SOURCE_LEDGER.items():
        events = bars[number - 1]['events']
        assert events is not None and len(events) == count, (number, 'event_count')
        actual = []
        for event in events:
            strikes = sorted(6 - string for string in event.get('percussive_strikes', []))
            actual.append(dict(kind=event['kind'], written=event['written'], dots=event['dots'],
                               tuplet=event['tuplet'], tie=list(event['tie']), percussive_strikes=strikes,
                               positions=sorted([[6 - string, None if 6 - string in strikes else fret]
                                                 for string, fret in event['positions']])))
        encoded = json.dumps(actual, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(encoded).hexdigest() == digest, (number, 'source_ledger_mismatch')


def test_all_written_bars_match_fresh_independent_pdf_ledger(converted):
    """Reject wrong note/rest values, dots, tuplets, ties, frets or string groups."""
    assert_source_ledger(converted[1])


@pytest.mark.parametrize('mutant', ['spacing_or_count_rhythm', 'wrong_non_strike_fret', 'drop_strike'])
def test_native_gpif_mutants_fail_independent_source_ledger(converted, mutant):
    """Mutate final relational output, not a mocked recogniser result."""
    _, bars, output = converted
    assert_source_ledger(bars)
    with zipfile.ZipFile(output) as package:
        root = ET.fromstring(package.read('Content/score.gpif'))
    if mutant == 'spacing_or_count_rhythm':
        # Equal slots are the false-success case: every beat gets one value.
        for value in root.findall('Rhythms/Rhythm/NoteValue'):
            value.text = 'Eighth'
    elif mutant == 'wrong_non_strike_fret':
        note = next(n for n in root.findall('Notes/Note') if n.find('DeadNote') is None)
        fret = note.find("Properties/Property[@name='Fret']/Fret")
        fret.text = str(int(fret.text) + 1)
    else:
        note = next(n for n in root.findall('Notes/Note') if n.find('DeadNote') is not None)
        note.remove(note.find('DeadNote'))
        props = note.find('Properties')
        props.remove(props.find("Property[@name='Muted']"))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        package.writestr('Content/score.gpif', ET.tostring(root))
    with pytest.raises(AssertionError, match='source_ledger_mismatch'):
        assert_source_ledger(read_gp_bars(buffer.getvalue()))


def assert_strike_census(route, bars):
    assert [b['output_bar_index'] for b in route['bars'] if b['status'] == 'written'] == [1, 3, 5, 7, 9]
    for number, printed in PRINTED_STRIKES.items():
        entry = route['bars'][number - 1]
        census = entry['percussive_strikes']
        assert census['notation_head_count'] == printed, (number, 'notation_strike_census')
        assert [(r['location']['event_index'], r['head_count']) for r in census['notation_events']] == STRIKE_EVENTS[number]
        assert all(r['location']['bar_index'] == number - 1
                   and len(r['location']['bbox']) == 4
                   and len(r['head_sources']) == r['head_count'] for r in census['notation_events'])
        assert len(census['tab_candidates']) == printed, (number, 'tab_strike_census')
        assert all(c['candidate_id'] and len(c['bbox']) == 4 for c in census['tab_candidates'])
        written = sum(len(e.get('percussive_strikes', [])) for e in bars[number - 1]['events'] or [])
        assert written == (printed if entry['status'] == 'written' else 0), (number, 'native_strike_count')


def test_every_printed_strike_is_written_or_located_in_its_refused_bar(converted):
    """Reject silently dropping strikes in refused bars or losing native mutes."""
    route, bars, _ = converted
    assert_strike_census(route, bars)
    for number in (2, 4, 6, 8):
        mutant = copy.deepcopy(route)
        mutant['bars'][number - 1]['percussive_strikes']['tab_candidates'].pop()
        with pytest.raises(AssertionError, match='tab_strike_census'):
            assert_strike_census(mutant, bars)


def test_refused_disputed_columns_keep_two_heads_against_one_tab_candidate(converted):
    """Reject writing bars 2/6 after bypassing the head-to-string gate."""
    route, bars, _ = converted
    for number, system in ((2, 0), (6, 1)):
        entry = route['bars'][number - 1]
        assert bars[number - 1]['events'] is None
        assert entry['reason'] == 'notehead_digit_count_mismatch'
        assert entry['location']['system_index'] == system
        assert entry['location']['event_index'] == 8
        evidence = entry['refusal_evidence']
        assert (evidence['notation_head_count'], evidence['tab_candidate_count'],
                evidence['distinct_tab_strings'], evidence['dx_spaces']) == (2, 1, 1, 0.0)


@pytest.mark.parametrize('mutant', ['drop_fix', 'restore_old_behavior'])
def test_real_conversion_rejects_lost_slanted_arc_recognition(converted, monkeypatch, mutant):
    """Both old arc bounds and deletion of the contour fix must lose bar 1."""
    assert_source_ledger(converted[1])
    if mutant == 'drop_fix':
        monkeypatch.setattr(note_duration, '_is_slanted_arc', lambda *_: False)
    else:
        monkeypatch.setattr(note_duration, '_slanted_slur_ids', lambda *_: set())
    folder = converted[2].parent / mutant
    output = folder / 'output.gp'
    run = CliRunner().invoke(app, ['convert', '--pdf', str(ROOT / 'fixtures/private/G-Am-C-Lick.pdf'),
        '--pdf-only-tab', '--out', str(output), '--work-dir', str(folder / 'build')])
    assert run.exit_code == 0
    with pytest.raises(AssertionError, match='event_count'):
        assert_source_ledger(read_gp_bars(output))


def test_real_columns_reject_head_to_string_gate_bypass(converted):
    """Execute the removed-check mutant at the measured production seam."""
    folder = converted[2].parent / 'build'
    reading = json.loads((folder / 'note-durations.json').read_text())
    tab = TabRaw.from_json_file(folder / 'tab/tab_raw.json')
    digits = [c for c in tab.candidates if c.kind == 'percussive-strike'
              or c.kind == 'fret' and c.parsed_fret is not None]
    placed, _ = assembler.place_tab_digits(digits, reading)
    source = inspect.getsource(assembler._match_bar)
    check = 'if len(cands) != heads or len({c.string for c in cands}) != len(cands):'
    assert source.count(check) == 1
    namespace = dict(vars(assembler))
    exec(source.replace(check, 'if False:  # named head-to-string bypass mutant'), namespace)
    mutant_score = ScoreIR.from_json_file(folder / 'score.ir.json')
    for number, system in ((2, 0), (6, 1)):
        records = [r for r in reading['events'] if r['bar_index'] == number - 1]
        space = reading['systems'][system]['staff_space']
        def check_refusal(match):
            _, refusal = match(records, placed[number - 1], space, None)
            assert refusal and refusal['reason'] == 'notehead_digit_count_mismatch'
            assert refusal['event_index'] == 8
        check_refusal(assembler._match_bar)
        with pytest.raises(AssertionError):
            check_refusal(namespace['_match_bar'])
        # Carry the unsafe real-source matches through the production writer.
        # No invented input/expected score: these are the actual PDF records
        # with their head-to-string refusal deliberately bypassed.
        matched, refusal = namespace['_match_bar'](records, placed[number - 1], space, None)
        assert refusal is None
        onset = Fraction(0)
        events = []
        for index, item in enumerate(matched):
            events.append(assembler.build_note_type_event(
                item['record'], positions=item['positions'], candidates=item['candidates'],
                output_bar_idx=number, event_idx=index,
                onset_ticks=ticks_for_quarters(onset) if onset else 0,
                track_id=mutant_score.tracks[0].id))
            onset += Fraction(item['record']['duration_quarters'])
        mutant_score.bars[number - 1].events = events
    output = converted[2].parent / 'head-to-string-bypass.gp'
    write_gp(mutant_score, output)
    mutant_bars = read_gp_bars(output)
    with pytest.raises(AssertionError):
        assert all(mutant_bars[number - 1]['events'] is None for number in (2, 6))


def test_slanted_slurs_do_not_broaden_tie_inference(monkeypatch):
    """Reject treating every tapered arc as a tie on another approved source.

    This is byte preservation of base output, not a source-correctness claim.
    The broad-arc mutant changes three previously written bars.
    """
    source = ROOT / 'fixtures/private/Combining_Maj_minor_pent_-_A.pdf'
    assert source.is_file(), 'required approved private source missing'
    original = note_duration._is_arc
    with tempfile.TemporaryDirectory(prefix='omit04fu5-', dir=ROOT / 'work') as directory:
        for mutant in (False, True):
            folder = Path(directory) / str(mutant)
            output = folder / 'output.gp'
            if mutant:
                monkeypatch.setattr(note_duration, '_is_arc',
                                    lambda g, s: original(g, s) or note_duration._is_slanted_arc(g, s))
            result = CliRunner().invoke(app, ['convert', '--pdf', str(source), '--pdf-only-tab',
                '--out', str(output), '--work-dir', str(folder / 'build')])
            assert result.exit_code == 0
            def check_bytes():
                with zipfile.ZipFile(output) as package:
                    assert hashlib.sha256(package.read('Content/score.gpif')).hexdigest() == (
                        'ba40820063273784c77bb572aa264bc8ea03a0e94a394e1b4176a5bacee574db')
            if mutant:
                with pytest.raises(AssertionError):
                    check_bytes()
            else:
                check_bytes()
