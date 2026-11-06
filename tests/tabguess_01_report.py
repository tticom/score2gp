"""TABGUESS-01 measurement driver: counts only, no private content.

Usage (after converting every source with ``convert --pdf-only-tab --work-dir <root>/<name>/build``):

    python tests/tabguess_01_report.py <root> measure
    python tests/tabguess_01_report.py <root> design
    python tests/tabguess_01_report.py <root> holdout      # score ONCE; do not tune on it

The report labels every inferred rhythm GUESS and writes no output file other than stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tabguess_01_scorer as T  # noqa: E402


def _sources(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if (p / "build" / "note-type-route.json").is_file())


def measure(root: Path) -> None:
    for name in _sources(root):
        bars = T.load_bars(root / name / "build", name)
        refused = T.refused_by_code(bars)
        no_rhythm = [b for b in bars if b.status == "refused" and (b.code or "").endswith("tab_column_without_rhythm_mark")
                     or b.code == "bar_without_notation_event"]
        if not no_rhythm:
            continue
        print(name, "ALL-BARS", json.dumps(T.spacing_stats(bars)))
        print(name, "NO-RHYTHM-BARS", json.dumps(T.spacing_stats(no_rhythm)))
        print(name, "REFUSED-BY-CODE", json.dumps(dict(refused)))
        cols = {}
        for b in no_rhythm:
            cols[len(b.col_x)] = cols.get(len(b.col_x), 0) + 1
        print(name, "NO-RHYTHM-COLUMNS-PER-BAR histogram", json.dumps(dict(sorted(cols.items()))))


def score(root: Path, which: str) -> None:
    total = T.Score()
    for name in _sources(root):
        if (name in T.HOLDOUT) != (which == "holdout"):
            continue
        s = T.score_bars(T.load_bars(root / name / "build", name))
        total.add(s)
        print(f"{name[:44]:44} comparable={s.comparable:3} exact={s.exact:3} abstained={s.abstained:2} "
              f"wrong={s.wrong:3} equal-division-baseline={s.baseline_exact:3} total_mismatch={s.total_mismatch} "
              f"excluded={dict(s.excluded)}")
    print("TOTAL", total.comparable, total.exact, round(total.share, 3), "abstained", total.abstained,
          "baseline", total.baseline_exact, "total_mismatch", total.total_mismatch, dict(total.excluded))
    for label in ("by_meter", "by_regularity", "by_columns"):
        print(label, {k: (v[0], v[1], round(v[1] / v[0], 3) if v[0] else None) for k, v in sorted(getattr(total, label).items())})


def apply_labelled(root: Path) -> None:
    """The GUESS report for bars whose rhythm is not printed. Counts only; nothing is written as read."""
    from collections import Counter
    for name in _sources(root):
        bars = [b for b in T.load_bars(root / name / "build", name)
                if b.status == "refused" and (b.code or "").endswith("tab_column_without_rhythm_mark")]
        if not bars:
            continue
        outcome, reg, shapes = Counter(), Counter(), Counter()
        for b in bars:
            guess = T.infer_rhythm(b.col_x, b.capacity)
            reg[T.regularity(b.col_x)] += 1
            if guess is None:
                outcome["GUESS_abstained_no_plausible_rhythm"] += 1
                continue
            outcome["GUESS_offered"] += 1
            assert sum(guess) == b.capacity
            shapes["all_equal" if len(set(guess)) == 1 else "mixed_values"] += 1
        print(name, "BARS", len(bars), "NOT-INDEPENDENTLY-VERIFIED (no reference, no printed rhythm)")
        print(name, "REGULARITY", json.dumps(dict(reg)))
        print(name, "OUTCOME", json.dumps(dict(outcome)), json.dumps(dict(shapes)))


if __name__ == "__main__":
    root_arg, mode = Path(sys.argv[1]), sys.argv[2]
    (measure(root_arg) if mode == "measure" else apply_labelled(root_arg) if mode == "apply" else score(root_arg, mode))
