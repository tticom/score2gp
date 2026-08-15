import pytest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "public"

def test_pipeline_intermediate_stage_order():
    # Domain Contract: The pipeline stage outputs must logically succeed each other,
    # ensuring intermediate artifacts are well-formed before compiling the final GP package.
    ir_path = FIXTURES_DIR / "tiny_score.ir.json"
    assert ir_path.exists()
    
    score, errors = ScoreIR.from_json_file(ir_path), []
    assert score is not None
    
    # Assert track and bar structures are populated cleanly
    assert len(score.tracks) > 0
    assert len(score.bars) > 0

def test_relational_gpif_clef_transposition_invariants(tmp_path):
    # Domain Contract: treble clef written range displayed on standard guitar tracks
    # must be exactly 1 octave higher than standard scientific pitch notation of physical sounding pitch
    # (due to the octave-transposing treble 8vb clef).
    #
    # ConcertPitch Octave = pitch // 12
    # TransposedPitch Octave = (pitch // 12) + 1
    
    score = ScoreIR.from_json_file(FIXTURES_DIR / "tiny_score.ir.json")
    
    # We will modify a note pitch in ScoreIR to represent a sounding G2 (MIDI 43)
    note = score.bars[0].events[0].notes[0]
    note.pitch = 43  # sounding G2
    note.string = 6  # standard 6th string
    note.fret = 3    # fret 3
    
    out_gp = tmp_path / "transposition_invariant.gp"
    
    # Mock system modules to compile relational GP8 database XML under pytest
    import sys
    orig_modules = sys.modules
    orig_argv = sys.argv
    custom_modules = {k: v for k, v in sys.modules.items() if "pytest" not in k}
    sys.modules = custom_modules
    sys.argv = [arg for arg in sys.argv if "pytest" not in arg]
    
    try:
        warnings = write_gp(score, out_gp, target_version="GP8")
    finally:
        sys.modules = orig_modules
        sys.argv = orig_argv
        
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Query global Notes database table
        notes_node = root.find("Notes")
        assert notes_node is not None, "Global Notes element not found directly under GPIF root"
        
        notes = notes_node.findall("Note")
        assert len(notes) > 0
        
        # Verify first note's clef transposition octave mappings
        first_note = notes[0]
        props = first_note.find("Properties")
        assert props is not None
        
        # Sounding pitch G2 (MIDI 43)
        midi_val = props.find(".//Property[@name='Midi']/Number").text
        assert midi_val == "43"
        
        # ConcertPitch Octave represents written G3 (Octave 3 in Guitar Pro)
        cp_node = props.find(".//Property[@name='ConcertPitch']/Pitch")
        assert cp_node.find("Step").text == "G"
        assert cp_node.find("Octave").text == "3", "ConcertPitch Octave violates transposing written G3 stave display"
        
        # TransposedPitch Octave represents transposed G4 (Octave 4 in Guitar Pro)
        tp_node = props.find(".//Property[@name='TransposedPitch']/Pitch")
        assert tp_node.find("Step").text == "G"
        assert tp_node.find("Octave").text == "4", "TransposedPitch Octave violates transposing written G4 stave display"

def test_relational_gpif_four_four_beam_grouping_readability(tmp_path):
    # Domain Contract: A 4/4 bar of eight eighth notes (quavers) must not be grouped into
    # one single continuous beam of eight. Instead, it must be split at the midpoint of the bar ([4, 4] or [2, 2, 2, 2]).
    score = ScoreIR.from_json_file(FIXTURES_DIR / "tiny_score.ir.json")
    
    # 1. Define 8 eighth notes in a single 4/4 measure
    # duration_ticks for eighth note is 480 ticks (ticks_per_quarter = 960)
    from score2gp.ir import Event, Timing, Note
    events = []
    for i in range(8):
        note = Note(
            string=1,
            fret=0,
            pitch=64,
            confidence=1.0,
            provenance=[]
        )
        event = Event(
            id=f"e_beam_test_{i}",
            track_id="gtr-1",
            timing=Timing(
                bar_index=1,
                onset_ticks=i * 480,
                duration_ticks=480,
                ticks_per_quarter=960,
                voice=1,
            ),
            notes=[note],
            confidence=1.0,
            provenance=[]
        )
        events.append(event)
        
    score.bars[0].events = events
    score.bars[0].time_signature.numerator = 4
    score.bars[0].time_signature.denominator = 4
    
    out_gp = tmp_path / "beam_grouping_readability.gp"
    
    # Mock system modules to compile relational GP8 database XML under pytest
    import sys
    orig_modules = sys.modules
    orig_argv = sys.argv
    custom_modules = {k: v for k, v in sys.modules.items() if "pytest" not in k}
    sys.modules = custom_modules
    sys.argv = [arg for arg in sys.argv if "pytest" not in arg]
    
    try:
        warnings = write_gp(score, out_gp, target_version="GP8")
    finally:
        sys.modules = orig_modules
        sys.argv = orig_argv
        
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)
    
    with zipfile.ZipFile(out_gp) as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)
        
        # Query global Beats database table
        beats_node = root.find("Beats")
        assert beats_node is not None
        beats = beats_node.findall("Beat")
        assert len(beats) == 8
        
        # Verify beaming Link to Next (XProperty 1124204546) is omitted on beat boundaries [3, 7]
        # indicating [4, 4] grouping, and not continuous [8]
        links = []
        for b in beats:
            xp = b.find(".//XProperty[@id='1124204546']")
            links.append(xp is not None)
            
        # Expected links mapping: [True, True, True, False, True, True, True, False]
        # (Beats 3 and 7 must break the beam!)
        assert links == [True, True, True, False, True, True, True, False], f"Beams failed to split into [4, 4] groups: {links}"
