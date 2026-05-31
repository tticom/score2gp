# PDF Score Extraction

## Purpose

This document defines the domain risks and expected behaviour when extracting guitar score information from PDFs.

A PDF is a rendered document, not a music data format. It may contain text glyphs, vector paths, embedded images, fonts and layout instructions. It does not necessarily preserve the musical structure that originally produced it.

## Extraction principle

Prefer evidence-preserving extraction.

The pipeline should avoid converting uncertain visual evidence into confident musical facts. A partial result with useful diagnostics is better than a plausible but silently corrupted score.

## Common evidence types

PDF score extraction may use:

- text glyph positions,
- font names and glyph identifiers,
- vector paths,
- line segments,
- filled shapes,
- bounding boxes,
- page coordinate systems,
- embedded raster images,
- inferred staff and tab line geometry,
- repeated layout patterns.

Each extracted symbol should ideally keep source evidence such as page number, bounding box and extraction method.

## Coordinate systems

PDF coordinate systems can differ from screen or image coordinates.

The implementation should define:

- origin convention,
- page units,
- y-axis direction,
- page rotation handling,
- crop box / media box handling,
- scaling used for diagnostics,
- tolerance units for grouping.

Do not mix coordinate spaces without explicit conversion.

## Page segmentation

The extraction process should identify:

- pages,
- systems,
- staves,
- tablature staves,
- measures,
- barlines,
- voices,
- events,
- annotations.

A system is a horizontal group of related staves. Guitar notation often places standard notation and tab together in the same system.

## Staff and tab line detection

Staff lines and tab lines are core anchors.

Detection should consider:

- number of parallel horizontal lines,
- line spacing,
- line length,
- vertical grouping,
- interruptions caused by notes, symbols or page artifacts,
- repeated line geometry across the page.

Standard notation usually has five staff lines. Standard six-string tablature usually has six tab lines. Do not assume every detected group is valid solely because it has five or six lines.

## Measures and barlines

Barlines divide systems into measures.

Barline detection should consider:

- vertical lines crossing staff or tab groups,
- alignment between standard staff and tab,
- double barlines,
- repeat barlines,
- partial or broken lines caused by rendering,
- page/system continuation.

The parser should not treat every vertical line as a barline. Stems, brackets, text and technique markings may also create vertical shapes.

## Symbol classes

Important symbol classes include:

- noteheads,
- stems,
- beams,
- rests,
- augmentation dots,
- ties and slurs,
- accidentals,
- clefs,
- time signatures,
- key signatures,
- barlines,
- tuplets,
- tab numbers,
- technique marks,
- dynamics,
- text directions,
- tempo markings,
- repeat symbols.

Initial work should focus on the smallest subset needed for reliable conversion of a target fixture.

## Glyph and font risks

PDF text extraction may return:

- one character per glyph,
- combined ligatures,
- missing Unicode mappings,
- unexpected character codes,
- font-specific symbols,
- separate digits for one fret number,
- text in visual order rather than musical order.

Architect tasks should require empirical checks against real extraction output before assuming a glyph mapping.

## Grouping risks

Visual grouping is difficult because notation is dense.

Common risks:

- multi-digit fret numbers split into separate events,
- stems confused with barlines,
- slurs confused with ties,
- dots confused with staccato or augmentation dots,
- lyrics or titles confused with directions,
- measure boundaries inferred from spacing rather than barlines,
- voices merged incorrectly,
- small coordinate drift across a system,
- accidental association with the wrong note.

Grouping rules must be tested against realistic page snippets.

## Vector-first and image-fallback strategy

A vector-first strategy is usually preferable when the PDF contains extractable text and paths.

Image fallback may be needed when:

- the PDF contains scanned pages,
- fonts do not expose useful text,
- vector paths are flattened,
- the source has been rasterised,
- symbol extraction confidence is too low.

Image-based extraction should be treated as a different pipeline with different diagnostics, not as a silent substitute.

## Diagnostics

Developer-facing diagnostics should be able to show:

- source PDF page,
- detected systems,
- detected staff/tab groups,
- measure boundaries,
- extracted glyph boxes,
- grouped tab events,
- timing assumptions,
- warnings,
- confidence categories.

Diagnostics must not require committing private source PDFs or generated artifacts.

## Confidence model

Recommended confidence categories:

- `confirmed`: multiple independent signals agree.
- `probable`: enough evidence to proceed with warning-free conversion.
- `uncertain`: usable only with warning.
- `unsupported`: recognised but not implemented.
- `conflicting`: evidence disagrees.
- `failed`: extraction could not produce a usable result.

Avoid fake precision. A numeric confidence score is useful only if it is calibrated and tested.

## Architect checklist

Before assigning an extraction task, define:

- the fixture or synthetic input,
- the exact visual feature to extract,
- expected evidence shape,
- known edge cases,
- output representation,
- diagnostics required,
- privacy constraints,
- validation command,
- acceptable warnings,
- stop conditions.

## Stop conditions

Stop and report if:

- the source file is private and would need to be committed,
- glyph extraction is insufficient and no fallback is in scope,
- the task requires unsupported music semantics,
- a proposed heuristic would silently corrupt ambiguous cases,
- no meaningful validation can be run.
