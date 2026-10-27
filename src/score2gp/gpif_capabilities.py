"""Pre-write limits of the current GPIF writer, never canonical IR repairs.

This is the existing writer's capability boundary, not the future ADR-008
target registry. A refusal includes a stable code and canonical source path.
"""
from __future__ import annotations

from .ir import ScoreBooklet, ScoreIR


def validate_gpif_capabilities(score: ScoreIR | ScoreBooklet, *, layout: str) -> None:
    errors: list[str] = []

    def refuse(code: str, path: str, detail: str) -> None:
        errors.append(f"{code} at {path}: {detail}")

    scores = score.scores if isinstance(score, ScoreBooklet) else [score]
    for score_index, movement in enumerate(scores):
        prefix = f"scores[{score_index}]." if isinstance(score, ScoreBooklet) else ""
        tracks = {track.id: track for track in movement.tracks}
        for index, track in enumerate(movement.tracks):
            path = f"{prefix}tracks[{index}].tuning"
            count = len(track.tuning.strings)
            if count > 12 or {s.number for s in track.tuning.strings} != set(range(1, count + 1)):
                refuse('gpif_tuning_unsupported', path, 'requires 1–12 consecutively numbered strings')
        for bar_index, bar in enumerate(movement.bars):
            bar_path = f"{prefix}bars[{bar_index}]"
            for field in ('numerator', 'denominator'):
                value = getattr(bar.time_signature, field)
                if not 1 <= value <= 64:
                    refuse('gpif_meter_out_of_range', f'{bar_path}.time_signature.{field}', f'{value}; supported range 1–64')
            for event_index, event in enumerate(bar.events):
                path = f'{bar_path}.events[{event_index}]'
                track = tracks[event.track_id]
                # Relational GPIF has four voices per staff. Single-staff
                # voice 5 must refuse rather than alias voice 1 via modulo.
                voice_limit = min(8, track.staff_count * 4) if layout == 'relational' else 8
                if not 1 <= event.timing.voice <= voice_limit:
                    refuse('gpif_voice_out_of_range', f'{path}.timing.voice', f'{event.timing.voice}; supported range 1–{voice_limit}')
                duration = event.timing.notated_duration
                if layout == 'relational' and duration is not None and duration.value == '128th':
                    refuse('gpif_duration_unsupported', f'{path}.timing.notated_duration.value', '128th is not implemented by the relational writer')
                diagram = event.chord_diagram
                if diagram is not None:
                    if diagram.string_count > 12 or diagram.base_fret > 36:
                        refuse('gpif_chord_out_of_range', f'{path}.chord_diagram', 'supports at most 12 strings and base fret 36')
                    for kind in ('frets', 'fingers'):
                        for index, position in enumerate(getattr(diagram, kind)):
                            if position.string > 12 or position.fret > 36:
                                refuse('gpif_chord_out_of_range', f'{path}.chord_diagram.{kind}[{index}]', 'supports strings 1–12 and frets 0–36')
                for note_index, note in enumerate(event.notes):
                    note_path = f'{path}.notes[{note_index}]'
                    count = len(track.tuning.strings)
                    if not 1 <= note.string <= count:
                        refuse('gpif_string_out_of_range', f'{note_path}.string', f'{note.string}; track {track.id!r} has {count} strings')
                    if note.fret is not None and not 0 <= note.fret <= 36:
                        refuse('gpif_fret_out_of_range', f'{note_path}.fret', f'{note.fret}; supported range 0–36')
                    if note.pitch is not None and not 0 <= note.pitch <= 127:
                        refuse('gpif_pitch_out_of_range', f'{note_path}.pitch', f'{note.pitch}; MIDI range 0–127')
                owners = [(path, event.techniques)] + [
                    (f'{path}.notes[{i}]', note.techniques) for i, note in enumerate(event.notes)]
                for owner, techniques in owners:
                    for index, technique in enumerate(techniques):
                        technique_path = f'{owner}.techniques[{index}]'
                        if technique.kind == 'trill' and technique.fret is not None and technique.fret > 36:
                            refuse('gpif_fret_out_of_range', f'{technique_path}.fret', 'supported range 0–36')
                        if layout == 'legacy' and technique.kind == 'bend' and technique.points and event.timing.duration_ticks == 0:
                            refuse('gpif_bend_duration_zero', technique_path, 'cannot normalize bend points over zero duration')
    if errors:
        raise ValueError('; '.join(errors))
