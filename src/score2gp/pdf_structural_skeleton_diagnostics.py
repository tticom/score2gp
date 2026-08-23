from typing import Any
from .pdf_staff_geometry import NotationStaffGeometry

def extract_structural_sections(text_dict: dict[str, Any], staff_geom: NotationStaffGeometry) -> list[dict[str, Any]]:
    sections = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                bbox = span.get("bbox")
                if not bbox:
                    continue
                sx0, sy0, sx1, sy1 = bbox

                # Check if it aligns horizontally with the staff
                center_x = (sx0 + sx1) / 2.0
                if center_x < staff_geom.x0 - 50.0 or center_x > staff_geom.x1 + 50.0:
                    continue

                # y_offset relative to staff.y0 (y_offset is negative if above)
                y_offset = sy1 - staff_geom.y0


                if abs(y_offset) > 50.0:
                    continue

                font_name = span.get("font", "").lower()
                is_bold = "bold" in font_name

                clean_text = text.strip()
                valid = ["Chorus", "Intro", "Verse", "Bridge", "Outro", "Coda", "Da Coda", "Da Capo", "D.S.", "D.C.", "Fine", "Segno", "A", "B", "C", "D", "E"]
                matched = False
                for v in valid:
                    if clean_text == v or clean_text.startswith(v + " ") or clean_text.startswith(v + "."):
                        matched = True
                        break

                if not matched and not is_bold:
                    continue

                sections.append({

                    "page_index": staff_geom.page_index,
                    "system_index": staff_geom.system_index,
                    "staff_index": staff_geom.staff_index,
                    "x0": sx0,
                    "y0": sy0,
                    "x1": sx1,
                    "y1": sy1,
                    "text": text,
                    "y_offset": y_offset,
                    "is_bold": is_bold
                })
    return sections

def extract_repeats_from_clusters(clusters: list[Any]) -> list[dict[str, Any]]:
    repeats = []
    if not clusters:
        return repeats

    for cluster in clusters:
        prims = sorted(cluster.primitives, key=lambda p: p.x0)
        valid_prims = [p for p in prims if p.kind in ["vertical_stroke", "rectangle"] and p.y1 - p.y0 >= 20.0]

        if len(valid_prims) < 2:
            continue

        for i in range(len(valid_prims) - 1):
            p0 = valid_prims[i]
            p1 = valid_prims[i+1]

            if p1.x0 <= p0.x1: continue
            w0 = p0.x1 - p0.x0
            w1 = p1.x1 - p1.x0

            if w0 > w1 and w0 > 1.5 and w1 < 1.5:
                repeats.append({
                    "page_index": cluster.page_index,
                    "system_index": cluster.system_index,
                    "staff_index": cluster.staff_index,
                    "x0": p0.x0,
                    "y0": min(p0.y0, p1.y0),
                    "x1": p1.x1,
                    "y1": max(p0.y1, p1.y1),
                    "direction": "start"
                })
            elif w1 > w0 and w1 > 1.5 and w0 < 1.5:
                repeats.append({
                    "page_index": cluster.page_index,
                    "system_index": cluster.system_index,
                    "staff_index": cluster.staff_index,
                    "x0": p0.x0,
                    "y0": min(p0.y0, p1.y0),
                    "x1": p1.x1,
                    "y1": max(p0.y1, p1.y1),
                    "direction": "end"
                })
    return repeats

def extract_structural_signals(diagnostics: Any) -> dict[str, list[dict[str, Any]]]:
    repeats = extract_repeats_from_clusters(diagnostics.x_aligned_cluster_candidates)

    return {
        "repeats": repeats,
        "sections": diagnostics.sections or [],
    }
