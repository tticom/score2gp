from __future__ import annotations

import xml.etree.ElementTree as ET


def validate_target(target_version: str) -> None:
    """Refuse targets without a writer proven for their container and profile.

    GP7 is the existing selection ID for the current GPIF-ZIP output. Keeping
    it does not claim application acceptance for another Guitar Pro version.
    """
    if not isinstance(target_version, str) or target_version.upper() != "GP7":
        raise ValueError(
            f"target_version: unsupported target {target_version!r}; "
            "available target: GP7 (current GPIF-ZIP output)"
        )


def adapt_gpif(gpif_xml: bytes, target_version: str) -> bytes:
    """Keep the default GPIF serialization; never fabricate another profile."""
    validate_target(target_version)
    root = ET.fromstring(gpif_xml)
    score_node = root.find("Score")
    if score_node is not None and score_node.find("Title") is not None:
        root.attrib.clear()
    else:
        root.set("version", "7")

    # Preserve the existing default element order under <Score>.
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
    """Container marker shared by the readable real GPIF-ZIP references."""
    validate_target(target_version)
    return b"7.0\n"
