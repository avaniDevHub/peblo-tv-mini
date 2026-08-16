"""Artwork validation — the 3 sizes must be *genuinely* enforced.

These are pure-function tests (no HTTP) over the validator, using in-memory
images generated with Pillow to mirror the shipped good/bad sample assets.
"""
from __future__ import annotations

import io

from PIL import Image

from app.services.artwork import validate_artwork


def _img_bytes(w: int, h: int, fmt: str = "JPEG", noise: bool = False) -> bytes:
    img = Image.new("RGB", (w, h), (30, 90, 160))
    if noise:  # make PNG incompressible to blow past the size ceiling
        px = img.load()
        for y in range(h):
            for x in range(w):
                px[x, y] = ((x * 131 + y * 57) % 256, (y * 197 + x * 29) % 256, (x * x + y * y) % 256)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def test_good_poster_accepted():
    res = validate_artwork("poster", _img_bytes(600, 900))
    assert res.ok, res.errors
    assert (res.width, res.height) == (600, 900)


def test_good_banner_and_thumbnail_accepted():
    assert validate_artwork("banner", _img_bytes(1280, 720)).ok
    assert validate_artwork("thumbnail", _img_bytes(640, 360)).ok


def test_wrong_aspect_rejected():
    # 900x900 square uploaded as a poster (should be 2:3)
    res = validate_artwork("poster", _img_bytes(900, 900))
    assert not res.ok
    assert any("shape" in e.lower() or "crop" in e.lower() for e in res.errors)


def test_too_small_rejected():
    # 64x36 has the right 16:9 ratio but is far too small for a thumbnail
    res = validate_artwork("thumbnail", _img_bytes(64, 36))
    assert not res.ok
    assert any("too small" in e.lower() or "blurry" in e.lower() for e in res.errors)


def test_over_size_limit_rejected():
    # Correct 16:9 ratio but > 200 KB (incompressible PNG at 1920x1080, which is
    # within the +15% dimension tolerance of the 1280x720 banner target's ...
    # actually it's larger, so it also trips dims — the point is the SIZE error).
    data = _img_bytes(1920, 1080, fmt="PNG", noise=True)
    assert len(data) > 200 * 1024  # sanity: our fixture really is oversized
    res = validate_artwork("banner", data)
    assert not res.ok
    assert any("KB" in e or "limit" in e.lower() for e in res.errors)


def test_non_image_rejected_cleanly():
    res = validate_artwork("poster", b"this is definitely not an image")
    assert not res.ok
    assert any("image" in e.lower() for e in res.errors)


def test_unknown_slot_rejected():
    res = validate_artwork("billboard", _img_bytes(600, 900))
    assert not res.ok
