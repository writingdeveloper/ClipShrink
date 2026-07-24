"""Monitor의 선택적 클립보드 캡처 저장 신호."""

import io

from PIL import Image

import notro_app.monitor as mon
from notro_app.monitor import Monitor


def png_bytes(color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def configured_monitor(monkeypatch):
    monkeypatch.setattr(mon.cb, "get_sequence_number", lambda: 7)
    monkeypatch.setattr(mon.cb, "clipboard_has_marker", lambda: False)
    monkeypatch.setattr(mon.cb, "clipboard_has_files", lambda: False,
                        raising=False)
    monitor = Monitor()
    monitor.capture_enabled = lambda: True
    monitor.captured = []
    monitor.on_capture_image = monitor.captured.append
    return monitor


def test_small_registered_png_emits_capture(monkeypatch):
    """한도 이하 PNG의 기존 조기 반환이 자동 저장을 건너뛰는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    data = png_bytes()
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: data)

    monitor.process_clipboard()

    assert monitor.captured == [data]
    assert monitor.history == []


def test_bitmap_emits_normalized_png(monkeypatch):
    """등록 PNG가 없는 CF_DIB 캡처가 누락되는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(
        mon.ImageGrab, "grabclipboard",
        lambda: Image.new("RGB", (4, 4), "blue"))

    monitor.process_clipboard()

    assert len(monitor.captured) == 1
    assert monitor.captured[0].startswith(b"\x89PNG")


def test_file_list_does_not_emit_capture(monkeypatch, tmp_path):
    """Explorer 이미지 파일 복사가 캡처로 저장되는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    path = tmp_path / "x.png"
    Image.new("RGB", (2, 2)).save(path)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(mon.ImageGrab, "grabclipboard", lambda: [str(path)])

    monitor.process_clipboard()

    assert monitor.captured == []


def test_registered_png_with_file_format_does_not_emit_capture(monkeypatch):
    """PNG 미리보기도 함께 제공하는 파일 복사를 캡처로 오인하는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    monkeypatch.setattr(mon.cb, "clipboard_has_files", lambda: True,
                        raising=False)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png_bytes())

    monitor.process_clipboard()

    assert monitor.captured == []


def test_disabled_capture_does_not_emit(monkeypatch):
    """기본 꺼짐 설정을 무시해 캡처가 저장되는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    monitor.capture_enabled = lambda: False
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png_bytes())

    monitor.process_clipboard()

    assert monitor.captured == []


def test_capture_callback_failure_does_not_block_compression(
        monkeypatch, tmp_path):
    """라이브러리 저장 실패가 기존 대용량 압축을 막는 회귀를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    attempted = []

    def fail_save(data):
        attempted.append(data)
        raise RuntimeError("save")

    monitor.on_capture_image = fail_save
    data = png_bytes()
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: data)
    monkeypatch.setattr(mon.config, "LIMIT_BYTES", 1)
    monkeypatch.setattr(mon.config, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(mon.compress, "compress_image",
                        lambda image, limit: (b"compressed", ".webp"))
    replaced = []
    monkeypatch.setattr(
        mon.cb, "set_clipboard_file",
        lambda path, guard_seq=None: replaced.append((path, guard_seq)) or True)

    monitor.process_clipboard()

    assert attempted == [data]
    assert len(replaced) == 1
    assert replaced[0][1] == 7


def test_notro_marker_excludes_capture(monkeypatch):
    """Notro가 쓴 압축 파일이 다시 캡처로 저장되는 루프를 잡는다."""
    monitor = configured_monitor(monkeypatch)
    monkeypatch.setattr(mon.cb, "clipboard_has_marker", lambda: True)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png_bytes())

    monitor.process_clipboard()

    assert monitor.captured == []
