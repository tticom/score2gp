"""Real-PDF event ledgers, strike census and located refusals.

Only counts, indices, digests and reason codes are tracked. Independent private
transcriptions and generated artifacts remain ignored. Neither PDF has a GP
reference; the source-ledger hashes come from its printed notation and TAB.
"""
from pathlib import Path
import hashlib
import copy
import io
import inspect
import zipfile
from xml.etree import ElementTree as ET
import json

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import font_glyphs, note_duration
from score2gp import pdf, pdf_tab_bar_assembler as assembler
from score2gp.tabraw import TabRaw
from test_dur_02_oracle import read_gp_bars


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Castles Made of Sand": ([2, 2, 1, 2, 2, 3], {1: 2, 3: 3, 8: 3}),
    "Crossroads": ([4, 4, 3, 3, 3, 2, 2, 2, 3, 4, 2, 2, 2, 2],
                   {1: 3, 3: 3, 8: 2, 14: 2, 15: 2, 16: 2, 19: 6, 25: 8, 26: 3, 33: 2}),
}


def assert_census(reading, name):
    counts, strikes = SOURCES[name]
    assert [s["bar_count"] for s in reading["systems"]] == counts, "printed_bar_census"
    for bar in range(sum(counts)):
        actual = sum(h["kind"] == "cross" for r in reading["events"]
                     if r["bar_index"] == bar
                     for h in (r.get("notehead") or {}).get("heads", []))
        assert actual == strikes.get(bar + 1, 0), (bar + 1, "printed_strike_census")


@pytest.fixture(scope="module", params=SOURCES)
def census(request):
    name = request.param
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved PERC-01 source missing"
    return name, source, note_duration.read_note_durations(source)


def test_printed_bar_boundaries_and_all_cross_heads(census):
    """Reject lost legacy font outlines and straight-cross/stem ownership.

    The five source pages were inspected independently. Bar counts are per
    system in page order; omitted strike-count entries mean zero printed Xs.
    """
    name, _, reading = census
    assert_census(reading, name)


@pytest.mark.parametrize("mutant", ["drop_legacy_outlines", "drop_straight_crosses", "cross_stems_as_barlines"])
def test_real_source_census_rejects_recognition_mutants(census, monkeypatch, mutant):
    """Run the reader with each lost-evidence mutant on both approved PDFs."""
    name, source, reading = census
    assert_census(reading, name)
    if mutant == "drop_legacy_outlines":
        monkeypatch.setattr(font_glyphs, "LEGACY_MUSIC_FONT_FAMILIES", frozenset())
    elif mutant == "drop_straight_crosses":
        original = note_duration._is_dead_note_x_head
        monkeypatch.setattr(note_duration, "_is_dead_note_x_head",
                            lambda g, s: g.curved and original(g, s))
    else:
        original = note_duration.extract_page_symbols

        def without_straight_head_contact(*args, **kwargs):
            result = original(*args, **kwargs)
            result.head_shapes = [g.shape for g in result.glyphs if g.curved]
            return result

        monkeypatch.setattr(note_duration, "extract_page_symbols", without_straight_head_contact)
    with pytest.raises(AssertionError, match="printed_(bar|strike)_census"):
        assert_census(note_duration.read_note_durations(source), name)


