from __future__ import annotations

import hashlib
from fractions import Fraction
from pathlib import Path
from pathlib import PurePosixPath
from typing import Literal
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, ConfigDict, Field

from .ir import DEFAULT_TICKS_PER_QUARTER, TimeSignature


class MusicXmlWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    source_path: str | None = None


class MusicXmlTimingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    part_id: str
    measure_index: int = Field(ge=1)
    measure_number: str
    voice: int | None = Field(default=None, ge=1, le=8)
    musicxml_note_id: str | None = None
    expected_duration_divisions: float | None = Field(default=None, ge=0.0)
    onset_divisions: int | None = Field(default=None, ge=0)
    duration_divisions: int | None = Field(default=None, ge=0)
    end_divisions: int | None = Field(default=None, ge=0)
    source_path: str | None = None
    meter: str | None = None
    backup_forward_count: int | None = None
    voice_extents: dict[str, int] | None = None
    voice_durations: dict[str, int] | None = None
    timing_calibration_possible: bool = False
    timing_repair_attempted: bool = False
    overfull_divisions: float | None = None
    overlap_count: int | None = None
    affected_event_ids: list[str] = Field(default_factory=list)
    primary_reason: str | None = None
    secondary_reasons: list[str] = Field(default_factory=list)


class MusicXmlVoiceCursorDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_id: str
    measure_index: int
    measure_number: str
    voice_id: int | None = None
    expected_measure_ticks: float | None = None
    expected_measure_divisions: float | None = None
    voice_cursor_starts: dict[str, int] = Field(default_factory=dict)
    voice_cursor_ends: dict[str, int] = Field(default_factory=dict)
    note_event_count: int = 0
    rest_event_count: int = 0
    chord_stack_count: int = 0
    backup_count: int = 0
    forward_count: int = 0
    same_voice_overlap_count: int = 0
    cross_voice_overlap_count: int = 0
    measure_overfull: bool = False
    measure_underfull: bool = False
    primary_reason: str
    secondary_reasons: list[str] = Field(default_factory=list)
    timing_calibration_possible: bool = False
    timing_repair_attempted: bool = False
    overfull_divisions: float | None = None
    affected_event_ids: list[str] = Field(default_factory=list)


class MusicXmlVoiceCursorModel:
    def __init__(
        self,
        part_id: str,
        measure_index: int,
        measure_number: str,
        divisions: int,
        expected_duration_divisions: float | None,
        allow_remediation: bool = False,
    ):
        self.part_id = part_id
        self.measure_index = measure_index
        self.measure_number = measure_number
        self.divisions = divisions
        self.expected_duration_divisions = expected_duration_divisions
        self.allow_remediation = allow_remediation

        self.parsing_cursor = 0
        self.last_note_onset: dict[int, int] = {}
        self.voice_cursors: dict[int, int] = {}
        self.voice_cursor_starts: dict[int, int] = {}
        self.voice_cursor_ends: dict[int, int] = {}

        self.note_event_count = 0
        self.rest_event_count = 0
        self.chord_stack_count = 0
        self.backup_count = 0
        self.forward_count = 0

        self.same_voice_overlap_count = 0
        self.cross_voice_overlap_count = 0

        self.primary_reason = "musicxml_voice_timeline_valid"
        self.secondary_reasons: list[str] = []
        self.events: list[tuple[int, int, int, bool, str]] = []
        self.measure_overfull = False
        self.measure_underfull = False

        self.note_onsets: dict[int, int] = {}
        self.note_truncated_durations: dict[int, int] = {}
        self.timing_repair_attempted = False

    def simulate(self, measure_node: ET.Element) -> MusicXmlVoiceCursorDiagnostics:
        note_index = 0
        for child in list(measure_node):
            name = _local_name(child.tag)
            if name == "note":
                note_index += 1
                grace = _child(child, "grace") is not None
                if grace:
                    self.note_onsets[note_index] = 0
                    continue

                voice = _int_text(_child(child, "voice"), default=1)
                duration = _duration(child)
                is_rest = _child(child, "rest") is not None
                chord = _child(child, "chord") is not None
                note_id = child.get("id") or f"note-{note_index}"

                if chord:
                    onset = self.last_note_onset.get(voice, None)
                    if onset is None:
                        if "musicxml_chord_stack_without_anchor" not in self.secondary_reasons:
                            self.secondary_reasons.append("musicxml_chord_stack_without_anchor")
                        onset = self.parsing_cursor

                    if self.allow_remediation and self.expected_duration_divisions is not None:
                        expected = int(self.expected_duration_divisions)
                        if onset >= expected:
                            onset = expected
                            if duration > 0:
                                duration = 0
                                self.note_truncated_durations[note_index] = 0
                                self.timing_repair_attempted = True
                        elif onset < expected and onset + duration > expected:
                            duration = expected - onset
                            self.note_truncated_durations[note_index] = duration
                            self.timing_repair_attempted = True

                    self.chord_stack_count += 1
                    self.note_onsets[note_index] = onset
                else:
                    onset = self.parsing_cursor
                    if self.allow_remediation and self.expected_duration_divisions is not None:
                        expected = int(self.expected_duration_divisions)
                        if onset >= expected:
                            onset = expected
                            if duration > 0:
                                duration = 0
                                self.note_truncated_durations[note_index] = 0
                                self.timing_repair_attempted = True
                        elif onset < expected and onset + duration > expected:
                            duration = expected - onset
                            self.note_truncated_durations[note_index] = duration
                            self.timing_repair_attempted = True

                    self.last_note_onset[voice] = onset
                    self.note_onsets[note_index] = onset
                    if voice not in self.voice_cursor_starts:
                        self.voice_cursor_starts[voice] = onset

                    # Same-voice overlap check
                    prev_cursor = self.voice_cursors.get(voice, 0)
                    if onset < prev_cursor and duration > 0:
                        self.same_voice_overlap_count += 1
                        has_rest_overlap = is_rest
                        if not has_rest_overlap:
                            for ev in self.events:
                                ev_voice, ev_onset, ev_end, ev_is_rest, _ = ev
                                if ev_voice == voice and ev_is_rest:
                                    if max(onset, ev_onset) < min(onset + duration, ev_end):
                                        has_rest_overlap = True
                                        break
                        if has_rest_overlap:
                            if "musicxml_rest_overlap_same_voice" not in self.secondary_reasons:
                                self.secondary_reasons.append("musicxml_rest_overlap_same_voice")
                        else:
                            if "musicxml_same_voice_overlap" not in self.secondary_reasons:
                                self.secondary_reasons.append("musicxml_same_voice_overlap")

                    self.voice_cursors[voice] = max(prev_cursor, onset + duration)
                    self.voice_cursor_ends[voice] = self.voice_cursors[voice]
                    self.parsing_cursor = onset + duration
                    if is_rest:
                        self.rest_event_count += 1
                    else:
                        self.note_event_count += 1

                    if duration > 0:
                        self.events.append((voice, onset, onset + duration, is_rest, note_id))

            elif name == "backup":
                self.backup_count += 1
                dur = _duration(child)
                self.parsing_cursor -= dur
                if self.parsing_cursor < 0:
                    if "musicxml_backup_cursor_before_measure_start" not in self.secondary_reasons:
                        self.secondary_reasons.append("musicxml_backup_cursor_before_measure_start")
                    self.parsing_cursor = 0

            elif name == "forward":
                self.forward_count += 1
                dur = _duration(child)
                self.parsing_cursor += dur
                if self.expected_duration_divisions is not None and self.parsing_cursor > self.expected_duration_divisions:
                    if "musicxml_forward_cursor_after_measure_end" not in self.secondary_reasons:
                        self.secondary_reasons.append("musicxml_forward_cursor_after_measure_end")

        # Compare pairs for cross-voice overlap
        for i in range(len(self.events)):
            v_a, s_a, e_a, r_a, id_a = self.events[i]
            for j in range(i + 1, len(self.events)):
                v_b, s_b, e_b, r_b, id_b = self.events[j]
                if v_a != v_b:
                    if max(s_a, s_b) < min(e_a, e_b):
                        self.cross_voice_overlap_count += 1
                        if "musicxml_cross_voice_overlap_unsupported" not in self.secondary_reasons:
                            self.secondary_reasons.append("musicxml_cross_voice_overlap_unsupported")

        # Check overfull/underfull
        overfull_divisions = None
        affected_event_ids = []
        if self.expected_duration_divisions is not None:
            overfull_voices = [v for v, end in self.voice_cursors.items() if end > self.expected_duration_divisions]
            if overfull_voices:
                self.measure_overfull = True
                if "musicxml_voice_duration_overfull" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_voice_duration_overfull")

            if self.voice_cursors:
                longest_voice_end = max(self.voice_cursors.values())
                if longest_voice_end > self.expected_duration_divisions:
                    overfull_divisions = float(longest_voice_end - self.expected_duration_divisions)
                if 0 < longest_voice_end < self.expected_duration_divisions:
                    self.measure_underfull = True
                    if "musicxml_voice_duration_underfull" not in self.secondary_reasons:
                        self.secondary_reasons.append("musicxml_voice_duration_underfull")

        # Determine affected event IDs
        if self.expected_duration_divisions is not None:
            for voice, onset, end, is_rest, note_id in self.events:
                if end > self.expected_duration_divisions:
                    if note_id not in affected_event_ids:
                        affected_event_ids.append(note_id)
        for i in range(len(self.events)):
            v_a, s_a, e_a, r_a, id_a = self.events[i]
            for j in range(i + 1, len(self.events)):
                v_b, s_b, e_b, r_b, id_b = self.events[j]
                if v_a == v_b and max(s_a, s_b) < min(e_a, e_b) and (s_a != s_b or (not r_a and not r_b)):
                    if id_a not in affected_event_ids:
                        affected_event_ids.append(id_a)
                    if id_b not in affected_event_ids:
                        affected_event_ids.append(id_b)

        # Check accumulated subdivision / rounding overflow
        if self.measure_overfull and overfull_divisions is not None:
            # If the overflow is very small relative to the expected duration divisions or division count,
            # it's likely an accumulated rounding error. Let's say <= 5 divisions or <= divisions // 100
            if overfull_divisions <= max(5.0, self.divisions / 100.0):
                if "musicxml_accumulated_duration_overflow" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_accumulated_duration_overflow")

        # Check invalid duration grid
        # E.g., expected duration is not a clean integer divisions
        if self.expected_duration_divisions is not None:
            if int(self.expected_duration_divisions) != self.expected_duration_divisions:
                if "musicxml_invalid_duration_grid" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_invalid_duration_grid")

        # Populate timing calibration possible and intermediate reasons
        timing_calibration_possible = False
        if self.measure_overfull and overfull_divisions is not None:
            if overfull_divisions > self.divisions:
                if "musicxml_overfull_too_large_for_calibration" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_overfull_too_large_for_calibration")

        if self.same_voice_overlap_count > 0 or self.cross_voice_overlap_count > 0:
            if "musicxml_overlap_blocks_calibration" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_overlap_blocks_calibration")

        if self.backup_count > 3:
            if "musicxml_many_risks_block_calibration" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_many_risks_block_calibration")

        if (self.measure_overfull or "musicxml_accumulated_duration_overflow" in self.secondary_reasons) and overfull_divisions is not None:
            # Calibration could be considered only when:
            # - error is small (e.g. <= self.divisions, which is 1 quarter-note beat)
            # - all events remain ordered (no backup before start, etc.)
            # - no overlaps occur (same voice or cross voice)
            if overfull_divisions <= self.divisions:
                if self.same_voice_overlap_count == 0 and self.cross_voice_overlap_count == 0:
                    if "musicxml_backup_cursor_before_measure_start" not in self.secondary_reasons:
                        timing_calibration_possible = True

        if len(self.voice_cursors) > 1:
            ends = list(self.voice_cursors.values())
            if any(e != ends[0] for e in ends):
                if "musicxml_measure_duration_inconsistent_across_voices" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_measure_duration_inconsistent_across_voices")

        # Map candidate codes to secondary reasons
        if self.measure_overfull:
            if "musicxml_same_voice_measure_overfull" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_same_voice_measure_overfull")
            # If notes extend past the end
            if "musicxml_event_extends_past_measure" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_event_extends_past_measure")

        if self.same_voice_overlap_count > 0:
            if "musicxml_same_voice_event_overlap" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_same_voice_event_overlap")
            if "musicxml_rest_overlap_same_voice" in self.secondary_reasons:
                if "musicxml_same_voice_rest_note_overlap" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_same_voice_rest_note_overlap")

        if self.timing_repair_attempted:
            if "musicxml_timing_overfull_resolved" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_timing_overfull_resolved")

        if self.measure_overfull or self.same_voice_overlap_count > 0 or self.cross_voice_overlap_count > 0 or "musicxml_invalid_duration_grid" in self.secondary_reasons:
            if not self.timing_repair_attempted:
                if "musicxml_timing_repair_not_attempted" not in self.secondary_reasons:
                    self.secondary_reasons.append("musicxml_timing_repair_not_attempted")
            if "musicxml_timing_calibration_required" not in self.secondary_reasons:
                self.secondary_reasons.append("musicxml_timing_calibration_required")

        if "musicxml_backup_cursor_before_measure_start" in self.secondary_reasons:
            self.primary_reason = "musicxml_backup_cursor_before_measure_start"
        elif "musicxml_forward_cursor_after_measure_end" in self.secondary_reasons:
            self.primary_reason = "musicxml_forward_cursor_after_measure_end"
        elif self.same_voice_overlap_count > 0:
            self.primary_reason = "musicxml_same_voice_overlap"
        elif self.cross_voice_overlap_count > 0:
            self.primary_reason = "musicxml_valid_multivoice_unsupported"
        else:
            self.primary_reason = "musicxml_voice_timeline_valid"

        return MusicXmlVoiceCursorDiagnostics(
            part_id=self.part_id,
            measure_index=self.measure_index,
            measure_number=self.measure_number,
            voice_id=None,
            expected_measure_ticks=self.expected_duration_divisions,
            expected_measure_divisions=self.expected_duration_divisions,
            voice_cursor_starts={str(k): v for k, v in self.voice_cursor_starts.items()},
            voice_cursor_ends={str(k): v for k, v in self.voice_cursor_ends.items()},
            note_event_count=self.note_event_count,
            rest_event_count=self.rest_event_count,
            chord_stack_count=self.chord_stack_count,
            backup_count=self.backup_count,
            forward_count=self.forward_count,
            same_voice_overlap_count=self.same_voice_overlap_count,
            cross_voice_overlap_count=self.cross_voice_overlap_count,
            measure_overfull=self.measure_overfull,
            measure_underfull=self.measure_underfull,
            primary_reason=self.primary_reason,
            secondary_reasons=self.secondary_reasons,
            timing_calibration_possible=timing_calibration_possible,
            timing_repair_attempted=self.timing_repair_attempted,
            overfull_divisions=overfull_divisions,
            affected_event_ids=affected_event_ids,
        )


class MusicXmlMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Untitled"
    composer: str | None = None
    lyricist: str | None = None
    rights: str | None = None
    source: str | None = None


class MusicXmlPitch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str
    alter: int = 0
    octave: int
    midi: int
    name: str


class MusicXmlTuplet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_notes: int
    normal_notes: int


class MusicXmlTechnique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["slide", "bend", "vibrato", "hammer-on", "pull-off", "slur", "unsupported"]
    state: Literal["start", "stop", "continue", "single", "unknown"] = "unknown"
    semitones: float | None = None
    text: str | None = None
    source_path: str


class MusicXmlNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    part_id: str
    measure_index: int = Field(ge=1)
    measure_number: str
    note_index: int = Field(ge=1)
    onset_divisions: int = Field(ge=0)
    duration_divisions: int = Field(ge=0)
    voice: int = Field(default=1, ge=1, le=8)
    staff: int | None = Field(default=None, ge=1)
    is_rest: bool = False
    pitch: MusicXmlPitch | None = None
    chord: bool = False
    ties: list[Literal["start", "stop"]] = Field(default_factory=list)
    notated_type: str | None = None
    dots: int = Field(default=0, ge=0)
    tuplet: MusicXmlTuplet | None = None
    grace: bool = False
    grace_slash: bool = False
    techniques: list[MusicXmlTechnique] = Field(default_factory=list)
    source_path: str
    duration_missing: bool = False
    duration_zero: bool = False
    tuplet_unsupported: bool = False
    is_suppressed: bool = False
    dedup_tab_note_id: str | None = None
    dedup_tab_note_voice: int | None = None
    dedup_tab_note_staff: int | None = None
    dedup_tab_note_techniques: list[MusicXmlTechnique] = Field(default_factory=list)
    dedup_tab_note_source_path: str | None = None
    dedup_tab_note_pitch_midi: int | None = None
    dedup_tab_note_pitch_name: str | None = None
    dedup_tab_note_string: int | None = None
    dedup_tab_note_fret: int | None = None
    dedup_tab_note_ties: list[str] = Field(default_factory=list)
    dedup_tab_note_onset_divisions: int | None = None
    dedup_tab_note_duration_divisions: int | None = None

    def duration_ticks(self, divisions: int) -> tuple[int, bool]:
        value = Fraction(self.duration_divisions * DEFAULT_TICKS_PER_QUARTER, divisions)
        return int(value), value.denominator == 1

    def onset_ticks(self, divisions: int) -> tuple[int, bool]:
        value = Fraction(self.onset_divisions * DEFAULT_TICKS_PER_QUARTER, divisions)
        return int(value), value.denominator == 1


