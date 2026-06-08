from pydantic import BaseModel, ConfigDict, model_validator
from typing import Self

class _BaseGeometryCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.x0 > self.x1:
            raise ValueError("x0 must be <= x1")
        if self.y0 > self.y1:
            raise ValueError("y0 must be <= y1")
        return self

class CircularMarkerCandidate(_BaseGeometryCandidate):
    """Represents roughly circular shapes."""
    pass

class VerticalStrokeCandidate(_BaseGeometryCandidate):
    """Represents tall, narrow lines or rectangles."""
    pass

class HorizontalStrokeCandidate(_BaseGeometryCandidate):
    """Represents wide, short lines or rectangles."""
    pass

class CurveMarkerCandidate(_BaseGeometryCandidate):
    """Represents bezier curves."""
    pass

class RectangleMarkerCandidate(_BaseGeometryCandidate):
    """Represents generic rectangular regions."""
    pass

class TextMarkerCandidate(_BaseGeometryCandidate):
    """Represents a span of rendered text."""
    text: str

class XAlignedPrimitiveCluster(BaseModel):
    """Represents a group of primitive geometry aligned roughly along the same X coordinate."""
    model_config = ConfigDict(frozen=True)
    
    x0: float
    x1: float
    
    circular_markers: tuple[CircularMarkerCandidate, ...] = ()
    vertical_strokes: tuple[VerticalStrokeCandidate, ...] = ()
    horizontal_strokes: tuple[HorizontalStrokeCandidate, ...] = ()
    curve_markers: tuple[CurveMarkerCandidate, ...] = ()
    rectangle_markers: tuple[RectangleMarkerCandidate, ...] = ()
    text_markers: tuple[TextMarkerCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.x0 > self.x1:
            raise ValueError("x0 must be <= x1")
        return self
