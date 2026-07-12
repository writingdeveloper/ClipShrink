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


# video.py의 _ACTIVE(실행 중인 ffmpeg 프로세스) 관례를 그대로 따른다: 열려 있는
# VideoWindow를 전부 추적해, 앱 종료 시 destroy_all()로 한꺼번에 닫을 수 있게 한다
# (리뷰 지적: 그렇지 않으면 webview.start()가 이 창들이 닫힐 때까지 반환하지 않아
# 프로세스가 Quit 이후에도 살아남고, 종료 후에도 열린 창에서 "압축" 버튼을 누르면
# 새 인코딩이 시작될 수 있다).
_ACTIVE: set["VideoWindow"] = set()
_ACTIVE_LOCK = threading.Lock()


def destroy_all() -> None:
    """앱 종료 시 호출 — 열려 있는 모든 확인/진행/알림 창을 닫는다.
    각 창의 close()가 destroy()를 거쳐 closed 이벤트를 발생시키므로, 진행 중이던
    _work 스레드의 cancelled(및 accepted) Event도 함께 set된다."""
    with _ACTIVE_LOCK:
        wins = list(_ACTIVE)
        _ACTIVE.clear()
    for w in wins:
        try:
            w.close()
        except Exception:
            pass


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
    """확인 → 진행 → 완료/실패를 한 창에서 전환한다.

    할 일이 아예 없는 경우(예: 예산이 360p/300kbps 하한에도 못 미쳐 압축 자체가
    불가능한 경우)를 위한 별도 상태도 있다 — `VideoWindow.info(...)`로 만든다.
    이 상태는 확인/취소 두 갈래도, 진행률 표시도 없이 메시지 하나 + 실제로 창을
    닫는 버튼 하나만 보여준다(리뷰 발견사항: 예전에는 이 경우도 보통 확인 창을
    재사용해 accept_label만 "닫기"로 바꿔 달았는데, 그 버튼은 accept()만 호출해
    창을 빈 진행률 화면(0%)으로 바꿔놓을 뿐 실제로 닫지는 않았다 — 창을 진짜로
    destroy()하는 cancel()은 "취소" 버튼에 연결돼 있었다)."""

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
        self._info = False
        self._win = None

    @classmethod
    def info(cls, headline: str, meta_line: str, message: str,
             close_label: str) -> "VideoWindow":
        """진행시킬 작업이 없는 알림 전용 창. 단일 버튼(close_label)만 있고,
        그 버튼은 실제로 창을 destroy()한다."""
        w = cls(headline, meta_line, message, None, close_label)
        w._info = True
        return w

    def _html(self) -> str:
        e = _html.escape
        warn = f'<div class="warn">{e(self._warn)}</div>' if self._warn else ""
        if self._info:
            # 진행률 영역도, 두 번째 버튼도 없다 — 유일한 버튼은 cancel()을 호출해
            # 실제로 창을 닫는다(accept()는 threading.Event만 set할 뿐 창을 닫지
            # 않으므로 여기서는 쓰지 않는다).
            body = (
                '<div class="btns" id="btns">'
                f'  <button class="primary" id="ok">{e(self._accept_label)}</button>'
                "</div>"
                "<script>"
                'document.getElementById("ok").onclick = function () {'
                "  window.pywebview.api.cancel();"
                "};"
                "</script>"
            )
        else:
            body = (
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
                "</script>"
            )
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            f"<title>{e(APP_NAME)}</title><style>{_CSS}</style></head><body>"
            f"<h1>{e(self._headline)}</h1>"
            f'<div class="row">{e(self._meta_line)}</div>'
            f'<div class="est">{e(self._estimate)}</div>'
            f"{warn}"
            f"{body}"
            "</body></html>"
        )

    def show(self):
        import webview

        self._win = webview.create_window(
            APP_NAME, html=self._html(), js_api=self._api,
            width=WIN_W, height=WIN_H, resizable=False,
        )
        self._api.window = self._win
        # 타이틀바 X로 닫는 것도 취소다(리뷰 지적): pywebview는 이 경우 accept()도
        # cancel()도 호출하지 않고 곧장 이 이벤트만 쏜다. 배선하지 않으면 사용자가
        # 인코딩 도중 창을 닫아도 should_cancel=w.cancelled.is_set이 절대 True가 되지
        # 않아 ffmpeg가 끝까지 돌고, 창을 닫은 지 몇 분 뒤에 클립보드가 조용히 바뀐다.
        self._win.events.closed += self._on_closed
        with _ACTIVE_LOCK:
            _ACTIVE.add(self)
        return self._win

    def _on_closed(self):
        """cancel()의 close()가 부르는 window.destroy()도 이 이벤트를 다시 쏘지만,
        threading.Event.set()은 이미 set된 상태에 다시 set해도 안전하므로(멱등)
        문제 없다. accepted도 같이 set하는 이유: _work 스레드가
        accepted.wait(timeout=300)에서 최대 5분까지 잠들어 있을 수 있는데, 여기서
        같이 깨워야 곧바로 cancelled.is_set()을 보고 리턴한다(그렇지 않으면 창은
        닫혔는데 스레드는 최대 5분간 아무것도 하지 않는 것처럼 보인다)."""
        self.cancelled.set()
        self.accepted.set()
        with _ACTIVE_LOCK:
            _ACTIVE.discard(self)

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
