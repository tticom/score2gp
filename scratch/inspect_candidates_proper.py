import json
from pathlib import Path

tabraw_path = Path("work/derek_trucks_conversion/tab/tab_raw.json")
if tabraw_path.exists():
    data = json.loads(tabraw_path.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    
    frets = [c for c in cands if c.get("kind") == "fret"]
    
    # In _tabraw_grouping_risk, playable is:
    has_detected_systems = any(c.get("system_index") is not None for c in cands)
    playable = []
    for candidate in frets:
        if candidate.get("parsed_fret") is None:
            continue
        if has_detected_systems:
            raw_dict = candidate.get("raw", {})
            ref_reason = raw_dict.get("refusal_reason")
            if ref_reason in {
                "pdf_fret_page_or_legend_number_excluded",
                "pdf_fret_chord_text_digit_excluded",
                "pdf_non_playable_text_not_string_assigned",
            }:
                continue
            if ref_reason == "pdf_fret_digit_symbol_overlap_ambiguous" and candidate.get("system_index") is None:
                continue
        playable.append(candidate)
        
    print(f"Total fret candidates: {len(frets)}")
    print(f"Playable fret candidates (according to _tabraw_grouping_risk): {len(playable)}")
    
    with_system = sum(1 for c in playable if c.get("system_index") is not None)
    with_bar = sum(1 for c in playable if c.get("bar_index") is not None)
    with_string = sum(1 for c in playable if c.get("string") is not None)
    
    print(f"Playable with system_index: {with_system}")
    print(f"Playable with bar_index: {with_bar}")
    print(f"Playable with string: {with_string}")
    
    # Print the ones that don't have bar_index
    no_bar = [c for c in playable if c.get("bar_index") is None]
    print(f"Playable without bar_index: {len(no_bar)}")
    if no_bar:
        print("First playable candidate without bar_index:")
        print(json.dumps(no_bar[0], indent=2))
else:
    print("tab_raw.json not found!")
