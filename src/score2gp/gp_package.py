from __future__ import annotations

import json
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .gpif import build_gpif, gpif_warnings
from .version_adapter import adapt_gpif, get_version_file_content
from .ir import (
    ScoreIR, ScoreBooklet, Track, Tuning, TuningString, Mixer, SoundConfig,
    TrackLayoutPreferences, TrackExpression, TrackAutomation, ScoreLayout,
    Metadata, Tempo, TimeSignature, KeySignature, Bar, Event, Note,
    BoundingBox, Provenance, ConversionInfo, MasterMixer, PipelinePresetCascade
)

REQUIRED_MEMBERS = {"VERSION", "Content/score.gpif"}


def write_gp(
    score: ScoreIR | ScoreBooklet,
    out_path: str | Path,
    template: str | Path | None = None,
    target_version: str = "GP7"
) -> list[str]:
    warnings: list[str] = gpif_warnings(score)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    copied: dict[str, bytes] = {}
    if template:
        template_path = Path(template)
        if template_path.exists():
            try:
                with zipfile.ZipFile(template_path, "r") as zin:
                    copied = {name: zin.read(name) for name in zin.namelist() if name != "Content/score.gpif"}
            except zipfile.BadZipFile:
                warnings.append(f"template is not a valid zip package: {template_path}")
        else:
            warnings.append(f"template does not exist: {template_path}")

    copied["VERSION"] = get_version_file_content(target_version)
    copied.setdefault("Content/Preferences.json", b"{}\n")
    copied.setdefault("Content/LayoutConfiguration", b"")
    copied.setdefault("Content/PartConfiguration", b"")
    copied.setdefault("Content/BinaryStylesheet", b"")

    if isinstance(score, ScoreBooklet):
        # Build main/primary score GPIF with Booklet index embedded
        gpif = build_gpif(score)
        gpif = adapt_gpif(gpif, target_version)
        copied["Content/score.gpif"] = gpif

        # Compile sequential movements and page indexing
        start_page = score.pagination.start_page if score.pagination else 1
        movements_list = []
        for idx, s in enumerate(score.scores):
            mov_gpif = build_gpif(s, booklet=score)
            mov_gpif = adapt_gpif(mov_gpif, target_version)
            mov_path = f"Content/movement_{idx + 1}.gpif"
            copied[mov_path] = mov_gpif

            movements_list.append({
                "index": idx + 1,
                "title": s.metadata.title,
                "file": mov_path,
                "start_page": start_page
            })
            pg_count = s.conversion.source_page_count if s.conversion.source_page_count is not None else 1
            start_page += pg_count

        # Write the Booklet index JSON
        booklet_index = {
            "booklet_title": score.booklet_title,
            "metadata": score.metadata.model_dump(exclude_none=True),
            "pagination": score.pagination.model_dump(exclude_none=True) if score.pagination else None,
            "movements": movements_list
        }
        copied["Content/booklet_index.json"] = json.dumps(booklet_index, indent=2).encode("utf-8")
    else:
        gpif = build_gpif(score)
        gpif = adapt_gpif(gpif, target_version)
        copied["Content/score.gpif"] = gpif

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        directories = {"Content/"}
        for directory in sorted(directories):
            zout.writestr(directory, b"")
        for name, data in copied.items():
            if not name.endswith("/"):
                zout.writestr(name, data)

    return warnings


def validate_gp(path: str | Path) -> dict[str, Any]:
    gp = Path(path)
    result: dict[str, Any] = {
        "path": str(gp),
        "is_zip": False,
        "required_members": {},
        "xml_well_formed": False,
        "errors": [],
    }
    try:
        with zipfile.ZipFile(gp, "r") as zf:
            result["is_zip"] = True
            names = set(zf.namelist())
            result["members"] = sorted(names)
            result["required_members"] = {name: name in names for name in sorted(REQUIRED_MEMBERS)}
            if not all(result["required_members"].values()):
                result["errors"].append("missing required GP package members")
            try:
                ET.fromstring(zf.read("Content/score.gpif"))
                result["xml_well_formed"] = True
            except Exception as exc:  # noqa: BLE001 - report parser detail to caller
                result["errors"].append(f"GPIF XML is not well formed: {exc}")
    except zipfile.BadZipFile:
        result["errors"].append("not a zip package")
    except FileNotFoundError:
        result["errors"].append("file does not exist")
    return result


