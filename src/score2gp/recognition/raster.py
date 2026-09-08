"""Raster Observation Adapter (REC-05).

Provides deterministic page rendering, typed raster evidence models (lines,
glyphs, regions) with source pixel boxes, coordinate transform provenance,
lossless page-to-raster round-trips, non-destructive peer observation integration,
and cross-modal disagreement preservation.
"""

from __future__ import annotations

from enum import StrEnum
import hashlib
import math
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

try:
    import pymupdf as fitz  # type: ignore[import-untyped]
except ImportError:
    try:
        import fitz  # type: ignore[import-untyped,no-redef]
    except ImportError:
        fitz = None  # type: ignore[assignment]

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from score2gp.recognition.schemas import (
    BoundingBox2D,
    DocumentObservations,
    ObservationProvenance,
    RasterObservation,
    SourceModality,
    TextObservation,
    VectorPathObservation,
)


# ---------------------------------------------------------------------------
# Exceptions (Fail-closed contract)
# ---------------------------------------------------------------------------

class RasterAdapterError(Exception):
    """Base exception for raster observation adapter."""


class RasterProvenanceError(RasterAdapterError):
    """Raised when renderer, scale, color mode, or transform provenance is missing or invalid."""


class RasterTransformError(RasterAdapterError):
    """Raised when coordinate transformation fails or matrix is non-invertible."""


class RasterRenderingError(RasterAdapterError):
    """Raised when deterministic page rendering fails."""


# ---------------------------------------------------------------------------
# Enums and Primitives
# ---------------------------------------------------------------------------

class ColorMode(StrEnum):
    """Color mode for page rendering and raster extraction."""
    GRAY = "gray"
    RGB = "rgb"
    RGBA = "rgba"
    BINARY = "binary"


class RasterPrimitiveType(StrEnum):
    """Typed primitive kind for raster observations."""
    LINE = "line"
    GLYPH = "glyph"
    REGION = "region"
    PAGE = "page"


class RasterPixelBox(BaseModel):
    """Pixel bounding box in raster coordinate space [px0, py0, px1, py1]."""
    model_config = ConfigDict(extra="forbid")

    px0: float
    py0: float
    px1: float
    py1: float

    @model_validator(mode="after")
    def validate_bounds(self) -> "RasterPixelBox":
        if self.px0 > self.px1 or self.py0 > self.py1:
            raise ValueError(
                f"Pixel box coordinates must be ordered: px0 ({self.px0}) <= px1 ({self.px1}) "
                f"and py0 ({self.py0}) <= py1 ({self.py1})"
            )
        return self

    @property
    def width(self) -> float:
        return self.px1 - self.px0

    @property
    def height(self) -> float:
        return self.py1 - self.py0

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def to_int_bounds(self) -> tuple[int, int, int, int]:
        """Returns integer pixel bounds [floor(px0), floor(py0), ceil(px1), ceil(py1)]."""
        return (
            int(math.floor(self.px0)),
            int(math.floor(self.py0)),
            int(math.ceil(self.px1)),
            int(math.ceil(self.py1)),
        )


class AffineMatrix2D(BaseModel):
    """2D Affine Transformation matrix:
    [a, c, e]
    [b, d, f]
    [0, 0, 1]

    Forward mapping:
      x' = a * x + c * y + e
      y' = b * x + d * y + f
    """
    model_config = ConfigDict(extra="forbid")

    a: float
    b: float = 0.0
    c: float = 0.0
    d: float
    e: float = 0.0
    f: float = 0.0

    def determinant(self) -> float:
        return self.a * self.d - self.b * self.c

    def is_invertible(self, tol: float = 1e-12) -> bool:
        return abs(self.determinant()) > tol

    def inverse(self) -> "AffineMatrix2D":
        det = self.determinant()
        if abs(det) <= 1e-12:
            raise RasterTransformError(
                f"Affine transformation matrix is singular (det={det}) and cannot be inverted."
            )
        ia = self.d / det
        ib = -self.b / det
        ic = -self.c / det
        id_ = self.a / det
        ie = (self.c * self.f - self.d * self.e) / det
        if_ = (self.b * self.e - self.a * self.f) / det
        return AffineMatrix2D(a=ia, b=ib, c=ic, d=id_, e=ie, f=if_)

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        tx = self.a * x + self.c * y + self.e
        ty = self.b * x + self.d * y + self.f
        return (tx, ty)

    def as_list(self) -> list[float]:
        return [self.a, self.b, self.c, self.d, self.e, self.f]


# ---------------------------------------------------------------------------
# Transform & Renderer Provenance (Fail-Closed Contract)
# ---------------------------------------------------------------------------

