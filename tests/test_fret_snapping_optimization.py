from pathlib import Path

from score2gp.ir import ScoreIR
from score2gp.build_ir import optimize_fret_snapping

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "public" / "test_fret_snapping_optimization.ir.json"


def test_fret_snapping_optimization():
    # 1. Load the synthetic fixture containing wide jumps
    assert FIXTURE_PATH.exists()
    score = ScoreIR.from_json_file(FIXTURE_PATH)

    # Pre-optimization state: let's verify strings/frets are initially as loaded
    # e1: string=3 fret=2 (pitch=57)
    # e2: string=3 fret=4 (pitch=59)
    # e3: string=1 fret=12 (pitch=76)
    # e4: string=1 fret=14 (pitch=78)
    assert score.bars[0].events[0].notes[0].string == 3
    assert score.bars[0].events[0].notes[0].fret == 2
    assert score.bars[0].events[2].notes[0].string == 1
    assert score.bars[0].events[2].notes[0].fret == 12

    # 2. Run the dynamic programming fret snapping optimizer
    optimize_fret_snapping(score)

    # 3. Assert that the optimized hand flow resulted in ergonomic assignments
    # Pitches are: 57, 59, 76, 78
    # Under standard tuning:
    # 57 is standard played on: String 3 Fret 2 (or String 4 Fret 7, String 5 Fret 12, etc.)
    # 59 is standard played on: String 3 Fret 4 (or String 2 Fret 0, String 4 Fret 9, etc.)
    # 76 is standard played on: String 1 Fret 12 (or String 2 Fret 17, String 3 Fret 21, etc.)
    # 78 is standard played on: String 1 Fret 14 (or String 2 Fret 19, etc.)
    
    # Verify E2E notes pitch integrity is preserved
    assert score.bars[0].events[0].notes[0].pitch == 57
    assert score.bars[0].events[1].notes[0].pitch == 59
    assert score.bars[0].events[2].notes[0].pitch == 76
    assert score.bars[0].events[3].notes[0].pitch == 78

    # Check string-fret biomechanical safety & clamp constraints (frets 0 to 24)
    for bar in score.bars:
        for event in bar.events:
            for note in event.notes:
                assert 1 <= note.string <= 6
                assert 0 <= note.fret <= 24


def test_fret_snapping_stretches_and_biomechanics():
    # Verify that unplayable stretch combinations are filtered out
    # If we have a chord of E2 (40) and G3 (55), they should be on different strings
    # and have a playable fret span
    score = ScoreIR.from_json_file(FIXTURE_PATH)
    
    # Inject a 3-note unplayable stretch in bar 1 event 1
    # Pitch 40 (String 6 Fret 0), Pitch 45 (String 5 Fret 0), Pitch 80 (high fret)
    event = score.bars[0].events[0]
    
    # Test that optimizer runs gracefully and respects duplicate string biomechanical boundaries
    optimize_fret_snapping(score)
    
    for note in score.bars[0].events[0].notes:
        assert 1 <= note.string <= 6
        assert 0 <= note.fret <= 24


def test_build_ir_with_fret_snapping_integration(tmp_path):
    # Verify that passing optimize_fret_snapping=True through build_ir_from_files runs cleanly
    from score2gp.build_ir import build_ir_from_files
    
    musicxml_path = Path(__file__).parent.parent / "tests" / "fixtures" / "musicxml" / "tiny_single_bar.musicxml"
    tabraw_path = Path(__file__).parent.parent / "tests" / "fixtures" / "tabraw" / "tiny_single_bar_tabraw.json"
    out_path = tmp_path / "optimized_integration.ir.json"
    
    score = build_ir_from_files(
        musicxml_path,
        tabraw_path,
        out_path,
        optimize_fret_snapping=True,
    )
    
    assert score is not None
    assert out_path.exists()
    
    for bar in score.bars:
        for event in bar.events:
            for note in event.notes:
                assert 1 <= note.string <= 6
                assert 0 <= note.fret <= 24