def inspect_gp(path: str | Path) -> dict[str, Any]:
    gp = Path(path)
    validation = validate_gp(gp)
    summary: dict[str, Any] = {
        "path": str(gp),
        "package": validation,
        "gp_version": None,
        "tracks": [],
        "tunings": [],
        "tempo": None,
        "time_signatures": [],
        "bar_count": 0,
        "note_count": 0,
        "chord_symbols": [],
        "techniques": [],
    }
    if validation["errors"]:
        return summary

    with zipfile.ZipFile(gp, "r") as zf:
        if "VERSION" in zf.namelist():
            summary["gp_version"] = zf.read("VERSION").decode("utf-8", errors="replace").strip()
        root = ET.fromstring(zf.read("Content/score.gpif"))

    summary.update(_summarize_gpif(root))
    return summary


def compare_gp(expected: str | Path, actual: str | Path) -> dict[str, Any]:
    expected_summary = inspect_gp(expected)
    actual_summary = inspect_gp(actual)
    fields = [
        "gp_version",
        "tracks",
        "tempo",
        "time_signatures",
        "bar_count",
        "note_count",
        "chord_symbols",
        "techniques",
    ]
    differences = {
        field: {"expected": expected_summary.get(field), "actual": actual_summary.get(field)}
        for field in fields
        if expected_summary.get(field) != actual_summary.get(field)
    }
    return {
        "expected": str(expected),
        "actual": str(actual),
        "matches": not differences,
        "differences": differences,
    }


def _summarize_gpif(root: ET.Element) -> dict[str, Any]:
    tracks: list[str] = []
    tunings: list[dict[str, Any]] = []
    for track in root.findall(".//Track"):
        name = _first_text(track, ["Name", "Name/Name"]) or track.get("name") or track.get("id") or "unknown"
        tracks.append(name)
        strings = []
        for string in track.findall(".//String"):
            if string.get("pitch") or string.get("name"):
                strings.append(
                    {
                        "number": string.get("number"),
                        "pitch": string.get("pitch") or string.text,
                        "name": string.get("name"),
                    }
                )

        has_staff_tuning = False
        for staff in track.findall(".//Staff"):
            pitches_node = staff.find(".//Property[@name='Tuning']/Pitches")
            if pitches_node is not None and pitches_node.text:
                pitches = pitches_node.text.split()
                staff_name = _first_text(staff, ["Name"]) or _known_tuning_name(pitches)
                staff_strings = sorted(
                    [
                        {"number": str(len(pitches) - index), "pitch": pitch, "name": None}
                        for index, pitch in enumerate(pitches)
                    ],
                    key=lambda s: int(s["number"])
                )
                if staff_strings:
                    tunings.append({"track": name, "name": staff_name, "strings": staff_strings})
                    has_staff_tuning = True

        if strings and not has_staff_tuning:
            tunings.append({"track": name, "strings": strings})

    tempo = _first_text(root, [".//Tempo/Value", ".//Tempo", ".//Tempos/Tempo/Value"])
    if tempo is None:
        for automation in root.findall(".//Automation"):
            if _first_text(automation, ["Type"]) == "Tempo":
                value = _first_text(automation, ["Value"])
                if value:
                    tempo = value.split()[0]
                    break
    time_signatures = []
    for node in root.findall(".//MasterBar"):
        value = _first_text(node, ["Time", "TimeSignature"])
        if value:
            time_signatures.append(value)

    chord_symbols = sorted(_chord_symbols(root))
    techniques = sorted(
        {
            node.get("name") or "".join(node.itertext()).strip()
            for node in root.findall(".//Technique")
            if (node.get("name") or "".join(node.itertext()).strip())
        }
    )
    notes = root.findall(".//Note")
    bars = root.findall(".//Bar")
    if not bars:
        bars = root.findall(".//MasterBar")

    return {
        "tracks": tracks,
        "tunings": tunings,
        "tempo": tempo,
        "time_signatures": sorted(set(time_signatures)),
        "bar_count": len(bars),
        "note_count": len(notes),
        "chord_symbols": chord_symbols,
        "techniques": techniques,
    }


def _first_text(root: ET.Element, paths: list[str]) -> str | None:
    for path in paths:
        node = root.find(path)
        if node is not None:
            text = "".join(node.itertext()).strip()
            if text:
                return text
    return None


