"""FND-02 validation infrastructure, not recognition/fidelity acceptance.

L3 compilation gate: agentops plans/2026-09-05-lesson3-native-working-slice.md:135.
Mutants: restore each IR sanitizer, restore GPIF string/staff clamps, bypass
target capabilities, or restore the 128th -> Quarter fallback. Real corpus
before/after CLI receipts provide the separate preservation evidence.
"""
from copy import deepcopy
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from score2gp.gpif import build_gpif
from score2gp.gp_package import extract_score_ir_from_gp, write_gp
from score2gp.gpif_builder import GPIFBuilder
from score2gp.errors import HumanReadableConversionError
from score2gp.ir import (BendTechnique, BendPoint, ChordDiagram, ChordFinger,
                        ChordFret, GraceTiming, Note, ScoreIR, ScoreBooklet,
                        TimeSignature, Timing, TrillTechnique, Tuning, TuningString)


@pytest.mark.parametrize('model,base,field,value,code', [
    (model, base, field, value, code)
    for model, base, fields in [
        (TimeSignature, dict(numerator=4, denominator=4),
         [('numerator', 0, 'greater_than'), ('denominator', 0, 'greater_than'),
          ('numerator', 4.6, 'int_from_float'), ('denominator', 3.6, 'int_from_float')]),
        (Timing, dict(bar_index=1, onset_ticks=0, duration_ticks=960, ticks_per_quarter=960, voice=1),
         [('bar_index', 0, 'greater_than_equal'), ('onset_ticks', -1, 'greater_than_equal'),
          ('duration_ticks', -1, 'greater_than_equal'), ('ticks_per_quarter', 0, 'greater_than'),
          ('voice', 0, 'greater_than_equal')]
         + [(f, 1.6, 'int_from_float') for f in
            ('bar_index', 'onset_ticks', 'duration_ticks', 'ticks_per_quarter', 'voice')]),
        (Note, dict(string=1, fret=0, pitch=64),
         [('string', 0, 'greater_than_equal'), ('fret', -3, 'greater_than_equal'),
          ('pitch', -1, 'greater_than_equal'), ('pitch', 140, 'less_than_equal')]
         + [(f, 1.6, 'int_from_float') for f in ('string', 'fret', 'pitch')]),
    ] for field, value, code in fields
])
def test_ir_rejects_without_changing_input(model, base, field, value, code):
    """Kills RESTORE_IR_SANITIZERS, including errors after a hidden mutation."""
    data = {**base, field: value}
    original = deepcopy(data)
    with pytest.raises(ValidationError) as exc:
        model.model_validate(data)
    assert data == original
    assert any(e['loc'] == (field,) and e['type'] == code and e['input'] == value
               for e in exc.value.errors())


@pytest.mark.parametrize('model,data', [
    (TimeSignature, dict(numerator=65, denominator=128)),
    (Timing, dict(bar_index=1, onset_ticks=0, duration_ticks=1, voice=9)),
    (Note, dict(string=13, fret=37, pitch=100)),
])
def test_ir_preserves_values_beyond_target_limits(model, data):
    """Kills moving GPIF upper limits back into IR, or restoring upper clamps."""
    original = deepcopy(data)
    result = model.model_validate(data).model_dump()
    assert data == original
    assert all(result[k] == v for k, v in original.items())


def test_nested_ir_error_has_original_location_and_value():
    """Kills note rounding or flattening the validation location."""
    data = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json').model_dump()
    data['bars'][0]['events'][0]['notes'][0]['fret'] = -3
    original = deepcopy(data)
    with pytest.raises(ValidationError) as exc:
        ScoreIR.model_validate(data)
    assert data == original
    assert any(e['loc'] == ('bars', 0, 'events', 0, 'notes', 0, 'fret')
               and e['type'] == 'greater_than_equal' and e['input'] == -3
               for e in exc.value.errors())


@pytest.mark.parametrize('change,code', [
    ('string', 'gpif_string_out_of_range'),
    ('fret', 'gpif_fret_out_of_range'),
    ('voice', 'gpif_voice_out_of_range'),
    ('meter', 'gpif_meter_out_of_range'),
    ('duration', 'gpif_duration_unsupported'),
])
def test_target_refuses_instead_of_changing_score(change, code, tmp_path):
    """Kills RESTORE_GPIF_CLAMPS and BYPASS_GPIF_CAPABILITIES via public writer."""
    score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
    event = score.bars[0].events[0]
    if change == 'string':
        event.notes[0].string = 7  # old writer silently stored string index zero
    elif change == 'fret':
        event.notes[0].fret = 37
    elif change == 'voice':
        event.timing.voice = 5  # single staff; old writer silently folded into voice 1
    elif change == 'meter':
        score.bars[0].time_signature.numerator = 65
    else:
        event.timing.notated_duration.value = '128th'
    original = score.model_dump()
    with pytest.raises(ValueError) as exc:
        write_gp(score, tmp_path / 'refused.gp')
    message = str(exc.value)
    assert code in message
    assert 'bars[0]' in message
    if change != 'meter':
        assert 'events[0]' in message
    assert score.model_dump() == original
    assert not (tmp_path / 'refused.gp').exists()


