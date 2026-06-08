import json
from pathlib import Path

data = {
    "page_width": 595.28,
    "page_height": 841.89,
    "notation_staves": [
        {
            "x0": 50.0,
            "x1": 545.28,
            "y_start": 100.0,
            "line_gap": 8.5,
            "line_count": 5
        },
        {
            "x0": 50.0,
            "x1": 545.28,
            "y_start": 250.0,
            "line_gap": 8.5,
            "line_count": 5
        }
    ],
    "barlines": [
        {
            "x": 50.0,
            "y_min": 100.0,
            "y_max": 134.0
        },
        {
            "x": 50.0,
            "y_min": 250.0,
            "y_max": 284.0
        }
    ],
    "margin_text_clusters": [],
    "wide_curves": [],
    "note_clusters": []
}

Path("fixtures/public/generated_standard_staff_multi_staff_unconnected.json").write_text(json.dumps(data, indent=2) + "\n")