def _chord_symbols(root: ET.Element) -> set[str]:
    symbols: set[str] = set()
    for node in root.findall(".//Chord"):
        text = "".join(node.itertext()).strip()
        if text and not text.isdigit():
            symbols.add(text)
    for item in root.findall(".//Property[@name='ChordCollection']//Item"):
        name = item.get("name")
        if name:
            symbols.add(name)
    return symbols


def _known_tuning_name(pitches: list[str]) -> str | None:
    known = {
        ("40", "45", "50", "55", "59", "64"): "Standard guitar",
        ("40", "47", "52", "56", "59", "64"): "Open E",
    }
    return known.get(tuple(pitches))


def dumps_summary(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)


def extract_score_ir_from_gp(path: str | Path) -> ScoreIR:
    gp_path = Path(path)
    with zipfile.ZipFile(gp_path, "r") as zf:
        xml_content = zf.read("Content/score.gpif")
        root = ET.fromstring(xml_content)

    # 1. Parse Metadata
    meta_node = root.find(".//Metadata")
    metadata = Metadata()
    if meta_node is not None:
        metadata.title = _first_text(meta_node, ["Title"]) or "Untitled"
        metadata.artist = _first_text(meta_node, ["Artist"])
        metadata.composer = _first_text(meta_node, ["Composer"])
        metadata.album = _first_text(meta_node, ["Album"])
        metadata.transcriber = _first_text(meta_node, ["Transcriber"])
        metadata.copyright = _first_text(meta_node, ["Copyright"])

    # 2. Parse Tempo
    tempo_node = root.find(".//Tempo")
    bpm = 120
    tempo_text = None
    if tempo_node is not None:
        bpm = int(_first_text(tempo_node, ["Value"]) or 120)
        tempo_text = _first_text(tempo_node, ["Text"])
    tempo = Tempo(bpm=bpm, text=tempo_text)

    # 3. Parse Tracks
    tracks: list[Track] = []
    for track_node in root.findall(".//Tracks/Track"):
        track_id = track_node.get("id") or "unknown"
        name = _first_text(track_node, ["Name"]) or "Track"
        instrument = _first_text(track_node, ["Instrument"]) or "guitar"
        capo = int(_first_text(track_node, ["Capo"]) or 0)
        color = _first_text(track_node, ["Color"])

        # Tuning
        tuning_node = track_node.find("Tuning")
        tuning_name = "Standard"
        if tuning_node is not None:
            tuning_name = tuning_node.get("name") or "Standard"

        strings: list[TuningString] = []
        if tuning_node is not None:
            for s_node in tuning_node.findall("String"):
                num = int(s_node.get("number") or 1)
                pitch = int(s_node.get("pitch") or 0)
                s_name = s_node.get("name") or ""
                strings.append(TuningString(number=num, pitch=pitch, name=s_name))

        # Staff properties for Balance/FineTuning
        staff_node = track_node.find(".//Staff")
        if staff_node is not None:
            tuning_prop = staff_node.find(".//Property[@name='Tuning']")
            if tuning_prop is not None:
                balance_node = tuning_prop.find("Balance")
                finetuning_node = tuning_prop.find("FineTuning")
                strings.sort(key=lambda s: s.number, reverse=True)
                if balance_node is not None and balance_node.text:
                    balances = [float(b) for b in balance_node.text.split()]
                    for s, bal in zip(strings, balances):
                        if bal != 0.0:
                            s.volume_offset = bal
                if finetuning_node is not None and finetuning_node.text:
                    finetunes = [float(f) for f in finetuning_node.text.split()]
                    for s, ft in zip(strings, finetunes):
                        if ft != 0.0:
                            s.fine_tune = ft
                strings.sort(key=lambda s: s.number)

        tuning = Tuning(name=tuning_name, strings=strings)

        # Mixer
        mixer = None
        mixer_node = track_node.find("Mixer")
        if mixer_node is not None:
            vol = float(_first_text(mixer_node, ["Volume"]) or 100) / 100.0
            pan = (float(_first_text(mixer_node, ["Pan"]) or 50) / 50.0) - 1.0
            mute = _first_text(mixer_node, ["Mute"]) == "true"
            solo = _first_text(mixer_node, ["Solo"]) == "true"
            mixer = Mixer(volume=vol, pan=pan, mute=mute, solo=solo)

        # Expressions
        expressions = None
        expr_texts_node = track_node.find("ExpressionTexts")
        if expr_texts_node is not None:
            expressions = []
            for expr_node in expr_texts_node.findall("ExpressionText"):
                bar_idx = int(expr_node.get("measure") or 1)
                text_val = expr_node.text or ""
                expressions.append(TrackExpression(bar_index=bar_idx, text=text_val))

        # Automations
        automations = None
        automations_node = track_node.find("Automations")
        if automations_node is not None:
            automations = []
            for auto_node in automations_node.findall("Automation"):
                auto_type = auto_node.get("type") or "Volume"
                for pt_node in auto_node.findall("Point"):
                    bar_idx = int(pt_node.get("measure") or 1)
                    val_val = float(pt_node.get("value") or 0.0)
                    automations.append(TrackAutomation(type=auto_type, bar_index=bar_idx, value=val_val))

        # Layout Preferences
        layout_preferences = None
        tab_only = False
        tab_node = track_node.find("Tablature")
        if tab_node is not None:
            tab_only = _first_text(tab_node, ["TabOnly"]) == "true"

        view_mode = None
        view_node = track_node.find("View")
        if view_node is not None:
            view_mode = (_first_text(view_node, ["Mode"]) or "page").lower()

        stem_dir = None
        line_sz = None
        brackets_vis = None
        stems_vis = None
        line_sz_sys = None

        if staff_node is not None:
            stems_prop = staff_node.find(".//Property[@name='Stems']")
            if stems_prop is not None:
                if _first_text(stems_prop, ["Enable"]) == "true":
                    stem_dir = (_first_text(stems_prop, ["Direction"]) or "auto").lower()
                else:
                    stem_dir = "auto"

            ls_prop = staff_node.find(".//Property[@name='LineSizing']")
            if ls_prop is not None:
                line_sz = (_first_text(ls_prop, ["Size"]) or "standard").lower()

            brackets_prop = staff_node.find(".//Property[@name='Brackets']")
            if brackets_prop is not None:
                brackets_vis = _first_text(brackets_prop, ["Enable"]) == "true"

            stem_vis_prop = staff_node.find(".//Property[@name='StemVisibility']")
            if stem_vis_prop is not None:
                stems_vis = _first_text(stem_vis_prop, ["Enable"]) == "true"

            ls_sys_prop = staff_node.find(".//Property[@name='LineSizingPerSystem']")
            if ls_sys_prop is not None:
                line_sz_sys = (_first_text(ls_sys_prop, ["Size"]) or "standard").lower()

        if any(v is not None for v in (tab_only, stem_dir, line_sz, view_mode, brackets_vis, stems_vis, line_sz_sys)):
            layout_preferences = TrackLayoutPreferences(
                tab_only=tab_only,
                stem_direction=stem_dir,
                line_sizing=line_sz,
                view_mode=view_mode,
                brackets_visible=brackets_vis,
                stems_visible=stems_vis,
                line_sizing_per_system=line_sz_sys
            )

        tab_enabled = True
        if staff_node is not None:
            tab_prop = staff_node.find(".//Property[@name='Tablature']")
            if tab_prop is not None:
                tab_enabled = _first_text(tab_prop, ["Enable"]) == "true"

        tracks.append(
            Track(
                id=track_id,
                name=name,
                instrument=instrument,
                tuning=tuning,
                capo=capo,
                tablature_enabled=tab_enabled,
                mixer=mixer,
                color=color,
                layout_preferences=layout_preferences,
                expressions=expressions,
                automations=automations
            )
        )

    # 4. Parse ScoreLayout
    layout = ScoreLayout()
    master_track_node = root.find(".//MasterTrack")
    if master_track_node is not None:
        tracks_text = _first_text(master_track_node, ["Tracks"])
        if tracks_text:
            layout.track_order = tracks_text.split()

        mm_node = master_track_node.find("Mixer")
        if mm_node is not None:
            vol = float(_first_text(mm_node, ["Volume"]) or 100) / 100.0
            pan = (float(_first_text(mm_node, ["Pan"]) or 50) / 50.0) - 1.0
            reverb = float(_first_text(mm_node, ["Reverb"]) or 0.0)
            chorus = float(_first_text(mm_node, ["Chorus"]) or 0.0)
            layout.master_mixer = MasterMixer(volume=vol, pan=pan, reverb=reverb, chorus=chorus)

        pc_node = master_track_node.find("PresetCascade")
        if pc_node is not None:
            p_name = pc_node.get("presetName") or "standard"
            t_engine = pc_node.get("targetEngine") or "gp7"
            opts = {}
            for opt in pc_node.findall("Option"):
                o_name = opt.get("name")
                o_val = opt.get("value")
                if o_name:
                    try:
                        if "." in o_val:
                            opts[o_name] = float(o_val)
                        else:
                            opts[o_name] = int(o_val)
                    except ValueError:
                        opts[o_name] = o_val
            layout.preset_cascade = PipelinePresetCascade(preset_name=p_name, target_engine=t_engine, options=opts)

    ps_node = root.find(".//PageSetup")
    if ps_node is not None:
        w = float(_first_text(ps_node, ["Width"]) or 210.0)
        h = float(_first_text(ps_node, ["Height"]) or 297.0)
        margin_top = float(_first_text(ps_node, ["MarginTop"]) or 15.0)
        margin_bottom = float(_first_text(ps_node, ["MarginBottom"]) or 15.0)
        margin_left = float(_first_text(ps_node, ["MarginLeft"]) or 15.0)
        margin_right = float(_first_text(ps_node, ["MarginRight"]) or 15.0)
        scale = float(_first_text(ps_node, ["Scale"]) or 1.0)

        from .ir import PageSetup, PageMargins
        layout.page_setup = PageSetup(
            width=w,
            height=h,
            margins=PageMargins(top=margin_top, bottom=margin_bottom, left=margin_left, right=margin_right),
            scale=scale
        )

    # 5. Parse Bars and Events
    bars: list[Bar] = []
    master_bars_node = root.find(".//MasterBars")
    mb_map = {}
    if master_bars_node is not None:
        for mb_node in master_bars_node.findall("MasterBar"):
            idx = int(mb_node.get("index") or 1)
            time_str = _first_text(mb_node, ["Time"]) or "4/4"
            num, den = map(int, time_str.split("/"))
            key_sig = None
            key_node = mb_node.find("Key")
            if key_node is not None:
                fifths = int(_first_text(key_node, ["Fifths"]) or 0)
                mode = _first_text(key_node, ["Mode"]) or "major"
                key_sig = KeySignature(fifths=fifths, mode=mode)
            mb_map[idx] = (num, den, key_sig)

    bars_node = root.find(".//Bars")
    if bars_node is not None:
        for bar_node in bars_node.findall("Bar"):
            idx = int(bar_node.get("index") or 1)
            num, den, key_sig = mb_map.get(idx, (4, 4, None))
            events: list[Event] = []
            for ev_node in bar_node.findall(".//Event"):
                ev_id = ev_node.get("id") or "e"
                tr_id = ev_node.get("track") or "t"
                rest = ev_node.get("rest") == "true"
                voice = int(ev_node.get("voice") or 0) + 1
                pos_frac = ev_node.get("position") or "0"
                dur_frac = ev_node.get("duration") or "1/2"

                pos = int(Fraction(pos_frac) * 960 * 4)
                dur = int(Fraction(dur_frac) * 960 * 4)

                from .ir import Timing
                timing = Timing(bar_index=idx, onset_ticks=pos, duration_ticks=dur, voice=voice)
                notes: list[Note] = []
                for n_node in ev_node.findall(".//Note"):
                    string = int(n_node.get("string") or 1)
                    fret = int(n_node.get("fret") or 0)
                    pitch = int(n_node.get("pitch") or 0)
                    notes.append(Note(string=string, fret=fret, pitch=pitch))
                events.append(Event(id=ev_id, track_id=tr_id, timing=timing, notes=notes, is_rest=rest))

            bars.append(
                Bar(
                    index=idx,
                    time_signature=TimeSignature(numerator=num, denominator=den),
                    key_signature=key_sig,
                    events=events
                )
            )

    return ScoreIR(
        schema_version="0.1.0",
        metadata=metadata,
        tempo=tempo,
        tracks=tracks,
        bars=bars,
        layout=layout
    )