class MusicXmlHarmony(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    part_id: str
    measure_index: int = Field(ge=1)
    measure_number: str
    onset_divisions: int = Field(ge=0)
    root_step: str
    root_alter: int = 0
    kind: str | None = None
    text: str
    source_path: str


class MusicXmlMeasure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    number: str
    divisions: int = Field(gt=0)
    time_signature: TimeSignature
    key_fifths: int | None = None
    notes: list[MusicXmlNote] = Field(default_factory=list)
    harmonies: list[MusicXmlHarmony] = Field(default_factory=list)
    divisions_missing: bool = False
    divisions_changed_mid_measure: bool = False
    backup_forward_risk: bool = False
    unbalanced_backup_forward: bool = False
    backup_rewinds_before_measure_start: bool = False
    forward_exceeds_measure_end: bool = False
    backup_forward_count: int = 0
    voice_cursor_diagnostics: MusicXmlVoiceCursorDiagnostics | None = None


class MusicXmlPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    measures: list[MusicXmlMeasure] = Field(default_factory=list)


class MusicXmlImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str
    metadata: MusicXmlMetadata
    tempo_bpm: int | None = Field(default=None, gt=0, le=400)
    parts: list[MusicXmlPart] = Field(default_factory=list)
    warnings: list[MusicXmlWarning] = Field(default_factory=list)
    allow_remediation: bool = False


def parse_musicxml(path: str | Path, *, allow_remediation: bool = False) -> MusicXmlImport:
    xml_path = Path(path)
    root = _parse_musicxml_root(xml_path)
    if _local_name(root.tag) != "score-partwise":
        raise ValueError("only partwise MusicXML scores are supported")

    warnings: list[MusicXmlWarning] = []
    part_names = _part_names(root)
    metadata = _metadata(root, xml_path)
    tempo_bpm = _tempo(root)
    parts = []

    for part_node in _children(root, "part"):
        part_id = part_node.get("id") or f"part-{len(parts) + 1}"
        part_name = part_names.get(part_id, part_id)
        parts.append(_parse_part(part_node, part_id, part_name, warnings, allow_remediation=allow_remediation))

    return MusicXmlImport(
        source_path=str(xml_path),
        source_sha256=_sha256(xml_path),
        metadata=metadata,
        tempo_bpm=tempo_bpm,
        parts=parts,
        warnings=warnings,
        allow_remediation=allow_remediation,
    )


def mxl_rootfile_path(path: str | Path) -> str:
    """Return the root MusicXML member for a compressed MXL package."""

    with ZipFile(path) as package:
        return _mxl_rootfile(package)


def _can_remediate_backup_forward_drift(
    measure: MusicXmlMeasure,
    measure_issues: list[MusicXmlTimingIssue],
    confirmed_pairs: list[tuple[int, int]],
) -> bool:
    vcd = measure.voice_cursor_diagnostics
    if vcd is None:
        return False

    # Measure is underfull-only, not overfull
    if not vcd.measure_underfull or vcd.measure_overfull:
        return False

    # No same-voice overlaps
    if vcd.same_voice_overlap_count > 0:
        return False

    # Backup/forward bounds violations
    if measure.backup_rewinds_before_measure_start or measure.forward_exceeds_measure_end:
        return False

    # No fatal overfull issues
    if any(issue.severity == "error" and issue.code in ("musicxml-overfull-bar", "musicxml_compound_meter_overfull") for issue in measure_issues):
        return False

    # No fatal same-voice overlap or rest/note overlap
    same_voice_overlap_codes = {
        "musicxml-voice-overlap",
        "musicxml_voice_cursor_overlap",
        "musicxml_same_voice_tick_overlap",
        "musicxml_rest_overlap",
        "musicxml_rest_voice_overlap",
    }
    for issue in measure_issues:
        if issue.severity == "error":
            if issue.code in same_voice_overlap_codes:
                return False
            if issue.code == "musicxml_voice_cursor_alignment_risk" and "cross-voice" not in str(issue.message):
                return False

    # No musicxml_invalid_duration_grid fatal issue
    if "musicxml_invalid_duration_grid" in vcd.secondary_reasons:
        return False

    # Duplicate staff/TAB voice evidence present
    has_duplicate_evidence = any(
        any(n.voice == v1 for n in measure.notes) and any(n.voice == v2 for n in measure.notes)
        for v1, v2 in confirmed_pairs
    )
    if not has_duplicate_evidence:
        return False

    return True


def analyze_musicxml_timing(imported: MusicXmlImport, include_polyphony_diagnostics: bool = False) -> list[MusicXmlTimingIssue]:
    """Return public-safe timing risks before ScoreIR construction."""

    issues: list[MusicXmlTimingIssue] = []

    # Track notes by voice to check for ties across measures
    voice_notes: dict[str, dict[int, list[MusicXmlNote]]] = {}

    for part in imported.parts:
        confirmed_pairs, _ = classify_musicxml_voice_duplication(part)
        part_vnotes = voice_notes.setdefault(part.id, {})
        previous_divisions: int | None = None
        for measure in part.measures:
            expected = _expected_measure_duration_divisions(measure)

            is_compound = measure.time_signature.numerator % 3 == 0 and measure.time_signature.denominator == 8
            meter_str = f"{measure.time_signature.numerator}/{measure.time_signature.denominator}"

            # Calculate voice extents and durations for the measure
            voice_extents: dict[str, int] = {}
            voice_durations: dict[str, int] = {}
            timed_notes = [n for n in measure.notes if not n.grace and not n.is_suppressed]
            for note in timed_notes:
                if note.duration_divisions > 0:
                    end = note.onset_divisions + note.duration_divisions
                    voice_extents[str(note.voice)] = max(voice_extents.get(str(note.voice), 0), end)
                    voice_durations[str(note.voice)] = voice_durations.get(str(note.voice), 0) + note.duration_divisions

            start_idx = len(issues)

            # Check 1: divisions missing
            if measure.divisions_missing:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_divisions_missing",
                        message=f"Measure {measure.number} is missing MusicXML divisions definition.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 2: divisions changed mid-measure
            if measure.divisions_changed_mid_measure:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_divisions_changed_mid_measure",
                        message=f"Measure {measure.number} changes MusicXML divisions mid-measure, which is unsupported.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 3: divisions changed mid-part
            if previous_divisions is not None and previous_divisions != measure.divisions:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml-divisions-changed",
                        message=(
                            f"Measure {measure.number} changes MusicXML divisions from "
                            f"{previous_divisions} to {measure.divisions}; timing conversion remains explicit."
                        ),
                        severity="info",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        expected_duration_divisions=expected,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )
            previous_divisions = measure.divisions

            # Check 4: 12/8 or other compound meter assumption
            if is_compound:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml-compound-meter-assumption",
                        message=(
                            f"Measure {measure.number} uses {measure.time_signature.numerator}/"
                            f"{measure.time_signature.denominator}; build-ir treats durations as exact "
                            "quarter-note ticks and reports alignment quality separately."
                        ),
                        severity="info",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        expected_duration_divisions=expected,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 5: measure duration unknown
            if expected is None:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml-measure-duration-unknown",
                        message=f"Measure {measure.number} has no computable expected duration.",
                        severity="warning",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )
                continue

            # Check 6: backup past zero
            if measure.backup_forward_risk:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_backup_forward_risk",
                        message=f"Measure {measure.number} contains a backup element that moves the cursor past zero.",
                        severity="warning",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 6b: backup rewinds before measure start
            if measure.backup_rewinds_before_measure_start:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_backup_rewinds_before_measure_start",
                        message=f"Measure {measure.number} contains a backup element that rewinds before measure start.",
                        severity="warning",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 6c: forward exceeds measure end
            if measure.forward_exceeds_measure_end:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_forward_exceeds_measure_end",
                        message=f"Measure {measure.number} contains a forward element that pushes beyond measure end.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Check 7: unbalanced backup/forward
            if measure.unbalanced_backup_forward:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_unbalanced_backup_forward",
                        message=f"Measure {measure.number} contains unbalanced backup/forward cursor movements.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_backup_forward_alignment_ambiguous",
                        message=f"Measure {measure.number} backup/forward cursor movements create ambiguous alignment.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Collect pitched notes for tie checking later
            for note in measure.notes:
                if not note.grace and not note.is_rest and note.pitch is not None and not note.is_suppressed:
                    part_vnotes.setdefault(note.voice, []).append(note)

            # Note-level duration and tuplet issues
            for note in measure.notes:
                if note.is_suppressed:
                    continue
                if note.duration_missing:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_duration_missing",
                            message=f"Measure {measure.number} note {note.id} is missing duration.",
                            severity="warning",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            voice=note.voice,
                            musicxml_note_id=note.id,
                            onset_divisions=note.onset_divisions,
                            source_path=note.source_path,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )
                if note.duration_zero:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_duration_zero",
                            message=f"Measure {measure.number} note {note.id} has duration 0.",
                            severity="warning",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            voice=note.voice,
                            musicxml_note_id=note.id,
                            onset_divisions=note.onset_divisions,
                            source_path=note.source_path,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )
                if note.tuplet_unsupported:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_tuplet_unsupported",
                            message=f"Measure {measure.number} note {note.id} uses an unsupported or malformed tuplet timing.",
                            severity="error",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            voice=note.voice,
                            musicxml_note_id=note.id,
                            onset_divisions=note.onset_divisions,
                            source_path=note.source_path,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )

            # Check overlaps and chord stacks using simulated voice cursor diagnostics
            overlap_count = 0
            affected_voices_set: set[int] = set()

            vcd = measure.voice_cursor_diagnostics
            if vcd is not None:
                # 1. Overfull bars
                if vcd.measure_overfull:
                    for note in timed_notes:
                        end = note.onset_divisions + note.duration_divisions
                        if end > expected:
                            issues.append(
                                MusicXmlTimingIssue(
                                    code="musicxml-overfull-bar",
                                    message=(
                                        f"Measure {measure.number} event {note.id} ends at MusicXML division "
                                        f"{end}, beyond expected measure length {expected}."
                                    ),
                                    severity="error",
                                    part_id=part.id,
                                    measure_index=measure.index,
                                    measure_number=measure.number,
                                    voice=note.voice,
                                    musicxml_note_id=note.id,
                                    expected_duration_divisions=expected,
                                    onset_divisions=note.onset_divisions,
                                    duration_divisions=note.duration_divisions,
                                    end_divisions=end,
                                    source_path=note.source_path,
                                    meter=meter_str,
                                    backup_forward_count=measure.backup_forward_count,
                                    voice_extents=voice_extents,
                                    voice_durations=voice_durations,
                                )
                            )
                            if is_compound:
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_compound_meter_overfull",
                                        message=(
                                            f"Measure {measure.number} event {note.id} ends at MusicXML division "
                                            f"{end}, beyond expected compound measure length {expected}."
                                        ),
                                        severity="error",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note.voice,
                                        musicxml_note_id=note.id,
                                        expected_duration_divisions=expected,
                                        onset_divisions=note.onset_divisions,
                                        duration_divisions=note.duration_divisions,
                                        end_divisions=end,
                                        source_path=note.source_path,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )

                # 2. Legitimate chord stacks
                for i in range(len(timed_notes)):
                    note_i = timed_notes[i]
                    for j in range(i + 1, len(timed_notes)):
                        note_j = timed_notes[j]
                        if note_i.voice == note_j.voice and note_i.onset_divisions == note_j.onset_divisions:
                            if note_i.chord or note_j.chord:
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_chord_stack_detected",
                                        message=f"Measure {measure.number} has a legitimate chord stack in voice {note_i.voice}.",
                                        severity="info",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_i.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=note_i.onset_divisions,
                                        duration_divisions=note_i.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_chord_stack_supported_or_blocked",
                                        message=f"Measure {measure.number} has a supported chord stack in voice {note_i.voice}.",
                                        severity="info",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_i.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=note_i.onset_divisions,
                                        duration_divisions=note_i.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_chord_stack_not_timing_overlap",
                                        message=f"Measure {measure.number} has a legitimate chord stack in voice {note_i.voice} that is distinguished from timing overlap.",
                                        severity="info",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_i.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=note_i.onset_divisions,
                                        duration_divisions=note_i.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )

                # 3. Same-voice overlaps
                if vcd.same_voice_overlap_count > 0:
                    for i in range(len(timed_notes)):
                        note_i = timed_notes[i]
                        if note_i.duration_divisions <= 0:
                            continue
                        onset_i = note_i.onset_divisions
                        end_i = onset_i + note_i.duration_divisions
                        for j in range(i + 1, len(timed_notes)):
                            note_j = timed_notes[j]
                            if note_j.duration_divisions <= 0:
                                continue
                            onset_j = note_j.onset_divisions
                            end_j = onset_j + note_j.duration_divisions
                            if note_i.voice == note_j.voice and max(onset_i, onset_j) < min(end_i, end_j) and (onset_i != onset_j or (not note_i.chord and not note_j.chord)):
                                overlap_count += 1
                                affected_voices_set.add(note_i.voice)
                                if note_i.is_rest or note_j.is_rest:
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml_rest_overlap",
                                            message=f"Measure {measure.number} voice {note_i.voice} has overlapping rest and note.",
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_i.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            end_divisions=end_j,
                                            source_path=note_j.source_path,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml_rest_voice_overlap",
                                            message=f"Measure {measure.number} voice {note_i.voice} has overlapping rest and note.",
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_i.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            end_divisions=end_j,
                                            source_path=note_j.source_path,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )
                                    if measure.backup_forward_count > 0:
                                        issues.append(
                                            MusicXmlTimingIssue(
                                                code="musicxml_voice_cursor_alignment_risk",
                                                message=f"Measure {measure.number} voice {note_i.voice} has voice cursor alignment risk due to rest overlap.",
                                                severity="error",
                                                part_id=part.id,
                                                measure_index=measure.index,
                                                measure_number=measure.number,
                                                voice=note_i.voice,
                                                musicxml_note_id=note_j.id,
                                                onset_divisions=onset_j,
                                                duration_divisions=note_j.duration_divisions,
                                                meter=meter_str,
                                                backup_forward_count=measure.backup_forward_count,
                                                voice_extents=voice_extents,
                                                voice_durations=voice_durations,
                                            )
                                        )
                                else:
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml-voice-overlap",
                                            message=(
                                                f"Measure {measure.number} voice {note_i.voice} overlaps: "
                                                f"{note_i.id} ends at {end_i}, before {note_j.id} starts at "
                                                f"{onset_j}."
                                            ),
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_i.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            end_divisions=end_j,
                                            source_path=note_j.source_path,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml_voice_cursor_overlap",
                                            message=(
                                                f"Measure {measure.number} voice {note_i.voice} cursor overlaps: "
                                                f"{note_i.id} ends at {end_i}, before {note_j.id} starts at "
                                                f"{onset_j}."
                                            ),
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_i.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            end_divisions=end_j,
                                            source_path=note_j.source_path,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml_same_voice_tick_overlap",
                                            message=f"Measure {measure.number} voice {note_i.voice} has overlapping ticks on the voice timeline.",
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_i.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            end_divisions=end_j,
                                            source_path=note_j.source_path,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )
                                    if measure.backup_forward_count > 0:
                                        issues.append(
                                            MusicXmlTimingIssue(
                                                code="musicxml_voice_cursor_alignment_risk",
                                                message=f"Measure {measure.number} voice {note_i.voice} has voice cursor alignment risk due to same-voice overlap.",
                                                severity="error",
                                                part_id=part.id,
                                                measure_index=measure.index,
                                                measure_number=measure.number,
                                                voice=note_i.voice,
                                                musicxml_note_id=note_j.id,
                                                onset_divisions=onset_j,
                                                duration_divisions=note_j.duration_divisions,
                                                end_divisions=end_j,
                                                source_path=note_j.source_path,
                                                meter=meter_str,
                                                backup_forward_count=measure.backup_forward_count,
                                                voice_extents=voice_extents,
                                                voice_durations=voice_durations,
                                            )
                                        )

                # 4. Cross-voice overlaps
                if vcd.cross_voice_overlap_count > 0:
                    for i in range(len(timed_notes)):
                        note_i = timed_notes[i]
                        if note_i.duration_divisions <= 0 or note_i.is_rest:
                            continue
                        onset_i = note_i.onset_divisions
                        end_i = onset_i + note_i.duration_divisions
                        for j in range(i + 1, len(timed_notes)):
                            note_j = timed_notes[j]
                            if note_j.duration_divisions <= 0 or note_j.is_rest:
                                continue
                            onset_j = note_j.onset_divisions
                            end_j = onset_j + note_j.duration_divisions
                            if note_i.voice != note_j.voice and max(onset_i, onset_j) < min(end_i, end_j):
                                overlap_count += 1
                                affected_voices_set.add(note_i.voice)
                                affected_voices_set.add(note_j.voice)
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_polyphony_not_supported",
                                        message=f"Measure {measure.number} has unsupported polyphony/multi-voice overlap between voice {note_i.voice} and voice {note_j.voice}.",
                                        severity="error",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_j.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=onset_j,
                                        duration_divisions=note_j.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_multivoice_timing_not_supported",
                                        message=f"Measure {measure.number} has unsupported multi-voice timing between voice {note_i.voice} and voice {note_j.voice}.",
                                        severity="error",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_j.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=onset_j,
                                        duration_divisions=note_j.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_cross_voice_timing_unsupported",
                                        message=f"Measure {measure.number} has unsupported cross-voice timing overlap between voice {note_i.voice} and voice {note_j.voice}.",
                                        severity="error",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_j.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=onset_j,
                                        duration_divisions=note_j.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                issues.append(
                                    MusicXmlTimingIssue(
                                        code="musicxml_valid_multivoice_unsupported",
                                        message=f"Measure {measure.number} has valid multi-voice timing but it is unsupported by ScoreIR.",
                                        severity="error",
                                        part_id=part.id,
                                        measure_index=measure.index,
                                        measure_number=measure.number,
                                        voice=note_j.voice,
                                        musicxml_note_id=note_j.id,
                                        onset_divisions=onset_j,
                                        duration_divisions=note_j.duration_divisions,
                                        meter=meter_str,
                                        backup_forward_count=measure.backup_forward_count,
                                        voice_extents=voice_extents,
                                        voice_durations=voice_durations,
                                    )
                                )
                                if measure.backup_forward_count > 0:
                                    issues.append(
                                        MusicXmlTimingIssue(
                                            code="musicxml_voice_cursor_alignment_risk",
                                            message=f"Measure {measure.number} has voice cursor alignment risk due to cross-voice timing overlap.",
                                            severity="error",
                                            part_id=part.id,
                                            measure_index=measure.index,
                                            measure_number=measure.number,
                                            voice=note_j.voice,
                                            musicxml_note_id=note_j.id,
                                            onset_divisions=onset_j,
                                            duration_divisions=note_j.duration_divisions,
                                            meter=meter_str,
                                            backup_forward_count=measure.backup_forward_count,
                                            voice_extents=voice_extents,
                                            voice_durations=voice_durations,
                                        )
                                    )

            if measure.backup_forward_count > 3:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_repeated_backup_forward_risk",
                        message=f"Measure {measure.number} has {measure.backup_forward_count} backup/forward cursor movements, exceeding the safe limit of 3.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            if getattr(imported, "allow_remediation", False):
                for issue in issues[start_idx:]:
                    if issue.code in {
                        "musicxml_polyphony_not_supported",
                        "musicxml_multivoice_timing_not_supported",
                        "musicxml_cross_voice_timing_unsupported",
                        "musicxml_valid_multivoice_unsupported",
                        "musicxml_cross_voice_overlap_unsupported",
                    } or (issue.code == "musicxml_voice_cursor_alignment_risk" and "cross-voice" in str(issue.message)):
                        issue.severity = "warning"

            if getattr(imported, "allow_remediation", False) and _can_remediate_backup_forward_drift(measure, issues[start_idx:], confirmed_pairs):
                for issue in issues[start_idx:]:
                    if issue.code in {
                        "musicxml_unbalanced_backup_forward",
                        "musicxml_backup_forward_alignment_ambiguous",
                    }:
                        issue.severity = "warning"

            # Check if we have many timing risks in this measure
            measure_errors = [issue for issue in issues[start_idx:] if issue.severity == "error"]
            if len(measure_errors) > 5:
                issues.append(
                    MusicXmlTimingIssue(
                        code="musicxml_many_timing_risks",
                        message=f"Measure {measure.number} has high-density timing risk with {overlap_count} overlapping event pairs affecting voice(s): {', '.join(map(str, sorted(affected_voices_set)))}.",
                        severity="error",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            if voice_extents:
                longest_voice = max(voice_extents.values())
                if 0 < longest_voice < expected:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml-underfull-bar",
                            message=(
                                f"Measure {measure.number} longest voice ends at MusicXML division "
                                f"{longest_voice}, before expected measure length {expected}."
                            ),
                            severity="warning",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            expected_duration_divisions=expected,
                            end_divisions=longest_voice,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )
                    if is_compound:
                        issues.append(
                            MusicXmlTimingIssue(
                                code="musicxml_compound_meter_underfull",
                                message=(
                                    f"Measure {measure.number} longest voice ends at division "
                                    f"{longest_voice}, before expected compound measure length {expected}."
                                ),
                                severity="warning",
                                part_id=part.id,
                                measure_index=measure.index,
                                measure_number=measure.number,
                                expected_duration_divisions=expected,
                                end_divisions=longest_voice,
                                meter=meter_str,
                                backup_forward_count=measure.backup_forward_count,
                                voice_extents=voice_extents,
                                voice_durations=voice_durations,
                            )
                        )

            # Check if this compound meter has no errors and is thus a valid compound meter
            measure_issues = issues[start_idx:]
            if is_compound and not any(issue.severity == "error" for issue in measure_issues):
                issues.append(
                    MusicXmlTimingIssue(
                        code="valid_compound_meter",
                        message=f"Measure {measure.number} is a valid compound meter.",
                        severity="info",
                        part_id=part.id,
                        measure_index=measure.index,
                        measure_number=measure.number,
                        meter=meter_str,
                        backup_forward_count=measure.backup_forward_count,
                        voice_extents=voice_extents,
                        voice_durations=voice_durations,
                    )
                )

            # Enrich all generated issues with the voice cursor diagnostics if present
            vcd = measure.voice_cursor_diagnostics
            if vcd is not None:
                if vcd.timing_repair_attempted:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_timing_overfull_resolved",
                            message=f"Measure {measure.number} overfull issue was conservatively resolved by truncating note durations to the measure boundary.",
                            severity="warning",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            expected_duration_divisions=expected,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )
                if "musicxml_invalid_duration_grid" in vcd.secondary_reasons:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_invalid_duration_grid",
                            message=f"Measure {measure.number} has an invalid duration grid: expected duration {expected} is not a clean integer divisions.",
                            severity="error",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                            expected_duration_divisions=expected,
                            meter=meter_str,
                            backup_forward_count=measure.backup_forward_count,
                            voice_extents=voice_extents,
                            voice_durations=voice_durations,
                        )
                    )
                for issue in issues[start_idx:]:
                    issue.timing_calibration_possible = vcd.timing_calibration_possible
                    issue.timing_repair_attempted = vcd.timing_repair_attempted
                    issue.overfull_divisions = vcd.overfull_divisions
                    issue.overlap_count = vcd.same_voice_overlap_count + vcd.cross_voice_overlap_count
                    issue.affected_event_ids = vcd.affected_event_ids
                    issue.primary_reason = vcd.primary_reason
                    issue.secondary_reasons = vcd.secondary_reasons

            # Measure-level polyphony gate diagnostics
            if include_polyphony_diagnostics:
                measure_polyphony_errs = [
                    issue for issue in issues[start_idx:]
                    if issue.severity == "error" and issue.code in {
                        "musicxml_polyphony_not_supported",
                        "musicxml_multivoice_timing_not_supported",
                        "musicxml_cross_voice_timing_unsupported",
                        "musicxml_valid_multivoice_unsupported",
                        "musicxml_voice_cursor_alignment_risk",
                        "musicxml-voice-overlap",
                        "musicxml_voice_cursor_overlap",
                        "musicxml_same_voice_tick_overlap",
                        "musicxml_rest_overlap",
                        "musicxml_rest_voice_overlap",
                    }
                ]
                if measure_polyphony_errs:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_polyphony_gate_blocking_measure",
                            message=f"Measure {measure.number} blocked by polyphony gate.",
                            severity="info",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                        )
                    )

                if vcd is not None and vcd.measure_overfull:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_polyphony_gate_overfull_measure",
                            message=f"Measure {measure.number} is overfull.",
                            severity="info",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                        )
                    )

                if vcd is not None and (vcd.same_voice_overlap_count > 0 or vcd.cross_voice_overlap_count > 0):
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_polyphony_gate_overlap_detected",
                            message=f"Measure {measure.number} has timeline overlap detected (same_voice={vcd.same_voice_overlap_count}, cross_voice={vcd.cross_voice_overlap_count}).",
                            severity="info",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                        )
                    )

                # Check for duplicate staff/TAB voice duplication
                notes_by_voice = {}
                for note in timed_notes:
                    if note.onset_divisions is not None and note.duration_divisions is not None:
                        notes_by_voice.setdefault(note.voice, []).append(note)

                if len(notes_by_voice) == 2:
                    voices = list(notes_by_voice.keys())
                    v1, v2 = voices[0], voices[1]
                    list1, list2 = notes_by_voice[v1], notes_by_voice[v2]
                    list1 = sorted(list1, key=lambda n: (n.onset_divisions, n.id or ""))
                    list2 = sorted(list2, key=lambda n: (n.onset_divisions, n.id or ""))

                    if len(list1) == len(list2) and len(list1) > 0:
                        all_overlap = True
                        pitch_12_offset = True
                        for n1, n2 in zip(list1, list2):
                            if n1.onset_divisions != n2.onset_divisions or n1.duration_divisions != n2.duration_divisions:
                                all_overlap = False
                                break
                            if n1.pitch is not None and n2.pitch is not None:
                                diff = abs(n1.pitch.midi - n2.pitch.midi)
                                if diff != 12:
                                    pitch_12_offset = False

                        if all_overlap and pitch_12_offset:
                            issues.append(
                                MusicXmlTimingIssue(
                                    code="musicxml_polyphony_gate_duplicate_staff_tab_suspected",
                                    message=f"Measure {measure.number} has suspected duplicate staff/TAB voice duplication (matching onset/duration and 12-semitone pitch offset).",
                                    severity="info",
                                    part_id=part.id,
                                    measure_index=measure.index,
                                    measure_number=measure.number,
                                )
                            )

                if any(issue.code == "musicxml_chord_stack_detected" for issue in issues[start_idx:]):
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_polyphony_gate_valid_chord_suspected",
                            message=f"Measure {measure.number} has a suspected valid guitar chord stack.",
                            severity="info",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                        )
                    )

                has_tie_or_slur = False
                for note in timed_notes:
                    if note.ties or any(tech.kind == "slur" for tech in note.techniques):
                        has_tie_or_slur = True
                        break
                if has_tie_or_slur:
                    issues.append(
                        MusicXmlTimingIssue(
                            code="musicxml_polyphony_gate_slur_tie_continuation_suspected",
                            message=f"Measure {measure.number} contains suspected tie/slur continuation notation.",
                            severity="info",
                            part_id=part.id,
                            measure_index=measure.index,
                            measure_number=measure.number,
                        )
                    )

                if any(issue.code == "musicxml_polyphony_gate_blocking_measure" for issue in issues[start_idx:]):
                    any_suspected = any(
                        issue.code in {
                            "musicxml_polyphony_gate_overfull_measure",
                            "musicxml_polyphony_gate_overlap_detected",
                            "musicxml_polyphony_gate_duplicate_staff_tab_suspected",
                            "musicxml_polyphony_gate_valid_chord_suspected",
                            "musicxml_polyphony_gate_slur_tie_continuation_suspected",
                        }
                        for issue in issues[start_idx:]
                    )
                    if not any_suspected:
                        issues.append(
                            MusicXmlTimingIssue(
                                code="musicxml_polyphony_gate_reason_unknown",
                                message=f"Measure {measure.number} blocked by polyphony gate for unknown reason.",
                                severity="info",
                                part_id=part.id,
                                measure_index=measure.index,
                                measure_number=measure.number,
                            )
                        )

        # Check for tie continuity risks
        for voice, notes in part_vnotes.items():
            for idx in range(len(notes)):
                note = notes[idx]
                if "start" in note.ties:
                    if note.measure_index < len(part.measures):
                        resolved = False
                        next_idx = idx + 1
                        while next_idx < len(notes):
                            cand = notes[next_idx]
                            if cand.onset_divisions > note.onset_divisions or cand.measure_index > note.measure_index:
                                onset_to_check = cand.onset_divisions
                                measure_to_check = cand.measure_index
                                while next_idx < len(notes):
                                    next_cand = notes[next_idx]
                                    if next_cand.onset_divisions == onset_to_check and next_cand.measure_index == measure_to_check:
                                        if "stop" in next_cand.ties and next_cand.pitch is not None and note.pitch is not None and next_cand.pitch.midi == note.pitch.midi:
                                            resolved = True
                                            break
                                        next_idx += 1
                                    else:
                                        break
                                break
                            next_idx += 1

                        if not resolved:
                            meas = part.measures[note.measure_index - 1]
                            m_meter_str = f"{meas.time_signature.numerator}/{meas.time_signature.denominator}"
                            m_extents: dict[str, int] = {}
                            m_durations: dict[str, int] = {}
                            for tn in meas.notes:
                                if not tn.grace and tn.duration_divisions > 0:
                                    tend = tn.onset_divisions + tn.duration_divisions
                                    m_extents[str(tn.voice)] = max(m_extents.get(str(tn.voice), 0), tend)
                                    m_durations[str(tn.voice)] = m_durations.get(str(tn.voice), 0) + tn.duration_divisions

                            issues.append(
                                MusicXmlTimingIssue(
                                    code="musicxml_tie_continuity_risk",
                                    message=f"Measure {note.measure_number} note {note.id} starts a tie but has no matching stop tie with same pitch.",
                                    severity="warning",
                                    part_id=part.id,
                                    measure_index=note.measure_index,
                                    measure_number=note.measure_number,
                                    voice=note.voice,
                                    musicxml_note_id=note.id,
                                    meter=m_meter_str,
                                    backup_forward_count=meas.backup_forward_count,
                                    voice_extents=m_extents,
                                    voice_durations=m_durations,
                                )
                            )
                if "stop" in note.ties:
                    if note.measure_index > 1:
                        resolved = False
                        prev_idx = idx - 1
                        while prev_idx >= 0:
                            cand = notes[prev_idx]
                            if cand.onset_divisions < note.onset_divisions or cand.measure_index < note.measure_index:
                                onset_to_check = cand.onset_divisions
                                measure_to_check = cand.measure_index
                                while prev_idx >= 0:
                                    prev_cand = notes[prev_idx]
                                    if prev_cand.onset_divisions == onset_to_check and prev_cand.measure_index == measure_to_check:
                                        if "start" in prev_cand.ties and prev_cand.pitch is not None and note.pitch is not None and prev_cand.pitch.midi == note.pitch.midi:
                                            resolved = True
                                            break
                                        prev_idx -= 1
                                    else:
                                        break
                                break
                            prev_idx -= 1

                        if not resolved:
                            meas = part.measures[note.measure_index - 1]
                            m_meter_str = f"{meas.time_signature.numerator}/{meas.time_signature.denominator}"
                            m_extents: dict[str, int] = {}
                            m_durations: dict[str, int] = {}
                            for tn in meas.notes:
                                if not tn.grace and tn.duration_divisions > 0:
                                    tend = tn.onset_divisions + tn.duration_divisions
                                    m_extents[str(tn.voice)] = max(m_extents.get(str(tn.voice), 0), tend)
                                    m_durations[str(tn.voice)] = m_durations.get(str(tn.voice), 0) + tn.duration_divisions

                            issues.append(
                                MusicXmlTimingIssue(
                                    code="musicxml_tie_continuity_risk",
                                    message=f"Measure {note.measure_number} note {note.id} stops a tie but has no matching start tie with same pitch.",
                                    severity="warning",
                                    part_id=part.id,
                                    measure_index=note.measure_index,
                                    measure_number=note.measure_number,
                                    voice=note.voice,
                                    musicxml_note_id=note.id,
                                    meter=m_meter_str,
                                    backup_forward_count=meas.backup_forward_count,
                                    voice_extents=m_extents,
                                    voice_durations=m_durations,
                                )
                            )

        # Part-level polyphony gate summary issues
        if include_polyphony_diagnostics:
            all_voices_in_part = set()
            for measure in part.measures:
                for note in measure.notes:
                    all_voices_in_part.add(note.voice)

            issues.append(
                MusicXmlTimingIssue(
                    code="musicxml_polyphony_gate_measure_count",
                    message=f"Total MusicXML measures parsed: {len(part.measures)}.",
                    severity="info",
                    part_id=part.id,
                    measure_index=1,
                    measure_number="1",
                )
            )
            issues.append(
                MusicXmlTimingIssue(
                    code="musicxml_polyphony_gate_voice_count",
                    message=f"Total voices detected across part: {len(all_voices_in_part)}.",
                    severity="info",
                    part_id=part.id,
                    measure_index=1,
                    measure_number="1",
                )
            )

    # Post-process global calibration feasibility and reasons
    has_tie_continuity_risk = any(issue.code == "musicxml_tie_continuity_risk" for issue in issues)
    has_invalid_duration_grid = any(issue.code == "musicxml_invalid_duration_grid" for issue in issues)

    # Identify overfull and underfull measures
    overfull_measures = {
        (issue.part_id, issue.measure_index)
        for issue in issues
        if issue.code in ("musicxml-overfull-bar", "musicxml_compound_meter_overfull", "musicxml_voice_duration_overfull")
        or "musicxml_voice_duration_overfull" in issue.secondary_reasons
        or "musicxml_same_voice_measure_overfull" in issue.secondary_reasons
    }
    underfull_measures = {
        (issue.part_id, issue.measure_index)
        for issue in issues
        if issue.code in ("musicxml-underfull-bar", "musicxml_compound_meter_underfull", "musicxml_voice_duration_underfull")
        or "musicxml_voice_duration_underfull" in issue.secondary_reasons
    }
    has_mixed_measures = len(overfull_measures) > 0 and len(underfull_measures) > 0

    has_overlap_risk = any(
        issue.code in (
            "musicxml-voice-overlap",
            "musicxml_voice_cursor_overlap",
            "musicxml_same_voice_tick_overlap",
            "musicxml_rest_overlap",
            "musicxml_rest_voice_overlap",
            "musicxml_polyphony_not_supported",
            "musicxml_multivoice_timing_not_supported",
            "musicxml_cross_voice_timing_unsupported",
            "musicxml_valid_multivoice_unsupported"
        )
        or "musicxml_overlap_blocks_calibration" in issue.secondary_reasons
        for issue in issues
    )

    has_many_risks = any(
        issue.code in ("musicxml_many_timing_risks", "musicxml_repeated_backup_forward_risk")
        or "musicxml_many_risks_block_calibration" in issue.secondary_reasons
        for issue in issues
    )

    has_large_overfull = any(
        "musicxml_overfull_too_large_for_calibration" in issue.secondary_reasons
        for issue in issues
    )

    global_blocked = (
        has_tie_continuity_risk
        or has_invalid_duration_grid
        or has_mixed_measures
        or has_overlap_risk
        or has_many_risks
        or has_large_overfull
    )

    # Update all issues' timing_calibration_possible and secondary reasons
    for issue in issues:
        if global_blocked:
            issue.timing_calibration_possible = False

        # Append appropriate global secondary reason codes
        if has_tie_continuity_risk:
            if "musicxml_tie_continuity_blocks_calibration" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_tie_continuity_blocks_calibration")
        if has_invalid_duration_grid:
            if "musicxml_invalid_grid_blocks_calibration" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_invalid_grid_blocks_calibration")
        if has_mixed_measures:
            if "musicxml_mixed_underfull_overfull_blocks_calibration" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_mixed_underfull_overfull_blocks_calibration")

        if issue.timing_calibration_possible:
            if "musicxml_timing_calibration_candidate" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_timing_calibration_candidate")
        else:
            if "musicxml_timing_calibration_not_safe" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_timing_calibration_not_safe")
            if "musicxml_calibration_boundary_reported" not in issue.secondary_reasons:
                issue.secondary_reasons.append("musicxml_calibration_boundary_reported")

    # Append alignment refused/due to risk issue if any error exists
    if any(issue.severity == "error" for issue in issues):
        first_err = next(issue for issue in issues if issue.severity == "error")
        issues.append(
            MusicXmlTimingIssue(
                code="musicxml_alignment_not_attempted_due_to_timing_risk",
                message="Alignment and ScoreIR generation were not attempted due to MusicXML timing risk.",
                severity="error",
                part_id=first_err.part_id,
                measure_index=first_err.measure_index,
                measure_number=first_err.measure_number,
                meter=first_err.meter,
                backup_forward_count=first_err.backup_forward_count,
                voice_extents=first_err.voice_extents,
                voice_durations=first_err.voice_durations,
                timing_calibration_possible=first_err.timing_calibration_possible,
                timing_repair_attempted=first_err.timing_repair_attempted,
                overfull_divisions=first_err.overfull_divisions,
                overlap_count=first_err.overlap_count,
                affected_event_ids=first_err.affected_event_ids,
                primary_reason=first_err.primary_reason,
                secondary_reasons=first_err.secondary_reasons,
            )
        )

    return issues


