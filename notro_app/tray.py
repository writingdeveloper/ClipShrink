# -*- coding: utf-8 -*-
"""트레이 아이콘·메뉴."""

from __future__ import annotations

import os
import threading

import pystray
from PIL import Image, ImageDraw

from . import APP_NAME, __version__, config
from .config import (get_setting_str, is_startup_registered, set_setting_int,
                     set_setting_str, set_startup)
from .i18n import set_language, tr


def make_icon_image(active=True, update_pending=False):
    """Notro 트레이 아이콘: 니트로식 블러플 캡슐에 'not Nitro' 대각선 슬래시.
    active=False(감시 중지)면 회색으로 표시. update_pending이면 우측 상단에
    주황 배지를 그려 업데이트 대기를 알린다 — Windows 알림이 꺼져 있어도
    트레이에서 보이는 신호다."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (88, 101, 242, 255) if active else (128, 128, 128, 255)  # 디스코드 블러플
    # 니트로 캡슐(알약)
    d.rounded_rectangle([12, 20, 52, 44], radius=12, fill=color)
    # "not Nitro" 대각선 슬래시 (흰 선으로 캡슐 위에 또렷하게)
    d.line([16, 46, 48, 18], fill=(255, 255, 255, 255), width=7)
    if update_pending:
        # 업데이트 대기 배지 (우측 상단 주황 원 + 흰 테두리). 16px 트레이에서도
        # 읽히도록 크게 그린다.
        d.ellipse([40, 2, 62, 24], fill=(255, 149, 0, 255),
                  outline=(255, 255, 255, 255), width=3)
    return img


def signal_update_ready(icon, monitor, tag: str) -> None:
    """업데이트 준비를 알림 설정과 무관한 경로로도 전달한다: 트레이 아이콘 배지 +
    툴팁 변경 + 메뉴 갱신(숨겨진 '재시작해 업데이트' 항목 노출). 알림이 켜져 있으면
    토스트도 함께 띄운다. on_ready가 icon.notify만 부르면 알림을 끈 사용자는
    업데이트를 전혀 인지하지 못하므로, 아이콘·툴팁·메뉴로도 신호를 남긴다."""
    try:
        icon.icon = make_icon_image(monitor.enabled, update_pending=True)
        icon.title = tr("update_ready", ver=tag)
        icon.update_menu()
    except Exception:
        pass
    try:
        icon.notify(tr("update_ready", ver=tag), APP_NAME)
    except Exception:
        pass


def build_icon(monitor, picker=None, listener=None, on_quit_extra=None, updater=None) -> "pystray.Icon":
    """트레이 아이콘 구성.

    picker/listener가 주어지면 피커 열기·핫키 메뉴가 추가된다 (없으면 v1 메뉴).
    on_quit_extra: 종료 시 추가 정리 콜백.
    """

    def on_toggle(icon, item):
        monitor.enabled = not monitor.enabled
        pending = bool(updater and updater.ready_exe)
        icon.icon = make_icon_image(monitor.enabled, update_pending=pending)

    def on_toggle_startup(icon, item):
        try:
            set_startup(not is_startup_registered())
        except Exception:
            icon.notify(tr("notify_startup_fail"), APP_NAME)

    def on_quit(icon, item):
        monitor.stop_flag = True
        if on_quit_extra:
            try:
                on_quit_extra()
            except Exception:
                pass
        icon.stop()

    def on_open_folder(icon, item):
        os.startfile(config.TEMP_DIR)

    def on_open_library(icon, item):
        try:
            os.startfile(config.DATA_DIR)
        except OSError:
            pass

    def make_open(path):
        def _open(icon, item):
            if os.path.exists(path):
                os.startfile(path)
            else:
                icon.notify(tr("notify_file_deleted"), APP_NAME)
        return _open

    def history_items():
        """최근 처리 내역 서브메뉴 (클릭 시 이미지 열기)."""
        with monitor.history_lock:
            snapshot = list(monitor.history)
        if not snapshot:
            yield pystray.MenuItem(tr("history_empty"), None, enabled=False)
            return
        for e in reversed(snapshot):
            label = f"{e['time']}  {e['orig_mb']:.1f}MB → {e['new_mb']:.1f}MB (-{e['pct']}%)"
            yield pystray.MenuItem(label, make_open(e["path"]))

    def make_limit_item(mb):
        def on_select(icon, item):
            config.set_limit_mb(mb)
            set_setting_int("limit_mb", mb)
            icon.update_menu()

        return pystray.MenuItem(
            f"{mb} MB",
            on_select,
            checked=lambda item, mb=mb: config.LIMIT_MB == mb,
            radio=True,
        )

    # 디스코드 한도: 무료 10 / 니트로 베이직 50 / 니트로 500 MB
    limit_menu = pystray.Menu(
        make_limit_item(10),
        make_limit_item(50),
        make_limit_item(500),
    )

    # 언어 메뉴 (자동 감지 + 각 언어). 언어명은 해당 언어 표기 그대로 둔다.
    lang_names = {
        "en": "English",
        "ko": "한국어",
        "ja": "日本語",
        "zh": "中文(简体)",
        "es": "Español",
    }

    def make_lang_item(code):
        def on_select(icon, item):
            set_setting_str("lang", code)
            set_language(code)
            icon.title = _tooltip()  # 언어를 바꾸면 툴팁도 새 언어로
            icon.update_menu()

        label = (lambda item: tr("lang_auto")) if code == "auto" else lang_names[code]
        return pystray.MenuItem(
            label,
            on_select,
            checked=lambda item, code=code: get_setting_str("lang", "auto") == code,
            radio=True,
        )

    lang_menu = pystray.Menu(
        make_lang_item("auto"),
        make_lang_item("en"),
        make_lang_item("ko"),
        make_lang_item("ja"),
        make_lang_item("zh"),
        make_lang_item("es"),
    )

    # ---------- 피커 항목 (picker/listener가 있을 때만) ----------
    picker_items = []
    if picker is not None:
        from .hotkey import HOTKEY_CHOICES, HOTKEY_OFF

        def on_open_picker(icon, item):
            picker.show_at_cursor()

        def make_hotkey_item(key):
            def on_select(icon, item):
                set_setting_str("hotkey", key)
                if listener:
                    listener.set_combo(key)
                icon.title = _tooltip()  # 툴팁의 단축키 표기도 따라간다
                icon.update_menu()

            label = (lambda item: tr("hotkey_off")) if key == HOTKEY_OFF \
                else HOTKEY_CHOICES[key][2]
            return pystray.MenuItem(
                label,
                on_select,
                checked=lambda item, key=key: get_setting_str("hotkey", "ctrl+shift+e") == key,
                radio=True,
            )

        hotkey_menu = pystray.Menu(
            *[make_hotkey_item(k) for k in HOTKEY_CHOICES],
            make_hotkey_item(HOTKEY_OFF),
        )
        picker_items = [
            pystray.MenuItem(lambda item: tr("picker_open"), on_open_picker),
            pystray.MenuItem(lambda item: tr("hotkey_menu"), hotkey_menu),
            pystray.Menu.SEPARATOR,
        ]

    # ---------- 업데이트 항목 (updater가 있을 때만) ----------
    updater_items = []
    if updater is not None:
        def _auto_on():
            # auto_update 미설정이면 기본 on(1)
            return config.get_setting_int("auto_update", 1) == 1

        def on_check_update(icon, item):
            icon.notify(tr("update_checking"), APP_NAME)

            def _bg():
                updater.check_once()
                if updater.ready_exe:
                    signal_update_ready(icon, monitor, updater.ready_tag)
                else:
                    icon.notify(tr("update_none"), APP_NAME)
            threading.Thread(target=_bg, daemon=True).start()

        def on_restart_update(icon, item):
            if updater.ready_exe:
                from . import updater as um
                um.apply_and_restart(updater.ready_exe)
                on_quit(icon, item)

        def on_toggle_auto(icon, item):
            config.set_setting_flag("auto_update", not _auto_on())
            icon.update_menu()

        updater_items = [
            pystray.MenuItem(lambda item: tr("update_restart"), on_restart_update,
                             visible=lambda item: bool(updater.ready_exe)),
            pystray.MenuItem(lambda item: tr("update_check"), on_check_update),
            pystray.MenuItem(lambda item: tr("update_auto"), on_toggle_auto,
                             checked=lambda item: _auto_on()),
            pystray.Menu.SEPARATOR,
        ]

    def _tooltip() -> str:
        """트레이 툴팁. 피커가 있으면 단축키까지 노출해 hover만으로 발견되게 한다."""
        c = get_setting_str("hotkey", "ctrl+shift+e")
        if picker is not None and c != "off":
            from .hotkey import label_for
            return tr("tooltip_picker", ver=__version__, combo=label_for(c))
        return tr("tooltip", ver=__version__)

    icon = pystray.Icon(
        APP_NAME,
        make_icon_image(True),
        _tooltip(),
        menu=pystray.Menu(
            *picker_items,
            pystray.MenuItem(
                lambda item: tr("pause") if monitor.enabled else tr("resume"),
                on_toggle,
            ),
            pystray.MenuItem(lambda item: tr("history"), pystray.Menu(history_items)),
            pystray.MenuItem(lambda item: tr("upload_limit"), limit_menu),
            pystray.MenuItem(lambda item: tr("open_folder"), on_open_folder),
            pystray.MenuItem(lambda item: tr("open_library_folder"), on_open_library),
            pystray.MenuItem(lambda item: tr("language"), lang_menu),
            pystray.MenuItem(
                lambda item: tr("run_at_startup"),
                on_toggle_startup,
                checked=lambda item: is_startup_registered(),
            ),
            *updater_items,
            pystray.MenuItem(lambda item: tr("quit"), on_quit),
        ),
    )
    monitor.on_history_change = icon.update_menu
    monitor.status_cb = lambda title, msg: icon.notify(msg, title)
    return icon