def validate_roundtrip(path: str | Path, original: ScoreIR) -> dict[str, Any]:
    recovered = extract_score_ir_from_gp(path)
    from .ir import semantic_scoreir_summary
    original_sum = semantic_scoreir_summary(original)
    recovered_sum = semantic_scoreir_summary(recovered)

    errors = []

    for k in ["title", "artist", "composer", "album", "transcriber", "copyright"]:
        orig_val = getattr(original.metadata, k, None)
        rec_val = getattr(recovered.metadata, k, None)
        if orig_val != rec_val:
            errors.append(f"metadata.{k} mismatch: original={orig_val}, recovered={rec_val}")

    if original.tempo.bpm != recovered.tempo.bpm:
        errors.append(f"tempo.bpm mismatch: original={original.tempo.bpm}, recovered={recovered.tempo.bpm}")
    if original.tempo.text != recovered.tempo.text:
        errors.append(f"tempo.text mismatch: original={original.tempo.text}, recovered={recovered.tempo.text}")

    orig_tracks_map = {t.id: t for t in original.tracks}
    rec_tracks_map = {t.id: t for t in recovered.tracks}

    if set(orig_tracks_map.keys()) != set(rec_tracks_map.keys()):
        errors.append(f"tracks IDs mismatch: original={sorted(orig_tracks_map.keys())}, recovered={sorted(rec_tracks_map.keys())}")
    else:
        for tid, orig_t in orig_tracks_map.items():
            rec_t = rec_tracks_map[tid]
            if orig_t.name != rec_t.name:
                errors.append(f"track '{tid}'.name mismatch: original={orig_t.name}, recovered={rec_t.name}")
            if orig_t.instrument != rec_t.instrument:
                errors.append(f"track '{tid}'.instrument mismatch: original={orig_t.instrument}, recovered={rec_t.instrument}")
            if orig_t.capo != rec_t.capo:
                errors.append(f"track '{tid}'.capo mismatch: original={orig_t.capo}, recovered={rec_t.capo}")
            if orig_t.tuning.name != rec_t.tuning.name:
                errors.append(f"track '{tid}'.tuning.name mismatch: original={orig_t.tuning.name}, recovered={rec_t.tuning.name}")

            orig_strings = sorted(orig_t.tuning.strings, key=lambda s: s.number)
            rec_strings = sorted(rec_t.tuning.strings, key=lambda s: s.number)
            if len(orig_strings) != len(rec_strings):
                errors.append(f"track '{tid}'.tuning strings count mismatch: original={len(orig_strings)}, recovered={len(rec_strings)}")
            else:
                for os, rs in zip(orig_strings, rec_strings):
                    if os.number != rs.number or os.pitch != rs.pitch:
                        errors.append(f"track '{tid}'.string {os.number} mismatch: original=({os.pitch}, {os.name}), recovered=({rs.pitch}, {rs.name})")
                    orig_offset = os.volume_offset if os.volume_offset is not None else 0.0
                    rec_offset = rs.volume_offset if rs.volume_offset is not None else 0.0
                    if orig_offset != rec_offset:
                        errors.append(f"track '{tid}'.string {os.number}.volume_offset mismatch: original={os.volume_offset}, recovered={rs.volume_offset}")
                    orig_ft = os.fine_tune if os.fine_tune is not None else 0.0
                    rec_ft = rs.fine_tune if rs.fine_tune is not None else 0.0
                    if orig_ft != rec_ft:
                        errors.append(f"track '{tid}'.string {os.number}.fine_tune mismatch: original={os.fine_tune}, recovered={rs.fine_tune}")

            if (orig_t.mixer is None) != (rec_t.mixer is None):
                errors.append(f"track '{tid}'.mixer presence mismatch: original={orig_t.mixer is not None}, recovered={rec_t.mixer is not None}")
            elif orig_t.mixer is not None:
                if int(orig_t.mixer.volume * 100) != int(rec_t.mixer.volume * 100):
                    errors.append(f"track '{tid}'.mixer.volume mismatch: original={orig_t.mixer.volume}, recovered={rec_t.mixer.volume}")
                if int((orig_t.mixer.pan + 1) * 50) != int((rec_t.mixer.pan + 1) * 50):
                    errors.append(f"track '{tid}'.mixer.pan mismatch: original={orig_t.mixer.pan}, recovered={rec_t.mixer.pan}")
                if orig_t.mixer.mute != rec_t.mixer.mute:
                    errors.append(f"track '{tid}'.mixer.mute mismatch: original={orig_t.mixer.mute}, recovered={rec_t.mixer.mute}")
                if orig_t.mixer.solo != rec_t.mixer.solo:
                    errors.append(f"track '{tid}'.mixer.solo mismatch: original={orig_t.mixer.solo}, recovered={rec_t.mixer.solo}")

            orig_exprs = sorted(orig_t.expressions or [], key=lambda e: e.bar_index)
            rec_exprs = sorted(rec_t.expressions or [], key=lambda e: e.bar_index)
            if len(orig_exprs) != len(rec_exprs):
                errors.append(f"track '{tid}'.expressions count mismatch: original={len(orig_exprs)}, recovered={len(rec_exprs)}")
            else:
                for oe, re in zip(orig_exprs, rec_exprs):
                    if oe.bar_index != re.bar_index or oe.text != re.text:
                        errors.append(f"track '{tid}'.expression mismatch: original=({oe.bar_index}, {oe.text}), recovered=({re.bar_index}, {re.text})")

            orig_autos = sorted(orig_t.automations or [], key=lambda a: (a.type, a.bar_index))
            rec_autos = sorted(rec_t.automations or [], key=lambda a: (a.type, a.bar_index))
            if len(orig_autos) != len(rec_autos):
                errors.append(f"track '{tid}'.automations count mismatch: original={len(orig_autos)}, recovered={len(rec_autos)}")
            else:
                for oa, ra in zip(orig_autos, rec_autos):
                    if oa.type != ra.type or oa.bar_index != ra.bar_index or abs(oa.value - ra.value) > 1e-4:
                        errors.append(f"track '{tid}'.automation mismatch: original=({oa.type}, {oa.bar_index}, {oa.value}), recovered=({ra.type}, {ra.bar_index}, {ra.value})")

            orig_lp = orig_t.layout_preferences
            rec_lp = rec_t.layout_preferences
            if orig_lp is not None and rec_lp is not None:
                for field in ["tab_only", "stem_direction", "line_sizing", "view_mode", "brackets_visible", "stems_visible", "line_sizing_per_system"]:
                    orig_val = getattr(orig_lp, field, None)
                    rec_val = getattr(rec_lp, field, None)
                    if orig_val != rec_val:
                        errors.append(f"track '{tid}'.layout_preferences.{field} mismatch: original={orig_val}, recovered={rec_val}")

    orig_order = original.layout.track_order if original.layout.track_order else [t.id for t in original.tracks]
    rec_order = recovered.layout.track_order if recovered.layout.track_order else [t.id for t in recovered.tracks]
    if orig_order != rec_order:
        errors.append(f"layout.track_order mismatch: original={original.layout.track_order}, recovered={recovered.layout.track_order}")

    orig_mm = original.layout.master_mixer
    rec_mm = recovered.layout.master_mixer
    if (orig_mm is None) != (rec_mm is None):
        errors.append(f"layout.master_mixer presence mismatch: original={orig_mm is not None}, recovered={rec_mm is not None}")
    elif orig_mm is not None:
        if int(orig_mm.volume * 100) != int(rec_mm.volume * 100):
            errors.append(f"layout.master_mixer.volume mismatch: original={orig_mm.volume}, recovered={rec_mm.volume}")
        if int((orig_mm.pan + 1) * 50) != int((rec_mm.pan + 1) * 50):
            errors.append(f"layout.master_mixer.pan mismatch: original={orig_mm.pan}, recovered={rec_mm.pan}")
        if orig_mm.reverb != rec_mm.reverb:
            errors.append(f"layout.master_mixer.reverb mismatch: original={orig_mm.reverb}, recovered={rec_mm.reverb}")
        if orig_mm.chorus != rec_mm.chorus:
            errors.append(f"layout.master_mixer.chorus mismatch: original={orig_mm.chorus}, recovered={rec_mm.chorus}")

    orig_pc = original.layout.preset_cascade
    rec_pc = recovered.layout.preset_cascade
    if (orig_pc is None) != (rec_pc is None):
        errors.append(f"layout.preset_cascade presence mismatch: original={orig_pc is not None}, recovered={rec_pc is not None}")
    elif orig_pc is not None:
        if orig_pc.preset_name != rec_pc.preset_name:
            errors.append(f"layout.preset_cascade.preset_name mismatch: original={orig_pc.preset_name}, recovered={rec_pc.preset_name}")
        if orig_pc.target_engine != rec_pc.target_engine:
            errors.append(f"layout.preset_cascade.target_engine mismatch: original={orig_pc.target_engine}, recovered={rec_pc.target_engine}")
        if orig_pc.options != rec_pc.options:
            errors.append(f"layout.preset_cascade.options mismatch: original={orig_pc.options}, recovered={rec_pc.options}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "original_summary": original_sum,
        "recovered_summary": recovered_sum
    }
