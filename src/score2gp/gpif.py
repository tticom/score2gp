from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from .ir import Event, ScoreIR


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
        for event in sorted(bar.events, key=lambda item: Fraction(item.position)):
            _event(bar_node, event)


def _event(parent: ET.Element, event: Event) -> None:
    attrs = {
        "id": event.id,
        "track": event.track_id,
        "voice": str(event.voice),
        "position": event.position,
        "duration": event.duration,
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
            ET.SubElement(techniques, "Technique", {"name": technique.value})
    for note in event.notes:
        note_node = ET.SubElement(
            node,
            "Note",
            {
                "string": str(note.string),
                "fret": str(note.fret),
                "pitch": str(note.pitch),
                "confidence": f"{note.confidence:.3f}",
            },
        )
        if note.tie:
            note_node.set("tie", note.tie)
        if note.slur:
            note_node.set("slur", note.slur)
        if note.techniques:
            techniques = ET.SubElement(note_node, "Techniques")
            for technique in note.techniques:
                ET.SubElement(techniques, "Technique", {"name": technique.value})
