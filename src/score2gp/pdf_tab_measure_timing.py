from __future__ import annotations

from fractions import Fraction

from .ir import DEFAULT_TICKS_PER_QUARTER


class PdfTabBarAssemblerError(Exception):
    """Internal structured exception raised during per-bar assembly.

    Translated into BuildIrInputRiskError at the build_ir.py public boundary.
    """

    def __init__(
        self,
        category: str,
        stage: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        self.category = category
        self.stage = stage
        self.message = message
        self.details = details or {}
        super().__init__(message)


def ticks_for_quarters(quarters: Fraction) -> int:
    """Exact ticks for a duration in quarter notes; a duration the tick grid cannot hold is refused."""
    ticks = Fraction(quarters) * DEFAULT_TICKS_PER_QUARTER
    if ticks.denominator != 1 or ticks <= 0:
        raise PdfTabBarAssemblerError(
            category="pdf_only_tab_duration_off_tick_grid",
            stage="measure-assembly",
            message=f"A duration of {quarters} quarters is not a whole number of ticks at {DEFAULT_TICKS_PER_QUARTER} per quarter.",
            details={"duration_quarters": str(quarters)},
        )
    return int(ticks)