def _parse_musicxml_root(path: Path) -> ET.Element:
    if path.suffix.lower() != ".mxl":
        return ET.parse(path).getroot()

    try:
        with ZipFile(path) as package:
            if not package.namelist():
                raise ValueError("MXL package is empty")
            rootfile = _mxl_rootfile(package)
            try:
                return ET.fromstring(package.read(rootfile))
            except ET.ParseError as exc:
                raise ValueError(f"MXL rootfile '{rootfile}' is not well-formed MusicXML") from exc
    except BadZipFile as exc:
        raise ValueError(f"invalid compressed MusicXML package: {path.name}") from exc
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise ValueError(f"MXL package does not contain its declared MusicXML rootfile: {missing}") from exc


def _mxl_rootfile(package: ZipFile) -> str:
    try:
        container_data = package.read("META-INF/container.xml")
    except KeyError:
        raise ValueError("MXL package is missing required META-INF/container.xml") from None
    try:
        container = ET.fromstring(container_data)
    except ET.ParseError as exc:
        raise ValueError("MXL container.xml is not well-formed XML") from exc

    for node in container.iter():
        if _local_name(node.tag) == "rootfile" and node.get("full-path"):
            rootfile = _validated_mxl_member_path(str(node.get("full-path")))
            if rootfile not in package.namelist():
                raise KeyError(rootfile)
            return rootfile
    raise ValueError("MXL container.xml does not declare a rootfile full-path")