# Independently transcribed from the printed notation and TAB. The private
# event ledger stays under ignored work/; only counts and digests are tracked.
LEDGER = {'Castles Made of Sand': {6: (16,
                              '943bf00cbf4aa2ead525b28b64471add69e94402e95ca19426995322b2873005'),
                          8: (13,
                              'f7b87c5e9bd10c538aa1691f693c8c0f2ce10bd5a454959f8ecef4de607979a9'),
                          10: (13,
                               '830ff267e7d7a5b30bb410f256fa42ab163d3e458c9625c7465e81e5e0a0d017'),
                          11: (7,
                               'f9dabb2318897c6f0ab6379d6f14b5436120cba3236ecfcde8f2f9a45fd6dcd5'),
                          12: (1,
                               'bbabb968b5dd1dd1b6906df6eb09b4be2f8c80a2b477bcba11d4e880282d686d')},
 'Crossroads': {3: (6, '3f7e44f06938d9b40b6c46975b47dfa3cccce99ca3702e5d965e75e12b6afea5'),
                # REFUSE-01B bars (natural signs): rhythm checked against the printed
                # notation; strings/frets are a regression pin, not an independent transcription.
                5: (12, '2ad74b0b23bef495cfabfac7e56ee70bccdd46cb94f6b2fccec52286d0dbd469'),
                9: (10, '998b2d5678921e055e2b8c63840c16bb6fa1d51b1f8af8f4be3f64c28056e1a4'),
                13: (11, '3e89a95544557898ac02d0ca1c0ef0444225cd1b6da5608601792703d54a8e6d'),
                18: (13, 'fddc955c4f9fb50722d6d588078a14cb971ea2e8e32b1ae1a11e536f72359f6d'),
                31: (14, '787894d0189d74f857139246ca8596efb6fc9f93146fbd9a7adb5021fa829879'),
                35: (14, '45fdf87a86d546ca20bea0eb7069591da8b343ec4228666a12ba3202d7468c39'),
                12: (10, '94b67832ba65be9c5008f65768bf49d60f7ea738b622a5c74c37f82cb6fc6706'),
                21: (13, 'a96e0c4d5ab7bf704227583df81567dc4f796631e3105c93b69ab1c87276877f'),
                23: (14, 'ba7604f63bd42f94ef678754d77dc93e5d8d077e1828a407cb1d9b67a29481dc'),
                28: (5, 'e9c5081b9def05d52b0851f36f1e41b6f0388807b5473ce7ad2c680549514665'),
                33: (9, '6da9ccb6e9a2259e0a190384cdebe4e0ff0fbd4b10ab819018d2c66f8138a89a'),
                34: (13, '0435d011aa8723a7b2b01382000a71a1803996b5e564862933549a3f5057765c')}}

STORAGE = {('Castles Made of Sand', 8): '7cb51280b9f8ce17671235a4e14a4c9d8ada64cdcade26897cd2b919806446d0',
 ('Crossroads', 1): '76d9674abe162b5396215b1aafce3692c3f2e7fc7a092f734b0cc5189d8bb965',
 ('Crossroads', 3): '76d9674abe162b5396215b1aafce3692c3f2e7fc7a092f734b0cc5189d8bb965',
 ('Crossroads', 33): '2b8056269f5fa44ed1ea4d098824e072daf030c8e359b22552fdd051891b0283'}


def assert_written_ledger(name, bars):
    written = {i + 1 for i, b in enumerate(bars) if b['events'] is not None}
    assert written == set(LEDGER[name]), 'written_bar_set'
    for number, (count, expected) in LEDGER[name].items():
        actual = []
        for e in bars[number - 1]['events']:
            strikes = sorted(6 - string for string in e.get('percussive_strikes', []))
            actual.append(dict(kind=e['kind'], written=e['written'], dots=e['dots'],
                               tuplet=e['tuplet'], tie=list(e['tie']),
                               positions=sorted([[6 - string, None if 6 - string in strikes else fret]
                                                 for string, fret in e['positions']]),
                               percussive_strikes=strikes))
        assert len(actual) == count, (number, 'source_event_count')
        digest = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest == expected, (number, 'source_ledger_mismatch')


@pytest.fixture(scope='module')
def converted(census, tmp_path_factory):
    name, source, _ = census
    folder = tmp_path_factory.mktemp('perc01')
    output = folder / 'out.gp'
    result = CliRunner().invoke(app, ['convert', '--pdf', str(source), '--pdf-only-tab',
                                   '--out', str(output), '--work-dir', str(folder / 'build')])
    assert result.exit_code == 0, result.output
    route = json.loads((folder / 'build/note-type-route.json').read_text())
    return name, source, output, folder, route


