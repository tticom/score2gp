# Unified compiler title provenance

`ScoreIRCompiler.compile` previously supplied the literal placeholder title for
every successful compilation. Its only production caller is
`GPIFBuilder.compile_to_score_ir`, which forwards timeline and ownership evidence.
The PDF-only CLI uses a separate compiler path; it does not call either entry
point. No title evidence was accepted by the unified compiler before this change.

Both entry points now accept the optional keyword-only `source_pdf`. The compiler
uses the existing page-one PDF metadata reader, without changing its recognition
rules. A readable title is copied without further transformation. An unreadable
or ambiguous title stays empty, with the reader's `pdf_title_*` code and page
location in `ScoreIR.warnings`; the message also identifies
`scoreir_compiler.compile`. Without a source PDF the title stays empty and the
warning code is `scoreir_title_source_missing`, located at the same compiler
route. No filename or reference GP value supplies metadata.

This change leaves timeline validation, ownership, event compilation, and the
existing empty-timeline behavior alone. It makes no claim that an accepted title
proves a musical conversion correct. Invalid timelines continue to be refused
before metadata is read.

## Regression checks

`tests/test_omit_05_fu2_private.py` exercises both entry points and reads the final
packaged `Content/score.gpif`. Its readable-title oracle independently reads the
engraved first PDF line and checks agreement with the approved GP reference.
Empty timelines isolate metadata transport; these tests carry no recognition,
timing, or coverage claim. All private packages use `TemporaryDirectory` under
`work/`. No private title or musical content is recorded here.

The six cases fail with a restored-placeholder mutant. An always-empty mutant
fails both readable-title cases; removing warnings fails the four refusal cases;
dropping the builder's source forwarding fails its readable and unreadable cases.
The mutation runner verifies that both imported compiler modules resolve below
the mutant source directory after the repository's pytest path setup.
A writer-only placeholder mutant also fails all six cases at the packaged-title
assertions, while their in-memory metadata assertions still pass.
## Corpus measurements

Base: `2eaf67965d966e406853a24ca7d43b0c1b5067ea`. The flattened mount has
42 PDFs, 11 GP references and one GPX reference; all 54 inputs match the
sibling fixture checkout. No fixture or reference was modified. All 78
tracked source files in the base snapshot match Git after checkout newline
normalization. The existing reader accepts 34 titles and refuses 8.

Fresh PDF-only CLI conversions with declared `4/4`, without sidecars,
reference inputs, templates or remediation, preserve all 42 exit statuses
and all 21 emitted GPIFs byte for byte (687 bars). The first remaining
CLI refusal is source 1, `pdf_only_tab_no_notation_bars`; this change does
not improve recognition or relax refusals.
Bar counts are GPIF MasterBar records, including any existing empty/refused bars.

The two compiler entry points were measured against identical genuine
recognition evidence (`run_recognition_on_file`, `assume_treble_clef=True`).
Each wrote 24 packages and refused 18 inputs, before and after. All 24
written packages changed only `Score/Title`; removing that one element
makes the complete GPIF bytes identical, including every bar. Nineteen
accepted inputs have empty timeline previews and retain the existing
one-bar fallback; five have nonempty previews. These outputs are route
preservation evidence, not a new musical-fidelity claim.

Without a PDF all 24 written titles become empty with
`scoreir_title_source_missing`. With the corresponding PDF, 17 retain
source title bytes and seven stay empty with `pdf_title_unreadable`.
All warnings locate `scoreir_compiler.compile`; PDF refusals retain page 1.
Both entry points produce identical GPIFs and diagnostic codes in every
case. No event, bar or other GPIF field changed.

The table uses sorted private PDF indices. Title sizes are UTF-8 byte
counts, never title content. `F` means compilation refused before metadata
was emitted. The final column is base / head without PDF / head with PDF;
it applies equally to both compiler entry points. CLI title sizes are
unchanged at head; `-` means no CLI package was written.

| Source | Reader title bytes | CLI exit | CLI title bytes | Compiler title bytes |
|---:|---:|---:|---:|---|
| 1 | 28 | 2 | - | 14 / 0 / 28 |
| 2 | 34 | 2 | - | 14 / 0 / 34 |
| 3 | 0 | 4 | - | 14 / 0 / 0 |
| 4 | 0 | 2 | - | 14 / 0 / 0 |
| 5 | 12 | 0 | 12 | 14 / 0 / 12 |
| 6 | 25 | 0 | 25 | 14 / 0 / 25 |
| 7 | 15 | 0 | 15 | 14 / 0 / 15 |
| 8 | 13 | 4 | - | F |
| 9 | 16 | 0 | 16 | F |
| 10 | 9 | 4 | - | 14 / 0 / 9 |
| 11 | 11 | 4 | - | 14 / 0 / 11 |
| 12 | 22 | 0 | 22 | F |
| 13 | 20 | 4 | - | F |
| 14 | 34 | 2 | - | 14 / 0 / 34 |
| 15 | 10 | 4 | - | 14 / 0 / 10 |
| 16 | 0 | 2 | - | F |
| 17 | 31 | 0 | 31 | 14 / 0 / 31 |
| 18 | 8 | 0 | 8 | F |
| 19 | 0 | 2 | - | 14 / 0 / 0 |
| 20 | 24 | 0 | 24 | 14 / 0 / 24 |
| 21 | 6 | 0 | 6 | F |
| 22 | 0 | 4 | - | 14 / 0 / 0 |
| 23 | 12 | 4 | - | 14 / 0 / 12 |
| 24 | 7 | 4 | - | 14 / 0 / 7 |
| 25 | 0 | 4 | - | 14 / 0 / 0 |
| 26 | 33 | 0 | 33 | F |
| 27 | 0 | 4 | - | 14 / 0 / 0 |
| 28 | 21 | 0 | 21 | F |
| 29 | 21 | 0 | 21 | F |
| 30 | 33 | 0 | 33 | F |
| 31 | 32 | 0 | 32 | F |
| 32 | 13 | 0 | 13 | F |
| 33 | 0 | 4 | - | 14 / 0 / 0 |
| 34 | 19 | 0 | 19 | 14 / 0 / 19 |
| 35 | 19 | 1 | - | F |
| 36 | 19 | 0 | 19 | F |
| 37 | 25 | 0 | 25 | 14 / 0 / 25 |
| 38 | 8 | 4 | - | 14 / 0 / 8 |
| 39 | 13 | 4 | - | F |
| 40 | 18 | 0 | 18 | 14 / 0 / 18 |
| 41 | 47 | 0 | 47 | F |
| 42 | 53 | 0 | 53 | F |

The existing `tests/gpif_layout_corpus_probe.py` reproduces CLI GPIF
hash measurements at each revision, using `--source-root` for an isolated
source snapshot and `--time-signature 4/4` for the declared mode.

The default-time-signature mode was also measured on all 42 PDFs. All 42 exit
statuses and all 23 emitted GPIFs are byte-identical (711 MasterBar records).
Together the modes preserve 84 status pairs and 44 emitted GPIF pairs; these
are mode-specific outputs, not a count of distinct sources or correct bars.
Final compiler and CLI replay receipts create packages only inside
`TemporaryDirectory` under `work/`; the tracked corpus probe supplies the CLI
measurement function. Private title text and generated packages are not tracked.
