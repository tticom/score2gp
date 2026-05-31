# Unresolved Domain Questions

This document tracks unknown or unverified domain behaviors, Guitar Pro undocumented properties, or pipeline constraints that require empirical research and validation before being treated as domain facts.

---

## 1. Relational Database Layout Behaviors

### Q1.1: Relational Beat XProperties IDs
*   **Status:** Assumption requiring validation.
*   **Question:** What do the integer `id` attributes on `<XProperty>` elements represent inside relational `<Beats>` (e.g. `<XProperty id="1124204546">`)? Are they static hashes, or are they dynamic identifiers mapped to specific RSE parameters?
*   **Action Plan:** Extract several minimal GP8 files with varying RSE configurations and diff their `XProperties` schemas.

### Q1.2: Relational Voice Track reference indices
*   **Status:** Assumption requiring validation.
*   **Question:** Does a GP8 parser strictly require all relational `<Voice>` nodes to use `<Event>` reference sequences, or can they refer to empty/rest beats directly under `<Bar>`?
*   **Action Plan:** Create synthetic GP8 files with omitted voice elements to test parser compliance.

---

## 2. Audio and Polyphony Interpretations

### Q2.1: Multi-Voice Staff representation rules
*   **Status:** Unknown / unresolved.
*   **Question:** When converting multi-staff scores (e.g. standard notation + tablature paired track), how does the Guitar Pro parser reconcile notes that exist in the staff voice but are omitted or duplicated in the tablature voice? Does it auto-merge them, or does it require strict voice folding?
*   **Action Plan:** Run E2E smoke conversions on multi-voice lessons and inspect the visual rendering results.

---

## 3. String Snapping Optimizations

### Q3.1: Left-Hand Biomechanical Stretch Limits
*   **Status:** Project decision.
*   **Question:** What is the maximum physical fret span that the fret-snapping optimizer should allow for simultaneous notes in a chord before flagging it as unplayable? (Current default is 5 frets).
*   **Action Plan:** Consult standard guitar chord fingering charts to determine if 5 frets is a universally safe biomechanical ceiling, or if it should be dynamically scaled based on the fretboard position (e.g., smaller fret spacing at higher frets).
