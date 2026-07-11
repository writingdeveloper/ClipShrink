# -*- coding: utf-8 -*-
"""피커 창 관리 (pywebview). webview 임포트는 지연 — 테스트가 GUI를 안 건드리게."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys

from .. import clipboard_win as cb

user32 = ctypes.windll.user32

WIN_W, WIN_H = 500, 420
MONITOR_DEFAULTTONEAREST = 2

_DEBUG_LOG = os.environ.get("NOTRO_DEBUG", "")


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
        return os.path.join(sys._MEIPASS, "notro_app", "picker", "ui", "index.html")
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


def prepare_for_paste(path: str, limit_bytes: int, temp_dir: str) -> tuple[str, bool]:
    """한도 초과 항목 전처리 (스펙 §6.7/§7).

    정지 이미지: 기존 압축 파이프라인으로 한도 내 재인코딩.
    GIF(애니메이션): 재압축 품질 저하가 커서 그대로 두고 경고만.
    반환: (붙여넣을 경로, 한도 초과 경고 여부)
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return path, False
    if size <= limit_bytes:
        return path, False
    if path.lower().endswith(".gif"):
        return path, True
    from datetime import datetime

    from PIL import Image

    from .. import compress

    try:
        with Image.open(path) as img:
            img.load()
            result = compress.compress_image(img, limit_bytes)
    except Exception:
        return path, True
    if result is None:
        return path, True
    data, ext = result
    out = os.path.join(temp_dir,
                       datetime.now().strftime("picker_%Y%m%d_%H%M%S_%f") + ext)
    with open(out, "wb") as f:
        f.write(data)
    return out, False


PICKER_STRING_KEYS = [
    "picker_search", "picker_tab_emoji", "picker_tab_sticker", "picker_tab_gif",
    "picker_recent", "picker_empty", "picker_hint", "picker_add_title",
    "picker_add_url_ph", "picker_add_name_ph", "picker_add_kw_ph",
    "picker_add_note", "picker_add_submit", "picker_cancel",
    "picker_folders_title", "picker_add_folder", "picker_drop_hint",
    "picker_ctx_file", "picker_ctx_url", "picker_ctx_delete",
    "picker_err_lottie", "picker_err_not_discord", "picker_err_download",
    "picker_convert_warn", "picker_paste_no_image",
    "picker_ctx_favorite", "picker_ctx_unfavorite", "picker_ctx_collection",
    "picker_col_all", "picker_col_favorites", "picker_open_library",
]


