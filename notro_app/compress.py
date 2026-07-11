# -*- coding: utf-8 -*-
"""이미지 압축 로직 (순수 함수 — Windows API 무관)."""

from __future__ import annotations

import io

from PIL import Image

WEBP_QUALITIES = [90, 80, 70, 60, 50]   # 1차: WebP 품질 단계
JPEG_QUALITIES = [85, 75, 65]           # 2차: JPEG 품질 단계 (WebP 실패 시)
MIN_SCALE = 0.4         # 해상도 축소 하한 (원본의 40%까지만)


def estimate_png_size(img: Image.Image) -> int:
    """디스코드가 클립보드 비트맵을 붙여넣을 때 만드는 PNG의 용량을 추정."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.tell()


def _to_rgb_on_white(im: Image.Image) -> Image.Image:
    """JPEG는 알파를 지원하지 않으므로 RGBA는 흰 배경에 합성해 RGB로 변환한다.
    (단순 convert('RGB')는 투명 영역을 검게 만든다.)"""
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        return bg
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def compress_image(img: Image.Image, limit: int):
    """
    한도 이하가 될 때까지 압축. (포맷 변환 → 품질 하향 → 해상도 축소 순)
    반환: (bytes, 확장자) 또는 None(실패)
    """
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    def try_encode(im, fmt, quality):
        buf = io.BytesIO()
        if fmt == "WEBP":
            im.save(buf, format="WEBP", quality=quality, method=4)
        else:
            rgb = _to_rgb_on_white(im)
            rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()

    scale = 1.0
    current = img
    while scale >= MIN_SCALE:
        # WebP는 한 변 16383px 제한
        if max(current.size) <= 16383:
            for q in WEBP_QUALITIES:
                data = try_encode(current, "WEBP", q)
                if len(data) <= limit:
                    return data, ".webp"
        for q in JPEG_QUALITIES:
            data = try_encode(current, "JPEG", q)
            if len(data) <= limit:
                return data, ".jpg"
        # 그래도 크면 해상도 15%씩 축소
        scale *= 0.85
        new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        current = img.resize(new_size, Image.LANCZOS)
    return None