def test_every_written_bar_matches_independent_printed_source(converted):
    """Reject wrong kinds, note values, dots, tuplets, ties, frets and strikes."""
    name, _, output, _, _ = converted
    assert_written_ledger(name, read_gp_bars(output))


def test_all_strikes_are_written_dead_or_located_in_refused_bar(converted):
    """Reject silent strike loss, duplicate vector paint and unsafe writes."""
    name, _, output, _, route = converted
    bars = read_gp_bars(output)
    assert_no_unprinted_strike_ties(output)
    counts, strikes = SOURCES[name]
    assert len(route['bars']) == sum(counts)
    for number, entry in enumerate(route['bars'], start=1):
        expected = strikes.get(number, 0)
        evidence = entry['percussive_strikes']
        assert evidence['notation_head_count'] == expected, (number, 'notation_strike_census')
        assert len(evidence['tab_candidates']) == expected, (number, 'tab_strike_census')
        assert sum(e['head_count'] for e in evidence['notation_events']) == expected
        assert all(e['location']['bar_index'] == number - 1 and len(e['location']['bbox']) == 4
                   and len(e['head_sources']) == e['head_count'] for e in evidence['notation_events'])
        written = bars[number - 1]['events']
        if entry['status'] == 'written':
            assert sum(len(e.get('percussive_strikes', [])) for e in written) == expected
            # UNREAD-02: these printed treble-head positions resolve directly;
            # verify stored dead frets separately from the sounding-event ledger.
            stored = sorted((6 - string, fret) for e in written for string, fret in e['positions']
                            if string in e.get('percussive_strikes', []))
            if stored:
                digest = hashlib.sha256(json.dumps(stored, separators=(',', ':')).encode()).hexdigest()
                assert digest == STORAGE[(name, number)], (number, 'stored_strike_position')
        else:
            assert written is None, (number, 'unsafe_written_bar')
            assert entry['reason']
            assert entry['location']['bar_index'] == number - 1
            assert all(k in entry['location'] for k in ['system_index', 'page_index'])


@pytest.mark.parametrize('mutant', ['guess_spacing_or_counts', 'wrong_non_strike_value', 'drop_strike'])
def test_native_ledger_rejects_named_output_mutants(converted, mutant):
    """Change actual real-file GPIF, then require the source oracle to reject it."""
    name, _, output, _, _ = converted
    assert_written_ledger(name, read_gp_bars(output))
    with zipfile.ZipFile(output) as package:
        root = ET.fromstring(package.read('Content/score.gpif'))
    if mutant == 'guess_spacing_or_counts':
        for rhythm in root.findall('Rhythms/Rhythm/NoteValue'):
            rhythm.text = 'Eighth'
    elif mutant == 'wrong_non_strike_value':
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
        assert_written_ledger(name, read_gp_bars(buffer.getvalue()))


@pytest.mark.parametrize('mutant', ['drop_geometry_fix', 'restore_old_strike_behavior'])
def test_normal_route_rejects_named_recognition_mutants(converted, monkeypatch, tmp_path, mutant):
    """Real-source normal CLI output fails its ledger when recovery is removed."""
    name, source, output, _, _ = converted
    assert_written_ledger(name, read_gp_bars(output))
    if mutant == 'drop_geometry_fix':
        source_code = inspect.getsource(pdf._detect_tab_systems).replace(
            'if (not _recover_paint and callable', 'if (False and callable')
        namespace = dict(vars(pdf))
        exec(source_code, namespace)
        monkeypatch.setattr(pdf, '_detect_tab_systems', namespace['_detect_tab_systems'])
    else:
        from score2gp import pdf_tab_strikes
        monkeypatch.setattr(pdf_tab_strikes, 'drawn_tab_crosses', lambda *args: [])
    mutant_output = tmp_path / 'mutant.gp'
    run = CliRunner().invoke(app, ['convert', '--pdf', str(source), '--pdf-only-tab',
                                 '--out', str(mutant_output), '--work-dir', str(tmp_path / 'build')])
    if not mutant_output.exists():
        assert run.exit_code != 0
    else:
        with pytest.raises(AssertionError, match='written_bar_set|source_ledger_mismatch'):
            assert_written_ledger(name, read_gp_bars(mutant_output))


