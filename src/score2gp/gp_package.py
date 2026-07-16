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
    BoundingBox, Provenance, ConversionInfo, MasterMixer, PipelinePresetCascade,
    BookletCoverPage, BarNumberingOverride, BookletPagination,
    ExpressionController, ExpressionControllerPoint, BendPoint, BendTechnique,
    RepeatCountOverlay, TempoAutomation
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

    # Dynamic companion files generation matching active layout styles
    primary_score = score.scores[0] if isinstance(score, ScoreBooklet) else score
    pref_dict = {}
    if getattr(primary_score, "layout", None) is not None:
        layout = primary_score.layout
        if layout.view is not None:
            pref_dict["scoreViewMode"] = layout.view.mode.capitalize()
        else:
            pref_dict["scoreViewMode"] = "Page"

        if layout.page_setup is not None:
            ps = layout.page_setup
            pref_dict["pageFormat"] = {
                "width": ps.width,
                "height": ps.height,
                "scale": ps.scale
            }
            if ps.margins is not None:
                pref_dict["pageFormat"].update({
                    "marginTop": ps.margins.top,
                    "marginBottom": ps.margins.bottom,
                    "marginLeft": ps.margins.left,
                    "marginRight": ps.margins.right
                })
    else:
        pref_dict["scoreViewMode"] = "Page"

    preferences_bytes = (json.dumps(pref_dict, indent=2) + "\n").encode("utf-8")

    layout_cfg_xml = ET.Element("LayoutConfiguration", {"version": "1.0"})
    if getattr(primary_score, "layout", None) is not None:
        layout = primary_score.layout
        if layout.view is not None:
            ET.SubElement(layout_cfg_xml, "ActiveLayout").text = layout.view.mode.capitalize()
        else:
            ET.SubElement(layout_cfg_xml, "ActiveLayout").text = "Page"
        ET.SubElement(layout_cfg_xml, "SystemLayout").text = str(layout.score_systems_layout)
        if layout.system_page_margins is not None:
            spm = ET.SubElement(layout_cfg_xml, "SystemPageMargins")
            ET.SubElement(spm, "Top").text = str(layout.system_page_margins.top)
            ET.SubElement(spm, "Bottom").text = str(layout.system_page_margins.bottom)
            ET.SubElement(spm, "Left").text = str(layout.system_page_margins.left)
            ET.SubElement(spm, "Right").text = str(layout.system_page_margins.right)
    else:
        ET.SubElement(layout_cfg_xml, "ActiveLayout").text = "Page"
        ET.SubElement(layout_cfg_xml, "SystemLayout").text = "4"

    ET.indent(layout_cfg_xml, space="  ")
    layout_cfg_bytes = ET.tostring(layout_cfg_xml, encoding="utf-8", xml_declaration=True)

    copied.setdefault("VERSION", get_version_file_content(target_version))
    copied.setdefault("Content/Preferences.json", preferences_bytes)
    copied.setdefault("Content/LayoutConfiguration", layout_cfg_bytes)
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
            "cover_page": score.cover_page.model_dump(exclude_none=True) if score.cover_page else None,
            "movements": movements_list
        }
        copied["Content/booklet_index.json"] = json.dumps(booklet_index, indent=2).encode("utf-8")
    else:
        gpif = build_gpif(score)
        gpif = adapt_gpif(gpif, target_version)
        copied["Content/score.gpif"] = gpif

    directories = {"Content/"}
    for name in copied.keys():
        parts = name.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i]) + "/"
            directories.add(dir_path)

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
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


