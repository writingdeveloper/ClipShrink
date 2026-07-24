"""클립보드 이미지 정규화와 캡처 라이브러리 중복 방지."""

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from notro_app import capture_store as cs
from notro_app.library import Library


def png_bytes(color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def test_read_prefers_registered_png(monkeypatch):
    """원본 PNG가 있는데 비트맵 재인코딩으로 바뀌는 회귀를 잡는다."""
    monkeypatch.setattr(cs.cb, "clipboard_has_files", lambda: False)
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: b"raw-png")
    monkeypatch.setattr(
        cs.ImageGrab, "grabclipboard",
        lambda: (_ for _ in ()).throw(AssertionError("unused")))

    assert cs.read_clipboard_png() == cs.CaptureReadResult(b"raw-png", None)


def test_read_converts_bitmap_to_png(monkeypatch):
    """CF_DIB만 제공하는 캡처 도구를 놓치는 회귀를 잡는다."""
    monkeypatch.setattr(cs.cb, "clipboard_has_files", lambda: False)
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(
        cs.ImageGrab, "grabclipboard",
        lambda: Image.new("RGB", (3, 2), "red"))

    result = cs.read_clipboard_png()

    assert result.error is None
    with Image.open(io.BytesIO(result.data)) as image:
        assert image.format == "PNG" and image.size == (3, 2)


def test_read_excludes_file_list(monkeypatch):
    """Explorer 파일 복사가 자동 캡처로 등록되는 회귀를 잡는다."""
    monkeypatch.setattr(cs.cb, "clipboard_has_files", lambda: True)
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(
        cs.ImageGrab, "grabclipboard", lambda: [r"C:\x.png"])

    assert cs.read_clipboard_png() == cs.CaptureReadResult(None, "no_image")


def test_read_reports_clipboard_failure(monkeypatch):
    """클립보드 잠김이 단순 이미지 없음으로 숨겨지는 회귀를 잡는다."""
    monkeypatch.setattr(cs.cb, "clipboard_has_files", lambda: False)
    monkeypatch.setattr(
        cs.cb, "get_clipboard_png",
        lambda: (_ for _ in ()).throw(OSError("busy")))
    monkeypatch.setattr(
        cs.ImageGrab, "grabclipboard",
        lambda: (_ for _ in ()).throw(OSError("busy")))

    assert cs.read_clipboard_png() == cs.CaptureReadResult(None, "read")


def test_save_places_capture_in_reserved_collection(tmp_path):
    """캡처가 현재 탭이나 미분류 컬렉션으로 새는 회귀를 잡는다."""
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)
    data = png_bytes()

    result = store.save_png(data)
    item = lib.get(result.item_id)

    assert result.ok and not result.duplicate
    assert item["type"] == "emoji"
    assert item["collection"] == cs.CAPTURE_COLLECTION_ID
    assert item["name"].startswith("capture-")
    assert item["content_hash"] == hashlib.sha256(data).hexdigest()


def test_save_same_png_returns_existing_item(tmp_path):
    """동일 클립보드 이미지가 반복 저장되는 회귀를 잡는다."""
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)
    first = store.save_png(png_bytes())

    second = store.save_png(png_bytes())

    assert second == cs.CaptureSaveResult(True, True, first.item_id, None)
    assert len(lib.items()) == 1


def test_concurrent_save_creates_one_item(tmp_path):
    """자동·수동 동시 저장의 해시 검사 레이스를 잡는다."""
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.save_png(png_bytes()), range(8)))

    assert len(lib.items()) == 1
    assert sum(not result.duplicate for result in results) == 1


def test_read_and_save_preserves_read_error(tmp_path, monkeypatch):
    """읽기 실패가 저장 실패로 잘못 보고되는 회귀를 잡는다."""
    store = cs.CaptureStore(Library(str(tmp_path / "d")))
    monkeypatch.setattr(
        cs, "read_clipboard_png",
        lambda: cs.CaptureReadResult(None, "read"))

    assert store.read_and_save() == cs.CaptureSaveResult(False, error="read")


def test_save_empty_data_returns_no_image(tmp_path):
    store = cs.CaptureStore(Library(str(tmp_path / "d")))
    assert store.save_png(b"") == cs.CaptureSaveResult(False, error="no_image")


def test_save_registration_error_is_reported(tmp_path, monkeypatch):
    store = cs.CaptureStore(Library(str(tmp_path / "d")))
    monkeypatch.setattr(
        cs.fetch, "register_from_png_bytes",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))

    assert store.save_png(png_bytes()) == \
        cs.CaptureSaveResult(False, error="register")
