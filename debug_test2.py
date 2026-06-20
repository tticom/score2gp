from score2gp.pdf_staff_notation_diagnostics import _extract_note_candidates

class MockPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class MockRect:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.width = x1 - x0
        self.height = y1 - y0

class MockPage:
    def __init__(self, drawings):
        self.drawings = drawings
    def get_drawings(self):
        return self.drawings

items = []
for _ in range(8):
    items.append(("c", MockPoint(0, 0), MockPoint(1, 0), MockPoint(2, 0), MockPoint(7, 0)))
for _ in range(8):
    items.append(("c", MockPoint(1, 1), MockPoint(2, 1), MockPoint(3, 1), MockPoint(6, 1)))

drawings = [{
    "rect": MockRect(0.0, 0.0, 7.0, 4.0),
    "fill": (0, 0, 0),
    "items": items
}]

page = MockPage(drawings)
draw = drawings[0]
x0, y0, x1, y1 = draw["rect"].x0, draw["rect"].y0, draw["rect"].x1, draw["rect"].y1
w, h = draw["rect"].width, draw["rect"].height
aspect = w / h if h > 0 else 0
c_count = sum(1 for item in items if item[0] == 'c')
print(f"aspect: {aspect}, c_count: {c_count}")

if 1.0 <= aspect <= 2.0 and c_count >= 2:
    is_hollow = not draw.get("fill")
    print(f"initial is_hollow: {is_hollow}")
    if not is_hollow and c_count >= 16:
        pts = []
        for item in items:
            if item[0] == 'l':
                pts.append(item[1])
                pts.append(item[2])
            elif item[0] == 'c':
                pts.append(item[1])
                pts.append(item[2])
                pts.append(item[3])
                pts.append(item[4])
        
        if pts:
            min_dist_to_center = float('inf')
            cx = x0 + w / 2.0
            cy = y0 + h / 2.0
            for p in pts:
                dist = ((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5
                if dist < min_dist_to_center:
                    min_dist_to_center = dist
                    
            max_dist = 0.0
            for p in pts:
                dist = ((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5
                if dist > max_dist:
                    max_dist = dist
                    
            print(f"min_dist_to_center: {min_dist_to_center}, threshold: {min(w, h) * 0.1}")
            print(f"max_dist: {max_dist}, max_threshold: {min(w, h) * 0.2}")
            if min_dist_to_center > min(w, h) * 0.1:
                if max_dist > min(w, h) * 0.2:
                    is_hollow = True
    print(f"final is_hollow: {is_hollow}")