def _validated_mxl_member_path(value: str) -> str:
    rootfile = value.strip()
    if not rootfile:
        raise ValueError("MXL container.xml rootfile full-path is empty")
    if "\\" in rootfile:
        raise ValueError(f"MXL rootfile path is unsafe: {rootfile}")
    path = PurePosixPath(rootfile)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or ":" in path.parts[0]:
        raise ValueError(f"MXL rootfile path is unsafe: {rootfile}")
    return rootfile


def _parse_part(
    part_node: ET.Element,
    part_id: str,
    part_name: str,
    warnings: list[MusicXmlWarning],
    *,
    allow_remediation: bool = False,
) -> MusicXmlPart:
    # Pre-scan divisions and max voice cursor length to infer default time signature if missing
    initial_divisions = 1
    for m_node in _children(part_node, "measure"):
        attrs = _child(m_node, "attributes")
        if attrs is not None:
            div_node = _child(attrs, "divisions")
            val = _optional_int_text(div_node)
            if val is not None and val > 0:
                initial_divisions = val
                break

    has_time = False
    for node in part_node.iter():
        if _local_name(node.tag) == "time":
            has_time = True
            break

    default_time = TimeSignature(numerator=4, denominator=4)
    if not has_time:
        max_len = 0
        for m_node in _children(part_node, "measure"):
            cursor = 0
            voice_cursors = {}
            for child in list(m_node):
                name = _local_name(child.tag)
                if name == "note":
                    grace = _child(child, "grace") is not None
                    if grace:
                        continue
                    chord = _child(child, "chord") is not None
                    dur_node = _child(child, "duration")
                    dur = int(dur_node.text) if dur_node is not None else 0
                    voice_node = _child(child, "voice")
                    voice = int(voice_node.text) if voice_node is not None else 1
                    if chord:
                        # Approximation for pre-scan
                        onset = cursor - dur
                    else:
                        onset = cursor
                    cursor = onset + dur
                    voice_cursors[voice] = max(voice_cursors.get(voice, 0), cursor)
                elif name == "backup":
                    dur_node = _child(child, "duration")
                    dur = int(dur_node.text) if dur_node is not None else 0
                    cursor = max(0, cursor - dur)
                elif name == "forward":
                    dur_node = _child(child, "duration")
                    dur = int(dur_node.text) if dur_node is not None else 0
                    cursor += dur
            if voice_cursors:
                max_len = max(max_len, max(voice_cursors.values()))

        beats = max_len / initial_divisions if initial_divisions > 0 else 0
        if beats >= 5.5:
            default_time = TimeSignature(numerator=12, denominator=8)

    measures = []
    current_divisions = 1
    current_time = default_time
    current_key: int | None = None
    has_divisions_defined = False

    for measure_index, measure_node in enumerate(_children(part_node, "measure"), start=1):
        measure_number = measure_node.get("number") or str(measure_index)

        # Pre-scan attributes to get correct current_divisions and current_time for this measure
        temp_div = current_divisions
        temp_time = current_time
        for child in list(measure_node):
            name = _local_name(child.tag)
            if name == "attributes":
                div_child = _child(child, "divisions")
                new_div = _optional_int_text(div_child)
                if new_div is not None and new_div > 0:
                    temp_div = new_div
                temp_time = _parse_time_signature(child, temp_time)

        temp_expected = None
        if temp_time is not None:
            val = Fraction(temp_time.numerator * temp_div * 4, temp_time.denominator)
            temp_expected = float(val)

        # Instantiate voice cursor model and simulate
        model = MusicXmlVoiceCursorModel(
            part_id=part_id,
            measure_index=measure_index,
            measure_number=measure_number,
            divisions=temp_div,
            expected_duration_divisions=temp_expected,
            allow_remediation=allow_remediation,
        )
        voice_cursor_diagnostics = model.simulate(measure_node)

        cursor = 0
        notes: list[MusicXmlNote] = []
        harmonies: list[MusicXmlHarmony] = []
        divisions_changed_mid_measure = False
        has_backup_or_forward = voice_cursor_diagnostics.backup_count > 0 or voice_cursor_diagnostics.forward_count > 0

        for child in list(measure_node):
            name = _local_name(child.tag)
            source_path = f"/score-partwise/part[@id='{part_id}']/measure[{measure_index}]/{name}"
            if name == "attributes":
                div_child = _child(child, "divisions")
                if div_child is not None:
                    has_divisions_defined = True
                new_div = _optional_int_text(div_child)
                if new_div is not None and new_div > 0:
                    if len(notes) > 0 and new_div != current_divisions:
                        divisions_changed_mid_measure = True
                    current_divisions = new_div
                current_time = _parse_time_signature(child, current_time)
                current_key = _parse_key(child, current_key)
            elif name == "note":
                note_index = len(notes) + 1
                onset_val = model.note_onsets.get(note_index, cursor)
                note, _, _ = _parse_note(
                    child,
                    part_id=part_id,
                    measure_index=measure_index,
                    measure_number=measure_number,
                    note_index=note_index,
                    cursor=onset_val,
                    last_note_onset=onset_val,
                    warnings=warnings,
                )
                if model.note_truncated_durations and note_index in model.note_truncated_durations:
                    orig_duration = note.duration_divisions
                    note.duration_divisions = model.note_truncated_durations[note_index]
                    warnings.append(
                        MusicXmlWarning(
                            code="musicxml_duration_truncated_to_measure_boundary",
                            message=(
                                f"Measure {measure_number} note {note.id} duration truncated from "
                                f"{orig_duration} to {note.duration_divisions} divisions to fit measure boundary."
                            ),
                            severity="warning",
                            source_path=note.source_path,
                        )
                    )
                notes.append(note)
                if not note.grace and not note.chord:
                    cursor = onset_val + note.duration_divisions
            elif name == "harmony":
                harmonies.append(
                    _parse_harmony(
                        child,
                        part_id=part_id,
                        measure_index=measure_index,
                        measure_number=measure_number,
                        harmony_index=len(harmonies) + 1,
                        cursor=cursor,
                    )
                )
            elif name == "backup":
                warnings.append(
                    MusicXmlWarning(
                        code="musicxml-backup-encountered",
                        message="MusicXML backup changes the timing cursor; build-ir will preflight the resulting voices.",
                        severity="info",
                        source_path=source_path,
                    )
                )
                dur = _duration(child)
                cursor = max(0, cursor - dur)
            elif name == "forward":
                warnings.append(
                    MusicXmlWarning(
                        code="musicxml-forward-encountered",
                        message="MusicXML forward changes the timing cursor; build-ir will preflight the resulting voices.",
                        severity="info",
                        source_path=source_path,
                    )
                )
                dur = _duration(child)
                cursor += dur
            elif name == "barline" and _has_descendant(child, "repeat"):
                warnings.append(
                    MusicXmlWarning(
                        code="unsupported-repeat",
                        message="repeat barlines are recorded as unsupported and ignored in this phase",
                        source_path=source_path,
                    )
                )
            elif name == "barline" and _has_descendant(child, "ending"):
                warnings.append(
                    MusicXmlWarning(
                        code="unsupported-ending",
                        message="alternate endings are recorded as unsupported and ignored in this phase",
                        source_path=source_path,
                    )
                )

        expected_divs = None
        if current_time is not None:
            val = Fraction(current_time.numerator * current_divisions * 4, current_time.denominator)
            expected_divs = float(val)

        unbalanced_bf = False
        if has_backup_or_forward and expected_divs is not None and cursor != expected_divs:
            if not any(note.duration_zero or note.duration_missing for note in notes):
                unbalanced_bf = True

        backup_past_zero = "musicxml_backup_cursor_before_measure_start" in voice_cursor_diagnostics.secondary_reasons
        backup_rewinds_before_measure_start = backup_past_zero
        forward_exceeds_measure_end = "musicxml_forward_cursor_after_measure_end" in voice_cursor_diagnostics.secondary_reasons

        measures.append(
            MusicXmlMeasure(
                index=measure_index,
                number=measure_number,
                divisions=current_divisions,
                time_signature=current_time,
                key_fifths=current_key,
                notes=notes,
                harmonies=harmonies,
                divisions_missing=not has_divisions_defined,
                divisions_changed_mid_measure=divisions_changed_mid_measure,
                backup_forward_risk=backup_past_zero,
                unbalanced_backup_forward=unbalanced_bf,
                backup_rewinds_before_measure_start=backup_rewinds_before_measure_start,
                forward_exceeds_measure_end=forward_exceeds_measure_end,
                backup_forward_count=voice_cursor_diagnostics.backup_count + voice_cursor_diagnostics.forward_count,
                voice_cursor_diagnostics=voice_cursor_diagnostics,
            )
        )

    return MusicXmlPart(id=part_id, name=part_name, measures=measures)