def _normalize_track_name(name: str) -> str:
    name = (name or "").lower()
    for modifier in ["clean"]:
        name = name.replace(modifier, "")
    words = name.split()
    return " ".join(words)


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
    differences = {}
    for field in fields:
        val_exp = expected_summary.get(field)
        val_act = actual_summary.get(field)
        if field == "tracks":
            norm_exp = [_normalize_track_name(t) for t in (val_exp or [])]
            norm_act = [_normalize_track_name(t) for t in (val_act or [])]
            if norm_exp != norm_act:
                differences[field] = {"expected": val_exp, "actual": val_act}
        else:
            if val_exp != val_act:
                differences[field] = {"expected": val_exp, "actual": val_act}
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
    bars = root.findall(".//Bars/Bar")
    voices_by_id = {v.get("id"): v for v in root.findall(".//Voices/Voice")}
    beats_by_id = {b.get("id"): b for b in root.findall(".//Beats/Beat")}

    logical_note_count = 0
    has_relational_structure = False

    if bars and voices_by_id and beats_by_id:
        for bar in bars:
            voices_tag = bar.find("Voices")
            if voices_tag is not None and voices_tag.text:
                voice_ids = voices_tag.text.split()
                for v_id in voice_ids:
                    if v_id != "-1" and v_id in voices_by_id:
                        voice = voices_by_id[v_id]
                        beats_tag = voice.find("Beats")
                        if beats_tag is not None and beats_tag.text:
                            beat_ids = beats_tag.text.split()
                            for b_id in beat_ids:
                                if b_id in beats_by_id:
                                    has_relational_structure = True
                                    beat = beats_by_id[b_id]
                                    notes_tag = beat.find("Notes")
                                    if notes_tag is not None and notes_tag.text:
                                        logical_note_count += len(notes_tag.text.split())

    if not has_relational_structure:
        logical_note_count = len(root.findall(".//Note"))

    track_bars = root.findall(".//Bars/Bar")
    raw_bars = root.findall(".//Bar")
    master_bars = root.findall(".//MasterBar")

    if track_bars:
        bar_count = len(track_bars)
        bar_count_source = "track_bars"
        gpif_bar_count_fallback_used = False
    elif master_bars:
        bar_count = len(master_bars)
        bar_count_source = "master_bars"
        gpif_bar_count_fallback_used = True
    elif raw_bars:
        bar_count = len(raw_bars)
        bar_count_source = "raw_bar_tags_fallback"
        gpif_bar_count_fallback_used = True
    else:
        bar_count = 0
        bar_count_source = "raw_bar_tags_fallback"
        gpif_bar_count_fallback_used = True

    raw_bar_tag_count = len(raw_bars)
    musical_track_bar_count = len(track_bars)
    master_bar_count = len(master_bars)
    automation_bar_tag_count = len(root.findall(".//Automation//Bar"))
    template_prelude_bar_count = 0

    return {
        "tracks": tracks,
        "tunings": tunings,
        "tempo": tempo,
        "time_signatures": sorted(set(time_signatures)),
        "bar_count": bar_count,
        "note_count": logical_note_count,
        "chord_symbols": chord_symbols,
        "techniques": techniques,
        "raw_bar_tag_count": raw_bar_tag_count,
        "musical_track_bar_count": musical_track_bar_count,
        "master_bar_count": master_bar_count,
        "automation_bar_tag_count": automation_bar_tag_count,
        "template_prelude_bar_count": template_prelude_bar_count,
        "bar_count_source": bar_count_source,
        "gpif_bar_count_fallback_used": gpif_bar_count_fallback_used,
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


def extract_score_ir_from_gp(path: str | Path) -> ScoreIR | ScoreBooklet:
    gp_path = Path(path)
    with zipfile.ZipFile(gp_path, "r") as zf:
        if "Content/booklet_index.json" in zf.namelist():
            index_data = json.loads(zf.read("Content/booklet_index.json").decode("utf-8"))
            booklet_title = index_data.get("booklet_title", "Untitled Booklet")
            metadata = Metadata(**index_data.get("metadata", {}))
            pagination = BookletPagination(**index_data.get("pagination", {})) if index_data.get("pagination") else None

            # Read booklet cover_page if present
            cover_page = None
            if "cover_page" in index_data and index_data["cover_page"] is not None:
                cover_page = BookletCoverPage(**index_data["cover_page"])
            else:
                # Or try to parse from primary score.gpif
                try:
                    primary_xml = zf.read("Content/score.gpif")
                    primary_root = ET.fromstring(primary_xml)
                    bk_node = primary_root.find(".//Score/Booklet")
                    if bk_node is not None:
                        cp_node = bk_node.find("CoverPage")
                        if cp_node is not None:
                            enabled = cp_node.get("enabled") == "true"
                            title_align = _first_text(cp_node, ["TitleAlignment"]) or "center"
                            margin_offset = float(_first_text(cp_node, ["MarginOffset"]) or 20.0)
                            sep_style = _first_text(cp_node, ["SeparatorStyle"]) or "line"
                            intro_text = _first_text(cp_node, ["IntroText"])
                            cover_page = BookletCoverPage(
                                enabled=enabled,
                                title_alignment=title_align,
                                margin_offset=margin_offset,
                                separator_style=sep_style,
                                intro_text=intro_text,
                            )
                except Exception:
                    pass

            scores = []
            for mov in index_data.get("movements", []):
                mov_file = mov["file"]
                mov_xml = zf.read(mov_file)
                mov_root = ET.fromstring(mov_xml)
                s = _extract_score_ir_from_gpif_root(mov_root)
                scores.append(s)

            return ScoreBooklet(
                schema_version="0.1.0",
                booklet_title=booklet_title,
                metadata=metadata,
                pagination=pagination,
                cover_page=cover_page,
                scores=scores
            )
        else:
            xml_content = zf.read("Content/score.gpif")
            root = ET.fromstring(xml_content)
            return _extract_score_ir_from_gpif_root(root)


def _extract_score_ir_from_relational_gpif_root(root: ET.Element) -> ScoreIR:
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
    else:
        # Fall back to tempo automation under MasterTrack
        for auto in root.findall(".//MasterTrack/Automations/Automation"):
            if _first_text(auto, ["Type"]) == "Tempo":
                val = _first_text(auto, ["Value"])
                if val:
                    bpm = int(float(val.split()[0]))
                    break
    tempo = Tempo(bpm=bpm, text=tempo_text)

    # 3. Parse Tracks
    tracks: list[Track] = []
    track_staves = [] # list of (track_id, staff_idx)
    for track_node in root.findall(".//Tracks/Track"):
        track_id = track_node.get("id") or "unknown"
        name = _first_text(track_node, ["Name"]) or "Track"
        color = _first_text(track_node, ["Color"])

        instrument = "guitar"
        capo = 0
        tuning_name = "Standard"
        strings: list[TuningString] = []

        staff_node = track_node.find(".//Staff")
        if staff_node is not None:
            # Parse Capo from CapoFret property
            capo_prop = staff_node.find(".//Property[@name='CapoFret']/Fret")
            if capo_prop is not None and capo_prop.text:
                capo = int(capo_prop.text)

            # Parse Tuning from Tuning property
            tuning_prop = staff_node.find(".//Property[@name='Tuning']")
            if tuning_prop is not None:
                inst_node = tuning_prop.find("Instrument")
                if inst_node is not None and inst_node.text:
                    instrument = inst_node.text.lower()

                pitches_node = tuning_prop.find("Pitches")
                if pitches_node is not None and pitches_node.text:
                    pitches = pitches_node.text.split()
                    tuning_name = _known_tuning_name(pitches) or "Standard"
                    for index, pitch_str in enumerate(pitches):
                        num = len(pitches) - index
                        pitch = int(pitch_str)
                        strings.append(TuningString(number=num, pitch=pitch, name=""))

                # Staff properties for Balance/FineTuning
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

        # Fallback to direct elements under Track if staff is not present or Tuning property is missing
        if not strings:
            instrument = _first_text(track_node, ["Instrument"]) or "guitar"
            capo = int(_first_text(track_node, ["Capo"]) or 0)
            tuning_node = track_node.find("Tuning")
            if tuning_node is not None:
                tuning_name = tuning_node.get("name") or "Standard"
                for s_node in tuning_node.findall("String"):
                    num = int(s_node.get("number") or 1)
                    pitch = int(s_node.get("pitch") or 0)
                    s_name = s_node.get("name") or ""
                    strings.append(TuningString(number=num, pitch=pitch, name=s_name))

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

        text_annotations = None
        if staff_node is not None:
            texts_node = staff_node.find("Texts")
            if texts_node is not None:
                text_annotations = []
                for t_node in texts_node.findall("Text"):
                    t_val = _first_text(t_node, ["Value"]) or t_node.text
                    if t_val:
                        text_annotations.append(t_val)

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
                automations=automations,
                text_annotations=text_annotations
            )
        )

        staff_nodes = track_node.findall(".//Staves/Staff")
        if not staff_nodes:
            track_staves.append((track_id, 0))
        else:
            for s_idx in range(len(staff_nodes)):
                track_staves.append((track_id, s_idx))

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

    layout_node = root.find(".//Layout")
    if layout_node is not None:
        sys_lay_node = layout_node.find("SystemLayout")
        if sys_lay_node is not None:
            sys_sz_str = _first_text(sys_lay_node, ["SystemSizePercent"])
            sys_sz = float(sys_sz_str) if sys_sz_str is not None else None

            cush_str = _first_text(sys_lay_node, ["StaffDistancingCushion"])
            cush = float(cush_str) if cush_str is not None else None

            bl_style = _first_text(sys_lay_node, ["BarlineStyle"])
            if bl_style is not None:
                bl_style = bl_style.lower()

            from .ir import SystemLayout
            layout.system_layout = SystemLayout(
                system_size_percent=sys_sz,
                staff_distancing_cushion=cush,
                barline_style=bl_style
            )

        staff_lay_node = layout_node.find("StaffLayout")
        if staff_lay_node is not None:
            sp_cush_str = _first_text(staff_lay_node, ["StaffSpacingCushion"])
            sp_cush = float(sp_cush_str) if sp_cush_str is not None else None

            sz_str = _first_text(staff_lay_node, ["StaffSize"])
            sz = float(sz_str) if sz_str is not None else None

            from .ir import StaffLayout
            layout.staff_layout = StaffLayout(
                staff_spacing_cushion=sp_cush,
                staff_size=sz
            )

    # 5. Parse Rhythms
    rhythms = {}
    duration_ticks_map = {
        "Whole": 3840,
        "Half": 1920,
        "Quarter": 960,
        "Eighth": 480,
        "Sixteenth": 240,
        "ThirtySecond": 120,
        "SixtyFourth": 60,
    }
    rhythms_node = root.find("Rhythms")
    if rhythms_node is not None:
        for r in rhythms_node.findall("Rhythm"):
            r_id = r.get("id")
            val_node = r.find("NoteValue")
            val = val_node.text if val_node is not None else "Quarter"
            ticks = duration_ticks_map.get(val, 960)

            dots = r.find("AugmentationDot")
            if dots is not None:
                count = int(dots.get("count") or 1)
                factor = 1.0
                for i in range(count):
                    factor += 1.0 / (2 ** (i + 1))
                ticks = int(ticks * factor)

            tuplet = r.find("PrimaryTuplet")
            tuplet_obj = None
            if tuplet is not None:
                num = int(tuplet.get("num") or 1)
                den = int(tuplet.get("den") or 1)
                ticks = int(ticks * den / num)
                from .ir import PrimaryTuplet
                tuplet_obj = PrimaryTuplet(actual_notes=num, normal_notes=den)

            from .ir import NotatedDuration
            inv_val_map = {
                "Whole": "whole",
                "Half": "half",
                "Quarter": "quarter",
                "Eighth": "eighth",
                "Sixteenth": "16th",
                "ThirtySecond": "32nd",
                "SixtyFourth": "64th",
            }
            duration_obj = NotatedDuration(value=inv_val_map.get(val, "quarter"), dots=int(dots.get("count") or 1) if dots is not None else 0)

            rhythms[r_id] = {
                "value": val,
                "ticks": ticks,
                "duration_obj": duration_obj,
                "tuplet_obj": tuplet_obj
            }

    # 6. Parse Notes
    notes = {}
    notes_node = root.find("Notes")
    if notes_node is not None:
        for n in notes_node.findall("Note"):
            n_id = n.get("id")
            props = n.find("Properties")

            fret_prop = props.find('.//Property[@name="Fret"]/Fret') if props is not None else None
            fret = int(fret_prop.text) if fret_prop is not None else 0

            string_prop = props.find('.//Property[@name="String"]/String') if props is not None else None
            string_idx = int(string_prop.text) if string_prop is not None else 0

            midi_prop = props.find('.//Property[@name="Midi"]/Number') if props is not None else None
            pitch = int(midi_prop.text) if midi_prop is not None else 0

            techniques = []
            articulations = []

            if n.find("LetRing") is not None:
                from .ir import LetRingTechnique
                techniques.append(LetRingTechnique())

            if n.find("PalmMute") is not None:
                from .ir import PalmMuteTechnique
                techniques.append(PalmMuteTechnique())

            if n.find("DeadNote") is not None:
                from .ir import Technique
                techniques.append(Technique(kind="dead-note"))

            acc = n.find("Accent")
            if acc is not None:
                val = acc.text
                if val == "1":
                    articulations.append("accent")
                elif val == "2":
                    articulations.append("marcato")

            vib = n.find("Vibrato")
            if vib is not None:
                from .ir import VibratoTechnique
                techniques.append(VibratoTechnique())

            tie = n.find("Tie")
            if tie is not None:
                state = "stop" if tie.get("destination") == "true" else "start"
                from .ir import TieTechnique
                techniques.append(TieTechnique(state=state))

            slur_state = n.get("slur")
            slur_prop = props.find('.//Property[@name="Slur"]') if props is not None else None
            slur_element = n.find("Slur")
            if slur_state is not None:
                from .ir import SlurTechnique
                if slur_state not in ("start", "stop", "continue"):
                    slur_state = "start"
                techniques.append(SlurTechnique(state=slur_state))
            elif slur_element is not None:
                from .ir import SlurTechnique
                state = slur_element.get("state") or "start"
                if state not in ("start", "stop", "continue"):
                    state = "start"
                techniques.append(SlurTechnique(state=state))
            elif slur_prop is not None:
                from .ir import SlurTechnique
                techniques.append(SlurTechnique(state="start"))

            slide_prop = props.find('.//Property[@name="Slide"]') if props is not None else None
            if slide_prop is not None:
                from .ir import SlideTechnique
                techniques.append(SlideTechnique())

            ho_prop = props.find('.//Property[@name="HammerOn"]') if props is not None else None
            if n.find("HO") is not None or ho_prop is not None:
                from .ir import HammerOnTechnique
                style = None
                flags = None
                legato = None
                if ho_prop is not None:
                    style = _first_text(ho_prop, ["Style"])
                    flags_str = _first_text(ho_prop, ["Flags"])
                    if flags_str:
                        flags = int(flags_str)
                    legato_str = _first_text(ho_prop, ["Legato"])
                    if legato_str:
                        legato = legato_str.lower() == "true"
                techniques.append(HammerOnTechnique(kind="hammer-on", target_event_id=None, style=style, flags=flags, legato=legato))

            po_prop = props.find('.//Property[@name="PullOff"]') if props is not None else None
            if n.find("PO") is not None or po_prop is not None:
                from .ir import PullOffTechnique
                style = None
                flags = None
                legato = None
                if po_prop is not None:
                    style = _first_text(po_prop, ["Style"])
                    flags_str = _first_text(po_prop, ["Flags"])
                    if flags_str:
                        flags = int(flags_str)
                    legato_str = _first_text(po_prop, ["Legato"])
                    if legato_str:
                        legato = legato_str.lower() == "true"
                techniques.append(PullOffTechnique(kind="pull-off", target_event_id=None, style=style, flags=flags, legato=legato))

            bend_prop = props.find('.//Property[@name="Bended"]') if props is not None else None
            if bend_prop is not None:
                pts = []
                bend_node = n.find("Bend")
                if bend_node is not None:
                    for pt_node in bend_node.findall("Point"):
                        off_pct = float(pt_node.get("offset") or 0.0)
                        val_gp = float(pt_node.get("value") or 0.0)
                        semitones = val_gp / 50.0
                        pts.append(BendPoint(offset_ticks=int(off_pct), semitones=semitones))
                from .ir import BendTechnique
                techniques.append(BendTechnique(kind="bend", points=pts))

            lh_fingering = None
            rh_fingering = None
            if props is not None:
                for prop in props.findall("Property"):
                    name = prop.get("name")
                    if name == "LeftHandFingering":
                        lh_fingering = _first_text(prop, ["Fingering"])
                    elif name == "RightHandFingering":
                        rh_fingering = _first_text(prop, ["Fingering"])

            notes[n_id] = {
                "string_idx": string_idx,
                "fret": fret,
                "pitch": pitch,
                "techniques": techniques,
                "articulations": articulations,
                "left_hand_fingering": lh_fingering,
                "right_hand_fingering": rh_fingering
            }

    # 7. Parse Beats
    beats = {}
    beats_node = root.find("Beats")
    if beats_node is not None:
        for b in beats_node.findall("Beat"):
            b_id = b.get("id")
            dyn_node = b.find("Dynamic")
            dyn = dyn_node.text if dyn_node is not None else "MF"

            rhythm_ref = b.find("Rhythm").get("ref")
            r_info = rhythms[rhythm_ref]

            rest = b.find("Rest") is not None

            notes_ref_text = b.find("Notes")
            notes_refs = notes_ref_text.text.split() if notes_ref_text is not None and notes_ref_text.text else []

            free_text = b.find("FreeText")
            text = free_text.text if free_text is not None else None

            brush = b.find("Brush")
            brush_dir = (brush.get("direction") or "none").lower() if brush is not None else None

            arpeggio = b.find("Arpeggio")
            arp_dir = (arpeggio.get("direction") or "none").lower() if arpeggio is not None else None

            chord_symbol = _first_text(b, ["Chord"])

            beats[b_id] = {
                "dynamic": dyn,
                "duration_ticks": r_info["ticks"],
                "duration_obj": r_info["duration_obj"],
                "tuplet_obj": r_info["tuplet_obj"],
                "rest": rest,
                "notes_refs": notes_refs,
                "text": text,
                "brush": brush_dir,
                "arpeggio": arp_dir,
                "chord_symbol": chord_symbol
            }

    # 8. Parse Voices
    voices = {}
    voices_node = root.find("Voices")
    if voices_node is not None:
        for v in voices_node.findall("Voice"):
            v_id = v.get("id")
            beats_ref_text = v.find("Beats")
            beat_refs = beats_ref_text.text.split() if beats_ref_text is not None and beats_ref_text.text else []
            voices[v_id] = beat_refs

    # 9. Parse Bars
    bars_dict = {}
    bars_node = root.find("Bars")
    if bars_node is not None:
        for bar in bars_node.findall("Bar"):
            bar_id = bar.get("id")
            voice_refs = bar.find("Voices").text.split()
            bars_dict[bar_id] = {
                "clef": _first_text(bar, ["Clef"]) or "G2",
                "voice_refs": voice_refs
            }

    # 10. Reconstruct Bars
    track_string_counts = {}
    for track in tracks:
        track_string_counts[track.id] = len(track.tuning.strings) if track.tuning else 6

    bars: list[Bar] = []
    master_bars_node = root.find(".//MasterBars")
    if master_bars_node is not None:
        for mb_counter, mb_node in enumerate(master_bars_node.findall("MasterBar"), 1):
            mb_idx = int(mb_node.get("index") or mb_counter)
            time_str = _first_text(mb_node, ["Time"]) or "4/4"
            num, den = map(int, time_str.split("/"))

            key_sig = None
            key_node = mb_node.find("Key")
            if key_node is not None:
                fifths_str = _first_text(key_node, ["Fifths"])
                if fifths_str is not None:
                    fifths = int(fifths_str)
                else:
                    acc_str = _first_text(key_node, ["AccidentalCount"])
                    acc = int(acc_str) if acc_str is not None else 0
                    trans = _first_text(key_node, ["TransposeAs"]) or "Sharps"
                    if "flat" in trans.lower():
                        fifths = -acc
                    else:
                        fifths = acc
                mode = _first_text(key_node, ["Mode"]) or "major"
                mode = mode.lower()
                key_sig = KeySignature(fifths=fifths, mode=mode)

            tempo_automation = None
            ta_node = mb_node.find("TempoAutomation")
            if ta_node is not None:
                ta_type = _first_text(ta_node, ["Type"])
                ta_style = _first_text(ta_node, ["Style"])
                ta_val = _first_text(ta_node, ["TargetBPM"])
                if ta_type is not None and ta_val is not None:
                    tempo_automation = TempoAutomation(
                        type=ta_type.lower(),
                        style=ta_style.lower() if ta_style else "default",
                        target_bpm=float(ta_val)
                    )

            layout_break = None
            break_val = _first_text(mb_node, ["Break"])
            if break_val == "Line":
                layout_break = "line"
            elif break_val == "Page":
                layout_break = "page"
            elif break_val == "None":
                layout_break = "none"

            marker = None
            section_node = mb_node.find("Section")
            if section_node is not None:
                marker = _first_text(section_node, ["Name"])

            barline = None
            barline_val = _first_text(mb_node, ["Barline"])
            if barline_val is not None:
                barline_inv_map = {
                    "Simple": "regular",
                    "Double": "double",
                    "End": "end",
                    "Section": "section",
                    "RepeatStart": "repeat-start",
                    "RepeatEnd": "repeat-end",
                    "Hidden": "hidden",
                    "Dashed": "dashed",
                }
                barline = barline_inv_map.get(barline_val, "regular")

            if mb_node.find("RepeatStart") is not None:
                barline = "repeat-start"

            repeat_count = None
            repeat_node = mb_node.find("Repeat")
            if repeat_node is not None:
                barline = "repeat-end"
                repeat_count_str = repeat_node.get("count")
                repeat_count = int(repeat_count_str) if repeat_count_str else 2

            events: list[Event] = []
            bar_ids_text = _first_text(mb_node, ["Bars"])
            bar_ids = bar_ids_text.split() if bar_ids_text else []

            for s_idx, bar_id in enumerate(bar_ids):
                if s_idx >= len(track_staves):
                    continue
                track_id, staff_idx = track_staves[s_idx]

                b_info = bars_dict.get(bar_id)
                if not b_info:
                    continue

                for v_idx, v_id in enumerate(b_info["voice_refs"]):
                    if v_id == "-1" or v_id not in voices:
                        continue

                    voice_num = v_idx + 1
                    onset = 0
                    for beat_id in voices[v_id]:
                        beat = beats.get(beat_id)
                        if not beat:
                            continue

                        num_strings = track_string_counts.get(track_id, 6)
                        resolved_notes = []
                        for nid in beat["notes_refs"]:
                            if nid in notes:
                                n_dict = notes[nid]
                                physical_string = num_strings - n_dict["string_idx"]
                                physical_string = max(1, min(num_strings, physical_string))
                                from .ir import Note
                                resolved_notes.append(Note(
                                    string=physical_string,
                                    fret=n_dict["fret"],
                                    pitch=n_dict["pitch"],
                                    techniques=n_dict["techniques"],
                                    articulations=n_dict["articulations"],
                                    left_hand_fingering=n_dict["left_hand_fingering"],
                                    right_hand_fingering=n_dict["right_hand_fingering"]
                                ))

                        from .ir import Timing
                        timing = Timing(
                            bar_index=mb_idx,
                            onset_ticks=onset,
                            duration_ticks=beat["duration_ticks"],
                            voice=voice_num,
                            notated_duration=beat["duration_obj"],
                            tuplet=beat["tuplet_obj"]
                        )

                        ev_id = f"e_m{mb_idx}_s{s_idx}_v{voice_num}_{onset}"

                        from .ir import Event

                        if len(resolved_notes) == 0 and beat.get("type", "") != "rest":
                            continue

                        events.append(Event(
                            id=ev_id,
                            track_id=track_id,
                            timing=timing,
                            notes=resolved_notes,
                            is_rest=beat["rest"],
                            dynamic=beat["dynamic"],
                            text=beat["text"],
                            brush=beat["brush"],
                            arpeggio=beat["arpeggio"],
                            chord_symbol=beat["chord_symbol"]
                        ))

                        onset += beat["duration_ticks"]

            bars.append(
                Bar(
                    index=mb_idx,
                    time_signature=TimeSignature(numerator=num, denominator=den),
                    key_signature=key_sig,
                    events=events,
                    tempo_automation=tempo_automation,
                    layout_break=layout_break,
                    barline=barline,
                    repeat_count=repeat_count,
                    marker=marker
                )
            )

    # Resolve target_event_id for HammerOnTechnique and PullOffTechnique
    from .ir import HammerOnTechnique, PullOffTechnique

    # Group all events by (track_id, voice)
    voice_events = {}
    for bar in bars:
        for event in bar.events:
            if event.is_rest:
                continue
            key = (event.track_id, event.timing.voice)
            if key not in voice_events:
                voice_events[key] = []
            voice_events[key].append(event)

    # For each track/voice group, sort chronologically
    for key, ev_list in voice_events.items():
        ev_list.sort(key=lambda e: (e.timing.bar_index, e.timing.onset_ticks))
        for i, ev_start in enumerate(ev_list):
            for note_start in ev_start.notes:
                for tech in note_start.techniques:
                    if isinstance(tech, (HammerOnTechnique, PullOffTechnique)) and tech.target_event_id is None:
                        # Look ahead for the next event in ev_list that has a note on the same string
                        for ev_next in ev_list[i+1:]:
                            if any(note_next.string == note_start.string for note_next in ev_next.notes):
                                tech.target_event_id = ev_next.id
                                break

    return ScoreIR(
        schema_version="0.1.0",
        metadata=metadata,
        tempo=tempo,
        tracks=tracks,
        bars=bars,
        layout=layout
    )


