from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def adapt_gpif(gpif_xml: bytes, target_version: str) -> bytes:
    """
    Applies target version-specific XML transformations and tag overrides
    to make the GPIF compliant with the target Guitar Pro version profile.
    Supports GP6 (legacy), GP7 (standard), and GP8 (modern).
    """
    version_str = target_version.upper()
    if version_str not in ("GP6", "GP7", "GP8"):
        version_str = "GP7"

    try:
        root = ET.fromstring(gpif_xml)
    except Exception:
        # Fallback if invalid XML is passed
        return gpif_xml

    # 1. Map root version attribute (only for classic layouts; relational layouts have no attributes on GPIF)
    is_relational = False
    score_node = root.find("Score")
    if score_node is not None and score_node.find("Title") is not None:
        is_relational = True

    if not is_relational:
        if version_str == "GP6":
            root.set("version", "6")
        elif version_str == "GP7":
            root.set("version", "7")
        elif version_str == "GP8":
            root.set("version", "8")
    else:
        # Relational database XML: ensure no attributes are on root GPIF element
        root.attrib.clear()

    score_node = root.find("Score")
    if score_node is not None:
        if version_str == "GP6":
            # --- GP6 (Legacy): Strip advanced visual elements ---
            # Remove StyleCollections if present
            style_collections = score_node.find("StyleCollections")
            if style_collections is not None:
                score_node.remove(style_collections)

            # Remove MasterMixer if present
            master_mixer = score_node.find("MasterMixer")
            if master_mixer is not None:
                score_node.remove(master_mixer)

            # Remove PipelinePresetCascade if present
            cascade = score_node.find("PipelinePresetCascade")
            if cascade is not None:
                score_node.remove(cascade)

            # Add legacy indicator inside PageSetup
            ps = score_node.find("PageSetup")
            if ps is not None:
                legacy_layout = ps.find("LegacyLayout")
                if legacy_layout is None:
                    ET.SubElement(ps, "LegacyLayout").text = "True"

        elif version_str == "GP8":
            # --- GP8 (Modern): Inject modern attributes/metadata blocks ---
            metadata = score_node.find("Metadata")
            if metadata is not None:
                # Inject GP8-specific metadata
                target_comp = metadata.find("TargetCompliancy")
                if target_comp is None:
                    ET.SubElement(metadata, "TargetCompliancy").text = "ModernGP8"
                version_layout = metadata.find("VersionLayout")
                if version_layout is None:
                    ET.SubElement(metadata, "VersionLayout").text = "GP8-Standard"

            # Check or add StyleCollections
            style_collections = score_node.find("StyleCollections")
            if style_collections is None:
                sc = ET.SubElement(score_node, "StyleCollections")
                ET.SubElement(sc, "StyleCollection", {"name": "ModernDefault", "active": "true"})
            else:
                style_collections.set("gp8Compatible", "true")

    # Enforce strict GP7/GP8 unmarshalling element sequence constraints under <Score> after adaptations
    if score_node is not None:
        if score_node.find("Title") is not None:
            # Relational database layout sorting!
            TAG_ORDER = [
                "Title",
                "SubTitle",
                "Artist",
                "Album",
                "Words",
                "Music",
                "WordsAndMusic",
                "Copyright",
                "Tabber",
                "Instructions",
                "Notices",
                "FirstPageHeader",
                "FirstPageFooter",
                "PageHeader",
                "PageFooter",
                "ScoreSystemsDefaultLayout",
                "ScoreSystemsLayout",
                "ScoreZoomPolicy",
                "ScoreZoom",
                "MultiVoice",
                "View",
                "Print",
                "Layout",
                "MusicFont",
                "SymbolFont",
                "Fonts",
                "StyleCollections",
                "Styles",
                "MasterTrack",
                "Booklet"
            ]
        else:
            # Classic layout sorting!
            TAG_ORDER = [
                "Metadata",
                "Tempo",
                "PageSetup",
                "ScoreSystemsDefaultLayout",
                "ScoreSystemsLayout",
                "View",
                "Print",
                "Layout",
                "MusicFont",
                "SymbolFont",
                "Fonts",
                "StyleCollections",
                "Styles",
                "MasterTrack",
                "Booklet",
                "Tracks",
                "MasterBars",
                "Bars"
            ]
        score_children = list(score_node)
        score_children.sort(key=lambda x: TAG_ORDER.index(x.tag) if x.tag in TAG_ORDER else len(TAG_ORDER))
        score_node[:] = score_children

    # ET.tostring returns bytes representing the XML tree
    return ET.tostring(root, encoding="utf-8")


def get_version_file_content(target_version: str) -> bytes:
    """
    Returns the target VERSION file byte string based on the Guitar Pro target.
    """
    version_str = target_version.upper()
    if version_str == "GP6":
        return b"6.0\n"
    elif version_str == "GP8":
        return b"8.0\n"
    else:
        return b"7.0\n"
