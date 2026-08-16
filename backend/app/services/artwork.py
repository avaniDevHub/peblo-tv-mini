"""Artwork validation.

Validates an uploaded image against the spec for its slot (poster/banner/
thumbnail) from ``reference.json`` and returns errors a *content editor* — not an
engineer — can act on. We check, in order: decodable image, aspect ratio,
dimensions, and file-size ceiling. All failing checks are returned together so
the editor fixes everything in one pass instead of playing whack-a-mole.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, UnidentifiedImageError

from ..reference import artwork_specs

# How much the pixel dimensions may drift from target and still be accepted.
# The specs say "~600×900" etc., so we allow a tolerance band rather than exact.
DIMENSION_TOLERANCE = 0.15  # ±15%
# Aspect ratio tolerance (ratios rarely land exactly on 0.6667).
ASPECT_TOLERANCE = 0.02
KB = 1024


@dataclass
class ArtworkValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    content_type: str | None = None


def _aspect_value(aspect: str) -> float:
    w, h = aspect.split(":")
    return int(w) / int(h)


def _fmt_kb(n: int) -> str:
    return f"{n / KB:.0f} KB"


def validate_artwork(kind: str, data: bytes, filename: str | None = None) -> ArtworkValidationResult:
    """Validate raw upload bytes for a given artwork ``kind``.

    Returns a result with human-readable errors. Never raises on bad *image*
    content — it reports it — so the endpoint can return a clean 422.
    """
    specs = artwork_specs()
    if kind not in specs:
        return ArtworkValidationResult(
            ok=False,
            errors=[f"Unknown artwork slot '{kind}'. Expected one of: {', '.join(specs)}."],
        )

    spec = specs[kind]
    target_w, target_h = spec["target_px"]
    max_kb = spec["max_kb"]
    aspect_label = spec["aspect"]
    target_aspect = _aspect_value(aspect_label)

    errors: list[str] = []

    # 1) Is it a real, decodable image?
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        return ArtworkValidationResult(
            ok=False,
            errors=[
                "This file isn't a readable image. Please upload a JPG or PNG exported from your design tool."
            ],
            bytes=len(data),
        )

    width, height = img.size
    size_bytes = len(data)
    content_type = Image.MIME.get(img.format, "application/octet-stream")

    # 2) Aspect ratio — the most common editor mistake (square export, etc.).
    actual_aspect = width / height if height else 0
    if abs(actual_aspect - target_aspect) > ASPECT_TOLERANCE:
        errors.append(
            f"Wrong shape for the {kind}: it should be {aspect_label} "
            f"(about {target_w}×{target_h}), but this image is {width}×{height}. "
            f"Please crop or export it as {aspect_label}."
        )

    # 3) Dimensions within tolerance of target.
    min_w, max_w = target_w * (1 - DIMENSION_TOLERANCE), target_w * (1 + DIMENSION_TOLERANCE)
    min_h, max_h = target_h * (1 - DIMENSION_TOLERANCE), target_h * (1 + DIMENSION_TOLERANCE)
    if not (min_w <= width <= max_w and min_h <= height <= max_h):
        if width < min_w or height < min_h:
            errors.append(
                f"The {kind} is too small: {width}×{height}. It will look blurry on a TV. "
                f"Please upload close to {target_w}×{target_h}."
            )
        else:
            errors.append(
                f"The {kind} is larger than expected: {width}×{height}. "
                f"Please resize it to about {target_w}×{target_h}."
            )

    # 4) File-size ceiling.
    if size_bytes > max_kb * KB:
        errors.append(
            f"The {kind} file is {_fmt_kb(size_bytes)}, over the {max_kb} KB limit. "
            f"Please export at a lower quality or as a JPG to shrink the file."
        )

    return ArtworkValidationResult(
        ok=not errors,
        errors=errors,
        width=width,
        height=height,
        bytes=size_bytes,
        content_type=content_type,
    )
