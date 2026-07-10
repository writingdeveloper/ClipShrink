"""fetch: URL 파싱·APNG 처리·등록 파이프라인 (다운로드는 monkeypatch)."""

import io
import os

import pytest
from PIL import Image

from clipshrink_app import fetch
from clipshrink_app.library import Library


# ---------- 픽스처 ----------
def png_bytes():
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def apng_bytes():
    f1 = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    f2 = Image.new("RGBA", (8, 8), (0, 0, 255, 255))
    buf = io.BytesIO()
    f1.save(buf, format="PNG", save_all=True, append_images=[f2],
            duration=100, loop=0)
    return buf.getvalue()


def gif_bytes():
    f1 = Image.new("P", (8, 8), 0)
    f2 = Image.new("P", (8, 8), 1)
    buf = io.BytesIO()
    f1.save(buf, format="GIF", save_all=True, append_images=[f2], duration=80)
    return buf.getvalue()


# ---------- URL 파싱 ----------
def test_parse_emoji_urls():
    for url in (
        "https://cdn.discordapp.com/emojis/123456789.png",
        "https://media.discordapp.net/emojis/123456789.gif?size=48&quality=lossless",
        "https://cdn.discordapp.com/emojis/123456789.webp?size=96",
    ):
        p = fetch.parse_discord_url(url)
        assert p and p.kind == "emoji" and p.asset_id == "123456789"


def test_parse_sticker_url_and_canonical():
    p = fetch.parse_discord_url(
        "https://media.discordapp.net/stickers/987.png?size=160")
    assert p and p.kind == "sticker" and p.ext == "png"
    assert fetch.canonical_url(p) == "https://cdn.discordapp.com/stickers/987.png"


def test_parse_lottie_sticker_raises():
    with pytest.raises(fetch.UnsupportedAssetError):
        fetch.parse_discord_url("https://cdn.discordapp.com/stickers/55.json")


def test_parse_non_discord_returns_none():
    assert fetch.parse_discord_url("https://example.com/emojis/1.png") is None
    assert fetch.parse_discord_url("not a url") is None


def test_canonical_url_emoji_strips_query():
    p = fetch.parse_discord_url("https://media.discordapp.net/emojis/42.gif?size=48")
    assert fetch.canonical_url(p) == "https://cdn.discordapp.com/emojis/42.gif"


# ---------- APNG ----------
def test_is_apng_detects(tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(apng_bytes())
    s = tmp_path / "s.png"
    s.write_bytes(png_bytes())
    assert fetch.is_apng(str(a)) is True
    assert fetch.is_apng(str(s)) is False


def test_apng_to_gif_animated_output(tmp_path):
    src = tmp_path / "a.png"
    src.write_bytes(apng_bytes())
    dest = tmp_path / "a.gif"
    fetch.apng_to_gif(str(src), str(dest))
    with Image.open(dest) as im:
        assert im.format == "GIF" and getattr(im, "n_frames", 1) > 1


# ---------- 등록 ----------
def fake_download(payload):
    def _dl(url, dest, timeout=10):
        with open(dest, "wb") as f:
            f.write(payload)
    return _dl


def test_register_from_url_emoji(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monkeypatch.setattr(fetch, "download", fake_download(png_bytes()))
    item = fetch.register_from_url(lib, "https://cdn.discordapp.com/emojis/1.png",
                                   name="wave", keywords=["hi"])
    assert item["type"] == "emoji" and item["animated"] is False
    assert item["source_kind"] == "discord-cdn"
    assert os.path.exists(lib.asset_path(item))


def test_register_from_url_apng_sticker_becomes_gif(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monkeypatch.setattr(fetch, "download", fake_download(apng_bytes()))
    item = fetch.register_from_url(lib, "https://cdn.discordapp.com/stickers/9.png")
    assert item["type"] == "sticker" and item["animated"] is True
    assert item["filename"].endswith(".gif")
    with Image.open(lib.asset_path(item)) as im:
        assert im.format == "GIF" and im.n_frames > 1


def test_register_from_url_rejects_non_discord(tmp_path):
    lib = Library(str(tmp_path / "d"))
    with pytest.raises(ValueError):
        fetch.register_from_url(lib, "https://example.com/x.png")


def test_register_from_file_copies_and_detects(tmp_path):
    lib = Library(str(tmp_path / "d"))
    src = tmp_path / "z.gif"
    src.write_bytes(gif_bytes())
    item = fetch.register_from_file(lib, str(src), "gif")
    assert item["animated"] is True and item["name"] == "z"
    assert os.path.exists(lib.asset_path(item))
    assert src.exists()  # 원본 보존


def test_register_from_file_rejects_unknown_ext(tmp_path):
    lib = Library(str(tmp_path / "d"))
    bad = tmp_path / "x.txt"
    bad.write_text("no")
    with pytest.raises(ValueError):
        fetch.register_from_file(lib, str(bad), "gif")


def test_register_from_file_apng_converts(tmp_path):
    lib = Library(str(tmp_path / "d"))
    src = tmp_path / "st.png"
    src.write_bytes(apng_bytes())
    item = fetch.register_from_file(lib, str(src), "sticker")
    assert item["animated"] is True and item["filename"].endswith(".gif")
