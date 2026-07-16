# -*- coding: utf-8 -*-
"""클립보드 레이스 수정 테스트 (Win32 호출 없음 — monkeypatch).

1) seq 가드: 이미지를 읽은 뒤 사용자가 새로 복사했으면(시퀀스 변화) 압축 결과로
   클립보드를 덮어쓰지 않는다.
2) 안정화 대기: 시퀀스가 두 폴 연속 같을 때만 처리한다 — 크로미움이 여러 포맷을
   쓰는 도중(수백 ms) 깨어나 PNG 포맷을 놓치는 mid-write 읽기를 막는다.
"""

import io

from PIL import Image

import notro_app.clipboard_win as cbwin
import notro_app.monitor as mon
from notro_app import config
from notro_app.monitor import Monitor


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _make_monitor(monkeypatch, png: bytes, seq_at_read: int):
    """PNG가 한도를 넘겨 압축이 도는 상황을 구성한다."""
    monkeypatch.setattr(config, "LIMIT_BYTES", len(png) - 1)
    monkeypatch.setattr(mon.cb, "clipboard_has_marker", lambda: False)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png)
    monkeypatch.setattr(mon.cb, "get_sequence_number", lambda: seq_at_read)
    m = Monitor()
    m.notifications = []
    m.status_cb = lambda title, msg: m.notifications.append(msg)
    return m


# ---------- 1) seq 가드 ----------
def test_replace_passes_seq_at_read_as_guard(monkeypatch, tmp_path):
    png = _png_bytes()
    m = _make_monitor(monkeypatch, png, seq_at_read=42)
    monkeypatch.setattr(config, "TEMP_DIR", str(tmp_path))
    seen = {}

    def fake_set(path, guard_seq=None):
        seen["guard_seq"] = guard_seq
        return True

    monkeypatch.setattr(mon.cb, "set_clipboard_file", fake_set)
    m.process_clipboard()
    assert seen["guard_seq"] == 42


def test_replace_aborted_by_guard_is_silent(monkeypatch, tmp_path):
    """가드에 걸리면(반환 None) 알림·내역·last_seq 어느 것도 남기지 않는다 —
    새 복사는 다음 폴에서 정상 처리돼야 한다."""
    png = _png_bytes()
    m = _make_monitor(monkeypatch, png, seq_at_read=42)
    monkeypatch.setattr(config, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(mon.cb, "set_clipboard_file",
                        lambda path, guard_seq=None: None)
    before_seq = m.last_seq
    m.process_clipboard()
    assert m.notifications == []
    assert m.history == []
    assert m.last_seq == before_seq


def test_replace_success_still_records_history(monkeypatch, tmp_path):
    png = _png_bytes()
    m = _make_monitor(monkeypatch, png, seq_at_read=42)
    monkeypatch.setattr(config, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(mon.cb, "set_clipboard_file",
                        lambda path, guard_seq=None: True)
    m.process_clipboard()
    assert len(m.history) == 1
    assert len(m.notifications) == 1


# ---------- 1b) clipboard_win 쪽 가드 (클립보드를 연 상태에서 판정) ----------
class _StubUser32:
    def __init__(self):
        self.calls = []

    def EmptyClipboard(self):
        self.calls.append("empty")
        return 1

    def CloseClipboard(self):
        self.calls.append("close")
        return 1


def test_set_clipboard_file_aborts_on_stale_guard(monkeypatch):
    stub = _StubUser32()
    monkeypatch.setattr(cbwin, "user32", stub)
    monkeypatch.setattr(cbwin, "_open_clipboard_retry", lambda: True)
    monkeypatch.setattr(cbwin, "get_sequence_number", lambda: 43)  # 읽은 뒤 변함
    result = cbwin.set_clipboard_file(r"C:\x.webp", guard_seq=42)
    assert result is None
    assert "empty" not in stub.calls   # 새 복사 내용을 지우지 않았다
    assert "close" in stub.calls       # 클립보드는 반드시 닫는다


def test_set_clipboard_file_proceeds_on_matching_guard(monkeypatch):
    stub = _StubUser32()
    puts = []
    monkeypatch.setattr(cbwin, "user32", stub)
    monkeypatch.setattr(cbwin, "_open_clipboard_retry", lambda: True)
    monkeypatch.setattr(cbwin, "get_sequence_number", lambda: 42)
    monkeypatch.setattr(cbwin, "_global_put",
                        lambda fmt, data: puts.append(fmt) or True)
    result = cbwin.set_clipboard_file(r"C:\x.webp", guard_seq=42)
    assert result is True
    assert "empty" in stub.calls
    assert cbwin.CF_HDROP in puts


def test_set_clipboard_file_without_guard_keeps_old_behavior(monkeypatch):
    stub = _StubUser32()
    monkeypatch.setattr(cbwin, "user32", stub)
    monkeypatch.setattr(cbwin, "_open_clipboard_retry", lambda: True)
    monkeypatch.setattr(cbwin, "_global_put", lambda fmt, data: True)
    assert cbwin.set_clipboard_file(r"C:\x.webp") is True


# ---------- 2) 안정화 대기 (mid-write 읽기 방지) ----------
def _make_tick_monitor(monkeypatch, seqs):
    """cb.get_sequence_number가 seqs를 순서대로 반환하도록 구성.
    첫 값은 Monitor.__init__이 소비한다."""
    it = iter(seqs)
    monkeypatch.setattr(mon.cb, "get_sequence_number", lambda: next(it))
    m = Monitor()
    m.processed = []
    m.process_clipboard = lambda: m.processed.append(m.last_seq)
    return m


def test_tick_waits_until_seq_stable(monkeypatch):
    # init=0 → 폴1: 5 (방금 변함 — 대기) → 폴2: 5 (안정 — 처리)
    m = _make_tick_monitor(monkeypatch, [0, 5, 5])
    m._tick()
    assert m.processed == []
    m._tick()
    assert m.processed == [5]


def test_tick_defers_while_seq_keeps_changing(monkeypatch):
    # 쓰기 세션이 진행 중이라 폴마다 seq가 다르면 계속 대기한다
    m = _make_tick_monitor(monkeypatch, [0, 1, 2, 3, 4])
    for _ in range(4):
        m._tick()
    assert m.processed == []


def test_tick_ignores_unchanged_seq(monkeypatch):
    m = _make_tick_monitor(monkeypatch, [7, 7, 7])
    m._tick()
    m._tick()
    assert m.processed == []