def _is_supported_tuplet(tuplet: MusicXmlTuplet | None) -> bool:
    if tuplet is None:
        return True
    return (
        (tuplet.actual_notes == 3 and tuplet.normal_notes == 2)
        or (tuplet.actual_notes == 4 and tuplet.normal_notes == 3)
        or (tuplet.actual_notes == 5 and tuplet.normal_notes == 3)
    )


def _parse_note(
    node: ET.Element,
    *,
    part_id: str,
    measure_index: int,
    measure_number: str,
    note_index: int,
    cursor: int,
    last_note_onset: int,
    warnings: list[MusicXmlWarning],
) -> tuple[MusicXmlNote, int, int]:
    chord = _child(node, "chord") is not None
    grace_node = _child(node, "grace")
    grace = grace_node is not None
    grace_slash = False
    if grace_node is not None:
        grace_slash = grace_node.get("slash") == "yes"
    onset = last_note_onset if chord else cursor
    duration = _duration(node)
    voice = _int_text(_child(node, "voice"), default=1)
    staff = _optional_int_text(_child(node, "staff"))
    source_path = f"/score-partwise/part[@id='{part_id}']/measure[{measure_index}]/note[{note_index}]"

    tuplet = _tuplet(node)
    duration_missing = not grace and _child(node, "duration") is None
    duration_zero = not grace and _child(node, "duration") is not None and duration == 0
    tuplet_unsupported = tuplet is not None and not _is_supported_tuplet(tuplet)


    note = MusicXmlNote(
        id=f"mx-{part_id}-m{measure_index}-n{note_index}",
        part_id=part_id,
        measure_index=measure_index,
        measure_number=measure_number,
        note_index=note_index,
        onset_divisions=onset,
        duration_divisions=duration,
        voice=voice,
        staff=staff,
        is_rest=_child(node, "rest") is not None,
        pitch=_pitch(node),
        chord=chord,
        ties=_ties(node),
        notated_type=_text(_child(node, "type")),
        dots=len(_children(node, "dot")),
        tuplet=tuplet,
        grace=grace,
        grace_slash=grace_slash,
        techniques=_techniques(node, source_path, warnings),
        source_path=source_path,
        duration_missing=duration_missing,
        duration_zero=duration_zero,
        tuplet_unsupported=tuplet_unsupported,
    )

    if not chord and duration > 0 and not grace:
        cursor += duration
    if not chord:
        last_note_onset = onset

    return note, cursor, last_note_onset


def _parse_harmony(
    node: ET.Element,
    *,
    part_id: str,
    measure_index: int,
    measure_number: str,
    harmony_index: int,
    cursor: int,
) -> MusicXmlHarmony:
    root = _child(node, "root")
    root_step = "C"
    root_alter = 0
    if root is not None:
        root_step = (_text(_child(root, "root-step")) or "C").upper()
        root_alter = _optional_int_text(_child(root, "root-alter")) or 0

    kind_node = _child(node, "kind")
    kind = _text(kind_node)
    kind_text = kind_node.get("text") if kind_node is not None else None
    offset = _optional_int_text(_child(node, "offset")) or 0
    accidental = "#" if root_alter == 1 else "b" if root_alter == -1 else f"{root_alter:+d}" if root_alter else ""
    text = f"{root_step}{accidental}{kind_text or _harmony_kind_suffix(kind)}"
    source_path = f"/score-partwise/part[@id='{part_id}']/measure[{measure_index}]/harmony[{harmony_index}]"
    return MusicXmlHarmony(
        id=f"mx-{part_id}-m{measure_index}-h{harmony_index}",
        part_id=part_id,
        measure_index=measure_index,
        measure_number=measure_number,
        onset_divisions=max(0, cursor + offset),
        root_step=root_step,
        root_alter=root_alter,
        kind=kind,
        text=text,
        source_path=source_path,
    )


