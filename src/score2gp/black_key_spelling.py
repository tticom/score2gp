"""Spell the black keys of TAB-derived notes from printed accidentals and the read key signature.

The pitch of a note is already known from the TAB and is never changed here. Only the name
the writer gives a black key is decided:

1. an accidental printed on the note in its bar decides, and persists to the barline for later
   notes of the same pitch class in any octave (the references spell the rest of the bar alike;
   octave-specific persistence measured worse); a tie carries the spelling of the note it
   continues across a barline;
2. otherwise the direction of the key signature read for the bar decides (flats below zero
   fifths, sharps above);
3. otherwise nothing was read: the format's sharp is written, labelled ``default`` and reported
   as ``spelling_unevidenced``, never presented as read data.
"""

from __future__ import annotations

from typing import Any, Sequence

from .ir import Bar, NoteSpelling, WarningItem
from .pdf_tab_event_factory import BLACK_KEYS


def _tied_onward(note: Any) -> bool:
    return any(t.kind == "tie" and t.state in ("start", "continue") for t in note.techniques)


def _tied_from_before(note: Any) -> bool:
    return any(t.kind == "tie" and t.state in ("stop", "continue") for t in note.techniques)


def apply_black_key_spelling(bars: Sequence[Bar], route_bars: Sequence[dict[str, Any]] = ()) -> list[WarningItem]:
    """Complete ``Note.spelling`` for every black-key note and return the located warnings."""
    warnings: list[WarningItem] = []
    for entry in route_bars:
        for item in entry.get("unjoined_accidentals", ()):
            warnings.append(WarningItem(
                code="printed_accidental_unjoined", severity="warning",
                message=(f"Bar {entry['output_bar_index']}, notation event {item['event_index']}: a printed "
                         f"accidental ({', '.join(item['sources'])}) names a pitch no TAB note of the event "
                         "has, so it spells no note."),
            ))
    tie_spellings: dict[int, NoteSpelling] = {}
    for bar in sorted(bars, key=lambda b: b.index):
        carried: dict[int, str] = {}
        fifths = bar.key_signature.fifths if bar.key_signature is not None else 0
        pending_ties: dict[int, NoteSpelling] = {}
        unevidenced: list[str] = []
        for event in sorted(bar.events, key=lambda e: e.timing.onset_ticks):
            fresh: dict[int, str] = {}
            for note in event.notes:
                if note.pitch % 12 not in BLACK_KEYS:
                    continue
                if note.spelling is not None:
                    fresh[note.pitch % 12] = note.spelling.accidental
                elif note.pitch % 12 in carried:
                    note.spelling = NoteSpelling(accidental=carried[note.pitch % 12], source="printed_carried")
                elif _tied_from_before(note) and note.pitch in tie_spellings:
                    origin = tie_spellings[note.pitch]
                    source = "printed_carried" if origin.source.startswith("printed") else origin.source
                    note.spelling = NoteSpelling(accidental=origin.accidental, source=source)
                elif fifths != 0:
                    note.spelling = NoteSpelling(accidental="flat" if fifths < 0 else "sharp", source="key")
                else:
                    note.spelling = NoteSpelling(accidental="sharp", source="default")
                if note.spelling.source == "default":
                    unevidenced.append(f"{event.id} pitch {note.pitch}")
                if _tied_onward(note):
                    pending_ties[note.pitch] = note.spelling
            carried.update(fresh)
        if unevidenced:
            warnings.append(WarningItem(
                code="spelling_unevidenced", severity="warning",
                message=(f"Bar {bar.index}: no printed accidental and no key signature read, so "
                         f"{len(unevidenced)} black-key note(s) ({'; '.join(unevidenced)}) are written with the "
                         "format default sharp. The spelling is not read from the PDF; the pitch is unchanged."),
            ))
        tie_spellings = pending_ties
    return warnings
