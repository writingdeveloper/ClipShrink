# -*- coding: utf-8 -*-
"""피커 창 관리 (pywebview). webview 임포트는 지연 — 테스트가 GUI를 안 건드리게."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys

from .. import clipboard_win as cb

user32 = ctypes.windll.user32

WIN_W, WIN_H = 440, 420
MONITOR_DEFAULTTONEAREST = 2

_DEBUG_LOG = os.environ.get("CLIPSHRINK_DEBUG", "")


def _dbg(msg: str) -> None:
    if not _DEBUG_LOG:
        return
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            import time as _t
            f.write(f"{_t.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def ui_index_path() -> str:
    """개발 실행과 PyInstaller(--add-data) 실행 모두에서 index.html 절대경로."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, "clipshrink_app", "picker", "ui", "index.html")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


# 64비트에서 HWND_TOPMOST(-1)가 c_int로 잘려 0xFFFFFFFF(잘못된 핸들)가 되는
# 것을 막기 위해 argtypes를 명시한다 (c_void_p는 -1을 부호 확장한다).
user32.SetWindowPos.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]


def popup_geometry() -> tuple[int, int, int, int]:
    """커서가 있는 모니터의 실제 DPI로 창 크기를 정하고, 커서 위쪽에 오도록
    좌표를 계산해 (x, y, w, h)를 돌려준다 (전부 물리 px — 같은 프로세스에서
    GetCursorPos/GetMonitorInfo/SetWindowPos를 호출해 좌표계를 일치시킨다)."""
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    scale = 1.0
    try:
        shcore = ctypes.windll.shcore
        dx, dy = wt.UINT(), wt.UINT()
        shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy))
        scale = dx.value / 96.0
    except Exception:
        pass
    win_w, win_h = int(WIN_W * scale), int(WIN_H * scale)
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    work = mi.rcWork
    x = min(max(pt.x - win_w // 2, work.left), max(work.left, work.right - win_w))
    y = pt.y - win_h - 16
    if y < work.top:
        y = min(pt.y + 16, max(work.top, work.bottom - win_h))
    return x, y, win_w, win_h


class PickerApi:
    """JS 브리지.

    주의: pywebview는 js_api 객체의 공개 속성을 재귀 탐색해 JS에 노출한다.
    비API 참조(컨트롤러·서버·라이브러리 등)를 공개 속성으로 두면 순환/거대
    그래프 탐색으로 브리지 생성이 멈춘다 — 반드시 `_` 접두 프라이빗으로.
    """

    def __init__(self, asset_server=None):
        self._ctrl: PickerController | None = None
        self._asset_server = asset_server

    def probe_url(self):
        """스켈레톤 검증용: 자산 서버를 통한 probe GIF URL."""
        if self._asset_server:
            return self._asset_server.url_for("probe")
        return ""

    def hide(self):
        if self._ctrl:
            self._ctrl.hide()
        return True


class PickerController:
    def __init__(self, api=None):
        self.window = None
        self.prev_hwnd = 0
        self.visible = False
        self._api = api

    def create_window(self):
        import webview
        self.window = webview.create_window(
            "ClipShrink Picker", url=ui_index_path(), js_api=self._api,
            width=WIN_W, height=WIN_H, frameless=True, on_top=True,
            hidden=True, resizable=False, easy_drag=False,
        )
        return self.window

    def _native_hwnd(self) -> int:
        return user32.FindWindowW(None, "ClipShrink Picker")

    def show_at_cursor(self):
        import time as _t

        _dbg("show_at_cursor: begin")
        self.prev_hwnd = cb.get_foreground_window()
        try:
            self.window.show()
        except Exception as e:
            _dbg(f"window.show() raised: {e!r}")
            raise
        x, y, w, h = popup_geometry()
        _dbg(f"target geometry: {x},{y} {w}x{h}")
        # pywebview의 show()가 GUI 스레드에서 창을 다시 배치할 수 있으므로,
        # 원하는 지오메트리가 실제 반영될 때까지 검증-재시도한다.
        # SWP_ASYNCWINDOWPOS: 다른 스레드 소유 창에 동기 메시지를 보내지 않아
        # (GUI 스레드가 바쁠 때의) 교착을 원천 차단한다.
        HWND_TOPMOST = -1
        SWP_SHOWWINDOW = 0x0040
        SWP_ASYNCWINDOWPOS = 0x4000
        for i in range(10):
            hwnd = self._native_hwnd()
            if hwnd:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, w, h,
                                    SWP_SHOWWINDOW | SWP_ASYNCWINDOWPOS)
                _t.sleep(0.04)
                r = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                _dbg(f"attempt {i}: hwnd={hwnd} rect={r.left},{r.top},{r.right},{r.bottom} vis={user32.IsWindowVisible(hwnd)}")
                if abs(r.left - x) <= 2 and abs(r.top - y) <= 2:
                    user32.SetForegroundWindow(hwnd)
                    break
            else:
                _dbg(f"attempt {i}: hwnd not found")
                _t.sleep(0.05)
        self.visible = True
        _dbg("show_at_cursor: end")
        try:
            self.window.evaluate_js("window.__onShow && window.__onShow()")
        except Exception:
            pass

    def hide(self):
        try:
            self.window.hide()
        except Exception:
            pass
        self.visible = False

    def toggle(self):
        _dbg(f"toggle: visible={self.visible}")
        if self.visible:
            self.hide()
        else:
            self.show_at_cursor()

    def destroy(self):
        try:
            self.window.destroy()
        except Exception:
            pass