def test_real_column_disagreement_requires_head_to_string_gate(converted):
    """Reject bypass of the head/string count check after one real digit is lost.

    The negative input removes a genuine source candidate; it invents no music.
    Disabling the production count check must make this test fail.
    """
    _, _, _, folder, route = converted
    reading = json.loads((folder / 'build/note-durations.json').read_text())
    tabraw = TabRaw.from_json_file(folder / 'build/tab/tab_raw.json')
    digits = [c for c in tabraw.candidates if c.kind in {'fret', 'percussive-strike'}]
    placed, _ = assembler.place_tab_digits(digits, reading)
    written = {b['source_bar_index'] for b in route['bars'] if b['status'] == 'written'}
    # A real multi-head event supplies the negative case. Remove one owning
    # column member and leave every printed duration/head record untouched.
    record = next(r for r in reading['events'] if r['bar_index'] in written
                  and r['kind'] in {'note', 'chord'} and r['notehead']['count'] > 1)
    number = record['bar_index']
    records = [r for r in reading['events'] if r['bar_index'] == number]
    system = next(s for s in reading['systems']
                  if s['first_bar_index'] <= number < s['first_bar_index'] + s['bar_count'])
    cx = sum(record['location']['bbox'][::2]) / 2
    victim = min((c for c in placed[number] if c.kind == 'fret'), key=lambda c: abs(c.x - cx))
    damaged = [c for c in placed[number] if c.id != victim.id]
    _, refusal = assembler._match_bar(records, damaged, system['staff_space'], None)
    assert refusal is not None and refusal['reason'] == 'notehead_digit_count_mismatch', 'head_to_string_gate'


def assert_no_unprinted_strike_ties(output):
    # These source strikes have no printed tie arcs. Event-level any(ties)
    # would miss a tie incorrectly copied from a pitched head in a mixed chord.
    with zipfile.ZipFile(output) as package:
        root = ET.fromstring(package.read('Content/score.gpif'))
    assert all(note.find('Tie') is None for note in root.findall('Notes/Note')
               if note.find('DeadNote') is not None), 'unprinted_strike_tie'


def test_mixed_tie_refusal_rejects_copying_a_pitched_tie_to_strikes(tmp_path, monkeypatch):
    """Reject the actual real-file event-level tie propagation defect."""
    source = ROOT / 'fixtures/private/Crossroads.pdf'
    normal = tmp_path / 'normal'
    output = normal / 'out.gp'
    result = CliRunner().invoke(app, ['convert', '--pdf', str(source), '--pdf-only-tab',
                                   '--out', str(output), '--work-dir', str(normal / 'build')])
    assert result.exit_code == 0
    route = json.loads((normal / 'build/note-type-route.json').read_text())
    first = route['bars'][0]
    assert first['status'] == 'refused'
    assert first['reason'] == 'mixed_percussive_tie_ownership_unread'
    assert first['location'] == dict(page_index=0, system_index=0, bar_index=0, event_index=3)
    assert_no_unprinted_strike_ties(output)
    source_code = inspect.getsource(assembler._match_bar)
    old = 'if cross_count and cross_count < heads and ('
    assert old in source_code
    scope = dict(vars(assembler))
    exec(source_code.replace(old, 'if False and cross_count and cross_count < heads and ('), scope)
    monkeypatch.setattr(assembler, '_match_bar', scope['_match_bar'])
    mutant = tmp_path / 'mutant'
    bad = mutant / 'out.gp'
    result = CliRunner().invoke(app, ['convert', '--pdf', str(source), '--pdf-only-tab',
                                   '--out', str(bad), '--work-dir', str(mutant / 'build')])
    assert result.exit_code == 0
    with pytest.raises(AssertionError, match='unprinted_strike_tie'):
        assert_no_unprinted_strike_ties(bad)