def _extract_score_ir_from_gpif_root(root: ET.Element) -> ScoreIR:
    if root.find("Beats") is not None and root.find(".//Score/Bars") is None:
        return _extract_score_ir_from_relational_gpif_root(root)

    # 1. Parse Metadata
    meta_node = root.find(".//Score/Metadata")
    metadata = Metadata()
    if meta_node is not None:
        metadata.title = _first_text(meta_node, ["Title"]) or "Untitled"
        metadata.artist = _first_text(meta_node, ["Artist"])
        metadata.composer = _first_text(meta_node, ["Composer"])
        metadata.album = _first_text(meta_node, ["Album"])
        metadata.transcriber = _first_text(meta_node, ["Transcriber"])
        metadata.copyright = _first_text(meta_node, ["Copyright"])

    # 2. Parse Tempo
    tempo_node = root.find(".//Score/Tempo")
    bpm = 120
    tempo_text = None
    if tempo_node is not None:
        bpm = int(_first_text(tempo_node, ["Value"]) or 120)
        tempo_text = _first_text(tempo_node, ["Text"])
    tempo = Tempo(bpm=bpm, text=tempo_text)

    # 3. Parse Tracks
    tracks: list[Track] = []
    for track_node in root.findall(".//Score/Tracks/Track"):
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

        text_annotations = None
        if staff_node is not None:
            texts_node = staff_node.find("Texts")
            if texts_node is not None:
                text_annotations = []
                for t_node in texts_node.findall("Text"):
                    t_val = _first_text(t_node, ["Value"]) or t_node.text
                    if t_val:
                        text_annotations.append(t_val)

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
                automations=automations,
                text_annotations=text_annotations
            )
        )

    # 4. Parse ScoreLayout
    layout = ScoreLayout()
    master_track_node = root.find(".//Score/MasterTrack")
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

    ps_node = root.find(".//Score/PageSetup")
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

    layout_node = root.find(".//Score/Layout")
    if layout_node is not None:
        sys_lay_node = layout_node.find("SystemLayout")
        if sys_lay_node is not None:
            sys_sz_str = _first_text(sys_lay_node, ["SystemSizePercent"])
            sys_sz = float(sys_sz_str) if sys_sz_str is not None else None

            cush_str = _first_text(sys_lay_node, ["StaffDistancingCushion"])
            cush = float(cush_str) if cush_str is not None else None

            bl_style = _first_text(sys_lay_node, ["BarlineStyle"])
            if bl_style is not None:
                bl_style = bl_style.lower()

            from .ir import SystemLayout
            layout.system_layout = SystemLayout(
                system_size_percent=sys_sz,
                staff_distancing_cushion=cush,
                barline_style=bl_style
            )

        staff_lay_node = layout_node.find("StaffLayout")
        if staff_lay_node is not None:
            sp_cush_str = _first_text(staff_lay_node, ["StaffSpacingCushion"])
            sp_cush = float(sp_cush_str) if sp_cush_str is not None else None

            sz_str = _first_text(staff_lay_node, ["StaffSize"])
            sz = float(sz_str) if sz_str is not None else None

            from .ir import StaffLayout
            layout.staff_layout = StaffLayout(
                staff_spacing_cushion=sp_cush,
                staff_size=sz
            )

    # 5. Parse Bars and Events
    bars: list[Bar] = []
    master_bars_node = root.find(".//Score/MasterBars")
    mb_map = {}
    if master_bars_node is not None:
        for mb_node in master_bars_node.findall("MasterBar"):
            idx = int(mb_node.get("index") or 1)
            time_str = _first_text(mb_node, ["Time"]) or "4/4"
            num, den = map(int, time_str.split("/"))
            key_sig = None
            key_node = mb_node.find("Key")
            if key_node is not None:
                fifths_str = _first_text(key_node, ["Fifths"])
                if fifths_str is not None:
                    fifths = int(fifths_str)
                else:
                    acc_str = _first_text(key_node, ["AccidentalCount"])
                    acc = int(acc_str) if acc_str is not None else 0
                    trans = _first_text(key_node, ["TransposeAs"]) or "Sharps"
                    if "flat" in trans.lower():
                        fifths = -acc
                    else:
                        fifths = acc
                mode = _first_text(key_node, ["Mode"]) or "major"
                mode = mode.lower()
                key_sig = KeySignature(fifths=fifths, mode=mode)

            tempo_automation = None
            ta_node = mb_node.find("TempoAutomation")
            if ta_node is not None:
                ta_type = _first_text(ta_node, ["Type"])
                ta_style = _first_text(ta_node, ["Style"])
                ta_val = _first_text(ta_node, ["TargetBPM"])
                if ta_type is not None and ta_val is not None:
                    tempo_automation = TempoAutomation(
                        type=ta_type.lower(),
                        style=ta_style.lower() if ta_style else "default",
                        target_bpm=float(ta_val)
                    )

            layout_break = None
            break_val = _first_text(mb_node, ["Break"])
            if break_val is not None:
                if break_val == "Line":
                    layout_break = "line"
                elif break_val == "Page":
                    layout_break = "page"
                elif break_val == "None":
                    layout_break = "none"

            barline = None
            barline_val = _first_text(mb_node, ["Barline"])
            if barline_val is not None:
                barline_inv_map = {
                    "Simple": "regular",
                    "Double": "double",
                    "End": "end",
                    "Section": "section",
                    "RepeatStart": "repeat-start",
                    "RepeatEnd": "repeat-end",
                    "Hidden": "hidden",
                    "Dashed": "dashed",
                }
                barline = barline_inv_map.get(barline_val, "regular")

            if mb_node.find("RepeatStart") is not None:
                barline = "repeat-start"

            repeat_count = None
            repeat_node = mb_node.find("Repeat")
            if repeat_node is not None:
                barline = "repeat-end"
                repeat_count_str = repeat_node.get("count")
                repeat_count = int(repeat_count_str) if repeat_count_str else 2

            alternate_ending_passes = None
            ae_node = mb_node.find("AlternateEndings")
            if ae_node is not None and ae_node.text:
                mask = int(ae_node.text)
                alternate_ending_passes = [p for p in range(1, 32) if (mask & (1 << (p - 1))) != 0]

            marker = None
            section_node = mb_node.find("Section")
            if section_node is not None:
                marker = _first_text(section_node, ["Name"])

            mb_map[idx] = {
                "num": num,
                "den": den,
                "key_sig": key_sig,
                "tempo_automation": tempo_automation,
                "layout_break": layout_break,
                "barline": barline,
                "repeat_count": repeat_count,
                "alternate_ending_passes": alternate_ending_passes,
                "marker": marker,
            }

    bars_node = root.find(".//Score/Bars")
    if bars_node is not None:
        for bar_node in bars_node.findall("Bar"):
            idx = int(bar_node.get("index") or 1)
            mb_data = mb_map.get(idx, {
                "num": 4,
                "den": 4,
                "key_sig": None,
                "tempo_automation": None,
                "layout_break": None,
                "barline": None,
                "repeat_count": None,
                "alternate_ending_passes": None,
            })
            num = mb_data["num"]
            den = mb_data["den"]
            key_sig = mb_data["key_sig"]
            tempo_automation = mb_data["tempo_automation"]
            layout_break = mb_data["layout_break"]
            lb_node = bar_node.find("LayoutBreak")
            if lb_node is not None:
                type_val = _first_text(lb_node, ["Type"])
                if type_val == "System":
                    layout_break = "line"
                elif type_val == "Page":
                    layout_break = "page"
                elif type_val == "None":
                    layout_break = "none"

            barline = mb_data["barline"]
            repeat_count = mb_data["repeat_count"]
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

                expression_controller = None
                ec_node = ev_node.find("ExpressionController")
                if ec_node is not None:
                    ec_type = ec_node.get("type") or "Expression"
                    dur_str = _first_text(ec_node, ["Duration"])
                    dur_ticks = int(dur_str) if dur_str is not None else None
                    points = []
                    for pt_node in ec_node.findall("Point"):
                        off_ticks = int(pt_node.get("offset") or 0)
                        val_float = float(pt_node.get("value") or 0.0)
                        points.append(ExpressionControllerPoint(offset_ticks=off_ticks, value=val_float))
                    expression_controller = ExpressionController(type=ec_type, duration_ticks=dur_ticks, points=points)

                notes: list[Note] = []
                for n_node in ev_node.findall(".//Note"):
                    string = int(n_node.get("string") or 1)
                    fret = int(n_node.get("fret") or 0)
                    pitch = int(n_node.get("pitch") or 0)

                    # Parse techniques (Slide, Hammer-On, Pull-Off, Bend)
                    techniques = []
                    if n_node.find("LetRing") is not None:
                        from .ir import LetRingTechnique
                        techniques.append(LetRingTechnique())

                    if n_node.find("PalmMute") is not None:
                        from .ir import PalmMuteTechnique
                        techniques.append(PalmMuteTechnique())

                    props_node = n_node.find("Properties")

                    slur_state = n_node.get("slur")
                    slur_prop = props_node.find('.//Property[@name="Slur"]') if props_node is not None else None
                    if slur_state is not None:
                        from .ir import SlurTechnique
                        if slur_state not in ("start", "stop", "continue"):
                            slur_state = "start"
                        techniques.append(SlurTechnique(state=slur_state))
                    elif slur_prop is not None:
                        from .ir import SlurTechnique
                        techniques.append(SlurTechnique(state="start"))

                    slide_prop = props_node.find('.//Property[@name="Slide"]') if props_node is not None else None
                    if n_node.find("Slide") is not None or slide_prop is not None:
                        from .ir import SlideTechnique
                        techniques.append(SlideTechnique())

                    ho_prop = props_node.find('.//Property[@name="HammerOn"]') if props_node is not None else None
                    if n_node.find("HO") is not None or ho_prop is not None:
                        from .ir import HammerOnTechnique
                        style = None
                        flags = None
                        legato = None
                        if ho_prop is not None:
                            style = _first_text(ho_prop, ["Style"])
                            flags_str = _first_text(ho_prop, ["Flags"])
                            if flags_str:
                                flags = int(flags_str)
                            legato_str = _first_text(ho_prop, ["Legato"])
                            if legato_str:
                                legato = legato_str.lower() == "true"
                        techniques.append(HammerOnTechnique(kind="hammer-on", target_event_id=None, style=style, flags=flags, legato=legato))

                    po_prop = props_node.find('.//Property[@name="PullOff"]') if props_node is not None else None
                    if n_node.find("PO") is not None or po_prop is not None:
                        from .ir import PullOffTechnique
                        style = None
                        flags = None
                        legato = None
                        if po_prop is not None:
                            style = _first_text(po_prop, ["Style"])
                            flags_str = _first_text(po_prop, ["Flags"])
                            if flags_str:
                                flags = int(flags_str)
                            legato_str = _first_text(po_prop, ["Legato"])
                            if legato_str:
                                legato = legato_str.lower() == "true"
                        techniques.append(PullOffTechnique(kind="pull-off", target_event_id=None, style=style, flags=flags, legato=legato))

                    bend_node = n_node.find("Bend")
                    if bend_node is not None:
                        pts = []
                        for pt_node in bend_node.findall("Point"):
                            off_pct = float(pt_node.get("offset") or 0.0)
                            off_ticks = int(round((off_pct / 100.0) * dur))
                            val_gp = float(pt_node.get("value") or 0.0)
                            semitones = val_gp / 50.0

                            v_x = pt_node.get("v_x")
                            v_y = pt_node.get("v_y")
                            pts.append(BendPoint(
                                offset_ticks=off_ticks,
                                semitones=semitones,
                                v_x=float(v_x) if v_x is not None else None,
                                v_y=float(v_y) if v_y is not None else None
                            ))
                        dest_val_str = _first_text(bend_node, ["DestinationValue"])
                        dest_val = float(dest_val_str) if dest_val_str is not None else None
                        gd_str = _first_text(bend_node, ["GraphicDuration"])
                        gd = int(gd_str) if gd_str is not None else None
                        b_type = bend_node.get("type")

                        techniques.append(BendTechnique(
                            kind="bend",
                            points=pts,
                            destination_value=dest_val,
                            graphic_duration=gd,
                            bend_type=b_type
                        ))

                    # Parse Note ExpressionController
                    note_ec = None
                    n_ec_node = n_node.find("ExpressionController")
                    if n_ec_node is not None:
                        ec_type = n_ec_node.get("type") or "Expression"
                        dur_str = _first_text(n_ec_node, ["Duration"])
                        dur_ticks = int(dur_str) if dur_str is not None else None
                        points = []
                        for pt_node in n_ec_node.findall("Point"):
                            off_ticks = int(pt_node.get("offset") or 0)
                            val_float = float(pt_node.get("value") or 0.0)
                            points.append(ExpressionControllerPoint(offset_ticks=off_ticks, value=val_float))
                        note_ec = ExpressionController(type=ec_type, duration_ticks=dur_ticks, points=points)

                    lh_fingering = None
                    rh_fingering = None
                    props_node = n_node.find("Properties")
                    if props_node is not None:
                        for prop in props_node.findall("Property"):
                            name = prop.get("name")
                            if name == "LeftHandFingering":
                                fing = _first_text(prop, ["Fingering"])
                                if fing:
                                    lh_inv = {
                                        "Open": "open",
                                        "Thumb": "thumb",
                                        "Index": "index",
                                        "Middle": "middle",
                                        "Ring": "ring",
                                        "Little": "little"
                                    }
                                    lh_fingering = lh_inv.get(fing, fing)
                            elif name == "RightHandFingering":
                                fing = _first_text(prop, ["Fingering"])
                                if fing:
                                    rh_inv = {
                                        "Thumb": "thumb",
                                        "Index": "index",
                                        "Middle": "middle",
                                        "Ring": "ring",
                                        "Little": "little"
                                    }
                                    rh_fingering = rh_inv.get(fing, fing)

                    notes.append(Note(
                        string=string,
                        fret=fret,
                        pitch=pitch,
                        techniques=techniques,
                        expression_controller=note_ec,
                        left_hand_fingering=lh_fingering,
                        right_hand_fingering=rh_fingering
                    ))

                chord_diagram = None
                cd_node = ev_node.find("ChordDiagram")
                if cd_node is not None:
                    name = cd_node.get("name") or "Unnamed"
                    string_count = int(cd_node.get("stringCount") or 6)
                    fret_count = int(cd_node.get("fretCount") or 5)
                    base_fret = int(cd_node.get("baseFret") or 0)

                    frets = []
                    for f_node in cd_node.findall("Fret"):
                        f_string = int(f_node.get("string") or 1)
                        f_fret = int(f_node.get("fret") or 0)
                        from .ir import ChordFret
                        frets.append(ChordFret(string=f_string, fret=f_fret))

                    fingers = []
                    fing_node = cd_node.find("Fingering")
                    if fing_node is not None:
                        for pos in fing_node.findall("Position"):
                            finger_val = pos.get("finger") or "None"
                            fg_fret = int(pos.get("fret") or 0)
                            fg_string = int(pos.get("string") or 1)
                            from .ir import ChordFinger
                            fingers.append(ChordFinger(string=fg_string, fret=fg_fret, finger=finger_val))

                    kn_node = cd_node.find("KeyNote")
                    key_note_step = "C"
                    key_note_accidental = "Natural"
                    if kn_node is not None:
                        key_note_step = kn_node.get("step") or "C"
                        key_note_accidental = kn_node.get("accidental") or "Natural"

                    bn_node = cd_node.find("BassNote")
                    bass_note_step = "C"
                    bass_note_accidental = "Natural"
                    if bn_node is not None:
                        bass_note_step = bn_node.get("step") or "C"
                        bass_note_accidental = bn_node.get("accidental") or "Natural"

                    from .ir import ChordDiagram
                    chord_diagram = ChordDiagram(
                        name=name,
                        string_count=string_count,
                        fret_count=fret_count,
                        base_fret=base_fret,
                        frets=frets,
                        fingers=fingers,
                        key_note_step=key_note_step,
                        key_note_accidental=key_note_accidental,
                        bass_note_step=bass_note_step,
                        bass_note_accidental=bass_note_accidental
                    )

                chord_symbol = _first_text(ev_node, ["Chord"])
                if chord_diagram is not None:
                    chord_symbol = chord_diagram.name

                events.append(Event(
                    id=ev_id,
                    track_id=tr_id,
                    timing=timing,
                    notes=notes,
                    is_rest=rest,
                    chord_symbol=chord_symbol,
                    chord_diagram=chord_diagram,
                    expression_controller=expression_controller
                ))

            bar_numbering = None
            bn_node = bar_node.find("BarNumbering")
            if bn_node is not None:
                prefix = _first_text(bn_node, ["Prefix"])
                offset_str = _first_text(bn_node, ["Offset"])
                offset = int(offset_str) if offset_str is not None else None
                show_str = _first_text(bn_node, ["Show"])
                show = (show_str == "true") if show_str is not None else None
                bar_numbering = BarNumberingOverride(prefix=prefix, offset=offset, show=show)

            multi_measure_rest_count = None
            mmr_node = bar_node.find("MultiMeasureRest")
            if mmr_node is not None:
                mmr_val = _first_text(mmr_node, ["BarCount"])
                if mmr_val is not None:
                    multi_measure_rest_count = int(mmr_val)

            repeat_count_overlay = None
            rc_node = bar_node.find("RepeatCount")
            if rc_node is not None:
                rc_count = _first_text(rc_node, ["Count"])
                if rc_count is not None:
                    rc_span = _first_text(rc_node, ["Span"])
                    rc_style = _first_text(rc_node, ["Style"])
                    repeat_count_overlay = RepeatCountOverlay(
                        count=int(rc_count),
                        span=int(rc_span) if rc_span is not None else None,
                        style=rc_style.lower() if rc_style is not None else "default"
                    )

            # Alternate endings
            ae_passes = mb_data.get("alternate_ending_passes")
            ae_node = bar_node.find("AlternateEndings")
            if ae_node is not None and ae_node.text:
                mask = int(ae_node.text)
                ae_passes = [p for p in range(1, 32) if (mask & (1 << (p - 1))) != 0]
            else:
                ae_node_alt = bar_node.find(".//AlternativeEnding/AlternateEndings")
                if ae_node_alt is not None and ae_node_alt.text:
                    mask = int(ae_node_alt.text)
                    ae_passes = [p for p in range(1, 32) if (mask & (1 << (p - 1))) != 0]

            ae_is_stop = None
            if ae_passes is not None:
                ae_is_stop = True

            bars.append(
                Bar(
                    index=idx,
                    time_signature=TimeSignature(numerator=num, denominator=den),
                    key_signature=key_sig,
                    events=events,
                    bar_numbering=bar_numbering,
                    multi_measure_rest_count=multi_measure_rest_count,
                    repeat_count_overlay=repeat_count_overlay,
                    tempo_automation=tempo_automation,
                    layout_break=layout_break,
                    barline=barline,
                    repeat_count=repeat_count,
                    alternate_ending_passes=ae_passes,
                    alternate_ending_is_stop=ae_is_stop,
                    marker=mb_data.get("marker")
                )
            )

    # Resolve target_event_id for HammerOnTechnique and PullOffTechnique
    from .ir import HammerOnTechnique, PullOffTechnique

    # Group all events by (track_id, voice)
    voice_events = {}
    for bar in bars:
        for event in bar.events:
            if event.is_rest:
                continue
            key = (event.track_id, event.timing.voice)
            if key not in voice_events:
                voice_events[key] = []
            voice_events[key].append(event)

    # For each track/voice group, sort chronologically
    for key, ev_list in voice_events.items():
        ev_list.sort(key=lambda e: (e.timing.bar_index, e.timing.onset_ticks))
        for i, ev_start in enumerate(ev_list):
            for note_start in ev_start.notes:
                for tech in note_start.techniques:
                    if isinstance(tech, (HammerOnTechnique, PullOffTechnique)) and tech.target_event_id is None:
                        # Look ahead for the next event in ev_list that has a note on the same string
                        for ev_next in ev_list[i+1:]:
                            if any(note_next.string == note_start.string for note_next in ev_next.notes):
                                tech.target_event_id = ev_next.id
                                break

    return ScoreIR(
        schema_version="0.1.0",
        metadata=metadata,
        tempo=tempo,
        tracks=tracks,
        bars=bars,
        layout=layout
    )


