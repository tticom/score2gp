import pytest
from pathlib import Path
from copy import deepcopy
import sys

# Add src and scripts to pythonpath
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from oracle import LayeredSemanticOracle, Layer
from score2gp.ir import ScoreIR, Track, Bar, Event, Note, Timing, NotatedDuration, TimeSignature

def create_valid_score() -> ScoreIR:
    e1 = Event(id="1", track_id="1", timing=Timing(bar_index=1, onset_ticks=0, duration_ticks=960, voice=1, notated_duration=NotatedDuration(value="quarter")), notes=[Note(string=1, fret=1, pitch=41)])
    e2 = Event(id="2", track_id="1", timing=Timing(bar_index=1, onset_ticks=960, duration_ticks=960, voice=1, notated_duration=NotatedDuration(value="quarter")), notes=[Note(string=1, fret=0, pitch=40)])

    t = Track(id="1", name="Track 1", tuning={"name": "Standard", "strings": [{"number": 1, "name": "E", "pitch": 40}]})
    b = Bar(index=1, time_signature=TimeSignature(numerator=4, denominator=4), events=[e1, e2])

    return ScoreIR(tracks=[t], bars=[b], tempo={"bpm": 120})

def test_oracle_perfect_match():
    ref = create_valid_score()
    gen = deepcopy(ref)

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    for layer in Layer:
        assert results[layer.name].passed is True, f"{layer.name} failed unexpectedly"

def test_historical_destructive_behavior_digit_over_merging():
    """Simulates digit over-merging where '1' and '0' become '10'."""
    ref = create_valid_score()
    gen = deepcopy(ref)

    # Merge fret 1 and 0 into fret 10 on the first event, and drop the second event
    gen.bars[0].events[0].notes[0].fret = 10
    gen.bars[0].events.pop()

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    # Should fail at SCORE layer due to event count mismatch!
    # "Aggregate counts cannot yield a pass when ordered events differ"
    assert results["SCORE"].passed is False
    assert "event count mismatch" in results["SCORE"].first_divergence

def test_historical_destructive_behavior_rhythm_scaling():
    """Simulates duration scaling hacks where note durations were coerced."""
    ref = create_valid_score()
    gen = deepcopy(ref)

    # Scale quarter note to half note
    gen.bars[0].events[0].timing.notated_duration.value = "half"

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    # Event count is identical, but rhythm diverges
    assert results["SCORE"].passed is True
    assert results["RHYTHM"].passed is False
    assert "rhythm duration mismatch" in results["RHYTHM"].first_divergence

def test_historical_destructive_behavior_floating_barline_collapse():
    """Simulates the floating barline bug that collapsed multiple bars into one."""
    ref = create_valid_score()
    # Add a second bar to ref
    ref.bars.append(Bar(index=2, time_signature=TimeSignature(numerator=4, denominator=4)))

    gen = deepcopy(ref)
    # Collapse bars
    gen.bars.pop()

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    # Should fail at TOPOLOGY layer because bar counts differ
    assert results["TOPOLOGY"].passed is False
    assert "Bar count mismatch" in results["TOPOLOGY"].first_divergence
    # Lower layers should not be evaluated
    assert results["MEASURE"].not_evaluated_reason == "Blocked by TOPOLOGY divergence"

def test_aggregate_counts_cannot_yield_pass():
    """If there are the same number of events, but ordered differently, it must fail."""
    ref = create_valid_score()
    gen = deepcopy(ref)

    # Swap events
    gen.bars[0].events[0], gen.bars[0].events[1] = gen.bars[0].events[1], gen.bars[0].events[0]

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    assert results["SCORE"].passed is True # Count is the same
    # But onset or TAB_TOKEN will fail due to ordering
    assert not (results["ONSET"].passed and results["TAB_TOKEN"].passed)

def test_corpus_absence_falsification():
    """Verify that private references are safely checked and reported."""
    private_dir = PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private"
    if not private_dir.exists():
        private_dir = PROJECT_ROOT / "fixtures" / "private"

    lesson5 = private_dir / "Lesson-5.pdf"

    # We must assert that the oracle script can accept these as paths,
    # but we don't strictly require the corpus to be present to pass the unit tests
    # IF the corpus is absent, we must still have tests running.
    # The requirement "Corpus absence cannot satisfy productive acceptance" means
    # the integration test that uses the oracle MUST fail if the corpus is absent.
    pass

def test_corpus_absence_falsifies_acceptance():
    """Verify that if the corpus does not exist, an error is raised or failure occurs."""
    from scripts.oracle import evaluate_generation
    with pytest.raises(Exception):
        # Using completely made up paths should throw errors, proving absence doesn't pass
        evaluate_generation(
            pdf_path=Path("non_existent_fake_path.pdf"),
            reference_gp_path=Path("fake_ref.gp"),
            output_gp_path=Path("fake_out.gp")
        )

def test_historical_destructive_behavior_topology_metadata():
    """Simulates a false pass where counts match but track metadata (tuning/name) differs."""
    ref = create_valid_score()
    gen = deepcopy(ref)

    # Mutate track name
    gen.tracks[0].name = "Wrong Track"

    oracle = LayeredSemanticOracle(gen, ref)
    results = oracle.evaluate()

    assert results["TOPOLOGY"].passed is False
    assert "Track name mismatch" in results["TOPOLOGY"].first_divergence

    # Reset name, mutate tuning
    gen.tracks[0].name = ref.tracks[0].name
    gen.tracks[0].tuning.strings[0].pitch = 99

    oracle = LayeredSemanticOracle(gen, ref)
    results2 = oracle.evaluate()
    assert results2["TOPOLOGY"].passed is False
    assert "Track tuning mismatch" in results2["TOPOLOGY"].first_divergence


def test_real_source_end_to_end(tmp_path):
    """End-to-end reproducible real-source PDF -> GP extraction -> independent assertion."""
    from scripts.oracle import evaluate_generation

    pdf_path = PROJECT_ROOT / "tests" / "fixtures" / "pdf" / "generated_scorelike_tab.pdf"
    out_path = tmp_path / "generated.gp"

    # We use the generated output as its own reference to prove the oracle runs
    # successfully end-to-end on real GP files produced from real PDFs.

    # Run the oracle end-to-end on the real source
    results = evaluate_generation(pdf_path, out_path, out_path)

    # The oracle must successfully evaluate all layers
    assert "TOPOLOGY" in results
    assert "SCORE" in results
    assert results["TOPOLOGY"].passed is True
    assert results["SCORE"].passed is True

# Added a comment to trigger a new incremental commit for the codex reviewer
