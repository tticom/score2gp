"""Pure meter arithmetic only; these synthetic cases prove no PDF fidelity.

Mutants: force 4/4, assume 960 TPQ, divide before multiplying, round a
fractional result, cache a preceding meter, or require a pickup to fill a bar.
"""
from fractions import Fraction

import pytest

from score2gp.meter import bar_capacity_ticks
from score2gp.notation_omr.timeline import TopologicallyLockedBarTimeline


@pytest.mark.parametrize(('numerator', 'denominator', 'tpq', 'expected'), [
    pytest.param(4, 4, 960, Fraction(3840), id='common-time'),
    pytest.param(12, 8, 960, Fraction(5760), id='compound-time'),
    pytest.param(2, 2, 960, Fraction(3840), id='cut-time'),
    pytest.param(6, 8, 960, Fraction(2880), id='six-eight'),
    pytest.param(3, 4, 960, Fraction(2880), id='three-four'),
    pytest.param(3, 8, 2, Fraction(3), id='exact-low-resolution'),
    pytest.param(1, 8, 1, Fraction(1, 2), id='fractional-capacity'),
    pytest.param(1, 3, 1, Fraction(4, 3), id='non-binary-fraction'),
    pytest.param(3, 4, Fraction(1, 3), Fraction(1), id='rational-resolution'),
])
def test_meter_capacity_is_exact(numerator, denominator, tpq, expected):
    """Reject forced meter/TPQ, premature integer division and rounding."""
    result = bar_capacity_ticks(numerator, denominator, tpq)
    assert isinstance(result, Fraction)
    assert result == expected


def test_pickup_and_changing_meter_capacity():
    """Reject cached/forced meter; short played length does not redefine meter."""
    capacities = [bar_capacity_ticks(n, d, 960) for n, d in [(3, 4), (12, 8), (2, 2), (3, 4)]]
    assert capacities == [2880, 5760, 3840, 2880]
    # A one-quarter pickup fits within its printed 3/4 bar capacity.
    assert 960 < capacities[0]
    assert TopologicallyLockedBarTimeline(
        measure_index=1, capacity_ticks=capacities[0], voice_1_final_tick=960
    ).validate_capacity()


@pytest.mark.parametrize(('numerator', 'denominator', 'tpq'), [(0, 4, 960), (4, 0, 960), (4, 4, 0)])
def test_meter_rejects_nonpositive_basis(numerator, denominator, tpq):
    """Reject zero-capacity defaults and division by zero instead of validation."""
    with pytest.raises(ValueError, match='positive'):
        bar_capacity_ticks(numerator, denominator, tpq)


def test_integer_rest_consumer_uses_capacity_or_refuses():
    """Reject a fixed fallback rest and silent flooring at an integer consumer."""
    from score2gp.errors import HumanReadableConversionError
    from score2gp.scoreir_compiler import ScoreIRCompiler

    for meter, expected in [((3, 4), 2880), ((12, 8), 5760), ((2, 2), 3840)]:
        score = ScoreIRCompiler().compile([], [], time_signature=meter)
        assert score.bars[0].events[0].timing.duration_ticks == expected
    with pytest.raises(HumanReadableConversionError, match=r'Measure 1.*non_integral_bar_capacity: 15/32'):
        ScoreIRCompiler().compile([], [], time_signature=(1, 8192))
