"""Unit tests for Notro's pure compression logic.

These exercise ``compress_image`` / ``estimate_png_size`` only — no clipboard or
Windows API calls. Importing ``notro_app`` modules requires Windows (they
bind to user32/kernel32 at import time), so these run on the ``windows-latest``
CI runner.
"""

from PIL import Image

from notro_app import compress, config


def test_small_image_compresses_to_webp():
    img = Image.new("RGB", (300, 300), (10, 20, 30))
    result = compress.compress_image(img, config.LIMIT_BYTES)
    assert result is not None
    data, ext = result
    assert ext == ".webp"
    assert 0 < len(data) <= config.LIMIT_BYTES


def test_result_always_under_requested_limit():
    # A solid image compresses to well under a small limit without downscaling.
    img = Image.new("RGB", (1000, 1000), (200, 100, 50))
    limit = 20_000  # 20 KB
    result = compress.compress_image(img, limit)
    assert result is not None
    data, ext = result
    assert len(data) <= limit
    assert ext in (".webp", ".jpg")


def test_impossible_limit_returns_none():
    # Nothing can be encoded under 1 byte, even after downscaling to MIN_SCALE.
    img = Image.new("RGB", (500, 500), (123, 222, 64))
    assert compress.compress_image(img, 1) is None


def test_rgba_image_is_supported():
    img = Image.new("RGBA", (200, 200), (0, 128, 255, 128))
    result = compress.compress_image(img, config.LIMIT_BYTES)
    assert result is not None
    data, ext = result
    assert len(data) > 0
    assert ext in (".webp", ".jpg")


def test_estimate_png_size_is_positive():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    assert compress.estimate_png_size(img) > 0


def test_limit_bytes_has_safety_margin():
    # LIMIT_BYTES must be below the raw MB limit (safety margin applied).
    raw = config.LIMIT_MB * 1024 * 1024
    assert config.LIMIT_BYTES < raw
    assert config.LIMIT_BYTES == int(raw * config.SAFETY)


def test_to_rgb_on_white_flattens_transparency():
    # Fully transparent pixels must become white, never black (JPEG has no alpha).
    im = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
    rgb = compress._to_rgb_on_white(im)
    assert rgb.mode == "RGB"
    assert rgb.getpixel((0, 0)) == (255, 255, 255)


def test_to_rgb_on_white_passes_through_rgb():
    im = Image.new("RGB", (4, 4), (12, 34, 56))
    assert compress._to_rgb_on_white(im).getpixel((0, 0)) == (12, 34, 56)


def test_compute_limit_bytes_scales_and_applies_margin():
    for mb in (10, 50, 500):
        assert config.compute_limit_bytes(mb) == int(
            mb * 1024 * 1024 * config.SAFETY
        )
    assert config.compute_limit_bytes(50) > config.compute_limit_bytes(10)
