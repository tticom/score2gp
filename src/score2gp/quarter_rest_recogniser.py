def overlap(box1: list[float], box2: list[float]) -> bool:
    """Returns True if two bounding boxes overlap."""
    if not box1 or not box2:
        return False
    # box format: [min_x, min_y, max_x, max_y]
    return not (box1[2] <= box2[0] or box1[0] >= box2[2] or box1[3] <= box2[1] or box1[1] >= box2[3])


def extract_quarter_rest_candidates(outcomes: list[dict]) -> list[dict]:
    """
    Extracts quarter_rest_candidate objects from orphan flag_candidate fragments.
    """
    flag_cands = [c for c in outcomes if c.get('symbol_type') == 'flag_candidate']
    
    # Exclude flags that overlap with note candidates or clef candidates
    exclude_cands = [
        c for c in outcomes 
        if 'clef_candidate' in str(c.get('symbol_type', '')) 
        or 'note_candidate' in str(c.get('symbol_type', ''))
    ]
    
    exclude_boxes = [c.get('bbox') for c in exclude_cands if c.get('bbox')]
    
    orphan_flags = []
    for f in flag_cands:
        fb = f.get('bbox')
        if not fb:
            continue
        
        has_overlap = False
        for eb in exclude_boxes:
            if overlap(fb, eb):
                has_overlap = True
                break
                
        if not has_overlap:
            orphan_flags.append(f)
            
    rest_candidates = []
    
    if not orphan_flags:
        return rest_candidates
        
    # Group remaining orphan flags by horizontal proximity
    orphan_flags.sort(key=lambda c: c.get('bbox', [0])[0])
    clusters = []
    current_cluster = [orphan_flags[0]]
    
    for f in orphan_flags[1:]:
        fb = f.get('bbox')
        last_fb = current_cluster[-1].get('bbox')
        # If horizontal distance is less than 5.0
        if fb[0] - last_fb[2] < 5.0:
            current_cluster.append(f)
        else:
            clusters.append(current_cluster)
            current_cluster = [f]
    clusters.append(current_cluster)
    
    # Classify clusters
    for i, cl in enumerate(clusters):
        bboxes = [c.get('bbox') for c in cl]
        min_x = min(b[0] for b in bboxes)
        max_x = max(b[2] for b in bboxes)
        min_y = min(b[1] for b in bboxes)
        max_y = max(b[3] for b in bboxes)
        
        width = max_x - min_x
        height = max_y - min_y
        fragment_count = len(cl)
        
        if 10.0 <= width <= 25.0 and 25.0 <= height <= 40.0 and fragment_count >= 30:
            primitive_ids = []
            for c in cl:
                primitive_ids.extend(c.get('primitive_source_ids', []))
                
            # Inherit staff association from first fragment
            staff_index = cl[0].get('system_staff_index')
            page_index = cl[0].get('page_index')
            system_index = cl[0].get('system_index')
            
            cand = {
                "symbol_type": "quarter_rest_candidate",
                "candidate_id": f"quarter_rest_candidate_{len(rest_candidates):03d}",
                "duration": "quarter",
                "bbox": [min_x, min_y, max_x, max_y],
                "primitive_source_ids": primitive_ids,
                "evidence": {
                    "fragment_count": fragment_count,
                    "width": width,
                    "height": height
                }
            }
            if staff_index is not None:
                cand["system_staff_index"] = staff_index
            if page_index is not None:
                cand["page_index"] = page_index
            if system_index is not None:
                cand["system_index"] = system_index
                
            rest_candidates.append(cand)
            
    return rest_candidates