class RasterTransformProvenance(BaseModel):
    """Pinned renderer, scale, color mode, and coordinate transform provenance.

    Fails closed if renderer identity, DPI, scale, or transform matrix is
    missing, corrupted, or non-invertible.
    """
    model_config = ConfigDict(extra="forbid")

    renderer: str
    renderer_version: str
    dpi: float = Field(gt=0)
    scale_x: float = Field(gt=0)
    scale_y: float = Field(gt=0)
    color_mode: ColorMode
    color_channels: int = Field(ge=1, le=4)
    page_width_pt: float = Field(gt=0)
    page_height_pt: float = Field(gt=0)
    pixel_width: int = Field(gt=0)
    pixel_height: int = Field(gt=0)
    pixel_offset_x: int = 0
    pixel_offset_y: int = 0
    transform_matrix: AffineMatrix2D
    inverse_matrix: AffineMatrix2D
    samples_sha256: str | None = None

    @model_validator(mode="after")
    def validate_provenance_metadata(self) -> "RasterTransformProvenance":
        if not self.renderer or not self.renderer.strip():
            raise RasterProvenanceError("Renderer name must not be empty.")
        if not self.renderer_version or not self.renderer_version.strip():
            raise RasterProvenanceError("Renderer version must not be empty.")
        if self.dpi <= 0:
            raise RasterProvenanceError(f"DPI must be positive, got {self.dpi}.")
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise RasterProvenanceError(
                f"Scale factors must be positive: scale_x={self.scale_x}, scale_y={self.scale_y}."
            )
        if not self.transform_matrix.is_invertible():
            raise RasterProvenanceError("Transform matrix is singular and cannot be inverted.")

        # Ensure supplied inverse_matrix matches the analytical inverse
        computed_inv = self.transform_matrix.inverse()
        if (
            abs(self.inverse_matrix.a - computed_inv.a) > 1e-6
            or abs(self.inverse_matrix.b - computed_inv.b) > 1e-6
            or abs(self.inverse_matrix.c - computed_inv.c) > 1e-6
            or abs(self.inverse_matrix.d - computed_inv.d) > 1e-6
            or abs(self.inverse_matrix.e - computed_inv.e) > 1e-4
            or abs(self.inverse_matrix.f - computed_inv.f) > 1e-4
        ):
            raise RasterProvenanceError(
                "Supplied inverse_matrix does not match analytical inverse of transform_matrix."
            )
        return self

    def page_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Maps canonical page coordinates (points) to continuous pixel coordinates."""
        return self.transform_matrix.transform_point(x, y)

    def pixel_to_page(self, px: float, py: float) -> tuple[float, float]:
        """Maps continuous pixel coordinates to canonical page coordinates (points)."""
        return self.inverse_matrix.transform_point(px, py)

    def page_bbox_to_pixel_box(self, bbox: BoundingBox2D) -> RasterPixelBox:
        """Maps a canonical page BoundingBox2D to continuous pixel bounding box."""
        corners = [
            self.page_to_pixel(bbox.x0, bbox.y0),
            self.page_to_pixel(bbox.x1, bbox.y0),
            self.page_to_pixel(bbox.x1, bbox.y1),
            self.page_to_pixel(bbox.x0, bbox.y1),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return RasterPixelBox(
            px0=float(min(xs)),
            py0=float(min(ys)),
            px1=float(max(xs)),
            py1=float(max(ys)),
        )

    def pixel_box_to_page_bbox(self, box: RasterPixelBox, page_index: int) -> BoundingBox2D:
        """Maps a RasterPixelBox to canonical page coordinates BoundingBox2D."""
        corners = [
            self.pixel_to_page(box.px0, box.py0),
            self.pixel_to_page(box.px1, box.py0),
            self.pixel_to_page(box.px1, box.py1),
            self.pixel_to_page(box.px0, box.py1),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return BoundingBox2D(
            page_index=page_index,
            x0=float(min(xs)),
            y0=float(min(ys)),
            x1=float(max(xs)),
            y1=float(max(ys)),
        )

    def round_trip_point(self, x: float, y: float) -> tuple[float, float]:
        """Performs page -> pixel -> page round-trip."""
        px, py = self.page_to_pixel(x, y)
        return self.pixel_to_page(px, py)

    def round_trip_pixel(self, px: float, py: float) -> tuple[float, float]:
        """Performs pixel -> page -> pixel round-trip."""
        x, y = self.pixel_to_page(px, py)
        return self.page_to_pixel(x, y)


def build_transform_provenance(
    page_rect: tuple[float, float, float, float],
    pixel_width: int,
    pixel_height: int,
    dpi: float = 150.0,
    color_mode: ColorMode = ColorMode.GRAY,
    pixel_offset_x: int = 0,
    pixel_offset_y: int = 0,
    samples_sha256: str | None = None,
    renderer_name: str = "pymupdf",
    renderer_ver: str | None = None,
) -> RasterTransformProvenance:
    """Builds and validates RasterTransformProvenance for a page raster."""
    if fitz is None:
        raise RasterAdapterError("PyMuPDF (fitz) is not available.")

    x0, y0, x1, y1 = page_rect
    page_w = float(x1 - x0)
    page_h = float(y1 - y0)
    if page_w <= 0 or page_h <= 0:
        raise RasterProvenanceError(f"Invalid page rectangle dimensions: {page_rect}")

    if dpi <= 0:
        raise RasterProvenanceError(f"DPI must be positive, got {dpi}")
    if pixel_width <= 0 or pixel_height <= 0:
        raise RasterProvenanceError(
            f"Pixel dimensions must be positive: width={pixel_width}, height={pixel_height}"
        )

    scale_x = dpi / 72.0
    scale_y = dpi / 72.0

    # Forward transform:
    # px = (x - x0) * scale_x + pixel_offset_x = scale_x * x + (pixel_offset_x - x0 * scale_x)
    # py = (y - y0) * scale_y + pixel_offset_y = scale_y * y + (pixel_offset_y - y0 * scale_y)
    a = scale_x
    b = 0.0
    c = 0.0
    d = scale_y
    e = float(pixel_offset_x) - float(x0) * scale_x
    f = float(pixel_offset_y) - float(y0) * scale_y

    fwd = AffineMatrix2D(a=a, b=b, c=c, d=d, e=e, f=f)
    inv = fwd.inverse()

    channels = 1
    if color_mode in (ColorMode.RGB,):
        channels = 3
    elif color_mode in (ColorMode.RGBA,):
        channels = 4

    version = renderer_ver if renderer_ver is not None else getattr(fitz, "__version__", "unknown")

    return RasterTransformProvenance(
        renderer=renderer_name,
        renderer_version=version,
        dpi=float(dpi),
        scale_x=float(scale_x),
        scale_y=float(scale_y),
        color_mode=color_mode,
        color_channels=channels,
        page_width_pt=page_w,
        page_height_pt=page_h,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
        pixel_offset_x=pixel_offset_x,
        pixel_offset_y=pixel_offset_y,
        transform_matrix=fwd,
        inverse_matrix=inv,
        samples_sha256=samples_sha256,
    )


# ---------------------------------------------------------------------------
# Typed Raster Evidence Models (Lines, Glyphs, Regions)
# ---------------------------------------------------------------------------

class RasterLineObservation(BaseModel):
    """Typed line observation detected from raster evidence with source pixel box."""
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    pixel_box: RasterPixelBox
    page_bbox: BoundingBox2D
    line_y_pixel: float
    line_y_page: float
    thickness_pixel: float
    thickness_page: float
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: RasterTransformProvenance

    def to_raster_observation(
        self,
        source_file: str | None = None,
        source_hash: str | None = None,
    ) -> RasterObservation:
        """Converts to canonical RasterObservation schema adhering to non-semantic contract."""
        raw_id = self.id
        source_px = self.pixel_box.model_dump()
        obs_prov = ObservationProvenance(
            modality=SourceModality.RASTER,
            source_file=source_file,
            source_hash=source_hash,
            page_index=self.page_index,
            raw_primitive_id=raw_id,
            acquisition_adapter=f"{self.provenance.renderer}.raster.line",
            extra={
                "raster_primitive_type": RasterPrimitiveType.LINE.value,
                "source_pixel_box": source_px,
                "line_y_pixel": self.line_y_pixel,
                "line_y_page": self.line_y_page,
                "thickness_pixel": self.thickness_pixel,
                "thickness_page": self.thickness_page,
                "dpi": self.provenance.dpi,
                "color_mode": self.provenance.color_mode.value,
            },
        )
        return RasterObservation(
            id=raw_id,
            modality=SourceModality.RASTER,
            provenance=obs_prov,
            bbox=self.page_bbox,
            resolution_dpi=self.provenance.dpi,
            pixel_width=self.provenance.pixel_width,
            pixel_height=self.provenance.pixel_height,
            color_channels=self.provenance.color_channels,
            feature_type="region",
            raster_ref=f"sha256:{self.provenance.samples_sha256[:16]}" if self.provenance.samples_sha256 else None,
            confidence=self.confidence,
            extra={
                "raster_primitive_type": RasterPrimitiveType.LINE.value,
                "source_pixel_box": source_px,
                "line_y_pixel": self.line_y_pixel,
                "line_y_page": self.line_y_page,
                "thickness_pixel": self.thickness_pixel,
                "thickness_page": self.thickness_page,
            },
        )


class RasterGlyphObservation(BaseModel):
    """Typed glyph observation detected from raster evidence with source pixel box."""
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    pixel_box: RasterPixelBox
    page_bbox: BoundingBox2D
    pixel_area: int = Field(ge=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: RasterTransformProvenance

    def to_raster_observation(
        self,
        source_file: str | None = None,
        source_hash: str | None = None,
    ) -> RasterObservation:
        """Converts to canonical RasterObservation schema adhering to non-semantic contract."""
        raw_id = self.id
        source_px = self.pixel_box.model_dump()
        obs_prov = ObservationProvenance(
            modality=SourceModality.RASTER,
            source_file=source_file,
            source_hash=source_hash,
            page_index=self.page_index,
            raw_primitive_id=raw_id,
            acquisition_adapter=f"{self.provenance.renderer}.raster.glyph",
            extra={
                "raster_primitive_type": RasterPrimitiveType.GLYPH.value,
                "source_pixel_box": source_px,
                "pixel_area": self.pixel_area,
                "dpi": self.provenance.dpi,
                "color_mode": self.provenance.color_mode.value,
            },
        )
        return RasterObservation(
            id=raw_id,
            modality=SourceModality.RASTER,
            provenance=obs_prov,
            bbox=self.page_bbox,
            resolution_dpi=self.provenance.dpi,
            pixel_width=self.provenance.pixel_width,
            pixel_height=self.provenance.pixel_height,
            color_channels=self.provenance.color_channels,
            feature_type="glyph_crop",
            raster_ref=f"sha256:{self.provenance.samples_sha256[:16]}" if self.provenance.samples_sha256 else None,
            confidence=self.confidence,
            extra={
                "raster_primitive_type": RasterPrimitiveType.GLYPH.value,
                "source_pixel_box": source_px,
                "pixel_area": self.pixel_area,
            },
        )


class RasterRegionObservation(BaseModel):
    """Typed region observation detected from raster evidence with source pixel box."""
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=1)
    pixel_box: RasterPixelBox
    page_bbox: BoundingBox2D
    region_type: str = "region"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: RasterTransformProvenance

    def to_raster_observation(
        self,
        source_file: str | None = None,
        source_hash: str | None = None,
    ) -> RasterObservation:
        """Converts to canonical RasterObservation schema adhering to non-semantic contract."""
        raw_id = self.id
        source_px = self.pixel_box.model_dump()
        obs_prov = ObservationProvenance(
            modality=SourceModality.RASTER,
            source_file=source_file,
            source_hash=source_hash,
            page_index=self.page_index,
            raw_primitive_id=raw_id,
            acquisition_adapter=f"{self.provenance.renderer}.raster.region",
            extra={
                "raster_primitive_type": RasterPrimitiveType.REGION.value,
                "region_type": self.region_type,
                "source_pixel_box": source_px,
                "dpi": self.provenance.dpi,
                "color_mode": self.provenance.color_mode.value,
            },
        )
        return RasterObservation(
            id=raw_id,
            modality=SourceModality.RASTER,
            provenance=obs_prov,
            bbox=self.page_bbox,
            resolution_dpi=self.provenance.dpi,
            pixel_width=self.provenance.pixel_width,
            pixel_height=self.provenance.pixel_height,
            color_channels=self.provenance.color_channels,
            feature_type="region",
            raster_ref=f"sha256:{self.provenance.samples_sha256[:16]}" if self.provenance.samples_sha256 else None,
            confidence=self.confidence,
            extra={
                "raster_primitive_type": RasterPrimitiveType.REGION.value,
                "region_type": self.region_type,
                "source_pixel_box": source_px,
            },
        )


# ---------------------------------------------------------------------------
# Deterministic Page Rendering
# ---------------------------------------------------------------------------

def render_page_deterministic(
    page: Any,
    dpi: float = 150.0,
    color_mode: ColorMode = ColorMode.GRAY,
    clip: tuple[float, float, float, float] | None = None,
) -> tuple[bytes, RasterTransformProvenance]:
    """Renders a PDF page deterministically to raw image bytes and returns pinned provenance.

    Guarantees:
    - Sets alpha=False and explicit colorspace to prevent non-deterministic compositing.
    - Repeated rendering of the same page yields byte-for-byte identical pixel samples.
    - Computes and records SHA-256 hash of pixel samples.
    - Fails closed on invalid page or parameters.
    """
    if fitz is None:
        raise RasterAdapterError("PyMuPDF (fitz) is not installed or available.")

    if not hasattr(page, "rect"):
        raise RasterProvenanceError("Invalid page object: missing 'rect' attribute.")

    if dpi <= 0:
        raise RasterProvenanceError(f"DPI must be positive, got {dpi}.")

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    # Determine colorspace
    if color_mode in (ColorMode.GRAY, ColorMode.BINARY):
        colorspace = fitz.csGRAY
    elif color_mode in (ColorMode.RGB, ColorMode.RGBA):
        colorspace = fitz.csRGB
    else:
        raise RasterProvenanceError(f"Unsupported color mode: {color_mode}")

    clip_rect = fitz.Rect(clip) if clip is not None else None

    try:
        pix = page.get_pixmap(
            matrix=matrix,
            clip=clip_rect,
            alpha=False,
            colorspace=colorspace,
        )
    except Exception as exc:
        raise RasterRenderingError(f"PyMuPDF rendering failed: {exc}") from exc

    raw_samples = bytes(pix.samples)

    # If binary mode, apply strict 128 threshold
    if color_mode == ColorMode.BINARY:
        thresholded = bytearray(len(raw_samples))
        for i, val in enumerate(raw_samples):
            thresholded[i] = 0 if val < 128 else 255
        raw_samples = bytes(thresholded)

    samples_hash = hashlib.sha256(raw_samples).hexdigest()

    # Determine effective page rectangle
    effective_rect = (
        (clip_rect.x0, clip_rect.y0, clip_rect.x1, clip_rect.y1)
        if clip_rect is not None
        else (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
    )

    provenance = build_transform_provenance(
        page_rect=effective_rect,
        pixel_width=int(pix.width),
        pixel_height=int(pix.height),
        dpi=dpi,
        color_mode=color_mode,
        pixel_offset_x=int(getattr(pix, "x", 0)),
        pixel_offset_y=int(getattr(pix, "y", 0)),
        samples_sha256=samples_hash,
    )

    return raw_samples, provenance


# ---------------------------------------------------------------------------
# Classical Feature Extraction (No ML Model Loading)
# ---------------------------------------------------------------------------

def extract_raster_line_observations(
    image_bytes: bytes,
    provenance: RasterTransformProvenance,
    page_index: int,
    min_width_ratio: float = 0.15,
    threshold: int = 128,
    max_x_gap_pt: float = 30.0,
) -> list[RasterLineObservation]:
    """Extracts horizontal line observations deterministically using run analysis.

    Lines are physical horizontal ink runs spanning >= min_width_ratio of the
    rendered width, merging collinear runs across small gaps (e.g. fret cutouts)
    and grouping vertically adjacent scanlines.
    """
    width = provenance.pixel_width
    height = provenance.pixel_height
    min_run_len = max(5, int(width * min_width_ratio))
    max_gap_px = int(max_x_gap_pt * provenance.scale_x) if max_x_gap_pt > 0 else 0

    if len(image_bytes) < width * height:
        raise RasterAdapterError(
            f"Image sample buffer length ({len(image_bytes)}) is smaller than width*height ({width*height})"
        )

    # Extract dark horizontal runs per scanline and merge collinear segments across gaps
    runs: list[tuple[int, int, int]] = []  # (y, x0, x1)
    for y in range(height):
        row_start = y * width
        run_start: int | None = None
        row_runs: list[tuple[int, int]] = []
        for x in range(width):
            pixel_val = image_bytes[row_start + x]
            if pixel_val < threshold:  # dark pixel
                if run_start is None:
                    run_start = x
            else:
                if run_start is not None:
                    if (x - run_start) >= 3:
                        row_runs.append((run_start, x))
                    run_start = None
        if run_start is not None and (width - run_start) >= 3:
            row_runs.append((run_start, width))

        if row_runs:
            # Merge collinear runs along the same scanline separated by <= max_gap_px
            merged_row: list[tuple[int, int]] = [row_runs[0]]
            for r in row_runs[1:]:
                last_r = merged_row[-1]
                if (r[0] - last_r[1]) <= max_gap_px:
                    merged_row[-1] = (last_r[0], r[1])
                else:
                    merged_row.append(r)

            for mr0, mr1 in merged_row:
                if (mr1 - mr0) >= min_run_len:
                    runs.append((y, mr0, mr1))

    # Merge vertically adjacent runs representing thick or multi-pixel lines
    merged: list[dict[str, Any]] = []
    for y, x0, x1 in runs:
        if not merged:
            merged.append({"y0": y, "y1": y, "x0": x0, "x1": x1, "count": 1})
        else:
            last = merged[-1]
            if y - last["y1"] <= 2 and max(x0, last["x0"]) < min(x1, last["x1"]):
                last["y1"] = y
                last["x0"] = min(last["x0"], x0)
                last["x1"] = max(last["x1"], x1)
                last["count"] += 1
            else:
                merged.append({"y0": y, "y1": y, "x0": x0, "x1": x1, "count": 1})

    line_observations: list[RasterLineObservation] = []
    for idx, item in enumerate(merged):
        y0, y1 = item["y0"], item["y1"]
        x0, x1 = item["x0"], item["x1"]
        px_box = RasterPixelBox(
            px0=float(x0),
            py0=float(y0),
            px1=float(x1),
            py1=float(y1 + 1),
        )
        page_bbox = provenance.pixel_box_to_page_bbox(px_box, page_index)
        mid_y_px = (y0 + y1 + 1) / 2.0
        mid_y_page = provenance.pixel_to_page(float(x0), mid_y_px)[1]
        thickness_px = float(y1 - y0 + 1)
        thickness_page = thickness_px / provenance.scale_y

        obs_id = f"p{page_index}_rline_{idx}"
        line_obs = RasterLineObservation(
            id=obs_id,
            page_index=page_index,
            pixel_box=px_box,
            page_bbox=page_bbox,
            line_y_pixel=mid_y_px,
            line_y_page=mid_y_page,
            thickness_pixel=thickness_px,
            thickness_page=thickness_page,
            confidence=1.0,
            provenance=provenance,
        )
        line_observations.append(line_obs)

    return line_observations


def extract_raster_glyph_observations(
    image_bytes: bytes,
    provenance: RasterTransformProvenance,
    page_index: int,
    min_area: int = 4,
    max_area: int | None = None,
    threshold: int = 128,
) -> list[RasterGlyphObservation]:
    """Extracts discrete glyph / symbol components deterministically using 8-connected CCL.

    Filters out single-pixel noise (< min_area) and huge border/frame regions.
    """
    width = provenance.pixel_width
    height = provenance.pixel_height

    if len(image_bytes) < width * height:
        raise RasterAdapterError("Sample buffer smaller than width*height")

    # 1. Extract runs of dark pixels per scanline
    runs_by_row: list[list[int]] = []
    all_runs: list[tuple[int, int, int]] = []  # (y, x0, x1)

    for y in range(height):
        row_offset = y * width
        run_start: int | None = None
        row_runs: list[int] = []
        for x in range(width):
            if image_bytes[row_offset + x] < threshold:
                if run_start is None:
                    run_start = x
            else:
                if run_start is not None:
                    run_idx = len(all_runs)
                    all_runs.append((y, run_start, x))
                    row_runs.append(run_idx)
                    run_start = None
        if run_start is not None:
            run_idx = len(all_runs)
            all_runs.append((y, run_start, width))
            row_runs.append(run_idx)
        runs_by_row.append(row_runs)

    if not all_runs:
        return []

    # 2. Union-Find for 8-connectivity between adjacent rows
    parent = list(range(len(all_runs)))

    def find_root(i: int) -> int:
        path: list[int] = []
        while parent[i] != i:
            path.append(i)
            i = parent[i]
        for node in path:
            parent[node] = i
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find_root(i), find_root(j)
        if ri != rj:
            parent[ri] = rj

    for y in range(1, height):
        prev_row = runs_by_row[y - 1]
        curr_row = runs_by_row[y]
        if not prev_row or not curr_row:
            continue
        p_idx = 0
        c_idx = 0
        while p_idx < len(prev_row) and c_idx < len(curr_row):
            _, px0, px1 = all_runs[prev_row[p_idx]]
            _, cx0, cx1 = all_runs[curr_row[c_idx]]
            # 8-connectivity: overlap with 1-pixel margin
            if max(px0 - 1, cx0) <= min(px1, cx1):
                union(prev_row[p_idx], curr_row[c_idx])
            if px1 < cx1:
                p_idx += 1
            else:
                c_idx += 1

    # 3. Aggregate components
    components: dict[int, list[int]] = {}  # root -> [min_x, min_y, max_x, max_y, area]
    for idx, (y, x0, x1) in enumerate(all_runs):
        root = find_root(idx)
        area = x1 - x0
        if root not in components:
            components[root] = [x0, y, x1, y + 1, area]
        else:
            comp = components[root]
            if x0 < comp[0]:
                comp[0] = x0
            if y < comp[1]:
                comp[1] = y
            if x1 > comp[2]:
                comp[2] = x1
            if y + 1 > comp[3]:
                comp[3] = y + 1
            comp[4] += area

    effective_max_area = max_area if max_area is not None else int(width * height * 0.15)
    max_glyph_w = int(width * 0.25)
    max_glyph_h = int(height * 0.25)

    glyphs: list[RasterGlyphObservation] = []
    glyph_idx = 0
    # Sort components by top-to-bottom, left-to-right for determinism
    sorted_comps = sorted(components.values(), key=lambda c: (c[1], c[0]))

    for c in sorted_comps:
        x0, y0, x1, y1, area = c[0], c[1], c[2], c[3], c[4]
        box_w = x1 - x0
        box_h = y1 - y0

        if area < min_area or area > effective_max_area:
            continue
        if box_w > max_glyph_w or box_h > max_glyph_h:
            continue

        px_box = RasterPixelBox(
            px0=float(x0),
            py0=float(y0),
            px1=float(x1),
            py1=float(y1),
        )
        page_bbox = provenance.pixel_box_to_page_bbox(px_box, page_index)
        glyph_obs = RasterGlyphObservation(
            id=f"p{page_index}_rglyph_{glyph_idx}",
            page_index=page_index,
            pixel_box=px_box,
            page_bbox=page_bbox,
            pixel_area=area,
            confidence=1.0,
            provenance=provenance,
        )
        glyphs.append(glyph_obs)
        glyph_idx += 1

    return glyphs


def extract_raster_region_observations(
    image_bytes: bytes,
    provenance: RasterTransformProvenance,
    page_index: int,
    threshold: int = 128,
) -> list[RasterRegionObservation]:
    """Extracts macro regions (e.g. content bounding box and page boundary)."""
    width = provenance.pixel_width
    height = provenance.pixel_height

    # 1. Full page observation
    page_px_box = RasterPixelBox(px0=0.0, py0=0.0, px1=float(width), py1=float(height))
    page_bbox = provenance.pixel_box_to_page_bbox(page_px_box, page_index)

    regions: list[RasterRegionObservation] = [
        RasterRegionObservation(
            id=f"p{page_index}_rreg_page",
            page_index=page_index,
            pixel_box=page_px_box,
            page_bbox=page_bbox,
            region_type="page_crop",
            confidence=1.0,
            provenance=provenance,
        )
    ]

    # 2. Content bounds (ink extents)
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1

    for y in range(height):
        row_offset = y * width
        for x in range(width):
            if image_bytes[row_offset + x] < threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y

    if max_x >= min_x and max_y >= min_y:
        content_box = RasterPixelBox(
            px0=float(min_x),
            py0=float(min_y),
            px1=float(max_x + 1),
            py1=float(max_y + 1),
        )
        content_bbox = provenance.pixel_box_to_page_bbox(content_box, page_index)
        regions.append(
            RasterRegionObservation(
                id=f"p{page_index}_rreg_content",
                page_index=page_index,
                pixel_box=content_box,
                page_bbox=content_bbox,
                region_type="content_extent",
                confidence=1.0,
                provenance=provenance,
            )
        )

    return regions


# ---------------------------------------------------------------------------
# Pluggable Feature Extractor Protocol
# ---------------------------------------------------------------------------

class RasterFeatureExtractor(Protocol):
    """Protocol for external raster detectors, keeping model loading outside the adapter."""
    def __call__(
        self,
        image_bytes: bytes,
        provenance: RasterTransformProvenance,
        page_index: int,
    ) -> list[RasterObservation]:
        ...


def extract_raster_observations_for_page(
    page: Any,
    page_index: int,
    dpi: float = 150.0,
    color_mode: ColorMode = ColorMode.GRAY,
    source_file: str | None = None,
    source_hash: str | None = None,
    extractor: RasterFeatureExtractor | Callable[[bytes, RasterTransformProvenance, int], list[RasterObservation]] | None = None,
) -> list[RasterObservation]:
    """Renders page deterministically and extracts typed raster observations.

    Uses classical algorithms by default. Accepts custom external extractors
    while keeping model loading strictly outside the adapter interface.
    """
    raw_samples, provenance = render_page_deterministic(
        page,
        dpi=dpi,
        color_mode=color_mode,
    )

    if extractor is not None:
        return extractor(raw_samples, provenance, page_index)

    # Classical extraction
    line_obs = extract_raster_line_observations(raw_samples, provenance, page_index)
    glyph_obs = extract_raster_glyph_observations(raw_samples, provenance, page_index)
    region_obs = extract_raster_region_observations(raw_samples, provenance, page_index)

    results: list[RasterObservation] = []
    for reg in region_obs:
        results.append(reg.to_raster_observation(source_file, source_hash))
    for line in line_obs:
        results.append(line.to_raster_observation(source_file, source_hash))
    for glyph in glyph_obs:
        results.append(glyph.to_raster_observation(source_file, source_hash))

    return results


def observe_raster(
    source: str | Path | bytes | Any,
    dpi: float = 150.0,
    color_mode: ColorMode = ColorMode.GRAY,
    extractor: RasterFeatureExtractor | Callable[[bytes, RasterTransformProvenance, int], list[RasterObservation]] | None = None,
) -> list[RasterObservation]:
    """Top-level entrypoint to acquire raster observations across all pages of a PDF."""
    if fitz is None:
        raise RasterAdapterError("PyMuPDF is not installed or available.")

    doc: Any = None
    source_file: str | None = None
    source_hash: str | None = None
    should_close = False

    try:
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.is_file():
                raise RasterAdapterError(f"File not found: {source}")
            source_file = str(p)
            data = p.read_bytes()
            source_hash = hashlib.sha256(data).hexdigest()
            doc = fitz.open(stream=data, filetype="pdf")
            should_close = True
        elif isinstance(source, bytes):
            source_hash = hashlib.sha256(source).hexdigest()
            doc = fitz.open(stream=source, filetype="pdf")
            should_close = True
        elif hasattr(source, "page_count") and hasattr(source, "__iter__"):
            doc = source
        else:
            raise RasterAdapterError(f"Unsupported document source type: {type(source)}")

        all_rasters: list[RasterObservation] = []
        for page_idx, page in enumerate(doc, start=1):
            page_rasters = extract_raster_observations_for_page(
                page=page,
                page_index=page_idx,
                dpi=dpi,
                color_mode=color_mode,
                source_file=source_file,
                source_hash=source_hash,
                extractor=extractor,
            )
            all_rasters.extend(page_rasters)

        return all_rasters
    finally:
        if should_close and doc is not None:
            doc.close()


# ---------------------------------------------------------------------------
# Non-Destructive Peer Observation Integration (Never Mutate/Overwrite)
# ---------------------------------------------------------------------------

def attach_raster_observations(
    observations: DocumentObservations,
    raster_observations: Sequence[RasterObservation],
) -> DocumentObservations:
    """Attaches raster observations as peer evidence without mutating vector/text observations.

    Invariant:
    - Never mutates, overwrites, or removes existing vector or text observations.
    - Preserves all vector and text IDs, counts, and contents exactly.
    - Transitions modality to HYBRID when peer modalities co-exist.
    """
    # Defensive snapshot checks
    orig_vector_ids = [v.id for v in observations.vectors]
    orig_text_ids = [t.id for t in observations.texts]
    orig_vector_count = len(observations.vectors)
    orig_text_count = len(observations.texts)

    existing_raster_ids = {r.id for r in observations.rasters}
    new_rasters = list(observations.rasters)

    for r in raster_observations:
        if r.id in existing_raster_ids:
            raise ValueError(f"Duplicate raster observation ID '{r.id}' cannot be attached.")
        existing_raster_ids.add(r.id)
        new_rasters.append(r)

    # Determine resulting modality
    has_vectors = orig_vector_count > 0
    has_texts = orig_text_count > 0
    has_rasters = len(new_rasters) > 0

    modality_count = sum([has_vectors, has_texts, has_rasters])
    if modality_count > 1:
        new_modality = SourceModality.HYBRID
    elif has_rasters:
        new_modality = SourceModality.RASTER
    elif has_vectors:
        new_modality = SourceModality.VECTOR
    elif has_texts:
        new_modality = SourceModality.TEXT
    else:
        new_modality = SourceModality.HYBRID

    # Build fresh DocumentObservations without mutating existing vectors/texts
    updated = DocumentObservations(
        schema_version=observations.schema_version,
        document_id=observations.document_id,
        modality=new_modality,
        source_file=observations.source_file,
        page_count=observations.page_count,
        vectors=list(observations.vectors),
        texts=list(observations.texts),
        rasters=new_rasters,
        scale_estimates=dict(observations.scale_estimates),
        metadata=dict(observations.metadata),
    )

    # Assert invariant: vectors and texts are identical
    assert len(updated.vectors) == orig_vector_count, "Vector observations count altered during attach!"
    assert [v.id for v in updated.vectors] == orig_vector_ids, "Vector observation IDs altered during attach!"
    assert len(updated.texts) == orig_text_count, "Text observations count altered during attach!"
    assert [t.id for t in updated.texts] == orig_text_ids, "Text observation IDs altered during attach!"

    return updated


# ---------------------------------------------------------------------------
# Cross-Modal Disagreement Preservation (Never Averaged Away)
# ---------------------------------------------------------------------------

class CrossModalDisagreementKind(StrEnum):
    """Categorization of observable cross-modal disparity."""
    VECTOR_ONLY = "vector_only"
    TEXT_ONLY = "text_only"
    RASTER_ONLY = "raster_only"
    POSITION_DISPARITY = "position_disparity"
    EXTENT_DISPARITY = "extent_disparity"
    COUNT_MISMATCH = "count_mismatch"


class CrossModalLineMatch(BaseModel):
    """Matched line pair retaining both vector and raster values distinctly."""
    model_config = ConfigDict(extra="forbid")

    vector_id: str
    raster_id: str
    vector_bbox: BoundingBox2D
    raster_bbox: BoundingBox2D
    vector_y_pt: float
    raster_y_pt: float
    delta_y_pt: float
    delta_x0_pt: float
    delta_x1_pt: float
    disparity_pt: float


class CrossModalDisagreement(BaseModel):
    """Observable disagreement between vector/text and raster evidence."""
    model_config = ConfigDict(extra="forbid")

    kind: CrossModalDisagreementKind
    description: str
    vector_id: str | None = None
    text_id: str | None = None
    raster_id: str | None = None
    vector_bbox: BoundingBox2D | None = None
    text_bbox: BoundingBox2D | None = None
    raster_bbox: BoundingBox2D | None = None
    disparity_pt: float | None = None


class CrossModalLineComparisonResult(BaseModel):
    """Observable outcome of cross-modal line comparison.

    Invariant: Coordinates are NEVER averaged together. Disagreements and
    individual modality measurements remain explicitly inspectable.
    """
    model_config = ConfigDict(extra="forbid")

    page_index: int
    total_vectors: int
    total_rasters: int
    matched_pairs: list[CrossModalLineMatch]
    vector_only_ids: list[str]
    raster_only_ids: list[str]
    disagreements: list[CrossModalDisagreement]
    mean_y_disparity_pt: float | None = None
    max_y_disparity_pt: float | None = None


def compare_vector_and_raster_lines(
    vectors: Sequence[VectorPathObservation],
    rasters: Sequence[RasterObservation],
    tolerance_pt: float = 3.0,
    page_index: int = 1,
) -> CrossModalLineComparisonResult:
    """Compares vector lines with raster line observations in canonical page coordinates.

    Matches lines within tolerance_pt along the y-axis, records differences,
    and preserves disagreements without averaging coordinates.
    """
    # Filter to horizontal lines on target page
    target_vectors: list[VectorPathObservation] = []
    for v in vectors:
        if v.bbox.page_index == page_index:
            w = v.bbox.x1 - v.bbox.x0
            h = v.bbox.y1 - v.bbox.y0
            if w >= 20.0 and h <= 5.0:
                target_vectors.append(v)

    target_rasters: list[RasterObservation] = []
    for r in rasters:
        if r.bbox.page_index == page_index:
            is_line = r.extra.get("raster_primitive_type") == RasterPrimitiveType.LINE.value
            w = r.bbox.x1 - r.bbox.x0
            h = r.bbox.y1 - r.bbox.y0
            if is_line or (w >= 20.0 and h <= 5.0):
                target_rasters.append(r)

    def vec_y(v: VectorPathObservation) -> float:
        return (v.bbox.y0 + v.bbox.y1) / 2.0

    def ras_y(r: RasterObservation) -> float:
        if "line_y_page" in r.extra:
            return float(r.extra["line_y_page"])
        return (r.bbox.y0 + r.bbox.y1) / 2.0

    sorted_vectors = sorted(target_vectors, key=vec_y)
    sorted_rasters = sorted(target_rasters, key=ras_y)

    matched_pairs: list[CrossModalLineMatch] = []
    unmatched_vector_ids: set[str] = {v.id for v in sorted_vectors}
    unmatched_raster_ids: set[str] = {r.id for r in sorted_rasters}
    disagreements: list[CrossModalDisagreement] = []

    for v in sorted_vectors:
        vy = vec_y(v)
        best_match: RasterObservation | None = None
        best_delta: float = float("inf")

        for r in sorted_rasters:
            if r.id not in unmatched_raster_ids:
                continue
            ry = ras_y(r)
            delta = abs(ry - vy)
            if delta <= tolerance_pt and delta < best_delta:
                if max(v.bbox.x0, r.bbox.x0) < min(v.bbox.x1, r.bbox.x1):
                    best_match = r
                    best_delta = delta

        if best_match is not None:
            ry = ras_y(best_match)
            unmatched_vector_ids.discard(v.id)
            unmatched_raster_ids.discard(best_match.id)

            dy = ry - vy
            dx0 = best_match.bbox.x0 - v.bbox.x0
            dx1 = best_match.bbox.x1 - v.bbox.x1

            match = CrossModalLineMatch(
                vector_id=v.id,
                raster_id=best_match.id,
                vector_bbox=v.bbox,
                raster_bbox=best_match.bbox,
                vector_y_pt=vy,
                raster_y_pt=ry,
                delta_y_pt=dy,
                delta_x0_pt=dx0,
                delta_x1_pt=dx1,
                disparity_pt=abs(dy),
            )
            matched_pairs.append(match)

            if abs(dy) > 0.5:
                disagreements.append(
                    CrossModalDisagreement(
                        kind=CrossModalDisagreementKind.POSITION_DISPARITY,
                        description=(
                            f"Vertical line disparity between vector '{v.id}' ({vy:.3f} pt) "
                            f"and raster '{best_match.id}' ({ry:.3f} pt): delta={dy:+.3f} pt"
                        ),
                        vector_id=v.id,
                        raster_id=best_match.id,
                        vector_bbox=v.bbox,
                        raster_bbox=best_match.bbox,
                        disparity_pt=abs(dy),
                    )
                )

    for vid in sorted(unmatched_vector_ids):
        v_item = next(v for v in sorted_vectors if v.id == vid)
        disagreements.append(
            CrossModalDisagreement(
                kind=CrossModalDisagreementKind.VECTOR_ONLY,
                description=f"Vector line '{vid}' at y={vec_y(v_item):.3f} pt has no matching raster line.",
                vector_id=vid,
                vector_bbox=v_item.bbox,
            )
        )

    for rid in sorted(unmatched_raster_ids):
        r_item = next(r for r in sorted_rasters if r.id == rid)
        disagreements.append(
            CrossModalDisagreement(
                kind=CrossModalDisagreementKind.RASTER_ONLY,
                description=f"Raster line '{rid}' at y={ras_y(r_item):.3f} pt has no matching vector line.",
                raster_id=rid,
                raster_bbox=r_item.bbox,
            )
        )

    if len(target_vectors) != len(target_rasters):
        disagreements.append(
            CrossModalDisagreement(
                kind=CrossModalDisagreementKind.COUNT_MISMATCH,
                description=(
                    f"Line count mismatch on page {page_index}: "
                    f"vectors={len(target_vectors)}, rasters={len(target_rasters)}"
                ),
            )
        )

    mean_disp = (
        sum(m.disparity_pt for m in matched_pairs) / len(matched_pairs)
        if matched_pairs
        else None
    )
    max_disp = (
        max((m.disparity_pt for m in matched_pairs), default=None)
        if matched_pairs
        else None
    )

    return CrossModalLineComparisonResult(
        page_index=page_index,
        total_vectors=len(target_vectors),
        total_rasters=len(target_rasters),
        matched_pairs=matched_pairs,
        vector_only_ids=sorted(unmatched_vector_ids),
        raster_only_ids=sorted(unmatched_raster_ids),
        disagreements=disagreements,
        mean_y_disparity_pt=mean_disp,
        max_y_disparity_pt=max_disp,
    )


class CrossModalGlyphMatch(BaseModel):
    """Matched text/glyph pair retaining independent coordinates."""
    model_config = ConfigDict(extra="forbid")

    text_id: str
    raster_id: str
    text_bbox: BoundingBox2D
    raster_bbox: BoundingBox2D
    disparity_center_pt: float
    overlap_iou: float


class CrossModalGlyphComparisonResult(BaseModel):
    """Outcome of cross-modal glyph/text comparison preserving disagreements."""
    model_config = ConfigDict(extra="forbid")

    page_index: int
    total_texts: int
    total_rasters: int
    matched_pairs: list[CrossModalGlyphMatch]
    text_only_ids: list[str]
    raster_only_ids: list[str]
    disagreements: list[CrossModalDisagreement]
    mean_disparity_pt: float | None = None


def compare_text_and_raster_glyphs(
    texts: Sequence[TextObservation],
    rasters: Sequence[RasterObservation],
    tolerance_pt: float = 5.0,
    page_index: int = 1,
) -> CrossModalGlyphComparisonResult:
    """Compares text observations with raster glyph observations in page coordinates."""
    target_texts = [t for t in texts if t.bbox.page_index == page_index]
    target_rasters = [
        r for r in rasters
        if r.bbox.page_index == page_index
        and r.extra.get("raster_primitive_type") == RasterPrimitiveType.GLYPH.value
    ]

    def box_center(b: BoundingBox2D) -> tuple[float, float]:
        return ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0)

    def compute_iou(b1: BoundingBox2D, b2: BoundingBox2D) -> float:
        ix0 = max(b1.x0, b2.x0)
        iy0 = max(b1.y0, b2.y0)
        ix1 = min(b1.x1, b2.x1)
        iy1 = min(b1.y1, b2.y1)
        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0
        inter = (ix1 - ix0) * (iy1 - iy0)
        a1 = (b1.x1 - b1.x0) * (b1.y1 - b1.y0)
        a2 = (b2.x1 - b2.x0) * (b2.y1 - b2.y0)
        denom = a1 + a2 - inter
        return inter / denom if denom > 0 else 0.0

    matched_pairs: list[CrossModalGlyphMatch] = []
    unmatched_text_ids: set[str] = {t.id for t in target_texts}
    unmatched_raster_ids: set[str] = {r.id for r in target_rasters}
    disagreements: list[CrossModalDisagreement] = []

    for t in target_texts:
        tc = box_center(t.bbox)
        best_r: RasterObservation | None = None
        best_dist = float("inf")

        for r in target_rasters:
            if r.id not in unmatched_raster_ids:
                continue
            rc = box_center(r.bbox)
            dist = math.hypot(rc[0] - tc[0], rc[1] - tc[1])
            if dist <= tolerance_pt and dist < best_dist:
                best_r = r
                best_dist = dist

        if best_r is not None:
            unmatched_text_ids.discard(t.id)
            unmatched_raster_ids.discard(best_r.id)
            iou = compute_iou(t.bbox, best_r.bbox)
            match = CrossModalGlyphMatch(
                text_id=t.id,
                raster_id=best_r.id,
                text_bbox=t.bbox,
                raster_bbox=best_r.bbox,
                disparity_center_pt=best_dist,
                overlap_iou=iou,
            )
            matched_pairs.append(match)

            if best_dist > 1.0:
                disagreements.append(
                    CrossModalDisagreement(
                        kind=CrossModalDisagreementKind.POSITION_DISPARITY,
                        description=(
                            f"Center disparity between text '{t.id}' and raster glyph '{best_r.id}': "
                            f"{best_dist:.3f} pt"
                        ),
                        text_id=t.id,
                        raster_id=best_r.id,
                        text_bbox=t.bbox,
                        raster_bbox=best_r.bbox,
                        disparity_pt=best_dist,
                    )
                )

    for tid in sorted(unmatched_text_ids):
        t_item = next(t for t in target_texts if t.id == tid)
        disagreements.append(
            CrossModalDisagreement(
                kind=CrossModalDisagreementKind.TEXT_ONLY,
                description=f"Text span '{tid}' has no matching raster glyph.",
                text_id=tid,
                text_bbox=t_item.bbox,
            )
        )

    for rid in sorted(unmatched_raster_ids):
        r_item = next(r for r in target_rasters if r.id == rid)
        disagreements.append(
            CrossModalDisagreement(
                kind=CrossModalDisagreementKind.RASTER_ONLY,
                description=f"Raster glyph '{rid}' has no matching text observation.",
                raster_id=rid,
                raster_bbox=r_item.bbox,
            )
        )

    mean_disp = (
        sum(m.disparity_center_pt for m in matched_pairs) / len(matched_pairs)
        if matched_pairs
        else None
    )

    return CrossModalGlyphComparisonResult(
        page_index=page_index,
        total_texts=len(target_texts),
        total_rasters=len(target_rasters),
        matched_pairs=matched_pairs,
        text_only_ids=sorted(unmatched_text_ids),
        raster_only_ids=sorted(unmatched_raster_ids),
        disagreements=disagreements,
        mean_disparity_pt=mean_disp,
    )