def validate_roundtrip(path: str | Path, original: ScoreIR | ScoreBooklet) -> dict[str, Any]:
    recovered = extract_score_ir_from_gp(path)
    from .ir import semantic_scoreir_summary

    if isinstance(original, ScoreBooklet):
        if not isinstance(recovered, ScoreBooklet):
            return {
                "valid": False,
                "errors": [f"type mismatch: original is ScoreBooklet, recovered is {type(recovered).__name__}"],
                "original_summary": {},
                "recovered_summary": {}
            }
        errors = []
        if original.booklet_title != recovered.booklet_title:
            errors.append(f"booklet_title mismatch: original={original.booklet_title}, recovered={recovered.booklet_title}")

        for k in ["title", "artist", "composer", "album", "transcriber", "copyright"]:
            orig_val = getattr(original.metadata, k, None)
            rec_val = getattr(recovered.metadata, k, None)
            if orig_val != rec_val:
                errors.append(f"booklet metadata.{k} mismatch: original={orig_val}, recovered={rec_val}")

        if (original.pagination is None) != (recovered.pagination is None):
            errors.append(f"booklet pagination presence mismatch: original={original.pagination is not None}, recovered={recovered.pagination is not None}")
        elif original.pagination is not None:
            if original.pagination.start_page != recovered.pagination.start_page:
                errors.append(f"booklet pagination.start_page mismatch: original={original.pagination.start_page}, recovered={recovered.pagination.start_page}")
            if original.pagination.running_headers != recovered.pagination.running_headers:
                errors.append(f"booklet pagination.running_headers mismatch: original={original.pagination.running_headers}, recovered={recovered.pagination.running_headers}")
            if original.pagination.continuous != recovered.pagination.continuous:
                errors.append(f"booklet pagination.continuous mismatch: original={original.pagination.continuous}, recovered={recovered.pagination.continuous}")

        if (original.cover_page is None) != (recovered.cover_page is None):
            errors.append(f"booklet cover_page presence mismatch: original={original.cover_page is not None}, recovered={recovered.cover_page is not None}")
        elif original.cover_page is not None:
            oc = original.cover_page
            rc = recovered.cover_page
            if oc.enabled != rc.enabled:
                errors.append(f"booklet cover_page.enabled mismatch: original={oc.enabled}, recovered={rc.enabled}")
            if oc.title_alignment != rc.title_alignment:
                errors.append(f"booklet cover_page.title_alignment mismatch: original={oc.title_alignment}, recovered={rc.title_alignment}")
            if oc.margin_offset != rc.margin_offset:
                errors.append(f"booklet cover_page.margin_offset mismatch: original={oc.margin_offset}, recovered={rc.margin_offset}")
            if oc.separator_style != rc.separator_style:
                errors.append(f"booklet cover_page.separator_style mismatch: original={oc.separator_style}, recovered={rc.separator_style}")
            if oc.intro_text != rc.intro_text:
                errors.append(f"booklet cover_page.intro_text mismatch: original={oc.intro_text}, recovered={rc.intro_text}")

        if len(original.scores) != len(recovered.scores):
            errors.append(f"booklet scores count mismatch: original={len(original.scores)}, recovered={len(recovered.scores)}")
        else:
            for idx, (orig_s, rec_s) in enumerate(zip(original.scores, recovered.scores)):
                sub_res = _validate_score_ir_roundtrip(orig_s, rec_s)
                for err in sub_res:
                    errors.append(f"score {idx}: {err}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "original_summary": {},
            "recovered_summary": {}
        }

    else:
        if isinstance(recovered, ScoreBooklet):
            return {
                "valid": False,
                "errors": [f"type mismatch: original is ScoreIR, recovered is ScoreBooklet"],
                "original_summary": {},
                "recovered_summary": {}
            }
        original_sum = semantic_scoreir_summary(original)
        recovered_sum = semantic_scoreir_summary(recovered)
        errors = _validate_score_ir_roundtrip(original, recovered)
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "original_summary": original_sum,
            "recovered_summary": recovered_sum
        }


