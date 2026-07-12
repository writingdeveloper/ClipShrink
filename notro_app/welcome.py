# -*- coding: utf-8 -*-
"""첫 실행 안내 창.

Notro는 창이 없는 트레이 앱이고 Windows 11은 새 트레이 아이콘을 기본으로 숨긴다.
그래서 첫 실행에는 "어디에 있고 어떻게 쓰는지"를 **사용자가 직접 읽고 닫는 창**으로
보여준다. 앞선 두 방식은 각각 이렇게 실패한다:
  - 토스트 알림: 알림을 끈 사용자에게는 아예 도달하지 못한다.
  - 시간 기반 자동 팝업(N초 뒤 피커 열기): 설치 마법사의 완료 화면 위로 떠서
    안내문을 덮고, 사용자가 준비되지 않은 순간에 나타난다.

창에는 트레이에 실제로 뜨는 것과 **동일한 아이콘 이미지**를 심어, 무엇을 찾아야
하는지 눈으로 보여준다.
"""

from __future__ import annotations

import base64
import html as _html
import io

from . import APP_NAME
from .i18n import tr
from .tray import make_icon_image

WIN_W, WIN_H = 520, 580

_CSS = """
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 26px 30px;
    background: #313338; color: #dbdee1;
    font-family: "Segoe UI", system-ui, sans-serif;
    -webkit-user-select: none; user-select: none;
  }
  h1 { margin: 0 0 8px; font-size: 19px; color: #fff; }
  .lead { margin: 0 0 14px; font-size: 13.5px; line-height: 1.55; color: #b5bac1; }
  .icon { display: flex; justify-content: center; margin: 0 0 16px; }
  .icon img {
    width: 56px; height: 56px; padding: 6px;
    background: #1e1f22; border-radius: 12px;
  }
  .pin {
    background: #2b2d31; border-left: 3px solid #f0b232; border-radius: 6px;
    padding: 12px 14px; margin: 0 0 18px; font-size: 12.5px; line-height: 1.55;
  }
  ul { margin: 0 0 22px; padding: 0; list-style: none; }
  li {
    display: flex; gap: 10px; align-items: baseline;
    padding: 10px 0; border-top: 1px solid #3f4147;
    font-size: 13px; line-height: 1.55;
  }
  li:first-child { border-top: none; }
  kbd {
    flex: none; white-space: nowrap;
    background: #1e1f22; border: 1px solid #111214; border-radius: 4px;
    padding: 3px 7px; font-family: inherit; font-size: 12px; color: #fff;
  }
  button {
    width: 100%; padding: 11px; border: none; border-radius: 6px;
    background: #5865f2; color: #fff;
    font-size: 14px; font-weight: 600; cursor: pointer;
  }
  button:hover { background: #4752c4; }
"""


def _icon_data_uri() -> str:
    """트레이에 뜨는 것과 동일한 아이콘을 data URI로 (찾아야 할 대상을 그대로 제시)."""
    buf = io.BytesIO()
    make_icon_image(True).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def build_html(combo_label: str | None = None) -> str:
    """안내 창 HTML. combo_label이 없으면(핫키 꺼짐) 단축키 줄을 생략한다."""
    e = _html.escape
    hotkey_li = ""
    if combo_label:
        hotkey_li = ("<li><kbd>" + e(combo_label) + "</kbd>"
                     "<span>" + e(tr("welcome_hotkey")) + "</span></li>")
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>" + e(APP_NAME) + "</title>"
        "<style>" + _CSS + "</style></head><body>"
        "<h1>" + e(tr("welcome_title")) + "</h1>"
        '<p class="lead">' + e(tr("welcome_tray")) + "</p>"
        '<div class="icon"><img src="' + _icon_data_uri() + '" alt=""></div>'
        '<div class="pin">' + e(tr("welcome_pin")) + "</div>"
        "<ul>"
        + hotkey_li
        + "<li><span>" + e(tr("welcome_compress")) + "</span></li>"
        "<li><span>" + e(tr("welcome_menu")) + "</span></li>"
        "</ul>"
        '<button id="ok">' + e(tr("welcome_ok")) + "</button>"
        "<script>"
        'document.getElementById("ok").addEventListener("click", function () {'
        "  if (window.pywebview && window.pywebview.api) window.pywebview.api.close();"
        "});"
        "</script>"
        "</body></html>"
    )


class _Api:
    """확인 버튼 → 창 닫기 (JS에서 호출)."""

    def __init__(self):
        self.window = None

    def close(self):
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass


def create_window(combo_label: str | None = None):
    """webview.start() 호출 전에 만든다. 사용자가 닫을 때까지 떠 있는다.

    피커 창이 hidden 상태로 함께 살아 있으므로, 이 창을 닫아도 앱은 종료되지 않고
    트레이에 그대로 남는다.
    """
    import webview

    api = _Api()
    win = webview.create_window(
        APP_NAME, html=build_html(combo_label), js_api=api,
        width=WIN_W, height=WIN_H, resizable=False,
    )
    api.window = win
    return win
