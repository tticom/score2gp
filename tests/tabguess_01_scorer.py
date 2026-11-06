"""TABGUESS-01 scorer: the spacing model for TAB that prints no rhythm, scored where the rhythm is printed.

This is a MEASUREMENT module. It writes no guessed duration into any output, report-as-read or read result:
it reads the build artefacts a normal ``convert --pdf-only-tab`` run already wrote (``note-type-route.json``,
``note-durations.json``, ``tab/tab_raw.json``), hides the printed rhythm of the bars that were read, infers a
rhythm from the horizontal spacing of the TAB columns alone, and compares it with the read rhythm.

Every inferred duration is labelled GUESS (``GUESS_LABEL``); nothing here is imported by ``src``.

The model (fixed on paper in docs/tabguess-01-spacing-model.md before it was scored):

* input per bar: the x of each TAB column (digits within 0.75 staff space are one column, the assembler's rule),
  the meter's capacity in quarters;
* the duration alphabet is whole, dotted half, half, dotted quarter, quarter, dotted eighth, eighth,
  dotted sixteenth and sixteenth (no tuplets, no ties, no rests: those are never inferable from spacing);
* a column's duration is proportional to the distance to the next column; the last column has no printed
  successor (the barline is padded) so it is never taken from spacing;
* the chosen rhythm minimises the squared log-error between each non-last column's gap and ``scale * duration``
  over a data-driven set of scales, subject to the METER-TOTAL CHECK: the durations add up to the capacity
  exactly, which fixes the last column's duration, and that must itself be in the alphabet;
* where no assignment reaches the capacity the model ABSTAINS (no plausible rhythm), which is not a wrong guess.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

GUESS_LABEL = "GUESS"

ALPHABET: tuple[Fraction, ...] = tuple(Fraction(v) for v in (
    "4", "3", "2", "3/2", "1", "3/4", "1/2", "3/8", "1/4"))
COLUMN_SPACES = 0.75  # digits closer than this (in staff spaces) are one column

# Mutation hooks for the tests (the named mutants flip these; production of any output never reads them).
SPACING_RULE = "log_gap"  # "log_gap" (the model) | "uniform" (mutant: ignore spacing, equal columns)
SPACING_EXPONENT = 0.5  # gap = scale * duration ** exponent (engraved spacing is sub-linear in duration)
ENFORCE_METER_TOTAL = True  # False (mutant): last column also taken from its gap, no total check

REGULAR_CV = 0.15
MODERATE_CV = 0.5

# Declared before the first score; never changed after seeing a holdout number.
HOLDOUT = ("Lesson-6", "Lesson-7", "Heartbreaker")


# ----------------------------------------------------------------------------------------------------------
# the model
# ----------------------------------------------------------------------------------------------------------
def _nearest(value: float) -> Fraction:
    return min(ALPHABET, key=lambda d: abs(math.log(float(d)) - math.log(value)))


def infer_rhythm(col_x: list[float], capacity: Fraction) -> list[Fraction] | None:
    """Return the inferred duration per column (all labelled GUESS by the caller), or None to abstain."""
    n = len(col_x)
    if n == 0:
        return None
    if n == 1:
        return [capacity] if capacity in ALPHABET else None
    gaps = [col_x[i + 1] - col_x[i] for i in range(n - 1)]
    if min(gaps) <= 0:
        return None
    if SPACING_RULE == "uniform":
        each = capacity / n
        return [each] * n if each in ALPHABET else None
    if not ENFORCE_METER_TOTAL:
        # mutant: every column, last included, is rounded from one mean scale; no total is checked
        scale = math.exp(sum(math.log(g) for g in gaps) / len(gaps)) / float(capacity / n)
        return [_nearest(g / scale) for g in gaps + [gaps[-1]]]
    logs = [math.log(g) for g in gaps]
    cand_scales = sorted({round(g / float(d) ** SPACING_EXPONENT, 6) for g in gaps for d in ALPHABET})
    best: tuple[float, tuple[Fraction, ...]] | None = None
    for s in cand_scales:
        ls = math.log(s)
        # dp over columns 0..n-2: remaining capacity -> (cost, durations)
        states: dict[Fraction, tuple[float, tuple[Fraction, ...]]] = {capacity: (0.0, ())}
        for i in range(n - 1):
            nxt: dict[Fraction, tuple[float, tuple[Fraction, ...]]] = {}
            for rem, (cost, seq) in states.items():
                for d in ALPHABET:
                    left = rem - d
                    if left <= 0:
                        continue
                    c = cost + (logs[i] - ls - SPACING_EXPONENT * math.log(float(d))) ** 2
                    cur = nxt.get(left)
                    if cur is None or c < cur[0] - 1e-12:
                        nxt[left] = (c, seq + (d,))
            states = nxt
        for rem, (cost, seq) in states.items():
            if rem in ALPHABET and (best is None or cost < best[0] - 1e-12):
                best = (cost, seq + (rem,))
    return list(best[1]) if best else None


def baseline_equal(n: int, capacity: Fraction) -> list[Fraction] | None:
    """Reference point only: n equal columns."""
    if n == 0:
        return None
    each = capacity / n
    return [each] * n if each in ALPHABET else None


def regularity(col_x: list[float]) -> str:
    n = len(col_x)
    if n == 1:
        return "single_column"
    if n == 2:
        return "two_columns"
    gaps = [col_x[i + 1] - col_x[i] for i in range(n - 2)]  # the last gap is barline-padded
    mean = sum(gaps) / len(gaps)
    cv = math.sqrt(sum((g - mean) ** 2 for g in gaps) / len(gaps)) / mean if mean > 0 else 9.9
    return "regular" if cv <= REGULAR_CV else "moderate" if cv <= MODERATE_CV else "irregular"


# ----------------------------------------------------------------------------------------------------------
# artefact reading
# ----------------------------------------------------------------------------------------------------------
@dataclass
class Bar:
    source: str
    bar_index: int
    meter: str
    capacity: Fraction
    space: float
    col_x: list[float]
    truth: list[Fraction] | None  # the read rhythm, one duration per column; None when not comparable
    status: str  # route status
    reason: str | None  # refusal reason, or why the bar is not comparable
    bar_x: tuple[float, float] | None = None
    code: str | None = None


def _columns(xs: list[float], space: float) -> list[float]:
    xs = sorted(xs)
    cols: list[list[float]] = []
    for x in xs:
        if cols and x - cols[-1][-1] < COLUMN_SPACES * space:
            cols[-1].append(x)
        else:
            cols.append([x])
    return [sum(c) / len(c) for c in cols]


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_bars(build: Path, source: str) -> list[Bar]:
    route = _load(build / "note-type-route.json")
    durations = _load(build / "note-durations.json")
    tabraw = _load(build / "tab" / "tab_raw.json")
    cand = {c["id"]: c for c in tabraw["candidates"]}
    fret_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for c in tabraw["candidates"]:
        if c["kind"] == "fret":
            fret_by_page[c["page_index"]].append(c)
    bar_geom: dict[int, tuple[dict[str, Any], tuple[float, float]]] = {}
    for system in durations["systems"]:
        for i, ab in enumerate(system["bars"]):
            bar_geom[system["first_bar_index"] + i] = (system, (ab[0], ab[1]))
    heights = [float(h) for h in durations["source"].get("page_heights") or []]
    checks = {c["bar_index"]: c for c in durations["bar_checks"]}
    ev_by_bar: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for e in durations["events"]:
        ev_by_bar[e["bar_index"]].append(e)
    bars: list[Bar] = []
    for rb in route["bars"]:
        bi = rb["source_bar_index"]
        geom = bar_geom.get(bi)
        check = checks.get(bi)
        if geom is None or check is None:
            continue
        system, (xa, xz) = geom
        space = float(system["staff_space"])
        capacity = Fraction(check["expected_quarters"])
        meter = rb["time_signature"]
        if rb["status"] == "written":
            col_x, truth, why = _written_columns(rb, ev_by_bar.get(bi, []), cand, space, capacity)
            bars.append(Bar(source, bi, meter, capacity, space, col_x, truth, "written", why, (xa, xz)))
            continue
        # refused: columns come from the TAB digits of the bar itself (no rhythm is read for it)
        staff = system.get("tab_staff") or system["staff"]
        page = system["page_index"] + 1
        offset = sum(heights[: page - 1])  # TabRaw candidates stack the pages' y coordinates
        xs = [c["x"] for c in fret_by_page.get(page, [])
              if xa <= c["x"] < xz and staff["top"] - space <= c["y"] - offset <= staff["bottom"] + space]
        bars.append(Bar(source, bi, meter, capacity, space, _columns(xs, space), None, "refused",
                        rb["reason"], (xa, xz), _refusal_code(rb)))
    return bars


def _refusal_code(rb: dict[str, Any]) -> str:
    reason = rb.get("reason") or ""
    detail = rb.get("detail")
    return f"{reason}/{detail}" if detail else reason


def _written_columns(rb: dict[str, Any], events: list[dict[str, Any]], cand: dict[str, Any], space: float,
                     capacity: Fraction) -> tuple[list[float], list[Fraction] | None, str | None]:
    route_events = rb["events"]
    if not route_events:
        return [], None, "no_events"
    if any(e["kind"] not in ("note", "chord") or e["match"]["kind"] != "tab_column" for e in route_events):
        kinds = {e["match"]["kind"] for e in route_events} - {"tab_column"}
        why = "has_" + ("rest" if "rest" in kinds else "tie_continuation" if kinds else "non_column_event")
        return [], None, why
    by_index = {e["event_index"]: e for e in events}
    col_x: list[float] = []
    truth: list[Fraction] = []
    for e in route_events:
        rec = by_index.get(e["event_index"])
        ids = e["match"]["candidate_ids"]
        if rec is None or rec["status"] != "read" or any(i not in cand for i in ids):
            return [], None, "event_not_read"
        if rec.get("tuplet"):
            return [], None, "has_tuplet"
        d = Fraction(rec["duration_quarters"])
        if d <= 0:
            return [], None, "grace_or_zero_duration"
        col_x.append(sum(cand[i]["x"] for i in ids) / len(ids))
        truth.append(d)
    if sum(truth) != capacity:
        return [], None, "read_total_differs_from_meter"
    order = sorted(range(len(col_x)), key=lambda i: col_x[i])
    col_x = [col_x[i] for i in order]
    truth = [truth[i] for i in order]
    if any(col_x[i + 1] - col_x[i] < COLUMN_SPACES * space for i in range(len(col_x) - 1)):
        return [], None, "columns_closer_than_one_column"
    return col_x, truth, None


# ----------------------------------------------------------------------------------------------------------
# scoring
# ----------------------------------------------------------------------------------------------------------
@dataclass
class Score:
    comparable: int = 0
    excluded: Counter = field(default_factory=Counter)
    exact: int = 0
    abstained: int = 0
    wrong: int = 0
    baseline_exact: int = 0
    total_mismatch: int = 0  # inferred bars whose durations do not add to the capacity (must stay 0)
    by_meter: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0]))
    by_regularity: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0]))
    by_columns: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0]))

    def add(self, other: "Score") -> None:
        self.comparable += other.comparable
        self.exact += other.exact
        self.abstained += other.abstained
        self.wrong += other.wrong
        self.baseline_exact += other.baseline_exact
        self.total_mismatch += other.total_mismatch
        self.excluded.update(other.excluded)
        for mine, theirs in ((self.by_meter, other.by_meter), (self.by_regularity, other.by_regularity),
                             (self.by_columns, other.by_columns)):
            for k, v in theirs.items():
                for j in range(3):
                    mine[k][j] += v[j]

    @property
    def share(self) -> float:
        return self.exact / self.comparable if self.comparable else 0.0


def column_bucket(n: int) -> str:
    return str(n) if n <= 4 else "5-8" if n <= 8 else "9+"


def score_bars(bars: list[Bar]) -> Score:
    s = Score()
    for bar in bars:
        if bar.truth is None:
            if bar.status == "written":
                s.excluded[bar.reason or "other"] += 1
            continue
        s.comparable += 1
        guess = infer_rhythm(bar.col_x, bar.capacity)
        cell = [s.by_meter[bar.meter], s.by_regularity[regularity(bar.col_x)], s.by_columns[column_bucket(len(bar.col_x))]]
        for c in cell:
            c[0] += 1  # bars
        if guess is None:
            s.abstained += 1
            continue
        if sum(guess) != bar.capacity:
            s.total_mismatch += 1
        if guess == bar.truth:
            s.exact += 1
            for c in cell:
                c[1] += 1
        else:
            s.wrong += 1
            for c in cell:
                c[2] += 1
        if baseline_equal(len(bar.col_x), bar.capacity) == bar.truth:
            s.baseline_exact += 1
    return s


def spacing_stats(bars: list[Bar]) -> dict[str, Any]:
    """Counts and spacing statistics over bars that have columns (staff-space units; no content)."""
    with_cols = [b for b in bars if b.col_x]
    per_bar = [len(b.col_x) for b in with_cols]
    gaps: list[float] = []
    cvs: list[float] = []
    for b in with_cols:
        g = [(b.col_x[i + 1] - b.col_x[i]) / b.space for i in range(len(b.col_x) - 1)]
        gaps.extend(g)
        if len(g) >= 3:
            inner = g[:-1]
            m = sum(inner) / len(inner)
            cvs.append(math.sqrt(sum((x - m) ** 2 for x in inner) / len(inner)) / m)

    def q(vals: list[float], p: float) -> float | None:
        if not vals:
            return None
        v = sorted(vals)
        return round(v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))], 2)

    return {
        "bars": len(bars), "bars_with_columns": len(with_cols), "bars_without_columns": len(bars) - len(with_cols),
        "columns": sum(per_bar), "columns_per_bar_min": min(per_bar, default=None),
        "columns_per_bar_median": q([float(x) for x in per_bar], 0.5), "columns_per_bar_max": max(per_bar, default=None),
        "gap_spaces_p10": q(gaps, 0.1), "gap_spaces_median": q(gaps, 0.5), "gap_spaces_p90": q(gaps, 0.9),
        "gap_cv_median": q(cvs, 0.5), "gap_cv_p90": q(cvs, 0.9),
    }


def refused_by_code(bars: list[Bar]) -> Counter:
    return Counter(b.code for b in bars if b.status == "refused")