def _validate_score_ir_roundtrip(original: ScoreIR, recovered: ScoreIR) -> list[str]:
    from .ir import normalize_lh_fingering, normalize_rh_fingering
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

    # Verify bar_numbering overrides
    orig_bars_map = {b.index: b for b in original.bars}
    rec_bars_map = {b.index: b for b in recovered.bars}
    for idx in sorted(orig_bars_map.keys()):
        if idx not in rec_bars_map:
            continue
        ob = orig_bars_map[idx]
        rb = rec_bars_map[idx]

        if ob.layout_break != rb.layout_break:
            errors.append(f"bar {idx} layout_break mismatch: original={ob.layout_break}, recovered={rb.layout_break}")
        if ob.barline != rb.barline:
            errors.append(f"bar {idx} barline mismatch: original={ob.barline}, recovered={rb.barline}")
        if ob.marker != rb.marker:
            errors.append(f"bar {idx} marker mismatch: original={ob.marker}, recovered={rb.marker}")

        if (ob.bar_numbering is None) != (rb.bar_numbering is None):
            errors.append(f"bar {idx} bar_numbering presence mismatch: original={ob.bar_numbering is not None}, recovered={rb.bar_numbering is not None}")
        elif ob.bar_numbering is not None:
            if ob.bar_numbering.prefix != rb.bar_numbering.prefix:
                errors.append(f"bar {idx} bar_numbering.prefix mismatch: original={ob.bar_numbering.prefix}, recovered={rb.bar_numbering.prefix}")
            if ob.bar_numbering.offset != rb.bar_numbering.offset:
                errors.append(f"bar {idx} bar_numbering.offset mismatch: original={ob.bar_numbering.offset}, recovered={rb.bar_numbering.offset}")
            if ob.bar_numbering.show != rb.bar_numbering.show:
                errors.append(f"bar {idx} bar_numbering.show mismatch: original={ob.bar_numbering.show}, recovered={rb.bar_numbering.show}")

        # Compare events
        orig_events = {e.id: e for e in ob.events}
        rec_events = {e.id: e for e in rb.events}
        for ev_id, oe in orig_events.items():
            if ev_id not in rec_events:
                continue
            re = rec_events[ev_id]

            if oe.chord_symbol != re.chord_symbol:
                errors.append(f"event '{ev_id}' chord_symbol mismatch: original={oe.chord_symbol}, recovered={re.chord_symbol}")

            if (oe.chord_diagram is None) != (re.chord_diagram is None):
                errors.append(f"event '{ev_id}' chord_diagram presence mismatch: original={oe.chord_diagram is not None}, recovered={re.chord_diagram is not None}")
            elif oe.chord_diagram is not None:
                ocd = oe.chord_diagram
                rcd = re.chord_diagram
                if ocd.name != rcd.name:
                    errors.append(f"event '{ev_id}' chord_diagram.name mismatch: original={ocd.name}, recovered={rcd.name}")
                if ocd.string_count != rcd.string_count:
                    errors.append(f"event '{ev_id}' chord_diagram.string_count mismatch: original={ocd.string_count}, recovered={rcd.string_count}")
                if ocd.fret_count != rcd.fret_count:
                    errors.append(f"event '{ev_id}' chord_diagram.fret_count mismatch: original={ocd.fret_count}, recovered={rcd.fret_count}")
                if ocd.base_fret != rcd.base_fret:
                    errors.append(f"event '{ev_id}' chord_diagram.base_fret mismatch: original={ocd.base_fret}, recovered={rcd.base_fret}")
                if ocd.key_note_step != rcd.key_note_step or ocd.key_note_accidental != rcd.key_note_accidental:
                    errors.append(f"event '{ev_id}' chord_diagram key note mismatch")
                if ocd.bass_note_step != rcd.bass_note_step or ocd.bass_note_accidental != rcd.bass_note_accidental:
                    errors.append(f"event '{ev_id}' chord_diagram bass note mismatch")

                o_frets = sorted(ocd.frets, key=lambda f: (f.string, f.fret))
                r_frets = sorted(rcd.frets, key=lambda f: (f.string, f.fret))
                if len(o_frets) != len(r_frets):
                    errors.append(f"event '{ev_id}' chord_diagram frets count mismatch")
                else:
                    for f_idx, (of, rf) in enumerate(zip(o_frets, r_frets)):
                        if of.string != rf.string or of.fret != rf.fret:
                            errors.append(f"event '{ev_id}' chord_diagram fret {f_idx} mismatch")

                o_fingers = sorted(ocd.fingers, key=lambda f: (f.string, f.fret))
                r_fingers = sorted(rcd.fingers, key=lambda f: (f.string, f.fret))
                if len(o_fingers) != len(r_fingers):
                    errors.append(f"event '{ev_id}' chord_diagram fingers count mismatch")
                else:
                    for f_idx, (of, rf) in enumerate(zip(o_fingers, r_fingers)):
                        if of.string != rf.string or of.fret != rf.fret or of.finger != rf.finger:
                            errors.append(f"event '{ev_id}' chord_diagram finger {f_idx} mismatch")

            # Compare event expression controller
            if (oe.expression_controller is None) != (re.expression_controller is None):
                errors.append(f"event '{ev_id}' expression_controller presence mismatch")
            elif oe.expression_controller is not None:
                oec = oe.expression_controller
                rec_c = re.expression_controller
                if oec.type != rec_c.type or oec.duration_ticks != rec_c.duration_ticks:
                    errors.append(f"event '{ev_id}' expression_controller type/duration mismatch: original={oec.type}/{oec.duration_ticks}, recovered={rec_c.type}/{rec_c.duration_ticks}")
                if len(oec.points) != len(rec_c.points):
                    errors.append(f"event '{ev_id}' expression_controller points count mismatch")
                else:
                    for p_idx, (op, rp) in enumerate(zip(oec.points, rec_c.points)):
                        if op.offset_ticks != rp.offset_ticks or abs(op.value - rp.value) > 1e-4:
                            errors.append(f"event '{ev_id}' expression_controller point {p_idx} mismatch")

            # Compare notes
            orig_notes = {n.string: n for n in oe.notes}
            rec_notes = {n.string: n for n in re.notes}
            for string_num, on in orig_notes.items():
                if string_num not in rec_notes:
                    continue
                rn = rec_notes[string_num]

                if normalize_lh_fingering(on.left_hand_fingering) != normalize_lh_fingering(rn.left_hand_fingering):
                    errors.append(f"event '{ev_id}' note string {string_num} left_hand_fingering mismatch: original={on.left_hand_fingering}, recovered={rn.left_hand_fingering}")
                if normalize_rh_fingering(on.right_hand_fingering) != normalize_rh_fingering(rn.right_hand_fingering):
                    errors.append(f"event '{ev_id}' note string {string_num} right_hand_fingering mismatch: original={on.right_hand_fingering}, recovered={rn.right_hand_fingering}")

                # Note expression controller
                if (on.expression_controller is None) != (rn.expression_controller is None):
                    errors.append(f"event '{ev_id}' note string {string_num} expression_controller presence mismatch")
                elif on.expression_controller is not None:
                    onec = on.expression_controller
                    rnec = rn.expression_controller
                    if onec.type != rnec.type or onec.duration_ticks != rnec.duration_ticks:
                        errors.append(f"event '{ev_id}' note string {string_num} expression_controller type/duration mismatch")
                    if len(onec.points) != len(rnec.points):
                        errors.append(f"event '{ev_id}' note string {string_num} expression_controller points count mismatch")
                    else:
                        for p_idx, (op, rp) in enumerate(zip(onec.points, rnec.points)):
                            if op.offset_ticks != rp.offset_ticks or abs(op.value - rp.value) > 1e-4:
                                errors.append(f"event '{ev_id}' note string {string_num} expression_controller point {p_idx} mismatch")

                # Note Bend technique
                on_bend = next((t for t in on.techniques if t.kind == "bend"), None)
                rn_bend = next((t for t in rn.techniques if t.kind == "bend"), None)
                if (on_bend is None) != (rn_bend is None):
                    errors.append(f"event '{ev_id}' note string {string_num} bend technique presence mismatch")
                elif on_bend is not None:
                    if on_bend.destination_value != rn_bend.destination_value:
                        errors.append(f"event '{ev_id}' note string {string_num} bend destination_value mismatch: original={on_bend.destination_value}, recovered={rn_bend.destination_value}")
                    if on_bend.graphic_duration != rn_bend.graphic_duration:
                        errors.append(f"event '{ev_id}' note string {string_num} bend graphic_duration mismatch: original={on_bend.graphic_duration}, recovered={rn_bend.graphic_duration}")
                    if len(on_bend.points) != len(rn_bend.points):
                        errors.append(f"event '{ev_id}' note string {string_num} bend points count mismatch: original={len(on_bend.points)}, recovered={len(rn_bend.points)}")
                    else:
                        for p_idx, (op, rp) in enumerate(zip(on_bend.points, rn_bend.points)):
                            # We tolerate slight tick rounding differences because GP represents offsets as float percentage of duration
                            if abs(op.offset_ticks - rp.offset_ticks) > 2 or abs(op.semitones - rp.semitones) > 1e-4:
                                errors.append(f"event '{ev_id}' note string {string_num} bend point {p_idx} offset/semitones mismatch: original=({op.offset_ticks}, {op.semitones}), recovered=({rp.offset_ticks}, {rp.semitones})")
                            if op.v_x != rp.v_x or op.v_y != rp.v_y:
                                errors.append(f"event '{ev_id}' note string {string_num} bend point {p_idx} vector coordinates mismatch: original=({op.v_x}, {op.v_y}), recovered=({rp.v_x}, {rp.v_y})")

                # Note Slide technique
                on_slide = next((t for t in on.techniques if t.kind == "slide"), None)
                rn_slide = next((t for t in rn.techniques if t.kind == "slide"), None)
                if (on_slide is None) != (rn_slide is None):
                    errors.append(f"event '{ev_id}' note string {string_num} slide technique presence mismatch")

                # Note Hammer-on technique
                on_ho = next((t for t in on.techniques if t.kind == "hammer-on"), None)
                rn_ho = next((t for t in rn.techniques if t.kind == "hammer-on"), None)
                if (on_ho is None) != (rn_ho is None):
                    errors.append(f"event '{ev_id}' note string {string_num} hammer-on technique presence mismatch")
                elif on_ho is not None:
                    if on_ho.target_event_id != rn_ho.target_event_id:
                        errors.append(f"event '{ev_id}' note string {string_num} hammer-on target_event_id mismatch: original={on_ho.target_event_id}, recovered={rn_ho.target_event_id}")

                # Note Pull-off technique
                on_po = next((t for t in on.techniques if t.kind == "pull-off"), None)
                rn_po = next((t for t in rn.techniques if t.kind == "pull-off"), None)
                if (on_po is None) != (rn_po is None):
                    errors.append(f"event '{ev_id}' note string {string_num} pull-off technique presence mismatch")
                elif on_po is not None:
                    if on_po.target_event_id != rn_po.target_event_id:
                        errors.append(f"event '{ev_id}' note string {string_num} pull-off target_event_id mismatch: original={on_po.target_event_id}, recovered={rn_po.target_event_id}")

    return errors
