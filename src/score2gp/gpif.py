from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from .ir import Event, Note, ScoreIR, Technique

SUPPORTED_MINIMAL_TECHNIQUES = {"slide", "vibrato", "hammer-on", "pull-off", "tie", "slur"}


def _text(parent: ET.Element, tag: str, value: object | None) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def build_gpif(score: ScoreIR) -> bytes:
    root = ET.Element("GPIF", {"version": "7", "generator": "score2gp"})
    score_node = ET.SubElement(root, "Score")

    _metadata(score_node, score)
    _tempo(score_node, score)
    _tracks(score_node, score)
    _master_bars(score_node, score)
    _bars(score_node, score)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _metadata(parent: ET.Element, score: ScoreIR) -> None:
    metadata = ET.SubElement(parent, "Metadata")
    _text(metadata, "Title", score.metadata.title)
    _text(metadata, "Artist", score.metadata.artist)
    _text(metadata, "Composer", score.metadata.composer)
    _text(metadata, "Album", score.metadata.album)
    _text(metadata, "Transcriber", score.metadata.transcriber)
    _text(metadata, "Copyright", score.metadata.copyright)


def _tempo(parent: ET.Element, score: ScoreIR) -> None:
    tempo = ET.SubElement(parent, "Tempo")
    _text(tempo, "Value", score.tempo.bpm)
    if score.tempo.text:
        _text(tempo, "Text", score.tempo.text)


def _tracks(parent: ET.Element, score: ScoreIR) -> None:
    tracks = ET.SubElement(parent, "Tracks")
    for track in score.tracks:
        node = ET.SubElement(tracks, "Track", {"id": track.id})
        _text(node, "Name", track.name)
        _text(node, "Instrument", track.instrument)
        _text(node, "Capo", track.capo)
        tuning = ET.SubElement(node, "Tuning", {"name": track.tuning.name})
        for string in sorted(track.tuning.strings, key=lambda item: item.number):
            ET.SubElement(
                tuning,
                "String",
                {
                    "number": str(string.number),
                    "pitch": str(string.pitch),
                    "name": string.name,
                },
            )


def _master_bars(parent: ET.Element, score: ScoreIR) -> None:
    master_bars = ET.SubElement(parent, "MasterBars")
    for bar in score.bars:
        node = ET.SubElement(master_bars, "MasterBar", {"index": str(bar.index)})
        _text(
            node,
            "Time",
            f"{bar.time_signature.numerator}/{bar.time_signature.denominator}",
        )
        if bar.key_signature is not None:
            key = ET.SubElement(node, "Key")
            _text(key, "Fifths", bar.key_signature.fifths)
            _text(key, "Mode", bar.key_signature.mode)


def _bars(parent: ET.Element, score: ScoreIR) -> None:
    bars = ET.SubElement(parent, "Bars")
    for bar in score.bars:
        bar_node = ET.SubElement(bars, "Bar", {"index": str(bar.index)})
        for event in sorted(bar.events, key=lambda item: item.timing.onset_ticks):
            _event(bar_node, event)


def _event(parent: ET.Element, event: Event) -> None:
    attrs = {
        "id": event.id,
        "track": event.track_id,
        "voice": str(event.timing.voice),
        "position": _ticks_to_fraction(event.timing.onset_ticks, event.timing.ticks_per_quarter),
        "duration": _ticks_to_fraction(event.timing.duration_ticks, event.timing.ticks_per_quarter),
        "confidence": f"{event.confidence:.3f}",
    }
    if event.is_rest:
        attrs["rest"] = "true"
    node = ET.SubElement(parent, "Event", attrs)
    if event.chord_symbol:
        _text(node, "Chord", event.chord_symbol)
    if event.techniques:
        techniques = ET.SubElement(node, "Techniques")
        for technique in event.techniques:
            ET.SubElement(techniques, "Technique", {"name": technique.kind})
    for note in event.notes:
        _note(node, note)


def _note(parent: ET.Element, note: Note) -> None:
    note_node = ET.SubElement(
        parent,
        "Note",
        {
            "string": str(note.string),
            "fret": str(note.fret),
            "pitch": str(note.pitch),
            "confidence": f"{note.confidence:.3f}",
        },
    )
    for technique in note.techniques:
        if technique.kind == "tie":
            note_node.set("tie", technique.state)
        if technique.kind == "slur":
            note_node.set("slur", technique.state)
    if note.techniques:
        techniques = ET.SubElement(note_node, "Techniques")
        for technique in note.techniques:
            ET.SubElement(techniques, "Technique", {"name": technique.kind})


def _ticks_to_fraction(ticks: int, ticks_per_quarter: int) -> str:
    return str(Fraction(ticks, ticks_per_quarter * 4))


def gpif_warnings(score: ScoreIR) -> list[str]:
    warnings: list[str] = []
    for track in score.tracks:
        if not track.tablature_enabled:
            warnings.append(f"track '{track.id}' tablature_enabled=false is not represented in the minimal GPIF writer")
        if track.staff_count != 1:
            warnings.append(f"track '{track.id}' staff_count={track.staff_count} is not represented in the minimal GPIF writer")
        if track.midi_program is not None or track.midi_channel is not None:
            warnings.append(f"track '{track.id}' MIDI program/channel is not represented in the minimal GPIF writer")
    for bar in score.bars:
        for event in bar.events:
            if event.timing.tuplet is not None:
                warnings.append(f"event '{event.id}' tuplet timing is not represented in the minimal GPIF writer")
            if event.timing.grace is not None:
                warnings.append(f"event '{event.id}' grace timing is not represented in the minimal GPIF writer")
            _technique_warnings(warnings, f"event '{event.id}'", event.techniques)
            for note in event.notes:
                _technique_warnings(warnings, f"event '{event.id}' note string {note.string}", note.techniques)
    return warnings


def _technique_warnings(warnings: list[str], owner: str, techniques: list[Technique]) -> None:
    for technique in techniques:
        if technique.kind not in SUPPORTED_MINIMAL_TECHNIQUES:
            warnings.append(f"{owner} technique '{technique.kind}' is not represented in the minimal GPIF writer")
