from __future__ import annotations

import fitz  # type: ignore[import-not-found]
from PIL import Image

def classify_raster_opening_symbol_candidate(staff: dict) -> dict:
    """
    Diagnostic-only read-only classifier to check if the raster_opening_symbol_candidate
    matches simple proportional heuristics for a treble clef.
    """
    if not isinstance(staff, dict):
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Malformed staff: not a dict",
            "features": {}
        }

    cand = staff.get("raster_opening_symbol_candidate")
    if not cand:
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Missing candidate evidence",
            "features": {}
        }

    if not isinstance(cand, dict):
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Malformed candidate: not a dict",
            "features": {}
        }

    y_coords = staff.get("y_coords", [])
    if not isinstance(y_coords, list) or len(y_coords) != 5 or not all(isinstance(y, (int, float)) for y in y_coords):
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Malformed staff y_coords",
            "features": {}
        }

    spacing = staff.get("spacing", 0.0)
    if not isinstance(spacing, (int, float)) or spacing <= 0.0:
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Invalid staff spacing",
            "features": {}
        }

    staff_height = float(y_coords[4] - y_coords[0])
    if staff_height <= 0.0:
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Invalid staff height",
            "features": {}
        }

    c_height = cand.get("height", 0.0)
    c_width = cand.get("width", 0.0)
    if not isinstance(c_height, (int, float)) or c_height <= 0.0 or not isinstance(c_width, (int, float)) or c_width <= 0.0:
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Malformed candidate dimensions",
            "features": {}
        }

    bbox = cand.get("bbox", [])
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4 or not all(isinstance(b, (int, float)) for b in bbox):
        return {
            "kind": "treble_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Malformed candidate bbox",
            "features": {}
        }

    staff_x0 = staff.get("x0", 0.0)
    if not isinstance(staff_x0, (int, float)):
        staff_x0 = 0.0

    height_to_spacing = float(c_height) / float(spacing)
    width_to_spacing = float(c_width) / float(spacing)
    height_to_staff_height = float(c_height) / staff_height
    x0_offset = float(bbox[0]) - float(staff_x0)

    features = {
        "height_to_spacing": round(height_to_spacing, 3),
        "width_to_spacing": round(width_to_spacing, 3),
        "height_to_staff_height": round(height_to_staff_height, 3),
        "x0_offset_from_staff_x0": round(x0_offset, 3)
    }

    # Conservative heuristic check for treble clef
    # A true treble clef must be significantly taller than the staff lines alone.
    if height_to_spacing >= 3.5 and width_to_spacing >= 1.5 and height_to_staff_height > 1.2:
        label = "treble_clef_candidate"
        reason = "Candidate matches proportional heuristics for a treble clef"
    else:
        label = "unknown"
        reason = "Evidence is ambiguous or does not strongly match treble clef heuristics"

    return {
        "kind": "treble_clef_candidate_classifier",
        "label": label,
        "reason": reason,
        "features": features
    }