def _metadata(root: ET.Element, xml_path: Path) -> MusicXmlMetadata:
    title = _text(_child(root, "movement-title"))
    work = _child(root, "work")
    if not title and work is not None:
        title = _text(_child(work, "work-title"))

    identification = _child(root, "identification")
    composer = None
    lyricist = None
    rights = None
    if identification is not None:
        for creator in _children(identification, "creator"):
            creator_type = creator.get("type")
            if creator_type == "composer":
                composer = _text(creator)
            elif creator_type == "lyricist":
                lyricist = _text(creator)
        rights = _text(_child(identification, "rights"))

    return MusicXmlMetadata(
        title=title or xml_path.stem,
        composer=composer,
        lyricist=lyricist,
        rights=rights,
        source=str(xml_path),
    )


def _part_names(root: ET.Element) -> dict[str, str]:
    part_list = _child(root, "part-list")
    if part_list is None:
        return {}
    names = {}
    for score_part in _children(part_list, "score-part"):
        part_id = score_part.get("id")
        if part_id:
            names[part_id] = _text(_child(score_part, "part-name")) or part_id
    return names


def _parse_divisions(attributes: ET.Element, current: int) -> int:
    divisions = _optional_int_text(_child(attributes, "divisions"))
    return divisions if divisions and divisions > 0 else current


def _parse_time_signature(attributes: ET.Element, current: TimeSignature) -> TimeSignature:
    time_node = _child(attributes, "time")
    if time_node is None:
        return current
    beats = _optional_int_text(_child(time_node, "beats"))
    beat_type = _optional_int_text(_child(time_node, "beat-type"))
    if beats is None or beat_type is None:
        return current
    return TimeSignature(numerator=beats, denominator=beat_type)


def _parse_key(attributes: ET.Element, current: int | None) -> int | None:
    key_node = _child(attributes, "key")
    if key_node is None:
        return current
    fifths = _optional_int_text(_child(key_node, "fifths"))
    return fifths if fifths is not None else current


def _tempo(root: ET.Element) -> int | None:
    for direction in _descendants(root, "direction"):
        sound = _child(direction, "sound")
        if sound is not None and sound.get("tempo"):
            return round(float(sound.get("tempo", "0")))
        metronome = _child(direction, "metronome") or _first_descendant(direction, "metronome")
        if metronome is not None:
            per_minute = _optional_int_text(_child(metronome, "per-minute"))
            if per_minute is not None:
                return per_minute
    for sound in _descendants(root, "sound"):
        if sound.get("tempo"):
            return round(float(sound.get("tempo", "0")))
    return None


def _pitch(note: ET.Element) -> MusicXmlPitch | None:
    pitch_node = _child(note, "pitch")
    if pitch_node is None:
        return None
    step = (_text(_child(pitch_node, "step")) or "C").upper()
    alter = _optional_int_text(_child(pitch_node, "alter")) or 0
    octave = _optional_int_text(_child(pitch_node, "octave")) or 4
    midi = (octave + 1) * 12 + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step] + alter
    accidental = "#" if alter == 1 else "b" if alter == -1 else f"{alter:+d}" if alter else ""
    return MusicXmlPitch(step=step, alter=alter, octave=octave, midi=midi, name=f"{step}{accidental}{octave}")


def _ties(note: ET.Element) -> list[Literal["start", "stop"]]:
    values: list[Literal["start", "stop"]] = []
    for tie in _children(note, "tie"):
        tie_type = tie.get("type")
        if tie_type in ("start", "stop") and tie_type not in values:
            values.append(tie_type)
    notations = _child(note, "notations")
    if notations is not None:
        for tied in _children(notations, "tied"):
            tied_type = tied.get("type")
            if tied_type in ("start", "stop") and tied_type not in values:
                values.append(tied_type)
    return values


def _tuplet(note: ET.Element) -> MusicXmlTuplet | None:
    time_modification = _child(note, "time-modification")
    if time_modification is None:
        return None
    actual = _optional_int_text(_child(time_modification, "actual-notes"))
    normal = _optional_int_text(_child(time_modification, "normal-notes"))
    if actual is None or normal is None:
        return None
    return MusicXmlTuplet(actual_notes=actual, normal_notes=normal)


def _techniques(
    note: ET.Element,
    source_path: str,
    warnings: list[MusicXmlWarning],
) -> list[MusicXmlTechnique]:
    notations = _child(note, "notations")
    if notations is None:
        return []

    techniques: list[MusicXmlTechnique] = []
    for slide in _children(notations, "slide"):
        techniques.append(
            MusicXmlTechnique(
                kind="slide",
                state=_technique_state(slide.get("type")),
                text=_text(slide),
                source_path=f"{source_path}/notations/slide",
            )
        )
    for slur in _children(notations, "slur"):
        techniques.append(
            MusicXmlTechnique(
                kind="slur",
                state=_technique_state(slur.get("type")),
                text=_text(slur),
                source_path=f"{source_path}/notations/slur",
            )
        )

    ornaments = _child(notations, "ornaments")
    if ornaments is not None and _child(ornaments, "wavy-line") is not None:
        techniques.append(MusicXmlTechnique(kind="vibrato", source_path=f"{source_path}/notations/ornaments/wavy-line"))

    technical = _child(notations, "technical")
    if technical is None:
        return techniques

    for child in list(technical):
        name = _local_name(child.tag)
        child_path = f"{source_path}/notations/technical/{name}"
        if name in {"string", "fret", "fingering"}:
            continue
        if name in {"hammer-on", "pull-off"}:
            techniques.append(
                MusicXmlTechnique(
                    kind=name,
                    state=_technique_state(child.get("type")),
                    text=_text(child),
                    source_path=child_path,
                )
            )
        elif name == "bend":
            bend_alter = _optional_float_text(_child(child, "bend-alter"))
            techniques.append(
                MusicXmlTechnique(
                    kind="bend",
                    semitones=bend_alter,
                    text=_text(child),
                    source_path=child_path,
                )
            )
        elif name == "other-technical" and ((_text(child) or "").lower().startswith(("vib", "~"))):
            techniques.append(MusicXmlTechnique(kind="vibrato", text=_text(child), source_path=child_path))
        else:
            warnings.append(
                MusicXmlWarning(
                    code="unsupported-technical-notation",
                    message=f"MusicXML technical notation '{name}' is preserved as unsupported.",
                    source_path=child_path,
                )
            )
            techniques.append(
                MusicXmlTechnique(
                    kind="unsupported",
                    text=name if _text(child) is None else _text(child),
                    source_path=child_path,
                )
            )
    return techniques


def _technique_state(value: str | None) -> Literal["start", "stop", "continue", "single", "unknown"]:
    if value in {"start", "stop", "continue", "single"}:
        return value
    return "unknown"


def _harmony_kind_suffix(kind: str | None) -> str:
    if kind is None:
        return ""
    mapping = {
        "major": "",
        "minor": "m",
        "dominant": "7",
        "major-seventh": "maj7",
        "minor-seventh": "m7",
        "diminished": "dim",
        "augmented": "aug",
        "suspended-fourth": "sus4",
        "suspended-second": "sus2",
    }
    return mapping.get(kind, kind)


def _expected_measure_duration_divisions(measure: MusicXmlMeasure) -> float | None:
    value = Fraction(measure.time_signature.numerator * measure.divisions * 4, measure.time_signature.denominator)
    return float(value)


def _measure_timing_groups(measure: MusicXmlMeasure) -> list[list[MusicXmlNote]]:
    groups: dict[tuple[int, int, int, bool], list[MusicXmlNote]] = {}
    for note in measure.notes:
        key = (note.onset_divisions, note.voice, note.duration_divisions, note.is_rest)
        groups.setdefault(key, []).append(note)
    return [
        group
        for _, group in sorted(groups.items(), key=lambda item: (item[0][1], item[0][0], item[0][2], item[1][0].note_index))
    ]


def _duration(node: ET.Element) -> int:
    return _int_text(_child(node, "duration"), default=0)


def _int_text(node: ET.Element | None, default: int) -> int:
    value = _optional_int_text(node)
    return default if value is None else value


def _optional_int_text(node: ET.Element | None) -> int | None:
    value = _text(node)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_float_text(node: ET.Element | None) -> float | None:
    value = _text(node)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _child(node: ET.Element, name: str) -> ET.Element | None:
    for child in list(node):
        if _local_name(child.tag) == name:
            return child
    return None


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if _local_name(child.tag) == name]


def _descendants(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node.iter() if _local_name(child.tag) == name]


def _first_descendant(node: ET.Element, name: str) -> ET.Element | None:
    for child in node.iter():
        if child is not node and _local_name(child.tag) == name:
            return child
    return None