def test_valid_ir_outside_target_limits_is_refused_only_by_target():
    """Kills target limits in canonical IR and ignoring target refusal."""
    data = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json').model_dump()
    data['bars'][0]['time_signature']['numerator'] = 65
    score = ScoreIR.model_validate(data)
    assert score.bars[0].time_signature.numerator == 65
    with pytest.raises(ValueError, match='gpif_meter_out_of_range.*bars\\[0\\]'):
        build_gpif(score)


@pytest.mark.parametrize('model,data', [
    (TuningString, dict(number=13, pitch=64, name='extra')),
    (Tuning, dict(name='extended', strings=[dict(number=i, pitch=64, name=str(i)) for i in range(1,14)])),
    (ChordFret, dict(string=13, fret=37)),
    (ChordFinger, dict(string=13, fret=37)),
    (ChordDiagram, dict(name='extended', string_count=13, base_fret=37)),
    (TrillTechnique, dict(fret=37)),
])
def test_related_canonical_positions_are_not_target_limited(model, data):
    """Kills retaining the same target ceiling on tuning/chord/trill fields."""
    model.model_validate(data)


@pytest.mark.parametrize('change,code', [
    ('tuning', 'gpif_tuning_unsupported'),
    ('chord', 'gpif_chord_out_of_range'),
    ('finger', 'gpif_chord_out_of_range'),
    ('trill', 'gpif_fret_out_of_range'),
    ('bend', 'gpif_bend_duration_zero'),
])
def test_legacy_capability_refusals_cover_related_positions(change, code):
    """Kills bypassing capabilities in the explicit legacy writer."""
    score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
    event = score.bars[0].events[0]
    if change == 'tuning':
        score.tracks[0].tuning.strings[0].number = 13
    elif change == 'chord':
        event.chord_diagram = ChordDiagram(name='extended', base_fret=37)
    elif change == 'finger':
        event.chord_diagram = ChordDiagram(name='extended', fingers=[ChordFinger(string=1,fret=37)])
    elif change == 'trill':
        event.notes[0].techniques.append(TrillTechnique(fret=37))
    else:
        event.timing.grace = GraceTiming()
        event.timing.duration_ticks = 0
        event.notes[0].techniques.append(BendTechnique(points=[BendPoint(offset_ticks=0,semitones=1)]))
    original = score.model_dump()
    with pytest.raises(ValueError, match=code + ' at '):
        build_gpif(score, layout='legacy')
    assert score.model_dump() == original


def test_later_booklet_movement_is_checked_before_serialization():
    """Kills checking only the booklet's primary score."""
    score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
    later = score.model_copy(deep=True)
    booklet = ScoreBooklet(scores=[score, later])
    later.bars[0].events[0].notes[0].string = 7
    with pytest.raises(ValueError, match=r'gpif_string_out_of_range at scores\[1\].bars\[0\]'):
        build_gpif(booklet)


@pytest.mark.parametrize('string_index,pitch', [(-1, 40), (6, 64)])
def test_reader_rejects_invalid_string_index_without_repositioning(string_index, pitch, tmp_path):
    """Kills RESTORE_READER_CLAMP via the public GP package reader."""
    score = ScoreIR.from_json_file('fixtures/public/tiny_score.ir.json')
    source = tmp_path / 'original.gp'
    write_gp(score, source)
    with ZipFile(source) as package:
        members = {name: package.read(name) for name in package.namelist()}
    root = ET.fromstring(members['Content/score.gpif'])
    note = root.find('./Notes/Note')
    note.find("./Properties/Property[@name='String']/String").text = str(string_index)
    note.find("./Properties/Property[@name='Fret']/Fret").text = '0'
    note.find("./Properties/Property[@name='Midi']/Number").text = str(pitch)
    # The old boundary string's open pitch would pass semantic validation,
    # so this cannot pass accidentally through a later pitch-mismatch error.
    members['Content/score.gpif'] = ET.tostring(root)
    malformed = tmp_path / 'malformed.gp'
    with ZipFile(malformed, 'w') as package:
        for name, data in members.items():
            package.writestr(name, data)
    original = malformed.read_bytes()
    with pytest.raises(ValueError) as exc:
        extract_score_ir_from_gp(malformed)
    assert 'gpif_string_out_of_range' in str(exc.value)
    assert 'MasterBar[1]' in str(exc.value)
    assert 'Note[0]/String' in str(exc.value)
    assert str(string_index) in str(exc.value)
    assert malformed.read_bytes() == original


@pytest.mark.parametrize('duration', [0, -3])
def test_compiler_rejects_nonpositive_duration_without_inventing_tick(duration):
    """Kills RESTORE_COMPILER_DURATION_CLAMP through the public builder seam."""
    timelines = [dict(page_index=2, staff_index=3, events=[
        dict(onset_ticks=0, duration_ticks=duration, is_rest=True, voice=1)])]
    original = deepcopy(timelines)
    with pytest.raises(HumanReadableConversionError) as exc:
        GPIFBuilder().compile_to_score_ir(timelines, [])
    assert 'scoreir_timing_invalid' in str(exc.value)
    assert 'duration_ticks' in str(exc.value)
    assert exc.value.page == 2
    assert exc.value.measure == 1
    assert exc.value.staff == 3
    assert exc.value.voice == 1
    assert timelines == original