def assert_located_refusals(located, name):
    counts, strikes = SOURCES[name]
    assert len(located) == sum(counts), "located_bar_count"
    assert [r["location"]["bar_index"] for r in located] == list(range(sum(counts)))
    for index, refusal in enumerate(located):
        assert refusal["reason"] == "unsafe_tab_layout_not_independently_partitionable"
        assert len(refusal["location"]["bbox"]) == 4
        assert refusal["blocking_layout_warnings"]
        assert refusal["notation_strike_count"] == strikes.get(index + 1, 0), "refused_strike_census"
        assert sum(s["head_count"] for s in refusal["notation_strikes"]) == strikes.get(index + 1, 0)
        assert all(s["location"]["bar_index"] == index and len(s["head_sources"]) == s["head_count"]
                   for s in refusal["notation_strikes"])


def assert_local_observations(located, reading):
    """Diagnostic completeness only; not an independent musical-value oracle."""
    for refusal in located:
        bar = refusal["location"]["bar_index"]
        expected = [{"code": event["reason"], "location": event["location"]}
                    for event in reading["events"]
                    if event["bar_index"] == bar and event["status"] != "read"]
        assert refusal.get("unread_notation_events") == expected, "unread_bar_evidence"
        assert refusal.get("refusal_scope") == "source_layout", "inherited_refusal_scope"
        assert refusal.get("strike_candidate_count_matches") == (
            refusal["notation_strike_count"] == refusal["tab_strike_candidate_count"]
        ), "strike_candidate_disagreement"


def test_normal_cli_refuses_all_printed_bars_with_strike_locations(census, tmp_path, monkeypatch):
    """Reject the old whole-file-only refusal and silently omitted X heads.

    This asserts continued refusal, not correct written musical events. No GP
    may be emitted while the layout is unsafe.
    """
    name, source, reading = census
    # Preserve the existing located-refusal regression on the real unsafe
    # geometry path. Normal recovery now has its separate positive ledger.
    source_code = inspect.getsource(pdf._detect_tab_systems).replace(
        'if (not _recover_paint and callable', 'if (False and callable')
    scope = dict(vars(pdf))
    exec(source_code, scope)
    monkeypatch.setattr(pdf, '_detect_tab_systems', scope['_detect_tab_systems'])
    output = tmp_path / "out.gp"
    folder = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                   "--out", str(output), "--work-dir", str(folder)])
    assert result.exit_code == 4
    assert not output.exists()
    diagnostic = json.loads((folder / "diagnostics.json").read_text())
    assert diagnostic["category"] == "pdf_only_tab_grouping_unsafe"
    located = diagnostic["details"]["located_bar_refusals"]
    assert_located_refusals(located, name)
    assert_local_observations(located, reading)
    # Named diagnostic mutants: restore the old record (drop this change),
    # attribute a source refusal to the local bar, and hide a strike mismatch.
    for field, value, message in [
        ("unread_notation_events", None, "unread_bar_evidence"),
        ("refusal_scope", "local_bar", "inherited_refusal_scope"),
        ("strike_candidate_count_matches", True, "strike_candidate_disagreement"),
    ]:
        mutant = copy.deepcopy(located)
        first = next(r for r in mutant if r["notation_strike_count"])
        first[field] = not first[field] if field == "strike_candidate_count_matches" else value
        with pytest.raises(AssertionError, match=message):
            assert_local_observations(mutant, reading)
    # Named output mutants: erase the old missing ledger, or drop one strike.
    with pytest.raises(AssertionError, match="located_bar_count"):
        assert_located_refusals([], name)
    mutant = copy.deepcopy(located)
    first = next(r for r in mutant if r["notation_strike_count"])
    first["notation_strike_count"] -= 1
    with pytest.raises(AssertionError, match="refused_strike_census"):
        assert_located_refusals(mutant, name)
