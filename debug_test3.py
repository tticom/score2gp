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
whole, half, quarter = _extract_note_candidates(page)
print(whole)
