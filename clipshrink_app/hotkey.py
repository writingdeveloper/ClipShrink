# -*- coding: utf-8 -*-
"""글로벌 핫키: RegisterHotKey + 전용 메시지 루프 스레드.

RegisterHotKey는 등록한 스레드의 메시지 큐로 WM_HOTKEY를 보낸다.
전용 스레드에서 등록+GetMessage 루프를 돌리고, 조합 변경 시 WM_QUIT으로
스레드를 재시작한다.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
_HOTKEY_ID = 1

HOTKEY_OFF = "off"
HOTKEY_CHOICES = {
    "ctrl+shift+e": (MOD_CONTROL | MOD_SHIFT, 0x45, "Ctrl+Shift+E"),
    "ctrl+alt+e": (MOD_CONTROL | MOD_ALT, 0x45, "Ctrl+Alt+E"),
    "ctrl+shift+space": (MOD_CONTROL | MOD_SHIFT, 0x20, "Ctrl+Shift+Space"),
}
_OFF_LABEL = "—"


def label_for(combo_key: str) -> str:
    if combo_key in HOTKEY_CHOICES:
        return HOTKEY_CHOICES[combo_key][2]
    return _OFF_LABEL


class HotkeyListener:
    def __init__(self, on_hotkey, on_register_fail=None):
        self.on_hotkey = on_hotkey
        self.on_register_fail = on_register_fail
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self.combo: str = HOTKEY_OFF

    def start(self, combo_key: str) -> None:
        self.combo = combo_key
        if combo_key not in HOTKEY_CHOICES:
            return  # off
        self._thread = threading.Thread(
            target=self._run, args=(combo_key,), daemon=True)
        self._thread.start()

    def set_combo(self, combo_key: str) -> None:
        self.stop()
        self.start(combo_key)

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def _run(self, combo_key: str) -> None:
        import os
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        mods, vk, label = HOTKEY_CHOICES[combo_key]
        registered = user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk)
        log = os.environ.get("CLIPSHRINK_DEBUG", "")
        if log:
            try:
                with open(log, "a", encoding="utf-8") as f:
                    f.write(f"hotkey register {label}: {bool(registered)}\n")
            except Exception:
                pass
        if not registered:
            if self.on_register_fail:
                try:
                    self.on_register_fail(label)
                except Exception:
                    pass
            return
        try:
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.on_hotkey()
                    except Exception:
                        pass
        finally:
            user32.UnregisterHotKey(None, _HOTKEY_ID)