def build_raster_notation_diagnostics(page: fitz.Page, page_index: int, scale: float = 2.0) -> dict:
    """
    Detects 5-line standard notation staffs and left-margin opening-symbol
    candidates using pure raster/image processing. This supplements the
    vector geometry pipeline for raster-only or mixed-PDF fixtures.
    """
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
    
    img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
    
    # 255 if dark (meaning part of the drawing/text), 0 if light (background)
    threshold = 128
    binary = img.point(lambda p: 255 if p < threshold else 0)
    
    width, height = binary.size
    
    # Extract flattened data to avoid deprecated Image.getdata()
    # Image.tobytes() or Image.getdata()
    try:
        if hasattr(binary, "get_flattened_data"):
            data = list(binary.get_flattened_data())
        else:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                data = list(binary.getdata())
    except Exception:
        data = list(binary.tobytes())

    horizontal_lines = []
    
    # 1. Detect horizontal runs
    for y in range(height):
        row = data[y * width : (y + 1) * width]
        run_start = None
        run_length = 0
        runs = []
        for x, val in enumerate(row):
            if val == 255:
                if run_start is None:
                    run_start = x
                run_length += 1
            else:
                if run_start is not None:
                    if run_length > width * 0.35:
                        runs.append((run_start, x - 1))
                    run_start = None
                    run_length = 0
        if run_start is not None and run_length > width * 0.35:
            runs.append((run_start, width - 1))
            
        for r in runs:
            horizontal_lines.append({'y': y, 'x0': r[0], 'x1': r[1]})
            
    # 2. Merge adjacent lines vertically
    merged_lines = []
    for line in horizontal_lines:
        if not merged_lines:
            merged_lines.append(line)
        else:
            last = merged_lines[-1]
            if line['y'] - last['y'] <= 3 and max(line['x0'], last['x0']) < min(line['x1'], last['x1']):
                last['y'] = (last['y'] + line['y']) / 2.0
                last['x0'] = min(last['x0'], line['x0'])
                last['x1'] = max(last['x1'], line['x1'])
            else:
                merged_lines.append(line)
                
    # 3. Group into 5-line staffs
    staffs = []
    for i in range(len(merged_lines) - 4):
        group = merged_lines[i:i+5]
        y_coords = [g['y'] for g in group]
        spacings = [y_coords[j+1] - y_coords[j] for j in range(4)]
        avg_spacing = sum(spacings) / 4.0
        
        # Staff lines should be roughly evenly spaced
        if avg_spacing > 5.0 and all(abs(s - avg_spacing) < avg_spacing * 0.35 for s in spacings):
            min_x1 = min(g['x1'] for g in group)
            max_x0 = max(g['x0'] for g in group)
            if min_x1 - max_x0 > width * 0.35:
                staffs.append({
                    'y_coords': [round(y, 3) for y in y_coords],
                    'x0': float(max_x0),
                    'x1': float(min_x1),
                    'spacing': float(avg_spacing)
                })
                
    # Remove overlapping staffs (greedy approach)
    final_staffs = []
    last_y = -1000.0
    for s in staffs:
        if s['y_coords'][0] - last_y > s['spacing'] * 2.0:
            final_staffs.append(s)
            last_y = s['y_coords'][4]
            
    # 4. Extract opening symbol candidates
    candidates = []
    for index, s in enumerate(final_staffs, start=1):
        margin_x0 = int(s['x0'])
        margin_x1 = int(s['x0'] + s['spacing'] * 4.5)
        margin_y0 = int(s['y_coords'][0] - s['spacing'] * 3.5)
        margin_y1 = int(s['y_coords'][4] + s['spacing'] * 3.5)
        
        margin_x0 = max(0, margin_x0)
        margin_x1 = min(width, margin_x1)
        margin_y0 = max(0, margin_y0)
        margin_y1 = min(height, margin_y1)
        
        crop_box = (margin_x0, margin_y0, margin_x1, margin_y1)
        cropped = binary.crop(crop_box)
        bbox = cropped.getbbox()
        
        cand = None
        if bbox:
            c_x0 = margin_x0 + bbox[0]
            c_y0 = margin_y0 + bbox[1]
            c_x1 = margin_x0 + bbox[2]
            c_y1 = margin_y0 + bbox[3]
            
            c_height = c_y1 - c_y0
            c_width = c_x1 - c_x0
            
            # Treble clefs span multiple staff lines
            if c_height >= s['spacing'] * 3.5 and c_width >= s['spacing'] * 1.5:
                cand = {
                    "kind": "raster_opening_symbol_candidate",
                    "bbox": [float(c_x0), float(c_y0), float(c_x1), float(c_y1)],
                    "width": float(c_width),
                    "height": float(c_height),
                }

        staff_data = {
            "staff_index": index,
            "y_coords": s['y_coords'],
            "x0": s['x0'],
            "x1": s['x1'],
            "spacing": round(s['spacing'], 3),
            "raster_opening_symbol_candidate": cand
        }
        staff_data["raster_opening_symbol_classification"] = classify_raster_opening_symbol_candidate(staff_data)
        candidates.append(staff_data)
        
    return {
        "status": "success",
        "page_index": page_index,
        "render_scale": scale,
        "threshold": threshold,
        "staffs": candidates
    }


def summarize_raster_treble_clef_diagnostics(diagnostics: dict) -> dict:
    """
    Consumes existing raster diagnostics output and reports aggregate diagnostic counts
    and staff-level summaries without changing the underlying diagnostics or emitting
    semantic music objects like ScoreIR.
    """
    summary = {
        "kind": "raster_treble_clef_diagnostics_summary",
        "status": "success",
        "page_index": diagnostics.get("page_index", -1),
        "staff_count": 0,
        "label_counts": {
            "treble_clef_candidate": 0,
            "unknown": 0,
        },
        "staffs": []
    }
    
    staffs = diagnostics.get("staffs")
    if not isinstance(staffs, list):
        summary["status"] = "unknown"
        return summary
        
    summary["staff_count"] = len(staffs)
    
    for staff in staffs:
        if not isinstance(staff, dict):
            summary["label_counts"]["unknown"] += 1
            summary["staffs"].append({
                "staff_index": -1,
                "label": "unknown",
                "reason": "Staff entry is malformed or missing",
                "features": {},
                "has_opening_symbol_candidate": False
            })
            continue
            
        staff_index = staff.get("staff_index", -1)
        has_cand = staff.get("raster_opening_symbol_candidate") is not None
        
        classification = staff.get("raster_opening_symbol_classification")
        if not isinstance(classification, dict):
            label = "unknown"
            reason = "Missing or malformed classification data"
            features = {}
        else:
            label = classification.get("label", "unknown")
            if label not in ("treble_clef_candidate", "unknown"):
                label = "unknown"
            reason = classification.get("reason", "")
            features = classification.get("features", {})
            
        summary["label_counts"][label] += 1
        summary["staffs"].append({
            "staff_index": staff_index,
            "label": label,
            "reason": reason,
            "features": features,
            "has_opening_symbol_candidate": has_cand
        })
        
    return summary