class PickerApi:
    """JS 브리지. 각 메서드는 pywebview API 스레드에서 호출된다.

    주의: pywebview는 js_api 객체의 공개 속성을 재귀 탐색해 JS에 노출한다.
    비API 참조(컨트롤러·서버·라이브러리 등)를 공개 속성으로 두면 순환/거대
    그래프 탐색으로 브리지 생성이 멈춘다 — 반드시 `_` 접두 프라이빗으로.
    """

    def __init__(self, library=None, asset_server=None):
        self._ctrl: PickerController | None = None
        self._library = library
        self._asset_server = asset_server

    def _display(self, item: dict) -> dict:
        return {
            "id": item["id"], "type": item["type"], "name": item["name"],
            "keywords": item["keywords"], "animated": item["animated"],
            "url": self._asset_server.url_for(item["id"]),
            "can_url": bool(item.get("source_url")),
            "is_folder": item["source_kind"] == "folder",
            "convert_warning": bool(item.get("convert_warning", False)),
            "favorite": bool(item.get("favorite", False)),
            "collection": item.get("collection", ""),
        }

    def get_state(self) -> dict:
        from ..i18n import tr
        cols = []
        for name in self._library.collections():
            icon_id = self._library.collection_icon(name)
            cols.append({
                "name": name,
                "icon": self._asset_server.url_for(icon_id) if icon_id else None,
            })
        return {
            "items": [self._display(i) for i in self._library.all_display_items()],
            "recent": [i["id"] for i in self._library.recent()],
            "folders": [{**f, "exists": os.path.isdir(f["path"])}
                        for f in self._library.folders()],
            "collections": cols,
            "strings": {k: tr(k) for k in PICKER_STRING_KEYS},
        }

    def select_item(self, item_id: str, mode: str = "file") -> bool:
        if self._ctrl:
            self._ctrl.select(item_id, mode)
        return True

    def register_url(self, url: str, name: str = "", keywords: str = "") -> dict:
        from .. import fetch
        kws = [k.strip() for k in (keywords or "").replace(",", " ").split()
               if k.strip()]
        try:
            item = fetch.register_from_url(self._library, url, name, kws)
        except fetch.UnsupportedAssetError:
            return {"ok": False, "error": "lottie"}
        except ValueError:
            return {"ok": False, "error": "not_discord"}
        except Exception:
            return {"ok": False, "error": "download"}
        return {"ok": True, "item": self._display(item)}

    def register_files(self, paths, type_: str) -> dict:
        from .. import fetch
        n = 0
        for p in paths or []:
            try:
                fetch.register_from_file(self._library, p, type_)
                n += 1
            except Exception:
                pass
        return {"ok": True, "count": n}

    def register_clipboard(self, type_: str) -> dict:
        """클립보드의 PNG 이미지를 라이브러리에 등록 (스펙 §5 — 디스코드/브라우저
        에서 이미지를 복사한 뒤 붙여넣는 주 경로). 재인코딩 추정이 아닌 클립보드
        원본 PNG 바이트를 그대로 캐시한다. 이미지가 없으면 ok=False."""
        from datetime import datetime

        from .. import fetch
        data = cb.get_clipboard_png()
        if not data:
            return {"ok": False, "error": "no_image"}
        name = datetime.now().strftime("clip-%Y%m%d-%H%M%S")
        try:
            fetch.register_from_png_bytes(self._library, data, type_, name=name)
        except Exception:
            return {"ok": False, "error": "register"}
        return {"ok": True}

    def add_folder(self, default_type: str = "gif") -> dict:
        import webview
        res = self._ctrl.window.create_file_dialog(webview.FOLDER_DIALOG)
        if res:
            self._library.add_folder(res[0], default_type)
            return {"ok": True}
        return {"ok": False}

    def remove_folder(self, path: str) -> bool:
        self._library.remove_folder(path)
        return True

    def remove_item(self, item_id: str) -> bool:
        self._library.remove_item(item_id)
        return True

    def toggle_favorite(self, item_id: str) -> dict:
        return {"ok": True, "favorite": self._library.toggle_favorite(item_id)}

    def set_collection(self, item_id: str, name: str = "") -> bool:
        self._library.set_collection(item_id, name)
        return True

    def open_data_dir(self) -> bool:
        from .. import config
        try:
            os.startfile(config.DATA_DIR)
        except OSError:
            pass
        return True

    def hide(self):
        if self._ctrl:
            self._ctrl.hide()
        return True


class PickerController:
    def __init__(self, library=None, api=None):
        self.window = None
        self.prev_hwnd = 0
        self.visible = False
        self.on_notify = None  # tr()된 메시지를 받는 콜백 (트레이 알림)
        self.library = library
        self._api = api

    def _resolve(self, item_id: str) -> dict | None:
        item = self.library.get(item_id)
        if item is None and item_id.startswith("folder:"):
            item = next((i for i in self.library.scan_folders()
                         if i["id"] == item_id), None)
        return item

    def _notify(self, msg: str) -> None:
        if self.on_notify:
            try:
                self.on_notify(msg)
            except Exception:
                pass

    def select(self, item_id: str, mode: str = "file") -> None:
        """피커 선택 → 숨김 → 클립보드 → 포커스 복귀 → Ctrl+V. 전송은 사용자."""
        import time as _t

        from .. import config
        from ..i18n import tr

        item = self._resolve(item_id)
        if not item:
            return
        self.hide()
        warn = False
        if mode == "url" and item.get("source_url"):
            ok = cb.set_clipboard_text(item["source_url"])
        else:
            path, warn = prepare_for_paste(self.library.asset_path(item),
                                           config.LIMIT_BYTES, config.TEMP_DIR)
            ok = cb.set_clipboard_file(path)
        focused = cb.focus_window(self.prev_hwnd)
        if ok and focused:
            _t.sleep(0.12)
            cb.send_ctrl_v()
            if warn:
                self._notify(tr("picker_oversize_warn"))
        elif ok:
            self._notify(tr("notify_paste_manual"))
        else:
            self._notify(tr("notify_clipboard_fail"))
        self.library.touch(item["id"])

    def create_window(self):
        import webview
        self.window = webview.create_window(
            "Notro Picker", url=ui_index_path(), js_api=self._api,
            width=WIN_W, height=WIN_H, frameless=True, on_top=True,
            hidden=True, resizable=False, easy_drag=False,
        )
        return self.window

    def _native_hwnd(self) -> int:
        return user32.FindWindowW(None, "Notro Picker")

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
