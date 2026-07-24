"""앱 오케스트레이션의 CaptureStore 공유 배선."""

from types import SimpleNamespace

from notro_app import app, config
from notro_app.capture_store import CaptureSaveResult
from notro_app.library import Library


def make_monitor():
    monitor = SimpleNamespace(
        capture_enabled=None, on_capture_image=None, notifications=[])
    monitor.notify = lambda title, message: monitor.notifications.append(
        (title, message))
    return monitor


def test_configure_capture_storage_wires_shared_store(tmp_path, monkeypatch):
    """Monitor와 PickerApi가 다른 저장 서비스를 쓰는 회귀를 잡는다."""
    lib = Library(str(tmp_path / "d"))
    monitor = make_monitor()
    monkeypatch.setattr(
        config, "get_setting_flag", lambda key: key == "auto_capture_save")

    store = app.configure_capture_storage(monitor, lib)

    assert monitor.capture_enabled() is True
    store.save_png = lambda data: CaptureSaveResult(True, False, "x", None)
    monitor.on_capture_image(b"png")
    assert monitor.notifications == []


def test_configure_capture_storage_notifies_only_real_failure(
        tmp_path, monkeypatch):
    """자동 저장 성공마다 토스트를 띄우거나 실패를 숨기는 회귀를 잡는다."""
    monitor = make_monitor()
    monkeypatch.setattr(config, "get_setting_flag", lambda key: True)
    monkeypatch.setattr(app, "tr", lambda key, **kwargs: key)
    store = app.configure_capture_storage(
        monitor, Library(str(tmp_path / "d")))
    store.save_png = lambda data: CaptureSaveResult(False, error="register")

    monitor.on_capture_image(b"png")

    assert monitor.notifications == [
        (app.APP_NAME, "notify_capture_save_fail")]
