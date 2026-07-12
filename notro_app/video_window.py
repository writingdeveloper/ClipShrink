# -*- coding: utf-8 -*-
"""비디오 압축 확인·진행 창.

토스트가 아니라 창인 이유: 알림을 끈 사용자에게 토스트는 도달하지 못한다(v2.5.5에서
확인한 문제). 인코딩은 수십 초 CPU를 쓰므로 사용자 승인 없이 시작하지 않는다.
welcome.py와 같은 방식(pywebview + Python에서 HTML 생성 + js_api)을 쓴다.
"""

from __future__ import annotations

import html as _html
import threading

from . import APP_NAME
from .i18n import tr

WIN_W, WIN_H = 480, 380

_CSS = """
  * { box-sizing: border-box; }
  body { margin:0; padding:22px 26px; background:#313338; color:#dbdee1;
         font-family:"Segoe UI",system-ui,sans-serif; -webkit-user-select:none; user-select:none; }
  h1 { margin:0 0 12px; font-size:17px; color:#fff; }
  .row { font-size:13px; line-height:1.6; color:#b5bac1; }
  .est { margin-top:8px; font-size:13.5px; color:#fff; }
  .warn { margin-top:10px; padding:9px 12px; border-left:3px solid #f0b232;
          background:#2b2d31; border-radius:6px; font-size:12.5px; }
  .bar { margin-top:16px; height:8px; background:#1e1f22; border-radius:4px; overflow:hidden; }
  .bar > i { display:block; height:100%; width:0%; background:#5865f2; transition:width .2s; }
  .status { margin-top:10px; font-size:13px; }
  .btns { margin-top:18px; display:flex; gap:8px; }
  button { flex:1; padding:10px; border:none; border-radius:6px; font-size:13.5px;
           font-weight:600; cursor:pointer; background:#4e5058; color:#fff; }
  button.primary { background:#5865f2; }
  button:hover { filter:brightness(1.1); }
  .hidden { display:none; }
"""


def fmt_size(n: int) -> str:
    """9961472 → '9.5MB'"""
    return f"{n / 1024 / 1024:.1f}MB"


def fmt_dur(sec: float) -> str:
    """72.34 → '1:12'"""
    total = int(sec)
    return f"{total // 60}:{total % 60:02d}"


class _Api:
    def __init__(self, accepted: threading.Event, cancelled: threading.Event):
        self.window = None
        self._accepted = accepted
        self._cancelled = cancelled

    def accept(self):
        self._accepted.set()

    def cancel(self):
        self._cancelled.set()
        self.close()

    def close(self):
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass


class VideoWindow:
    """확인 → 진행 → 완료/실패를 한 창에서 전환한다."""

    def __init__(self, headline: str, meta_line: str, estimate: str,
                 warn: str | None, accept_label: str):
        self.accepted = threading.Event()
        self.cancelled = threading.Event()
        self._api = _Api(self.accepted, self.cancelled)
        self._headline = headline
        self._meta_line = meta_line
        self._estimate = estimate
        self._warn = warn
        self._accept_label = accept_label
        self._win = None

    def _html(self) -> str:
        e = _html.escape
        warn = f'<div class="warn">{e(self._warn)}</div>' if self._warn else ""
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            f"<title>{e(APP_NAME)}</title><style>{_CSS}</style></head><body>"
            f"<h1>{e(self._headline)}</h1>"
            f'<div class="row">{e(self._meta_line)}</div>'
            f'<div class="est">{e(self._estimate)}</div>'
            f"{warn}"
            '<div id="prog" class="hidden">'
            '  <div class="bar"><i id="fill"></i></div>'
            '  <div class="status" id="status"></div>'
            "</div>"
            '<div class="btns" id="btns">'
            f'  <button class="primary" id="ok">{e(self._accept_label)}</button>'
            f'  <button id="no">{e(tr("video_btn_cancel"))}</button>'
            "</div>"
            "<script>"
            'document.getElementById("ok").onclick = function () {'
            '  document.getElementById("btns").classList.add("hidden");'
            '  document.getElementById("prog").classList.remove("hidden");'
            "  window.pywebview.api.accept();"
            "};"
            'document.getElementById("no").onclick = function () {'
            "  window.pywebview.api.cancel();"
            "};"
            "function notroProgress(text, pct) {"
            '  document.getElementById("status").textContent = text;'
            '  document.getElementById("fill").style.width = pct + "%";'
            "}"
            "function notroFinish(text) {"
            '  document.getElementById("prog").classList.add("hidden");'
            '  document.getElementById("btns").classList.remove("hidden");'
            '  document.getElementById("ok").classList.add("hidden");'
            '  document.getElementById("no").textContent = ' + f'"{e(tr("video_btn_close"))}";'
            '  document.querySelector(".est").textContent = text;'
            '  document.querySelector(".row").textContent = "";'
            "}"
            "</script></body></html>"
        )

    def show(self):
        import webview

        self._win = webview.create_window(
            APP_NAME, html=self._html(), js_api=self._api,
            width=WIN_W, height=WIN_H, resizable=False,
        )
        self._api.window = self._win
        return self._win

    def set_progress(self, text: str, pct: int):
        if self._win is None:
            return
        try:
            self._win.evaluate_js(f"notroProgress({_js(text)}, {int(pct)})")
        except Exception:
            pass

    def finish(self, text: str):
        """완료·실패 공통: 메시지를 보여주고 [닫기]만 남긴다."""
        if self._win is None:
            return
        try:
            self._win.evaluate_js(f"notroFinish({_js(text)})")
        except Exception:
            pass

    def close(self):
        self._api.close()


def _js(s: str) -> str:
    """JS 문자열 리터럴로 안전하게 감싼다."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
