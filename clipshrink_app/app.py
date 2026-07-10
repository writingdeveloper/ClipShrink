# -*- coding: utf-8 -*-
"""애플리케이션 오케스트레이션.

스레드 구성:
  - 메인 스레드: webview.start() (WebView2 GUI 루프 — 창 destroy 시 반환)
  - pystray: run_detached() (자체 스레드)
  - HotkeyListener: RegisterHotKey + GetMessage 루프 (전용 스레드)
  - Monitor: 클립보드 감시 (전용 스레드)
WebView2 런타임이 없으면 피커 없이 v1 모드(icon.run이 메인 스레드)로 동작한다.
"""

from __future__ import annotations

import threading

from . import APP_NAME, config, tray
from .config import (cleanup_temp, ensure_single_instance, get_setting_flag,
                     get_setting_int, get_setting_str, set_setting_flag)
from .i18n import set_language, tr
from .monitor import Monitor


def webview2_available() -> bool:
    """WebView2 Evergreen 런타임 설치 여부 (레지스트리)."""
    import winreg
    guid = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{guid}"),
    ]
    for root, sub in paths:
        try:
            with winreg.OpenKey(root, sub) as key:
                if winreg.QueryValueEx(key, "pv")[0]:
                    return True
        except OSError:
            continue
    return False


def _enable_dpi_awareness():
    """좌표 계산이 물리 px로 일관되도록 Per-Monitor DPI aware로 설정."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    import os
    if os.environ.get("CLIPSHRINK_DEBUG"):
        import faulthandler
        _fh = open(os.environ["CLIPSHRINK_DEBUG"] + ".stacks", "w", encoding="utf-8")
        faulthandler.dump_traceback_later(18, file=_fh)

    _enable_dpi_awareness()
    ensure_single_instance()
    cleanup_temp()

    # 저장된 업로드 한도 불러오기 (없으면 기본값 유지)
    config.set_limit_mb(get_setting_int("limit_mb", config.LIMIT_MB))

    # 언어: 저장된 설정(없으면 'auto' → 시스템 언어 감지)
    set_language(get_setting_str("lang", "auto"))

    # 자동 시작은 opt-in: 첫 실행이면 안내만 하고, 등록은 사용자가 트레이 메뉴에서 직접 켠다.
    first_run = not get_setting_flag("welcomed")
    if first_run:
        set_setting_flag("welcomed")

    monitor = Monitor()
    threading.Thread(target=monitor.run, daemon=True).start()

    if not webview2_available():
        # 피커 없이 v1 모드로 동작 (압축 기능은 그대로)
        icon = tray.build_icon(monitor)
        if first_run:
            threading.Timer(1.5, lambda: icon.notify(tr("notify_first_run"), APP_NAME)).start()
        threading.Timer(2.5, lambda: icon.notify(tr("notify_webview2_missing"), APP_NAME)).start()
        icon.run()
        return

    import os

    import webview

    from .hotkey import HotkeyListener
    from .picker.assets_server import AssetServer
    from .picker.window import PickerApi, PickerController

    # 스켈레톤 resolver: probe만 서빙 (T7에서 라이브러리 기반으로 교체)
    def _resolve_asset(item_id: str):
        if item_id == "probe":
            return os.path.join(config.DATA_DIR, "assets", "probe.gif")
        return None

    asset_server = AssetServer(_resolve_asset)
    asset_server.start()

    api = PickerApi(asset_server=asset_server)
    picker = PickerController(api=api)
    api._ctrl = picker
    listener = HotkeyListener(on_hotkey=picker.toggle)

    icon = tray.build_icon(
        monitor, picker=picker, listener=listener,
        on_quit_extra=lambda: (listener.stop(), asset_server.stop(), picker.destroy()),
    )
    listener.on_register_fail = lambda label: icon.notify(
        tr("notify_hotkey_fail", combo=label), APP_NAME)

    picker.create_window()
    icon.run_detached()
    combo = get_setting_str("hotkey", "ctrl+shift+e")
    if combo != "off":
        listener.start(combo)
    if first_run:
        threading.Timer(1.5, lambda: icon.notify(tr("notify_first_run"), APP_NAME)).start()

    # QA 훅: 핫키와 동일한 코드 경로(toggle)를 합성 키 입력 없이 구동
    import os
    if os.environ.get("CLIPSHRINK_DEBUG_AUTOSHOW"):
        threading.Timer(3.0, picker.toggle).start()

    # http_server=False: UI를 file:// origin으로 로드해 로컬 자산 <img src="file:///...">
    # 로드가 차단되지 않게 한다 (내부 HTTP 서버 origin에서는 local resource 차단됨)
    webview.start(gui="edgechromium", http_server=False)  # 메인 스레드 블록
    monitor.stop_flag = True
