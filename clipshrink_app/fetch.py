# -*- coding: utf-8 -*-
"""디스코드 CDN 자산: URL 파싱·다운로드·APNG→GIF 변환·라이브러리 등록.

디스코드는 업로드된 APNG를 애니메이션 재생하지 않으므로 (스티커만 특별 취급)
APNG는 등록 시 GIF로 변환해 저장한다 — FakeNitro와 동일한 해법.
"""

from __future__ import annotations

import os
import re
import shutil
import urllib.request
from dataclasses import dataclass

from PIL import Image, ImageSequence

from . import __version__

EMOJI_RE = re.compile(
    r"(?:cdn|media)\.discordapp\.(?:com|net)/emojis/(\d+)\.(png|gif|webp)", re.I)
STICKER_RE = re.compile(
    r"(?:cdn|media)\.discordapp\.(?:com|net)/stickers/(\d+)\.(png|gif|json)", re.I)

ACCEPT_FILE_EXTS = (".png", ".gif", ".webp", ".jpg", ".jpeg")


class UnsupportedAssetError(Exception):
    """Lottie(.json) 스티커 등 지원 불가 자산."""


@dataclass
class ParsedAsset:
    kind: str      # "emoji" | "sticker"
    asset_id: str
    ext: str       # 소문자, 점 없음


def parse_discord_url(url: str) -> ParsedAsset | None:
    m = EMOJI_RE.search(url)
    if m:
        return ParsedAsset("emoji", m.group(1), m.group(2).lower())
    m = STICKER_RE.search(url)
    if m:
        ext = m.group(2).lower()
        if ext == "json":
            raise UnsupportedAssetError("lottie")
        return ParsedAsset("sticker", m.group(1), ext)
    return None


def canonical_url(p: ParsedAsset) -> str:
    """쿼리 파라미터를 제거한 원본 바이트 URL (cdn 호스트 고정 — media 호스트는
    리사이즈/변환본을 줄 수 있다)."""
    kind_path = "emojis" if p.kind == "emoji" else "stickers"
    return f"https://cdn.discordapp.com/{kind_path}/{p.asset_id}.{p.ext}"


def download(url: str, dest_path: str, timeout: int = 10) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": f"ClipShrink/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r, \
            open(dest_path, "wb") as f:
        shutil.copyfileobj(r, f)


def is_apng(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return im.format == "PNG" and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


def sniff_animated(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return bool(getattr(im, "is_animated", False))
    except Exception:
        return False


def apng_to_gif(src: str, dest: str) -> None:
    """APNG → GIF. GIF 투명도는 1비트라 알파<128은 완전 투명으로 처리."""
    with Image.open(src) as im:
        frames, durations = [], []
        for frame in ImageSequence.Iterator(im):
            f = frame.convert("RGBA")
            alpha = f.getchannel("A")
            p = f.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            mask = alpha.point(lambda a: 255 if a < 128 else 0)
            p.paste(255, mask)
            frames.append(p)
            durations.append(int(frame.info.get("duration", 50)) or 50)
    frames[0].save(dest, format="GIF", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=2, transparency=255)


def _first_frame_png(src: str, dest: str) -> None:
    """APNG 첫 프레임을 정지 PNG로 저장 (GIF 변환 실패 시 폴백)."""
    with Image.open(src) as im:
        im.seek(0)
        im.convert("RGBA").save(dest, format="PNG")


def _finalize_asset(library, tmp_path: str, ext: str) -> tuple[str, bool, bool]:
    """APNG면 GIF로 변환해 저장, 아니면 그대로.

    (최종 파일명, animated, convert_failed) 반환. APNG→GIF 변환이 실패하면
    정지 PNG(첫 프레임)로 폴백하고 convert_failed=True (스펙 §7 — 등록 자체는
    성공시키고 항목에 경고 배지를 남긴다)."""
    if ext == ".png" and is_apng(tmp_path):
        gif_name = library.new_asset_filename(".gif")
        gif_path = os.path.join(library.assets_dir, gif_name)
        try:
            apng_to_gif(tmp_path, gif_path)
        except Exception:
            if os.path.exists(gif_path):  # 부분 생성된 GIF 정리
                os.remove(gif_path)
            png_name = library.new_asset_filename(".png")
            _first_frame_png(tmp_path, os.path.join(library.assets_dir, png_name))
            os.remove(tmp_path)
            return png_name, False, True
        os.remove(tmp_path)
        return gif_name, True, False
    filename = library.new_asset_filename(ext)
    final = os.path.join(library.assets_dir, filename)
    os.replace(tmp_path, final)
    return filename, ext == ".gif" or sniff_animated(final), False


def register_from_url(library, url: str, name: str = "", keywords=None) -> dict:
    p = parse_discord_url(url)
    if p is None:
        raise ValueError("not a discord asset url")
    ext = "." + p.ext
    tmp = os.path.join(library.assets_dir, "_dl" + library.new_asset_filename(ext))
    try:
        download(canonical_url(p), tmp)
        filename, animated, convert_failed = _finalize_asset(library, tmp, ext)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    type_ = "emoji" if p.kind == "emoji" else "sticker"
    return library.add_item(type_, name or p.asset_id, keywords or [],
                            "discord-cdn", canonical_url(p), filename, animated,
                            convert_failed)


def register_from_file(library, src_path: str, type_: str,
                       name: str = "", keywords=None) -> dict:
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in ACCEPT_FILE_EXTS:
        raise ValueError(f"unsupported extension: {ext}")
    tmp = os.path.join(library.assets_dir, "_cp" + library.new_asset_filename(ext))
    try:
        shutil.copyfile(src_path, tmp)
        filename, animated, convert_failed = _finalize_asset(library, tmp, ext)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    return library.add_item(type_, name or stem, keywords or [],
                            "local", "", filename, animated, convert_failed)


def register_from_png_bytes(library, data: bytes, type_: str,
                            name: str = "", keywords=None) -> dict:
    """클립보드 PNG 바이트를 캐시에 저장하고 라이브러리에 등록 (스펙 §5 —
    클립보드 이미지 붙여넣기: 스티커를 수동 저장한 경우의 주 경로).

    파일 등록과 동일하게 _finalize_asset을 재사용해 정지/애니메이션(APNG→GIF)을
    판정한다. 원본 파일이 없으므로 source_kind는 파일 드롭과 같은 'local'."""
    tmp = os.path.join(library.assets_dir, "_pb" + library.new_asset_filename(".png"))
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        filename, animated, convert_failed = _finalize_asset(library, tmp, ".png")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return library.add_item(type_, name, keywords or [],
                            "local", "", filename, animated, convert_failed)
