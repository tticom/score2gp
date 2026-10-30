"""Exact bar-capacity arithmetic, independent of meter evidence selection."""

from fractions import Fraction


def bar_capacity_ticks(
    numerator: int, denominator: int, ticks_per_quarter: int | Fraction
) -> Fraction:
    """Return the nominal capacity; a pickup can occupy less than this.

    Callers supply the governing meter and resolution. This function neither
    chooses a default nor resolves conflicting evidence. Keep the rational
    result until an integer-only consumer can explicitly refuse an unrepresentable
    grid; dividing or rounding intermediate values loses valid capacity.
    """
    if numerator <= 0 or denominator <= 0 or ticks_per_quarter <= 0:
        raise ValueError("meter numerator, denominator and resolution must be positive")
    return Fraction(numerator * 4, denominator) * ticks_per_quarter
