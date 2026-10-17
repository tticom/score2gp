"""Digest of a GPIF with its slide marks removed, to prove everything else is unchanged by SLIDE-01."""

import hashlib
from xml.etree import ElementTree as ET


def gpif_without_slides_sha256(data: bytes) -> str:
    root = ET.fromstring(data)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "Slide" or (child.tag == "Property" and child.get("name") == "Slide"):
                parent.remove(child)
    for element in root.iter():
        element.tail = None
        element.text = (element.text or "").strip() or None
    return hashlib.sha256(ET.tostring(root)).hexdigest()
