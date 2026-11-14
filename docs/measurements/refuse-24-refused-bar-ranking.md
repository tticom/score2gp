# REFUSE-24: refused-bar ranking after REFUSE-23 (measurement; task blocked, no reader change)

Baseline `8c74ab0` (main after REFUSE-23). Normal CLI (`convert --pdf <approved-pdf> --pdf-only-tab`) over all 43 approved PDFs in `fixtures/private/`, Windows runtime. Counts, codes and indices only; page/system/bar/event indices are zero-based. No source file, gate or test was changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed.

## Before (and after: nothing changed)

- Bars written: 1441. Bars refused: 210. Whole-source refusals without a route record: 4 PDFs (exit 4), 1 PDF with exit 2 and no bars (unchanged, "unfinished" sources, not correct refusals).

| Refused bars by code | n |
|---|---:|
| `note_duration_event_unread` | 123 |
| `notation_note_without_tab_digit` | 50 |
| `bar_without_notation_event` | 11 |
| `notehead_digit_count_mismatch` | 11 |
| `bar_total_mismatch` | 6 |
| `tie_head_ownership_unconfirmed`, `tab_system_digit_unassigned_to_bar`, `tab_digit_without_notation_event` | 2 each |
| `tab_chord_arrow_unread`, `notation_tab_column_ambiguous`, `duration_off_tick_grid` | 1 each |

## Located causes, ranked by bar count (all are unfinished; none is a correct refusal)

| bars | code / cause | sources | gap kind |
|---:|---|---:|---|
| 73 | `note_duration_event_unread` / `tab_column_without_rhythm_mark` | 2 | reader gap; the page prints no rhythm, only a spacing guess could settle it (excluded by the no-guess rule; REFUSE-23 already left it) |
| 42 | `notation_note_without_tab_digit` / `no_tab_column_at_notation_event` | 4 (37 in one) | reader gap; every bar withholds TAB digits for a printed technique (bend, hammer/pull, vibrato chord, ...), see REFUSE-13/15 |
| 15 | `note_duration_event_unread` / `unsupported_overlapping_form` | 5 | reader + representation gap; glyphs are slides ("sl." arcs), grace/ghost curves, accidental forms, tuplet arcs |
| 8 | `notation_note_without_tab_digit` / `tie_stop_without_written_predecessor` | 3 | reader gap that cascades from refused predecessor bars (bend/technique bars) |
| 8 | `note_duration_event_unread` / `symbol_unclassified` | 5 (the 4 non-Melodic_Expressions bars are bend arrows) | reader gap (bends) |
| 8 | `note_duration_event_unread` / `rest_glyph_unidentified` | 1 | reader gap |
| 6 | `bar_without_notation_event` / `bar_without_notation_or_tab_item` | 3 | reader gap (repeat signs, a clef-and-key-only stub) |
| 11 | `notehead_digit_count_mismatch` | 4 | reader gap (hammer/pull clusters; REFUSE-15 stopped) |
| 6 | `bar_total_mismatch` | 3 | reader gap |
| rest | 1 to 4 each (`concurrent_events`, `filled_notehead_without_stem`, `mixed_notehead_kinds`, tuplet and fermata forms, ...) | | unknown |

Classes earlier REFUSE tasks addressed are reduced or excluded: ghost heads and detached parentheses (REFUSE-14, -23), empty bars (REFUSE-17, -22), tied chords/carry-over ties (REFUSE-11, -12), accidentals and curved forms (REFUSE-16), chord ghost (REFUSE-18), TAB digits at refused bars (REFUSE-19/NOTAB-01). Bend (REFUSE-13) and hammer/pull (REFUSE-15) stopped without a rule.

## Why no class could be read

The largest class the page could settle without a guess has no safe single rule, and the classes that are single rules have no positive holdout:

- **Bend arrows (`symbol_unclassified`, 4 sources, one bar each).** The existing reader (`bends.py`) reads only a single labelled up-bend on one sounding head and requires the bar's bend labels to equal the read bends. Each of the four bars fails a different gate, found by instrumenting the reader: one bar also holds a release (down arrow with its own label), the others have more than one sounding head, a bend that ends beside or past the next note, or a grace head. Reading any of them means extending bends to releases, chords or grace heads, a new representation for which no reference exists and which each source would only partly validate. No design source/holdout pair shares one gate.
- **Hammer/pull clusters, slides, overlapping forms.** Same finding as REFUSE-15: each bar also carries unread slide, ghost or tuplet curves; the shared digit-count gap cannot be fixed without inferring which head owns a missing digit.
- **`rest_glyph_unidentified` (8 bars) and `bar_without_notation_or_tab_item` (6 bars).** The first is one source only. The second is a two-bar repeat sign, an end-repeat bar, a start-repeat dot pair in a TAB-rhythm system and a clef-and-key stub, each in a different source or form; each needs a repeat or stub representation. None has a second source whose bar the same rule would write.

Acceptance criterion 2 requires a positive separate-source holdout, which does not exist for any class the page settles. The task is therefore reported **blocked, not complete**; the gate is not waived. All 210 refused bars stay refused with their located reasons, and no test was added (a test needs a rule to reject a mutant; none exists).
