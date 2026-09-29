"""Conservative page-one score metadata reading from PDF text geometry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pymupdf


@dataclass(frozen=True)
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    size: float
    font: str


@dataclass(frozen=True)
class MetadataReading:
    title: str = ""
    music: str = ""
    copyright: str = ""
    diagnostics: tuple[str, ...] = ()


def read_pdf_score_metadata(path: str | Path) -> MetadataReading:
    """Read strong title and explicit music credit; locate every refusal on page one.

    Geometry is in PDF points. The boundaries follow measured first-page lines
    across the mounted score corpus, documented in the OMIT-05 design note.
    """
    with pymupdf.open(path) as document:
        page = document[0]
        width, height = page.rect.width, page.rect.height
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [span for span in line["spans"] if span["text"].strip()]
                if spans:
                    lines.append(TextLine("".join(s["text"] for s in spans).strip(),
                                          tuple(line["bbox"]), max(s["size"] for s in spans),
                                          spans[0]["font"]))

    def location(line: TextLine) -> str:
        return f"page 1 bbox ({', '.join(f'{value:.1f}' for value in line.bbox)})"

    # The title is the uniquely largest centered text above the score. Printed
    # lesson labels, tempo marks, page furniture, and footer text fail this gate.
    title_candidates = [line for line in lines if line.bbox[1] < height * .18
                        and line.size >= 17 and abs((line.bbox[0] + line.bbox[2]) / 2 - width / 2) <= width * .08
                        and len(line.text) >= 4 and not re.search(r"[=©%]", line.text)
                        and not re.search(r"Bravura|Stava|Tempo", line.font, re.I)]
    diagnostics = []
    title = ""
    if title_candidates:
        largest = max(line.size for line in title_candidates)
        leaders = [line for line in title_candidates if line.size >= largest * .9]
        if len(leaders) == 1:
            title = leaders[0].text
        else:
            diagnostics.append("pdf_title_ambiguous: " + "; ".join(location(line) for line in leaders))
    else:
        diagnostics.append("pdf_title_unreadable: page 1 top 18%")

    # An explicit music attribution is safer than inferring a composer's name
    # from an unlabeled subtitle, artist line, transcriber, or page footer.
    credits = [(line, match.group(1).strip()) for line in lines
               if line.bbox[1] < height * .18
               if (match := re.fullmatch(r"Music\s+by\s+(.+)", line.text, re.I))]
    music = ""
    if len(credits) == 1 and credits[0][1]:
        music = credits[0][1]
    elif credits:
        diagnostics.append("pdf_music_ambiguous: " + "; ".join(location(line) for line, _ in credits))
    else:
        diagnostics.append("pdf_music_unreadable: page 1 top 18%; no explicit music credit")

    rights = [line for line in lines if "©" in line.text or re.search(r"\bcopyright\b", line.text, re.I)]
    copyright_text = rights[0].text if len(rights) == 1 else ""
    if len(rights) > 1:
        diagnostics.append("pdf_copyright_ambiguous: " + "; ".join(location(line) for line in rights))
    elif not rights:
        diagnostics.append("pdf_copyright_unreadable: page 1; no copyright line")
    return MetadataReading(title, music, copyright_text, tuple(diagnostics))