def _has_descendant(node: ET.Element, name: str) -> bool:
    return any(_local_name(child.tag) == name for child in node.iter())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def classify_musicxml_voice_duplication(part: MusicXmlPart) -> tuple[list[tuple[int, int]], list[tuple[int, int, str]]]:
    """
    Classifies voice pairs in a part.
    Returns:
      - confirmed_pairs: list of confirmed (notation_voice, tab_voice)
      - warnings_to_log: list of (v1, v2, code) warnings
    """
    from collections import Counter
    voices = sorted(list({note.voice for measure in part.measures for note in measure.notes if not note.grace}))

    pair_statuses = {}
    warnings_to_log = []

    # 1. Evaluate each pair (v1, v2)
    for i in range(len(voices)):
        for j in range(i + 1, len(voices)):
            v1 = voices[i]
            v2 = voices[j]

            # Active measures with pitched notes for each voice
            active_m_v1 = set()
            active_m_v2 = set()
            for measure in part.measures:
                if any(n.voice == v1 and not n.grace and not n.is_rest and n.pitch is not None for n in measure.notes):
                    active_m_v1.add(measure.index)
                if any(n.voice == v2 and not n.grace and not n.is_rest and n.pitch is not None for n in measure.notes):
                    active_m_v2.add(measure.index)

            if not active_m_v1 or not active_m_v2:
                # One or both voices not active at all in part
                pair_statuses[(v1, v2)] = "duplicate_staff_tab_rejected"
                continue

            shared_measures = active_m_v1.intersection(active_m_v2)
            if not shared_measures:
                pair_statuses[(v1, v2)] = "independent_polyphony"
                continue

            # Same pitched note count, onsets, durations, and stable pitch offset
            has_timing_errors = False
            chord_stack_confusion = False
            perfect_matches = 0
            observed_diffs = set()

            for m_idx in sorted(list(shared_measures)):
                measure = part.measures[m_idx - 1]
                notes1 = [n for n in measure.notes if n.voice == v1 and not n.grace and not n.is_rest and n.pitch is not None]
                notes2 = [n for n in measure.notes if n.voice == v2 and not n.grace and not n.is_rest and n.pitch is not None]

                # Check same-voice timing overlaps inside either voice
                for n_list in (notes1, notes2):
                    for a_idx in range(len(n_list)):
                        for b_idx in range(a_idx + 1, len(n_list)):
                            na = n_list[a_idx]
                            nb = n_list[b_idx]
                            if max(na.onset_divisions, nb.onset_divisions) < min(na.onset_divisions + na.duration_divisions, nb.onset_divisions + nb.duration_divisions):
                                has_timing_errors = True

                if has_timing_errors:
                    break

                # Check for chord stack count confusion
                onsets1 = [n.onset_divisions for n in notes1]
                onsets2 = [n.onset_divisions for n in notes2]
                if len(set(onsets1)) != len(notes1) or len(set(onsets2)) != len(notes2):
                    # We have a chord stack! Check if they have the exact same onset groups
                    groups1 = {}
                    groups2 = {}
                    for n in notes1:
                        groups1.setdefault(n.onset_divisions, []).append(n)
                    for n in notes2:
                        groups2.setdefault(n.onset_divisions, []).append(n)

                    if len(groups1) != len(groups2) or set(groups1.keys()) != set(groups2.keys()):
                        chord_stack_confusion = True
                        break

                    # Within each onset group, check size matches
                    for onset in groups1:
                        g1 = sorted(groups1[onset], key=lambda n: n.pitch.midi if n.pitch else 0)
                        g2 = sorted(groups2[onset], key=lambda n: n.pitch.midi if n.pitch else 0)
                        if len(g1) != len(g2):
                            chord_stack_confusion = True
                            break
                        for n1, n2 in zip(g1, g2):
                            if n1.duration_divisions != n2.duration_divisions:
                                chord_stack_confusion = True
                                break
                            diff = abs(n1.pitch.midi - n2.pitch.midi)
                            if diff not in (0, 12):
                                chord_stack_confusion = True
                                break
                            observed_diffs.add(diff)
                    if chord_stack_confusion:
                        break
                    perfect_matches += 1
                    continue

                # Simple sequence matching
                if len(notes1) != len(notes2):
                    break

                notes1.sort(key=lambda n: n.onset_divisions)
                notes2.sort(key=lambda n: n.onset_divisions)

                match = True
                for idx in range(len(notes1)):
                    n1 = notes1[idx]
                    n2 = notes2[idx]
                    if n1.onset_divisions != n2.onset_divisions or n1.duration_divisions != n2.duration_divisions:
                        match = False
                        break
                    diff = abs(n1.pitch.midi - n2.pitch.midi)
                    if diff not in (0, 12):
                        match = False
                        break
                    observed_diffs.add(diff)

                if match:
                    perfect_matches += 1

            if has_timing_errors or chord_stack_confusion:
                pair_statuses[(v1, v2)] = "duplicate_staff_tab_rejected"
            elif len(observed_diffs) != 1 or next(iter(observed_diffs)) not in (0, 12):
                # Reject if there is no stable, consistent pitch offset across the entire voice pair
                pair_statuses[(v1, v2)] = "duplicate_staff_tab_rejected"
            elif perfect_matches == len(active_m_v1) and perfect_matches == len(active_m_v2):
                pair_statuses[(v1, v2)] = "duplicate_staff_tab_confirmed"
            elif perfect_matches > 0:
                pair_statuses[(v1, v2)] = "duplicate_staff_tab_partial"
            else:
                pair_statuses[(v1, v2)] = "independent_polyphony"

    # 2. Check for multiple competing duplicate matches to prevent ambiguity
    initially_confirmed = [pair for pair, status in pair_statuses.items() if status == "duplicate_staff_tab_confirmed"]
    voice_usage = Counter()
    for v1, v2 in initially_confirmed:
        voice_usage[v1] += 1
        voice_usage[v2] += 1

    confirmed_pairs = []
    competing_voices = {voice for voice, count in voice_usage.items() if count > 1}

    for v1, v2 in initially_confirmed:
        if v1 in competing_voices or v2 in competing_voices:
            # Downgrade competing duplicate matches to rejected/ambiguous!
            pair_statuses[(v1, v2)] = "duplicate_staff_tab_rejected"
            warnings_to_log.append((v1, v2, "musicxml_duplicate_staff_tab_rejected_independent_polyphony"))
        else:
            confirmed_pairs.append((v1, v2))

    # Add warnings for other categories
    for pair, status in pair_statuses.items():
        v1, v2 = pair
        if status == "duplicate_staff_tab_partial":
            warnings_to_log.append((v1, v2, "musicxml_duplicate_staff_tab_partial_match"))
        elif status == "duplicate_staff_tab_rejected" and pair not in initially_confirmed:
            warnings_to_log.append((v1, v2, "musicxml_duplicate_staff_tab_not_applied_low_confidence"))
        elif status == "independent_polyphony":
            warnings_to_log.append((v1, v2, "musicxml_duplicate_staff_tab_rejected_independent_polyphony"))

    return confirmed_pairs, warnings_to_log


def deduplicate_suspected_staff_tab_voices(musicxml: MusicXmlImport) -> MusicXmlImport:
    """
    Returns a deduplicated deep copy of the MusicXmlImport.
    Preserves authoritative rhythmic timelines, merges TAB playability details
    into the notation notes, and suppresses duplicate TAB notes from active timing streams.
    """
    dedup_musicxml = musicxml.model_copy(deep=True)

    for part in dedup_musicxml.parts:
        confirmed_pairs, warnings = classify_musicxml_voice_duplication(part)

        # Log voice pair warnings
        for v1, v2, code in warnings:
            dedup_musicxml.warnings.append(
                MusicXmlWarning(
                    code=code,
                    message=f"Duplicate staff/TAB check returned code '{code}' for voice {v1} and voice {v2}.",
                    severity="warning" if "rejected" in code or "partial" in code or "low_confidence" in code else "info",
                    source_path=dedup_musicxml.source_path,
                )
            )

        for v1, v2 in confirmed_pairs:
            # Choose notation/TAB roles by staff evidence, not min/max voice number
            v1_staves = {note.staff for measure in part.measures for note in measure.notes if note.voice == v1 and note.staff is not None}
            v2_staves = {note.staff for measure in part.measures for note in measure.notes if note.voice == v2 and note.staff is not None}

            if 1 in v1_staves and 2 in v2_staves:
                notation_voice = v1
                tab_voice = v2
            elif 2 in v1_staves and 1 in v2_staves:
                notation_voice = v2
                tab_voice = v1
            else:
                notation_voice = min(v1, v2)
                tab_voice = max(v1, v2)

            # Emit detection and preservation warnings
            dedup_musicxml.warnings.append(
                MusicXmlWarning(
                    code="musicxml_duplicate_staff_tab_detected",
                    message=f"Duplicate staff/TAB voices detected: voice {notation_voice} and voice {tab_voice}.",
                    severity="info",
                    source_path=dedup_musicxml.source_path,
                )
            )
            dedup_musicxml.warnings.append(
                MusicXmlWarning(
                    code="musicxml_duplicate_staff_tab_dedup_applied",
                    message=f"Deduplication applied successfully for voice {notation_voice} and voice {tab_voice}.",
                    severity="info",
                    source_path=dedup_musicxml.source_path,
                )
            )
            dedup_musicxml.warnings.append(
                MusicXmlWarning(
                    code="musicxml_duplicate_staff_tab_preserved_rhythm_authority",
                    message=f"Preserved Voice {notation_voice} as the authoritative rhythmic timeline.",
                    severity="info",
                    source_path=dedup_musicxml.source_path,
                )
            )
            dedup_musicxml.warnings.append(
                MusicXmlWarning(
                    code="musicxml_duplicate_staff_tab_preserved_tab_evidence",
                    message=f"Preserved Voice {tab_voice} fret and playability evidence.",
                    severity="info",
                    source_path=dedup_musicxml.source_path,
                )
            )

            # Merge notes measure by measure
            for measure in part.measures:
                # Suppress all duplicate TAB rests/events first
                for n in measure.notes:
                    if n.voice == tab_voice:
                        n.is_suppressed = True

                notes1 = [n for n in measure.notes if n.voice == notation_voice and not n.grace and not n.is_rest]
                notes2 = [n for n in measure.notes if n.voice == tab_voice and not n.grace and not n.is_rest]

                if notes1 and notes2:
                    # Chords or simple notes: sort by onset and pitch to align perfectly
                    notes1.sort(key=lambda n: (n.onset_divisions, n.pitch.midi if n.pitch else 0))
                    notes2.sort(key=lambda n: (n.onset_divisions, n.pitch.midi if n.pitch else 0))

                    for idx in range(min(len(notes1), len(notes2))):
                        n1 = notes1[idx]
                        n2 = notes2[idx]

                        # Merge techniques
                        existing_tech_kinds = {t.kind for t in n1.techniques}
                        for tech in n2.techniques:
                            if tech.kind not in existing_tech_kinds:
                                n1.techniques.append(tech)

                        # Merge ties
                        for tie in n2.ties:
                            if tie not in n1.ties:
                                n1.ties.append(tie)

                        # Save dedup tab note fields on the notation note n1 to preserve evidence
                        n1.dedup_tab_note_id = n2.id
                        n1.dedup_tab_note_voice = n2.voice
                        n1.dedup_tab_note_staff = n2.staff
                        n1.dedup_tab_note_techniques = n2.techniques
                        n1.dedup_tab_note_source_path = n2.source_path
                        if n2.pitch:
                            n1.dedup_tab_note_pitch_midi = n2.pitch.midi
                            n1.dedup_tab_note_pitch_name = n2.pitch.name
                        n1.dedup_tab_note_ties = n2.ties
                        n1.dedup_tab_note_onset_divisions = n2.onset_divisions
                        n1.dedup_tab_note_duration_divisions = n2.duration_divisions

                        # Suppress duplicate TAB voice notes from active ScoreIR/timing stream
                        n2.is_suppressed = True

                # Merge grace notes sequentially
                grace1 = [n for n in measure.notes if n.voice == notation_voice and n.grace and not n.is_rest]
                grace2 = [n for n in measure.notes if n.voice == tab_voice and n.grace and not n.is_rest]
                if grace1 and grace2:
                    grace1.sort(key=lambda n: n.note_index)
                    grace2.sort(key=lambda n: n.note_index)
                    for idx in range(min(len(grace1), len(grace2))):
                        gn1 = grace1[idx]
                        gn2 = grace2[idx]

                        # Merge techniques
                        existing_tech_kinds = {t.kind for t in gn1.techniques}
                        for tech in gn2.techniques:
                            if tech.kind not in existing_tech_kinds:
                                gn1.techniques.append(tech)

                        # Merge ties
                        for tie in gn2.ties:
                            if tie not in gn1.ties:
                                gn1.ties.append(tie)

                        # Save dedup tab note fields on the notation grace note gn1 to preserve evidence
                        gn1.dedup_tab_note_id = gn2.id
                        gn1.dedup_tab_note_voice = gn2.voice
                        gn1.dedup_tab_note_staff = gn2.staff
                        gn1.dedup_tab_note_techniques = gn2.techniques
                        gn1.dedup_tab_note_source_path = gn2.source_path
                        if gn2.pitch:
                            gn1.dedup_tab_note_pitch_midi = gn2.pitch.midi
                            gn1.dedup_tab_note_pitch_name = gn2.pitch.name
                        gn1.dedup_tab_note_ties = gn2.ties
                        gn1.dedup_tab_note_onset_divisions = gn2.onset_divisions
                        gn1.dedup_tab_note_duration_divisions = gn2.duration_divisions

                        gn1.grace_slash = gn1.grace_slash or gn2.grace_slash

                        # Suppress duplicate TAB voice grace notes from active ScoreIR/timing stream
                        gn2.is_suppressed = True

    return dedup_musicxml
