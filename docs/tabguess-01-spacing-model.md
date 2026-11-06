# TABGUESS-01: the spacing model for TAB that prints no rhythm, designed and scored

Measured with the normal CLI (`convert --pdf-only-tab`) over every approved PDF in `fixtures/private/` (43 `*.pdf`), `main` at 04e77d5, 2026-11-06. Counts, codes and labels only; no private content. **Nothing in this task writes, reports as read or counts as read a guessed duration.** `src` is untouched (every source's output stays byte-identical because no source file changed); the scorer lives in `tests/tabguess_01_scorer.py` and the driver in `tests/tabguess_01_report.py`. Every duration the model produces is labelled **GUESS**.

## 1. Measurement: what prints no rhythm

The briefed counts re-measure as follows on the current runtime.

| bars | code | what it is |
|---|---|---|
| 53 | `note_duration_event_unread` / `tab_column_without_rhythm_mark` | all in `7_Grateful_Dead_Melodies`: TAB with fret digits and no stem, beam, flag, dot, circle, bracket or notation staff |
| 22 | `bar_without_notation_event` | `7_Grateful_Dead_Melodies`: **0 TAB columns** (no digit in the bar) |
| 4 | `bar_without_notation_event` | `Gloria`: 0 TAB columns |
| 2 | `bar_without_notation_event` | `The_EXACT_System_Pros...`: 0 TAB columns |
| 1 | `bar_without_notation_event` | `Ex 2 Hands Up`: 0 TAB columns |

So the 29 `bar_without_notation_...` bars (22 + 4 + 2 + 1) are **not** TAB that prints no rhythm: they print no TAB column at all, so a spacing model has nothing to read and they are out of this model's reach (they stay refused; whatever is on those bars is a separate reader/detection question, not a rhythm guess). Only the 53 bars carry columns.

`5_Grateful_Dead_Intros` is refused by the CLI before any bar exists (`percussive_strike_without_owning_note`, exit 1), so the scorer cannot place its bars; from TabRaw alone it has 76 fret candidates in 8 grouped bars of 4, 6 or 8 columns (4 bars of 8, 2 of 6, 2 of 4) and 6 percussive-strike candidates. Its rhythm status is unmeasured and it is not scored or guessed.

### The 53 bars of `7_Grateful_Dead_Melodies` (columns = digits within 0.75 staff space)

* 202 fret digits, all single-digit columns (one string per column): 202 columns, none a chord.
* Columns per bar: 1 column × 7 bars, 2 × 4, 3 × 13, 4 × 15, 5 × 6, 6 × 4, 8 × 2, 9 × 2 (min 1, median 4, max 9).
* Meter: 52 bars 4/4, 1 bar 2/4.
* Spacing (staff-space units, 10.23 pt per space): column-to-column gap p10 2.07, median 2.57, p90 3.90; coefficient of variation of the interior gaps median 0.0, p90 0.0 (every bar with 4 or more columns prints perfectly even gaps).
* Regularity class (defined in section 3): 42 regular, 4 two-column, 7 single-column; none moderate or irregular.

The 22 empty bars of the same source have 0 columns. The other 7 bars that were written are printed whole rests.

## 2. The model, fixed on paper before it was scored

**Input per bar:** the x of each TAB column (digits within 0.75 staff space merge: the assembler's own rule) and the meter's capacity in quarters (from the printed or declared meter, as the reader already derives it). Nothing else; no rhythm mark, no pitch.

**What it infers from spacing.** Engraving software gives a column room in proportion to a sub-linear function of its duration, not to the duration itself (a quarter is not twice as wide as an eighth). The model: `gap(i) = scale * duration(i) ** 0.5`, where `gap(i)` is the distance from column *i* to column *i+1*. The exponent 0.5 was chosen on the design sources only, from {1.0, 0.75, 0.6, 0.5, 0.4} (exact share 0.746, 0.749, 0.821, 0.855, 0.804), and then fixed. The alphabet is whole, dotted half, half, dotted quarter, quarter, dotted eighth, eighth, dotted sixteenth and sixteenth. Tuplets, ties, rests, graces and mixed-meter bars are never inferred (spacing cannot show them), so such bars are excluded from scoring rather than guessed.

**The last column.** It has no printed successor (the barline is padded), so its duration is never taken from spacing.

**How it reaches a bar total equal to the meter (the meter-total check).** The chosen assignment minimises the squared log-error between each non-last column's gap and `scale * duration ** 0.5` over a data-driven set of scales, *subject to the durations adding up to the capacity exactly*. That constraint fixes the last column's duration, which must itself be in the alphabet. If no assignment reaches the capacity the model **abstains** (no plausible rhythm) and the bar stays refused. A guess whose durations do not add up to the meter is never produced.

**Reading order.** This is strategy 4 of `tab-rhythm-reading-strategy.md`: it applies only to a bar where strategies 1 to 3 produce nothing. It never overrides a printed mark and never makes a bar that otherwise disagrees pass.

**Label format.** Every inferred duration, in the report and in any output, carries the label `GUESS` (constant `GUESS_LABEL`), is reported apart from read results, is never counted as a read result, and the bar is labelled `NOT INDEPENDENTLY VERIFIED` (no reference, no printed rhythm). In a Guitar Pro file a guess would be marked `GUESS` on its bar and its notes' text; **this task writes none** (test `test_no_rhythm_source_keeps_every_refusal_and_writes_no_guess` pins that all 75 refused bars stay refused and that `GUESS` appears in no output).

## 3. Scoring

**Method.** For every bar the reader wrote, with the model hidden from the printed rhythm: take only the columns' x and the meter, infer a rhythm, and compare it with the read rhythm column by column. A bar is **comparable** only if every event is a TAB column with a read, positive, non-tuplet duration totalling the meter; bars with rests, tie continuations, tuplets, graces or a read total that differs from the meter are excluded and counted. Truth is the reader's own output (strategies 1 and 2). **Verified by reference** means the corpus holds a `.gp` for the source (Bebop Licks in Am, Can't Find My Way Home, Derek Trucks BB King, Ex 2 Hands Up, Lesson-3 to 7, Melodic Soloing Masterclass, Mixing Lead & Rhythm pt1); the other sources are **not independently verified**: their truth is the reader's output.

**Regularity of the printed spacing** (per bar): single column; two columns (one gap, no regularity); otherwise the coefficient of variation of the interior gaps (the barline-padded last gap is left out): **regular** ≤ 0.15, **moderate** ≤ 0.5, **irregular** > 0.5.

**Split.** The holdout set was declared in the scorer before any score was produced and was scored once, with the model as fixed above: `Lesson-6`, `Lesson-7`, `Heartbreaker` (two verified by reference, one not). Every other source is the design set. (The exponent sweep above used the design set only.)

### Design set (every source with a route record except the three held out; tuned on)

| | bars comparable | exact | share | equal-division baseline |
|---|---|---|---|---|
| **Total** | 414 | 354 | **0.855** | 294 (0.710) |
| 5 abstained, 55 wrong. Excluded: 224 bars with a rest, 57 tuplet, 25 tie continuation, 18 grace/zero duration, 9 with no events. Inferred bars whose total differs from the meter: **0**. | | | | |

By meter: 4/4 404 bars 350 exact (0.866); 3/4 4 bars 4 (1.0); 12/8 6 bars 0 (0.0).
By regularity: single column 37 / 36 (0.973); two columns 6 / 0 (0.0); regular 291 / 278 (0.955); moderate 80 / 40 (0.50).
By column count: 1: 36/37; 2: 0/6; 3: 1/2; 4: 27/28; 5–8: 252/269 (0.937); 9+: 38/72 (0.528).

Per design source (comparable, exact): 12 Bar Blues Solo Guitar Jam 61/61 (TAB-only route, no reference: not independently verified); 5 MUST KNOW Pentatonic Licks 15/15 (no reference); Mixing Lead & Rhythm pt1 34/34 (reference); Finger postition tips TAB 17/17 (no reference); Lesson-4 72/75 and Lesson-3 59/65 and Lesson-5 17/18 (reference); Can't Find My Way Home 11/12 (reference); Ex 2 Hands Up 6/6 (reference); Melodic Soloing Masterclass 6/8 (reference); Bebop Licks in Am 10/10 (reference); E_Chord_Lick_Chord 5/5; A_blues_lick_5_positions 5/5; A7-Blues-Lick 2/2; G-Am-C-Lick 4/5; Melodic_Expressions_Chap_19_ 11/14; The_EXACT_System_Pros 8/12; This_039_Boring... 7/8; Brown Sugar 2/3; Gloria 1/1; Back In Black 0/4 (1 abstained); Black Dog 0/2 (2 abstained); Hey Joe 0/5 (1 abstained); Castles Made of Sand 1/7; Crossroads 0/14; Pride and Joy 0/6 (1 abstained). Eight sources have no comparable bar (all their written bars carry a rest, tuplet, tie or grace). (All the above are the design run; the model scored well wherever printed spacing is even and poorly where an engraver spaced for notation, e.g. Crossroads.)

### Holdout set (3 sources, scored once, not tuned on)

| source | comparable | exact | equal-division baseline |
|---|---|---|---|
| Lesson-6 (reference) | 23 | 23 | 23 |
| Lesson-7 (reference) | 50 | 25 | 0 |
| Heartbreaker (no reference: not independently verified) | 6 | 1 | 1 |
| **Total** | 79 | **49 (0.620)** | 24 (0.304) |

All 79 are 4/4 (no other meter is held out). By regularity: single column 1/1; two columns 0/7; regular 22/42 (0.524); moderate 26/29 (0.897). By column count: 1: 1/1; 2: 0/7; 3: 0/1; 4: 22/23; 5–8: 0/13; 9+: 26/34. Excluded: 45 tuplet bars, 5 tie continuation. Abstained 0; total mismatch 0.

The wrong holdout bars are all bars whose true durations are mixed while the printed gaps look even or the bar has two columns (a long held last note or one long first note): even spacing does not show a held last note, and two columns are two durations that must sum to the meter with a single gap to read. 0 of the 7 two-column holdout bars were right.

## 4. What accuracy would make a guess worth offering (recommendation for the maintainer, not a promotion)

* The held-out result is **0.620**, against 0.855 on the design sources: the model fitted the design set and did not generalise at the level it scored there. At 0.62 a labelled guess is wrong for roughly 4 bars in 10, and a wrong guess writes wrong music into a GP file that the user must find by ear.
* **Recommended bar for offering a labelled guess:** at least 0.90 exact on held-out bars **of the class that would be offered**, over at least 100 held-out comparable bars of that class and from at least three held-out sources of which at least two have a reference `.gp`, with zero inferred bars whose total differs from the meter. The class to offer is the narrowest that clears it. By this measurement no class is promotable yet: four-column regular bars look good (design 27/28, holdout 22/23) but that is 51 bars, and the holdout shows the 5–8 column bars (the bulk of the real material) at 0/13 while the design set shows them at 0.937, so the class result does not transfer.
* **For the target no-rhythm source in particular:** its 53 bars are 42 regular and 11 one- or two-column bars. The model's accuracy on one- and two-column bars is 36/37 and 0/6 on design, and 1/1 and 0/7 on holdout: a **two-column bar must not be offered**; a single-column bar is only "the note fills the bar" and is not a spacing inference. The 42 regular bars are the only ones the spacing model speaks to, and their measured held-out accuracy is 0.524, below the bar.
* **Verdict:** at the measured accuracy a labelled guess is **not yet worth offering**. The only evidence that could change this is more held-out sources whose printed rhythm is read, and a model that can use evidence this one does not (a held final note is invisible to spacing). Nothing here promotes TABGUESS-01 or TABONLY-01.

## 5. Hand-off notes

* Synthetic tests carry no acceptance weight; none are used. The tests in `tests/test_tabguess_01_private.py` run on approved private sources (12 Bar Blues Solo Guitar Jam, Mixing Lead & Rhythm pt1 as design; Lesson-6, Lesson-7, Heartbreaker as holdout; 7_Grateful_Dead_Melodies as the no-rhythm source) and are a measurement; they fail, not skip, when the corpus is absent.
* Named mutants, both shown failing on a real source: **UNIFORM_SPACING** (`SPACING_RULE = "uniform"`) scores 73 of 95 instead of 95 on the design sources; **DROP_METER_TOTAL** (`ENFORCE_METER_TOTAL = False`) produces 22 inferred bars whose durations do not add up to the meter.
* Reference-less sources (12 Bar Blues, 5 MUST KNOW, Finger postition tips, Heartbreaker and the other no-`.gp` sources) are labelled **not independently verified**; the 53 bars of the target source have neither a printed rhythm nor a reference.
* Reproduce: convert every PDF with `convert --pdf-only-tab --work-dir <root>/<name>/build`, then `python tests/tabguess_01_report.py <root> measure|design|holdout|apply`. The `holdout` mode must not be used to tune.
