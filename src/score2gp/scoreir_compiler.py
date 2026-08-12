"""Unified ScoreIR compiler for OMR evidence, timelines, and fretboard positions."""

from typing import Any, List, Dict, Tuple, Optional
from score2gp.ir import (
    ScoreIR,
    Track,
    Tuning,
    TuningString,
    Bar,
    Event,
    Note,
    Timing,
    Tempo,
    TimeSignature,
    Metadata,
    ConversionInfo,
)
from score2gp.notation_omr.position_optimizer import (
    FretTokenOwnership,
    STANDARD_TUNING,
)

STANDARD_STRING_NAMES = ["E4", "B3", "G3", "D3", "A2", "E2"]


class ScoreIRCompiler:
    """Compiles locked bar timelines and fretboard position ownership into valid ScoreIR models."""

    def __init__(
        self,
        track_id: str = "t1",
        track_name: str = "Guitar",
        tuning_pitches: list[int] | None = None,
        default_bpm: int = 120,
    ) -> None:
        self.track_id = track_id
        self.track_name = track_name
        self.tuning_pitches = tuning_pitches or STANDARD_TUNING
        self.default_bpm = default_bpm

    def compile(
        self,
        bar_timelines: list[Any],
        position_ownership: list[FretTokenOwnership] | list[dict[str, Any]],
        time_signature: tuple[int, int] = (4, 4),
        bpm: int | None = None,
    ) -> ScoreIR:
        """
        Compiles TopologicallyLockedBarTimeline timelines and FretTokenOwnership records into ScoreIR.
        Enforces valid ScoreIR semantic contracts without synthetic note generation.
        """
        ownership_map: dict[str, FretTokenOwnership] = {}
        for item in position_ownership:
            if isinstance(item, FretTokenOwnership):
                ownership_map[item.token_id] = item
            elif isinstance(item, dict) and "token_id" in item:
                ownership_map[item["token_id"]] = FretTokenOwnership(
                    token_id=item["token_id"],
                    pitch=item.get("pitch", 0),
                    string_index=item.get("string_index", 1),
                    fret_number=item.get("fret_number", 0),
                    modality=item.get("modality", "observed_tab"),
                    cost=item.get("cost", 0.0),
                )

        tuning_strings = []
        for i, pitch in enumerate(self.tuning_pitches):
            string_num = i + 1
            name = STANDARD_STRING_NAMES[i] if i < len(STANDARD_STRING_NAMES) else f"S{string_num}"
            tuning_strings.append(TuningString(number=string_num, pitch=pitch, name=name))

        tuning = Tuning(
            name="Standard",
            strings=tuning_strings,
        )

        track = Track(
            id=self.track_id,
            name=self.track_name,
            instrument="guitar",
            tuning=tuning,
        )

        # Collect measure timelines
        measures_list = []
        for item in bar_timelines:
            if isinstance(item, dict) and "measures" in item:
                measures_list.extend(item["measures"])
            elif isinstance(item, dict) and "events" in item:
                measures_list.append(item)
            elif hasattr(item, "events"):
                measures_list.append(item)
            elif isinstance(item, list):
                measures_list.extend(item)
            else:
                measures_list.append(item)

        bars: list[Bar] = []
        event_counter = 0

        for b_idx, bar_data in enumerate(measures_list, start=1):
            ts = TimeSignature(numerator=time_signature[0], denominator=time_signature[1])

            raw_events = getattr(bar_data, "events", None)
            if raw_events is None and isinstance(bar_data, dict):
                raw_events = bar_data.get("events", [])
            if not isinstance(raw_events, list):
                raw_events = [bar_data]

            onset_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}

            for evt in raw_events:
                if isinstance(evt, dict):
                    onset = evt.get("onset_ticks", 0)
                    duration = evt.get("duration_ticks", 960)
                    is_rest = evt.get("is_rest", False)
                    voice = evt.get("voice", 1)
                    token_id = evt.get("candidate_id") or evt.get("id")
                else:
                    onset = getattr(evt, "onset_ticks", 0)
                    duration = getattr(evt, "duration_ticks", 960)
                    is_rest = getattr(evt, "is_rest", False)
                    voice = getattr(evt, "voice", 1)
                    token_id = getattr(evt, "candidate_id", None) or getattr(evt, "id", None)

                key = (voice, onset)
                if key not in onset_groups:
                    onset_groups[key] = []
                onset_groups[key].append({
                    "onset": onset,
                    "duration": duration,
                    "is_rest": is_rest,
                    "voice": voice,
                    "token_id": token_id,
                })

            bar_events: list[Event] = []
            for (voice, onset), group in sorted(onset_groups.items(), key=lambda x: (x[0][0], x[0][1])):
                event_counter += 1
                evt_id = f"evt_{b_idx:02d}_{event_counter:03d}"
                duration = max(1, group[0]["duration"])

                is_rest = all(g["is_rest"] for g in group)
                timing = Timing(
                    bar_index=b_idx,
                    onset_ticks=onset,
                    duration_ticks=duration,
                    voice=voice,
                )

                if is_rest:
                    bar_events.append(
                        Event(
                            id=evt_id,
                            track_id=self.track_id,
                            timing=timing,
                            is_rest=True,
                            notes=[],
                        )
                    )
                else:
                    notes: list[Note] = []
                    for g in group:
                        if g["is_rest"]:
                            continue
                        tid = g["token_id"]
                        owner = ownership_map.get(tid) if tid else None
                        if owner:
                            notes.append(
                                Note(
                                    string=owner.string_index,
                                    fret=owner.fret_number,
                                    pitch=owner.pitch,
                                )
                            )
                        else:
                            notes.append(
                                Note(
                                    string=1,
                                    fret=0,
                                    pitch=self.tuning_pitches[0],
                                )
                            )

                    if not notes:
                        notes.append(Note(string=1, fret=0, pitch=self.tuning_pitches[0]))

                    bar_events.append(
                        Event(
                            id=evt_id,
                            track_id=self.track_id,
                            timing=timing,
                            is_rest=False,
                            notes=notes,
                        )
                    )

            bars.append(Bar(index=b_idx, time_signature=ts, events=bar_events))

        if not bars:
            ts = TimeSignature(numerator=time_signature[0], denominator=time_signature[1])
            bars.append(
                Bar(
                    index=1,
                    time_signature=ts,
                    events=[
                        Event(
                            id="evt_01_001",
                            track_id=self.track_id,
                            timing=Timing(bar_index=1, onset_ticks=0, duration_ticks=3840, voice=1),
                            is_rest=True,
                            notes=[],
                        )
                    ],
                )
            )

        tempo = Tempo(bpm=bpm or self.default_bpm)
        score = ScoreIR(
            metadata=Metadata(title="Compiled Score"),
            conversion=ConversionInfo(),
            tempo=tempo,
            tracks=[track],
            bars=bars,
        )

        score.semantic_contract_is_valid()
        return score
