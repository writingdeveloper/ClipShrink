"""피커 클립보드 이미지 붙여넣기 등록 경로 (스펙 §5).

백엔드: PNG 바이트 → 라이브러리 등록(fetch.register_from_png_bytes)과
PickerApi.register_clipboard. 실제 클립보드/GUI는 건드리지 않고 monkeypatch로
클립보드 PNG 판독만 대체한다.
"""

import io
import os

from PIL import Image

from notro_app import fetch, i18n
from notro_app.library import Library
from notro_app.picker import window


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 200, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def apng_bytes():
    f1 = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    f2 = Image.new("RGBA", (8, 8), (0, 0, 255, 255))
    buf = io.BytesIO()
    f1.save(buf, format="PNG", save_all=True, append_images=[f2],
            duration=100, loop=0)
    return buf.getvalue()


# ---------- fetch.register_from_png_bytes ----------
def test_register_from_png_bytes_still_image(tmp_path):
    lib = Library(str(tmp_path / "d"))
    item = fetch.register_from_png_bytes(lib, png_bytes(), "sticker")
    assert item["type"] == "sticker"
    assert item["animated"] is False
    assert item["convert_warning"] is False
    assert item["source_kind"] == "local"
    path = lib.asset_path(item)
    assert os.path.exists(path)
    with Image.open(path) as im:
        assert im.format == "PNG"


def test_register_from_png_bytes_apng_becomes_gif(tmp_path):
    lib = Library(str(tmp_path / "d"))
    item = fetch.register_from_png_bytes(lib, apng_bytes(), "sticker")
    assert item["animated"] is True
    assert item["filename"].endswith(".gif")
    with Image.open(lib.asset_path(item)) as im:
        assert im.format == "GIF" and im.n_frames > 1


def test_register_from_png_bytes_keywords_and_type(tmp_path):
    lib = Library(str(tmp_path / "d"))
    item = fetch.register_from_png_bytes(lib, png_bytes(), "emoji",
                                         name="hi", keywords=["a", "b"])
    assert item["type"] == "emoji" and item["name"] == "hi"
    assert item["keywords"] == ["a", "b"]


# ---------- PickerApi.register_clipboard ----------
def test_register_clipboard_registers_png(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    api = window.PickerApi(library=lib)
    monkeypatch.setattr(window.cb, "get_clipboard_png", lambda: png_bytes())
    res = api.register_clipboard("sticker")
    assert res["ok"] is True
    items = lib.items()
    assert len(items) == 1 and items[0]["type"] == "sticker"
    assert os.path.exists(lib.asset_path(items[0]))


def test_register_clipboard_no_image_returns_error(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    api = window.PickerApi(library=lib)
    monkeypatch.setattr(window.cb, "get_clipboard_png", lambda: None)
    res = api.register_clipboard("emoji")
    assert res["ok"] is False
    assert res.get("error")
    assert lib.items() == []


# ---------- i18n 계약 (신규 문자열) ----------
def test_paste_no_image_string_registered_all_langs():
    assert "picker_paste_no_image" in window.PICKER_STRING_KEYS
    for lang in i18n.SUPPORTED_LANGS:
        assert i18n.STRINGS[lang].get("picker_paste_no_image")
