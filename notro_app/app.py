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


def _set_app_user_model_id():
    """작업 표시줄이 트레이·피커 창을 Notro exe 아이콘으로 묶어 표시하도록
    명시적 AppUserModelID를 지정한다. 지정하지 않으면 pythonw/WebView2 기본
    아이콘으로 흩어져, 시작 표시줄에 Notro 아이콘 대신 기본 아이콘이 뜬다."""
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("writingdeveloper.Notro")
    except Exception:
        pass


def main():
    import os
    import sys
    if os.environ.get("NOTRO_DEBUG"):
        import faulthandler
        _fh = open(os.environ["NOTRO_DEBUG"] + ".stacks", "w", encoding="utf-8")
        faulthandler.dump_traceback_later(18, file=_fh)

    _enable_dpi_awareness()
    _set_app_user_model_id()
    ensure_single_instance()
    config.migrate_legacy_data()  # v2.0 ClipShrink → Notro 데이터/설정 이전 (1회)
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

    # 자동 업데이터는 frozen(exe)일 때만. on_ready는 아이콘 생성 후 재배선한다.
    upd = None
    if getattr(sys, "frozen", False):
        from .updater import UpdateChecker
        upd = UpdateChecker(
            os.path.join(config.TEMP_DIR, "update"),
            on_ready=lambda tag, exe: None,
            is_enabled=lambda: config.get_setting_int("auto_update", 1) == 1)

    if not webview2_available():
        # 피커 없이 v1 모드로 동작 (압축 기능은 그대로)
        icon = tray.build_icon(monitor, updater=upd)
        if upd:
            upd.on_ready = lambda tag, exe: tray.signal_update_ready(icon, monitor, tag)
            upd.start()
        if first_run:
            threading.Timer(1.5, lambda: icon.notify(tr("notify_first_run"), APP_NAME)).start()
        threading.Timer(2.5, lambda: icon.notify(tr("notify_webview2_missing"), APP_NAME)).start()
        icon.run()
        return

    import webview

    from .hotkey import HotkeyListener
    from .library import Library
    from .picker.assets_server import AssetServer
    from .picker.window import PickerApi, PickerController

    library = Library(config.DATA_DIR)

    def _resolve_asset(item_id: str):
        item = library.get(item_id)
        if item is None and item_id.startswith("folder:"):
            item = next((i for i in library.scan_folders()
                         if i["id"] == item_id), None)
        return library.asset_path(item) if item else None

    asset_server = AssetServer(_resolve_asset)
    asset_server.start()

    api = PickerApi(library=library, asset_server=asset_server)
    picker = PickerController(library=library, api=api)
    api._ctrl = picker
    listener = HotkeyListener(on_hotkey=picker.toggle)

    icon = tray.build_icon(
        monitor, picker=picker, listener=listener, updater=upd,
        on_quit_extra=lambda: (listener.stop(), asset_server.stop(), picker.destroy(),
                               upd.stop() if upd else None),
    )
    listener.on_register_fail = lambda label: icon.notify(
        tr("notify_hotkey_fail", combo=label), APP_NAME)
    picker.on_notify = lambda msg: icon.notify(msg, APP_NAME)
    if upd:
        upd.on_ready = lambda tag, exe: tray.signal_update_ready(icon, monitor, tag)
        upd.start()

    picker.create_window()
    icon.run_detached()
    combo = get_setting_str("hotkey", "ctrl+shift+e")
    if combo != "off":
        listener.start(combo)
    if first_run:
        # 창이 없는 트레이 앱이라 첫 실행에는 앱이 떴는지조차 모르기 쉽다 — 특히
        # Windows 11은 새 트레이 아이콘을 기본으로 숨긴다. 그래서 사용자가 직접 읽고
        # 닫는 안내 창을 띄운다. (토스트는 알림을 끈 사용자에게 아예 도달하지 못하고,
        # 시간 기반 자동 팝업은 설치 마법사의 완료 화면을 덮어버린다.) 안내 창에는
        # 트레이에 뜨는 것과 같은 아이콘을 심어 무엇을 찾아야 하는지 보여준다.
        from . import welcome
        from .hotkey import label_for
        combo_label = label_for(combo) if combo != "off" else None
        welcome.create_window(combo_label)
        first_msg = (tr("notify_first_run_picker", combo=combo_label)
                     if combo_label else tr("notify_first_run"))
        threading.Timer(1.5, lambda: icon.notify(first_msg, APP_NAME)).start()

    # QA 훅: 핫키와 동일한 코드 경로(toggle)를 합성 키 입력 없이 구동
    import os
    if os.environ.get("NOTRO_DEBUG_AUTOSHOW"):
        threading.Timer(3.0, picker.toggle).start()

    # http_server=False: UI를 file:// origin으로 로드해 로컬 자산 <img src="file:///...">
    # 로드가 차단되지 않게 한다 (내부 HTTP 서버 origin에서는 local resource 차단됨)
    webview.start(gui="edgechromium", http_server=False)  # 메인 스레드 블록
    monitor.stop_flag = True
