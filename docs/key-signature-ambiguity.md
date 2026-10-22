# Mid-system key and note accidental ownership

The key reader inspects a contiguous accidental run immediately after a
notation barline. Its existing 1.5 staff-space barline window is deliberately
narrow: an accidental later in the bar can belong to a chord, even when it
occupies the first key-signature slot vertically.

An accidental attached to the first note can also occupy a signature slot.
Without a signature prefix, the reader accepts direct note attachment only
inside the existing half-space first-note-column tolerance. A slot-compatible
mark separated from that column, but still inside the 1.5-space attachment
window, has two plausible owners. The reader refuses it rather than carrying
the previous key. It retains the accidental source ID and the page, staff and
barline location in `key_signature_partial_or_ambiguous`.

This refusal includes `refuse_bar: true` in the bar-key diagnostic. The TAB bar
assembler writes that bar empty and records the located cause and source IDs
in `refusal_evidence`. An unresolved key remains refused until another key is
read; an intervening unread run cannot clear that refusal. Older key refusals
without this explicit bar-refusal marker retain their existing behavior.

The mounted 42-PDF corpus contained no detached single-flat ambiguity of this
kind. Its 15 attached, slot-compatible candidates had gaps of 0.188–0.310 staff
spaces. The half-space tolerance is reused from the existing note-column
grouping; the broad attachment window is not enlarged to infer ownership.

The genuine Lesson 7 negative controls retain four displaced flats at
1.344–1.464 spaces, plus an additional displaced sharp at 1.344 spaces. They
remain note accidentals with unchanged bar keys. These source checks and GPIF
preservation establish compatibility, not recognition of a new real key
change. Under the maintainer's 2026-10-22 exception (acceptance item 4),
`tests/test_omit_01_fu1_constructed.py` exercises constructed P3 geometry at
gaps of 0.5–1.5 spaces through the production bar-key reader. It asserts the
refusal, unset key, source ID, exact location and bar-refusal marker. Restoring
the base reader, always reading a key change, or always carrying the old key
each fails all six cases. This constructed test carries acceptance only for
the detached slot-0 ambiguity branch; it supplies no other real-source
recognition, geometry or fidelity evidence.
