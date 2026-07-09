# ClipShrink v2.0 디스코드 피커 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 디스코드 입력창의 이모지/스티커/GIF 피커 패널을 클라이언트 수정 없이 대체하는 핫키 팝업 피커를 ClipShrink에 통합한다.

**Architecture:** 기존 단일 파일을 `clipshrink_app` 패키지로 분리한 뒤, pywebview(WebView2) 숨김 창을 글로벌 핫키로 토글하는 피커를 추가한다. 피커는 로컬 라이브러리(%APPDATA%\ClipShrink)의 이모지/스티커/GIF를 디스코드 다크테마 HTML 그리드로 보여주고, 선택 시 CF_HDROP 클립보드 세팅 + SendInput Ctrl+V로 디스코드 입력창에 첨부한다. 전송(Enter)은 항상 사용자.

**Tech Stack:** Python 3.10+, Pillow, pystray, pywebview≥5 (WebView2), ctypes (RegisterHotKey/SendInput/클립보드), pytest.

**Spec:** `docs/superpowers/specs/2026-07-09-discord-picker-design.md`

## Global Constraints

- ToS 불변 조건: 디스코드 클라이언트 불가침 / 유저 토큰 API 호출 금지 / 전송(Enter)은 항상 사용자가.
- 진입점 `clipshrink.py`는 `main()` 호출만 남긴다 (build.bat/pythonw 호환).
- 의존성 추가는 pywebview 하나. 핫키·SendInput은 ctypes 직접 구현 (pywin32 금지).
- 피커 창: frameless, on_top, 고정 440×420, 시작 시 생성 후 숨김.
- 신규 i18n 키는 **5개 언어 전부** 작성한다 (기존 테스트 `test_all_languages_have_same_keys`가 키 패리티를 강제 — 스펙 §9의 "en 폴백" 계획을 상향).
- 디스코드 자산(로고·아이콘·gg sans 폰트) 복사 금지 — 자체 CSS만.
- 커밋 메시지 끝에 항상:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` + `Claude-Session: https://claude.ai/code/session_016VnVCHyBdcAWPhhka2xMm9`
- 모든 명령은 레포 루트 `C:\Users\SIHYEONG\Documents\GitHub\CaptureOptimize`에서 실행.

## File Structure (최종)

```
clipshrink.py                # 진입점: from clipshrink_app.app import main; main()
clipshrink_app/
  __init__.py                # __version__, APP_NAME
  config.py                  # 설정·경로·한도·시작등록·단일인스턴스·cleanup_temp
  i18n.py                    # STRINGS(5개 언어)·tr·set_language
  compress.py                # compress_image·estimate_png_size·_to_rgb_on_white
  clipboard_win.py           # 클립보드(파일/텍스트/PNG/marker)·포커스·SendInput
  monitor.py                 # Monitor (클립보드 감시)
  hotkey.py                  # HotkeyListener (RegisterHotKey 스레드)
  library.py                 # Library (items/folders JSON + assets 캐시)
  fetch.py                   # CDN URL 파싱·다운로드·APNG→GIF·등록
  tray.py                    # 트레이 아이콘·메뉴 빌드
  app.py                     # main() 오케스트레이션 (webview.start 메인스레드)
  picker/
    __init__.py
    window.py                # PickerController + PickerApi(JS 브리지)
    ui/index.html, ui/app.css, ui/app.js   # 디스코드 다크테마 피커 UI
tests/
  test_compress.py           # (임포트 경로만 갱신)
  test_i18n.py               # (임포트 경로만 갱신)
  test_clipboard_data.py     # build_drop_data 등 순수 함수 (신규)
  test_library.py            # (신규)
  test_fetch.py              # (신규)
  test_hotkey.py             # (신규, 순수 헬퍼만)
```

스펙 §3 대비 변경: 오케스트레이션 홈으로 `app.py` 추가(트레이와 분리), `picker/server.py` → `picker/window.py` 명칭 확정.

---

### Task 1: 패키지 분리 리팩터링 (동작 불변)

**Files:**
- Create: `clipshrink_app/__init__.py`, `config.py`, `i18n.py`, `compress.py`, `clipboard_win.py`, `monitor.py`, `tray.py`, `app.py`
- Modify: `clipshrink.py` (진입점만 남김), `tests/test_compress.py`, `tests/test_i18n.py`
- Test: 기존 테스트 전부 그대로 통과

**Interfaces (Produces):**
- `clipshrink_app.__init__`: `__version__: str`, `APP_NAME = "ClipShrink"`
- `config`: `LIMIT_MB/LIMIT_BYTES/SAFETY/POLL_INTERVAL`, `compute_limit_bytes(mb)->int`, `set_limit_mb(mb)`, `TEMP_DIR`, `DATA_DIR`, `cleanup_temp()`, `get/set_setting_int|str|flag`, `get_launch_command()`, `is_startup_registered()`, `set_startup(bool)`, `ensure_single_instance()`
- `i18n`: `STRINGS`, `SUPPORTED_LANGS`, `current_lang`, `tr(key, **kw)->str`, `set_language(pref)`, `detect_system_lang()`
- `compress`: `compress_image(img, limit)->(bytes, ext)|None`, `estimate_png_size(img)->int`, `_to_rgb_on_white(im)`
- `clipboard_win`: `set_clipboard_file(path)->bool`, `clipboard_has_marker()->bool`, `get_clipboard_png()->bytes|None`, `get_sequence_number()->int`
- `monitor`: `class Monitor` (기존 시그니처 유지: `.enabled .stop_flag .status_cb .history .history_lock .on_history_change .run() .notify()`)
- `tray`: `make_icon_image(active)->Image`, `build_icon(monitor, on_quit_extra=None)->pystray.Icon`
- `app`: `main()`

- [ ] **Step 1: 패키지 골격 + 코드 이동**

`clipshrink_app/__init__.py`:

```python
"""ClipShrink 애플리케이션 패키지."""
__version__ = "1.2.0"
APP_NAME = "ClipShrink"
```

`clipshrink_app/config.py` — 기존 `clipshrink.py`의 33-50행(상수), 78-167행(시작등록·설정), 304-317행(단일 인스턴스), 604-612행(cleanup_temp)을 이동하고 아래만 변경:

```python
# -*- coding: utf-8 -*-
"""설정(레지스트리)·경로·업로드 한도·시작 프로그램·단일 인스턴스."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
import tempfile
import time

from . import APP_NAME

LIMIT_MB = 10           # 디스코드 무료 업로드 한도 (MB)
SAFETY = 0.95           # 안전 마진
POLL_INTERVAL = 0.4     # 클립보드 확인 주기 (초)


def compute_limit_bytes(mb: int) -> int:
    """업로드 한도(MB)에 안전 마진을 적용한 바이트 한도."""
    return int(mb * 1024 * 1024 * SAFETY)


LIMIT_BYTES = compute_limit_bytes(LIMIT_MB)


def set_limit_mb(mb: int) -> None:
    """런타임 업로드 한도 변경 (트레이 메뉴에서 호출)."""
    global LIMIT_MB, LIMIT_BYTES
    LIMIT_MB = mb
    LIMIT_BYTES = compute_limit_bytes(mb)


TEMP_DIR = os.path.join(tempfile.gettempdir(), "ClipShrink")
os.makedirs(TEMP_DIR, exist_ok=True)

# 피커 라이브러리 영구 데이터 (Task 3에서 사용)
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipShrink")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SETTINGS_KEY = r"Software\ClipShrink"
# ... (get_launch_command / is_startup_registered / set_startup /
#      get_setting_int / set_setting_int / get_setting_flag / set_setting_flag /
#      get_setting_str / set_setting_str / ensure_single_instance / cleanup_temp
#      — 원본 그대로 이동. 단 두 가지 수정:)
```

이동 시 수정 2건 (원본과 달라지는 유일한 부분):

1. `get_launch_command()`의 `script = os.path.abspath(__file__)` → `script = os.path.abspath(sys.argv[0])` — 이동 후 `__file__`이 config.py를 가리키게 되므로 진입 스크립트 기준으로 교정.
2. `cleanup_temp()`는 `TEMP_DIR`를 같은 모듈에서 참조 (변경 없음, 위치만).

`clipshrink_app/i18n.py` — 기존 170-301행 그대로 이동. `kernel32`는 모듈 상단에서 자체 바인딩:

```python
# -*- coding: utf-8 -*-
"""다국어 (i18n)."""
from __future__ import annotations

import ctypes

kernel32 = ctypes.windll.kernel32

SUPPORTED_LANGS = ("en", "ko", "ja", "zh", "es")
_PRIMARY_LANG_MAP = {0x09: "en", 0x12: "ko", 0x11: "ja", 0x04: "zh", 0x0A: "es"}
STRINGS = { ... }   # 원본 176-272행 그대로
current_lang = "en"
# detect_system_lang / set_language / tr — 원본 그대로
```

`clipshrink_app/compress.py` — 기존 36-38행(품질 상수)과 403-457행 그대로 이동:

```python
# -*- coding: utf-8 -*-
"""이미지 압축 로직 (순수 함수 — Windows API 무관)."""
from __future__ import annotations

import io

from PIL import Image

WEBP_QUALITIES = [90, 80, 70, 60, 50]
JPEG_QUALITIES = [85, 75, 65]
MIN_SCALE = 0.4
# estimate_png_size / _to_rgb_on_white / compress_image — 원본 그대로
```

`clipshrink_app/clipboard_win.py` — 기존 52-72행(바인딩·상수), 320-400행 이동. `set_clipboard_file`은 공용 헬퍼로 재구성 (Task 5에서 텍스트 세터가 재사용):

```python
# -*- coding: utf-8 -*-
"""Windows 클립보드: CF_HDROP 파일·마커·PNG 읽기."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wt.LPVOID
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [wt.HGLOBAL]
user32.SetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.GetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]

CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
MARKER_FORMAT = user32.RegisterClipboardFormatW("ClipShrinkMarker")
PNG_FORMATS = [
    user32.RegisterClipboardFormatW("PNG"),
    user32.RegisterClipboardFormatW("image/png"),
]


def build_drop_data(path: str) -> bytes:
    """CF_HDROP용 DROPFILES 구조체 바이트를 만든다 (순수 함수 — 테스트 대상)."""
    files = path + "\0"
    return struct.pack("<Iiiii", 20, 0, 0, 0, 1) + files.encode("utf-16-le") + b"\0\0"


def _open_clipboard_retry() -> bool:
    for _ in range(10):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def _global_put(fmt: int, data: bytes) -> bool:
    hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not hmem:
        return False
    ptr = kernel32.GlobalLock(hmem)
    if not ptr:
        return False
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(hmem)
    return bool(user32.SetClipboardData(fmt, hmem))


def _put_marker() -> None:
    _global_put(MARKER_FORMAT, b"\x01\x00")  # best-effort


def set_clipboard_file(path: str) -> bool:
    """파일을 CF_HDROP로 클립보드에 넣어 Ctrl+V 업로드가 되게 한다."""
    if not _open_clipboard_retry():
        return False
    try:
        user32.EmptyClipboard()
        if not _global_put(CF_HDROP, build_drop_data(path)):
            return False
        _put_marker()
        return True
    finally:
        user32.CloseClipboard()


def clipboard_has_marker() -> bool:
    return bool(user32.IsClipboardFormatAvailable(MARKER_FORMAT))


def get_sequence_number() -> int:
    return user32.GetClipboardSequenceNumber()


def get_clipboard_png() -> bytes | None:
    # 원본 372-400행 그대로 (OpenClipboard 재시도는 _open_clipboard_retry() 사용으로 교체)
    ...
```

`clipshrink_app/monitor.py` — 기존 461-601행 Monitor 이동. 치환 규칙: `user32.GetClipboardSequenceNumber()` → `cb.get_sequence_number()`, `LIMIT_BYTES` → `config.LIMIT_BYTES` (호출 시점 참조 유지), `clipboard_has_marker/get_clipboard_png/set_clipboard_file` → `cb.` 접두, `compress_image/estimate_png_size` → `compress.` 접두, `cleanup_temp/TEMP_DIR/POLL_INTERVAL` → `config.` 접두, `tr` → `from .i18n import tr`, `APP_NAME` → `from . import APP_NAME`:

```python
# -*- coding: utf-8 -*-
"""클립보드 감시 루프."""
from __future__ import annotations

import io
import os
import threading
import time
from datetime import datetime

from PIL import Image, ImageGrab

from . import APP_NAME
from . import clipboard_win as cb
from . import compress, config
from .i18n import tr


class Monitor:
    # 원본 로직 그대로 (위 치환 규칙만 적용)
    ...
```

`clipshrink_app/tray.py` — 기존 616-624행(make_icon_image)과 main() 안의 트레이 메뉴 구성(651-761행)을 `build_icon(monitor)`로 이동:

```python
# -*- coding: utf-8 -*-
"""트레이 아이콘·메뉴."""
from __future__ import annotations

import os
import threading

import pystray
from PIL import Image, ImageDraw

from . import APP_NAME, __version__, config
from .i18n import tr, set_language


def make_icon_image(active=True):
    # 원본 그대로


def build_icon(monitor, on_quit_extra=None) -> "pystray.Icon":
    """트레이 아이콘 구성. on_quit_extra: 종료 시 추가 정리 콜백 (Task 7에서 피커 destroy)."""
    # 원본 main()의 on_toggle/on_toggle_startup/on_open_folder/make_open/history_items/
    # make_limit_item/limit_menu/lang_names/make_lang_item/lang_menu/icon 구성을 그대로 이동.
    # 변경점:
    #  - global LIMIT_MB 갱신 → config.set_limit_mb(mb)
    #  - on_quit: monitor.stop_flag = True; (on_quit_extra and on_quit_extra()); icon.stop()
    #  - 반환 전 monitor.on_history_change / monitor.status_cb 연결도 이곳에서 수행
    ...
    return icon
```

`clipshrink_app/app.py` — 기존 main()의 나머지(627-649, 762-769행):

```python
# -*- coding: utf-8 -*-
"""애플리케이션 오케스트레이션."""
from __future__ import annotations

import threading

from . import config
from .config import (cleanup_temp, ensure_single_instance, get_setting_flag,
                     get_setting_int, get_setting_str, set_setting_flag)
from .i18n import set_language, tr
from .monitor import Monitor
from . import tray


def main():
    ensure_single_instance()
    cleanup_temp()
    config.set_limit_mb(get_setting_int("limit_mb", config.LIMIT_MB))
    set_language(get_setting_str("lang", "auto"))

    first_run = not get_setting_flag("welcomed")
    if first_run:
        set_setting_flag("welcomed")

    monitor = Monitor()
    threading.Thread(target=monitor.run, daemon=True).start()

    icon = tray.build_icon(monitor)
    if first_run:
        threading.Timer(1.5, lambda: icon.notify(tr("notify_first_run"), tray.APP_NAME)).start()
    icon.run()
```

`clipshrink.py` (전체 교체):

```python
# -*- coding: utf-8 -*-
"""ClipShrink 진입점. 실제 구현은 clipshrink_app 패키지."""
from clipshrink_app.app import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 테스트 임포트 갱신**

`tests/test_compress.py`: `import clipshrink` → `from clipshrink_app import compress, config`, 참조 치환 `clipshrink.compress_image`→`compress.compress_image`, `clipshrink.estimate_png_size`→`compress.estimate_png_size`, `clipshrink._to_rgb_on_white`→`compress._to_rgb_on_white`, `clipshrink.LIMIT_BYTES|LIMIT_MB|SAFETY|compute_limit_bytes`→`config.` 접두.

`tests/test_i18n.py`: `import clipshrink` → `from clipshrink_app import i18n`, 모든 `clipshrink.` → `i18n.` (예: `i18n.current_lang = "ko"`, `i18n.tr("quit")`).

- [ ] **Step 3: 테스트 실행 (전부 통과 확인)**

Run: `python -m pytest -q`
Expected: `16 passed` (기존 9+7개, 실패 0)

- [ ] **Step 4: 수동 스모크 — 기존 기능 회귀 없음**

Run: `python clipshrink.py` (트레이 뜸) → 10MB 초과 이미지 복사 → 압축 알림 확인 → 트레이 종료.

- [ ] **Step 5: Commit**

```
git add -A && git commit -m "refactor: split clipshrink.py into clipshrink_app package (no behavior change)"
```

---

### Task 2: Walking Skeleton — pywebview+pystray+핫키 동거 검증

목적: 스펙 §10 최대 리스크(이벤트 루프 동거)와 file:/// 애니메이션 렌더를 기능 개발 **전에** 검증.

**Files:**
- Create: `clipshrink_app/hotkey.py`, `clipshrink_app/picker/__init__.py`, `clipshrink_app/picker/window.py`, `clipshrink_app/picker/ui/index.html`, `ui/app.css`, `ui/app.js` (스켈레톤 수준)
- Modify: `clipshrink_app/app.py`, `requirements.txt`
- Test: `tests/test_hotkey.py` (순수 헬퍼) + 수동 체크리스트

**Interfaces (Produces):**
- `hotkey.HOTKEY_CHOICES: dict[str, tuple[int, int, str]]` — key→(modifiers, vk, label). 키: `"ctrl+shift+e"`, `"ctrl+alt+e"`, `"ctrl+shift+space"`
- `hotkey.HOTKEY_OFF = "off"`, `hotkey.label_for(key)->str`
- `hotkey.HotkeyListener(on_hotkey, on_register_fail)` — `.start(combo_key)`, `.set_combo(combo_key)`, `.stop()`
- `picker.window.ui_index_path()->str`, `picker.window.PickerController` — `.create_window()`, `.toggle()`, `.show_at_cursor()`, `.hide()`, `.destroy()`, `.prev_hwnd`
- `app.webview2_available()->bool`

- [ ] **Step 1: 실패 테스트 작성 — hotkey 순수 헬퍼**

`tests/test_hotkey.py`:

```python
"""hotkey 모듈의 순수 부분 테스트 (스레드/Win32 등록은 수동 검증)."""
from clipshrink_app import hotkey


def test_choices_have_label_mod_vk():
    for key, (mods, vk, label) in hotkey.HOTKEY_CHOICES.items():
        assert mods and vk and label
        assert key == key.lower()


def test_default_combo_is_ctrl_shift_e():
    assert "ctrl+shift+e" in hotkey.HOTKEY_CHOICES
    mods, vk, label = hotkey.HOTKEY_CHOICES["ctrl+shift+e"]
    assert mods == hotkey.MOD_CONTROL | hotkey.MOD_SHIFT
    assert vk == 0x45  # 'E'
    assert label == "Ctrl+Shift+E"


def test_label_for_off_and_unknown():
    assert hotkey.label_for(hotkey.HOTKEY_OFF)
    assert hotkey.label_for("nope") == hotkey.label_for(hotkey.HOTKEY_OFF)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_hotkey.py -q`
Expected: FAIL (`ModuleNotFoundError: clipshrink_app.hotkey`)

- [ ] **Step 3: hotkey.py 구현**

```python
# -*- coding: utf-8 -*-
"""글로벌 핫키: RegisterHotKey + 전용 메시지 루프 스레드."""
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
    """RegisterHotKey는 등록한 스레드의 메시지 큐로 WM_HOTKEY를 보낸다.
    전용 스레드에서 등록+GetMessage 루프를 돌리고, 변경 시 WM_QUIT으로 재시작한다."""

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
        self._thread = threading.Thread(target=self._run, args=(combo_key,), daemon=True)
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
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        mods, vk, label = HOTKEY_CHOICES[combo_key]
        if not user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk):
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_hotkey.py -q`
Expected: `3 passed`

- [ ] **Step 5: 스켈레톤 피커 창 + UI 자산 경로 헬퍼**

`requirements.txt`에 `pywebview>=5.0` 추가 후 `pip install -r requirements.txt`.

`clipshrink_app/picker/__init__.py`: 빈 파일.

`clipshrink_app/picker/window.py` (스켈레톤 — Task 7에서 API 확장):

```python
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


def ui_index_path() -> str:
    """개발 실행과 PyInstaller(--add-data) 실행 모두에서 index.html 절대경로."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, "clipshrink_app", "picker", "ui", "index.html")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")


class _RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", wt.DWORD)]


def popup_position() -> tuple[int, int]:
    """커서 위쪽에 창이 오도록 좌표 계산, 모니터 작업영역으로 클램프."""
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    work = mi.rcWork
    x = min(max(pt.x - WIN_W // 2, work.left), max(work.left, work.right - WIN_W))
    y = pt.y - WIN_H - 16
    if y < work.top:
        y = min(pt.y + 16, max(work.top, work.bottom - WIN_H))
    return x, y


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

    def show_at_cursor(self):
        self.prev_hwnd = cb.get_foreground_window()
        x, y = popup_position()
        self.window.move(x, y)
        self.window.show()
        self.visible = True
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
        if self.visible:
            self.hide()
        else:
            self.show_at_cursor()

    def destroy(self):
        try:
            self.window.destroy()
        except Exception:
            pass
```

`clipboard_win.py`에 이번 태스크가 쓰는 최소 추가 (전체 포커스/SendInput은 Task 5):

```python
def get_foreground_window() -> int:
    return user32.GetForegroundWindow()
```

스켈레톤 UI — `ui/index.html`은 `%APPDATA%\ClipShrink\assets`의 아무 GIF나 file:///로 표시해 렌더 검증:

```html
<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="app.css"><title>ClipShrink Picker</title></head>
<body><div id="root">skeleton — <span id="probe">no probe gif</span></div>
<script src="app.js"></script></body></html>
```

`ui/app.css`: `body{background:#313338;color:#dbdee1;font-family:"Segoe UI",sans-serif;margin:0}`
`ui/app.js`:

```js
// 스켈레톤: file:/// GIF 렌더 검증 프로브 (Task 6에서 전체 교체)
window.__onShow = () => {};
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && window.pywebview) pywebview.api.hide();
});
```

프로브: 수동 검증 단계에서 `%APPDATA%\ClipShrink\assets\probe.gif`를 하나 두고 index.html에 `<img src="file:///C:/Users/SIHYEONG/AppData/Roaming/ClipShrink/assets/probe.gif">`를 임시 삽입해 애니메이션 재생을 확인한다 (확인 후 임시 태그 제거).

스켈레톤용 `PickerApi` 최소형 (window.py에 함께):

```python
class PickerApi:
    def __init__(self):
        self.ctrl: PickerController | None = None

    def hide(self):
        if self.ctrl:
            self.ctrl.hide()
```

- [ ] **Step 6: app.py 재배선 (webview 메인스레드 + 트레이 detached + 핫키 + Monitor)**

`app.py`의 `main()` 끝부분 교체:

```python
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


def main():
    # ... (기존 초기화 그대로) ...
    monitor = Monitor()
    threading.Thread(target=monitor.run, daemon=True).start()

    if not webview2_available():
        # 피커 없이 v1 모드로 동작
        icon = tray.build_icon(monitor)
        monitor.notify(APP_NAME, tr("notify_webview2_missing"))  # i18n 키는 Task 8에서 추가; 스켈레톤 단계에선 영어 리터럴로 임시
        icon.run()
        return

    import webview
    from .hotkey import HotkeyListener
    from .picker.window import PickerApi, PickerController

    api = PickerApi()
    picker = PickerController(api=api)
    api.ctrl = picker
    listener = HotkeyListener(on_hotkey=picker.toggle)

    icon = tray.build_icon(monitor, on_quit_extra=lambda: (listener.stop(), picker.destroy()))
    picker.create_window()
    icon.run_detached()
    listener.start(get_setting_str("hotkey", "ctrl+shift+e"))
    if first_run:
        threading.Timer(1.5, lambda: icon.notify(tr("notify_first_run"), APP_NAME)).start()
    webview.start(gui="edgechromium")   # 메인 스레드 블록; 창 destroy 시 반환
    monitor.stop_flag = True
```

- [ ] **Step 7: 수동 검증 체크리스트 (전부 통과해야 태스크 완료)**

Run: `python clipshrink.py`

1. 트레이 아이콘 정상, 기존 메뉴 전부 동작
2. `Ctrl+Shift+E` → 커서 근처에 어두운 스켈레톤 창 표시, 다시 누르면 숨김, ESC로 숨김
3. probe.gif 임시 태그 삽입 상태에서 **애니메이션 재생 확인** (file:/// 검증) — 확인 후 태그 제거
4. 창 떠 있는 동안 10MB 초과 이미지 복사 → 압축 알림 (Monitor 동거 확인)
5. 트레이 종료 → 프로세스 완전 종료 (작업관리자 확인)

- [ ] **Step 8: Commit**

```
git add -A && git commit -m "feat: walking skeleton — hotkey-toggled hidden webview picker window coexisting with tray+monitor"
```

---

### Task 3: library.py — 라이브러리 저장소 (TDD)

**Files:**
- Create: `clipshrink_app/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `config.DATA_DIR` (기본값이지만 생성자에 경로 주입 — 테스트는 tmp_path 사용)
- Produces:
  - `library.SUPPORTED_EXTS = (".png", ".gif", ".webp")` (폴더 스캔용)
  - `class Library(data_dir: str)`:
    - `.assets_dir: str`
    - `.add_item(type_, name, keywords, source_kind, source_url, filename, animated) -> dict`
    - `.get(item_id) -> dict | None`, `.remove_item(item_id)`, `.touch(item_id)`
    - `.items() -> list[dict]` (등록 항목), `.recent(limit=16) -> list[dict]`
    - `.add_folder(path, default_type="gif")`, `.remove_folder(path)`, `.folders() -> list[dict]`
    - `.scan_folders() -> list[dict]` (id=`"folder:<abs path>"`, `abs_path` 키 포함)
    - `.all_display_items() -> list[dict]` (items + scan_folders)
    - `.asset_path(item) -> str` (등록 항목=assets_dir 안, 폴더 항목=abs_path)
    - `.new_asset_filename(ext) -> str` (fetch.py가 사용: `"<12hex>.<ext>"`)
  - 항목 dict 키: `id, type, name, keywords, source_kind("discord-cdn"|"local"|"folder"), source_url, filename, animated, added_at, use_count, last_used`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_library.py`:

```python
"""Library: JSON 영속·CRUD·recent·폴더 스캔 (순수 파일시스템 — tmp_path)."""
import json
import os
import time

from PIL import Image

from clipshrink_app.library import Library, SUPPORTED_EXTS


def make_lib(tmp_path):
    return Library(str(tmp_path / "data"))


def put_asset(lib, name="a.png"):
    p = os.path.join(lib.assets_dir, name)
    Image.new("RGB", (4, 4), (255, 0, 0)).save(p)
    return name


def test_add_get_persist_roundtrip(tmp_path):
    lib = make_lib(tmp_path)
    fn = put_asset(lib)
    item = lib.add_item("emoji", "smile", ["happy"], "discord-cdn",
                        "https://cdn.discordapp.com/emojis/1.png", fn, False)
    assert item["id"] and item["use_count"] == 0
    lib2 = Library(lib.data_dir)  # 재로드
    got = lib2.get(item["id"])
    assert got["name"] == "smile" and got["keywords"] == ["happy"]


def test_remove_item_deletes_asset(tmp_path):
    lib = make_lib(tmp_path)
    fn = put_asset(lib)
    item = lib.add_item("gif", "g", [], "local", "", fn, True)
    path = lib.asset_path(item)
    assert os.path.exists(path)
    lib.remove_item(item["id"])
    assert not os.path.exists(path)
    assert lib.get(item["id"]) is None


def test_touch_updates_recent_order(tmp_path):
    lib = make_lib(tmp_path)
    a = lib.add_item("emoji", "a", [], "local", "", put_asset(lib, "a.png"), False)
    b = lib.add_item("emoji", "b", [], "local", "", put_asset(lib, "b.png"), False)
    lib.touch(a["id"]); time.sleep(0.01); lib.touch(b["id"])
    rec = lib.recent()
    assert [i["name"] for i in rec[:2]] == ["b", "a"]
    assert lib.get(a["id"])["use_count"] == 1


def test_recent_excludes_never_used(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "never", [], "local", "", put_asset(lib), False)
    assert lib.recent() == []


def test_folder_scan_lists_supported_exts_only(tmp_path):
    lib = make_lib(tmp_path)
    folder = tmp_path / "gifs"; folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "x.png")
    Image.new("RGB", (4, 4)).save(folder / "y.gif")
    (folder / "note.txt").write_text("no")
    lib.add_folder(str(folder), "gif")
    items = lib.scan_folders()
    names = sorted(i["name"] for i in items)
    assert names == ["x", "y"]
    gif = next(i for i in items if i["name"] == "y")
    assert gif["id"].startswith("folder:") and gif["animated"] is True
    assert os.path.samefile(lib.asset_path(gif), folder / "y.gif")


def test_folder_scan_missing_folder_is_skipped(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_folder(str(tmp_path / "ghost"), "gif")
    assert lib.scan_folders() == []


def test_folder_scan_cache_invalidates_on_new_file(tmp_path):
    lib = make_lib(tmp_path)
    folder = tmp_path / "f"; folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "1.png")
    lib.add_folder(str(folder), "sticker")
    assert len(lib.scan_folders()) == 1
    Image.new("RGB", (4, 4)).save(folder / "2.png")
    assert len(lib.scan_folders()) == 2


def test_corrupt_json_recovers_empty(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "a", [], "local", "", put_asset(lib), False)
    with open(os.path.join(lib.data_dir, "library.json"), "w") as f:
        f.write("{broken")
    lib2 = Library(lib.data_dir)
    assert lib2.items() == []
    assert os.path.exists(os.path.join(lib.data_dir, "library.json.bak"))


def test_all_display_items_merges(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "reg", [], "local", "", put_asset(lib), False)
    folder = tmp_path / "f"; folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "z.webp")
    lib.add_folder(str(folder), "gif")
    kinds = {i["source_kind"] for i in lib.all_display_items()}
    assert kinds == {"local", "folder"}


def test_touch_folder_item_is_noop(tmp_path):
    lib = make_lib(tmp_path)
    lib.touch("folder:C:/nope/x.gif")  # 예외 없이 무시
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_library.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현**

`clipshrink_app/library.py`:

```python
# -*- coding: utf-8 -*-
"""피커 라이브러리: 항목/폴더 JSON 영속 + 자산 캐시."""
from __future__ import annotations

import json
import os
import time
import uuid

SUPPORTED_EXTS = (".png", ".gif", ".webp")
SCHEMA_VERSION = 1


def _now() -> float:
    return time.time()


class Library:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.assets_dir = os.path.join(data_dir, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
        self._items: dict[str, dict] = {}
        self._folders: list[dict] = []
        self._scan_cache: dict[str, tuple[tuple, list[dict]]] = {}
        self._load()

    # ---------- 영속 ----------
    def _lib_path(self) -> str:
        return os.path.join(self.data_dir, "library.json")

    def _folders_path(self) -> str:
        return os.path.join(self.data_dir, "folders.json")

    def _load(self) -> None:
        self._items = {}
        self._folders = []
        for path, apply in ((self._lib_path(), self._apply_lib),
                            (self._folders_path(), self._apply_folders)):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    apply(json.load(f))
            except (json.JSONDecodeError, OSError, KeyError, TypeError):
                try:  # 손상 파일은 백업하고 빈 상태로 시작
                    os.replace(path, path + ".bak")
                except OSError:
                    pass

    def _apply_lib(self, data: dict) -> None:
        self._items = {i["id"]: i for i in data.get("items", [])}

    def _apply_folders(self, data: dict) -> None:
        self._folders = list(data.get("folders", []))

    def _save(self) -> None:
        self._atomic_write(self._lib_path(),
                           {"schema": SCHEMA_VERSION, "items": list(self._items.values())})
        self._atomic_write(self._folders_path(),
                           {"schema": SCHEMA_VERSION, "folders": self._folders})

    @staticmethod
    def _atomic_write(path: str, obj: dict) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ---------- 항목 ----------
    def new_asset_filename(self, ext: str) -> str:
        return uuid.uuid4().hex[:12] + ext

    def add_item(self, type_, name, keywords, source_kind, source_url,
                 filename, animated) -> dict:
        item = {
            "id": uuid.uuid4().hex[:12], "type": type_, "name": name,
            "keywords": list(keywords or []), "source_kind": source_kind,
            "source_url": source_url, "filename": filename,
            "animated": bool(animated), "added_at": _now(),
            "use_count": 0, "last_used": 0,
        }
        self._items[item["id"]] = item
        self._save()
        return item

    def get(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def remove_item(self, item_id: str) -> None:
        item = self._items.pop(item_id, None)
        if item:
            try:
                os.remove(os.path.join(self.assets_dir, item["filename"]))
            except OSError:
                pass
            self._save()

    def touch(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item:
            return  # 폴더 항목 등은 무시
        item["use_count"] += 1
        item["last_used"] = _now()
        self._save()

    def items(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda i: i["name"].lower())

    def recent(self, limit: int = 16) -> list[dict]:
        used = [i for i in self._items.values() if i["last_used"] > 0]
        return sorted(used, key=lambda i: i["last_used"], reverse=True)[:limit]

    def asset_path(self, item: dict) -> str:
        if item.get("abs_path"):
            return item["abs_path"]
        return os.path.join(self.assets_dir, item["filename"])

    # ---------- 폴더 ----------
    def add_folder(self, path: str, default_type: str = "gif") -> None:
        ap = os.path.abspath(path)
        if any(f["path"] == ap for f in self._folders):
            return
        self._folders.append({"path": ap, "default_type": default_type})
        self._save()

    def remove_folder(self, path: str) -> None:
        ap = os.path.abspath(path)
        self._folders = [f for f in self._folders if f["path"] != ap]
        self._scan_cache.pop(ap, None)
        self._save()

    def folders(self) -> list[dict]:
        return list(self._folders)

    def scan_folders(self) -> list[dict]:
        out: list[dict] = []
        for folder in self._folders:
            path, dtype = folder["path"], folder["default_type"]
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                continue  # 소실 폴더는 건너뜀 (UI 회색 처리는 folders()의 exists로)
            names = [n for n in entries
                     if os.path.splitext(n)[1].lower() in SUPPORTED_EXTS]
            sig = (self._dir_sig(path), tuple(names))
            cached = self._scan_cache.get(path)
            if cached and cached[0] == sig:
                out.extend(cached[1])
                continue
            items = []
            for n in names:
                ap = os.path.join(path, n)
                stem, ext = os.path.splitext(n)
                items.append({
                    "id": "folder:" + ap, "type": dtype, "name": stem,
                    "keywords": [], "source_kind": "folder", "source_url": "",
                    "filename": n, "abs_path": ap,
                    "animated": ext.lower() == ".gif",
                    "added_at": 0, "use_count": 0, "last_used": 0,
                })
            self._scan_cache[path] = (sig, items)
            out.extend(items)
        return out

    @staticmethod
    def _dir_sig(path: str) -> float:
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return 0

    def all_display_items(self) -> list[dict]:
        return self.items() + self.scan_folders()
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_library.py -q`
Expected: `10 passed`

- [ ] **Step 5: Commit**

```
git add clipshrink_app/library.py tests/test_library.py
git commit -m "feat: picker library store (items/folders JSON + asset cache)"
```

---

### Task 4: fetch.py — CDN 파싱·다운로드·APNG→GIF·등록 (TDD)

**Files:**
- Create: `clipshrink_app/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `Library.add_item / new_asset_filename / assets_dir` (Task 3)
- Produces:
  - `fetch.UnsupportedAssetError(Exception)` — Lottie(.json) 스티커
  - `fetch.parse_discord_url(url) -> ParsedAsset | None` — `ParsedAsset(kind: "emoji"|"sticker", asset_id: str, ext: str)`
  - `fetch.canonical_url(p: ParsedAsset) -> str` (항상 cdn.discordapp.com — 원본 바이트)
  - `fetch.download(url, dest_path, timeout=10)` (urllib, UA 헤더)
  - `fetch.is_apng(path) -> bool`, `fetch.apng_to_gif(src, dest)`
  - `fetch.sniff_animated(path) -> bool`
  - `fetch.register_from_url(library, url, name="", keywords=None) -> dict` — `ValueError`(비 디스코드 URL) / `UnsupportedAssetError` / `OSError`(다운로드 실패) 전파
  - `fetch.register_from_file(library, src_path, type_, name="", keywords=None) -> dict`
  - `fetch.ACCEPT_FILE_EXTS = (".png", ".gif", ".webp", ".jpg", ".jpeg")`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_fetch.py`:

```python
"""fetch: URL 파싱·APNG 처리·등록 파이프라인 (다운로드는 monkeypatch)."""
import io
import os

import pytest
from PIL import Image

from clipshrink_app import fetch
from clipshrink_app.library import Library


# ---------- 픽스처 ----------
def png_bytes():
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def apng_bytes():
    f1 = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    f2 = Image.new("RGBA", (8, 8), (0, 0, 255, 255))
    buf = io.BytesIO()
    f1.save(buf, format="PNG", save_all=True, append_images=[f2],
            duration=100, loop=0)
    return buf.getvalue()


def gif_bytes():
    f1 = Image.new("P", (8, 8), 0)
    f2 = Image.new("P", (8, 8), 1)
    buf = io.BytesIO()
    f1.save(buf, format="GIF", save_all=True, append_images=[f2], duration=80)
    return buf.getvalue()


# ---------- URL 파싱 ----------
def test_parse_emoji_urls():
    for url in (
        "https://cdn.discordapp.com/emojis/123456789.png",
        "https://media.discordapp.net/emojis/123456789.gif?size=48&quality=lossless",
        "https://cdn.discordapp.com/emojis/123456789.webp?size=96",
    ):
        p = fetch.parse_discord_url(url)
        assert p and p.kind == "emoji" and p.asset_id == "123456789"


def test_parse_sticker_url_and_canonical():
    p = fetch.parse_discord_url(
        "https://media.discordapp.net/stickers/987.png?size=160")
    assert p and p.kind == "sticker" and p.ext == "png"
    assert fetch.canonical_url(p) == "https://cdn.discordapp.com/stickers/987.png"


def test_parse_lottie_sticker_raises():
    with pytest.raises(fetch.UnsupportedAssetError):
        fetch.parse_discord_url("https://cdn.discordapp.com/stickers/55.json")


def test_parse_non_discord_returns_none():
    assert fetch.parse_discord_url("https://example.com/emojis/1.png") is None
    assert fetch.parse_discord_url("not a url") is None


def test_canonical_url_emoji_strips_query():
    p = fetch.parse_discord_url("https://media.discordapp.net/emojis/42.gif?size=48")
    assert fetch.canonical_url(p) == "https://cdn.discordapp.com/emojis/42.gif"


# ---------- APNG ----------
def test_is_apng_detects(tmp_path):
    a = tmp_path / "a.png"; a.write_bytes(apng_bytes())
    s = tmp_path / "s.png"; s.write_bytes(png_bytes())
    assert fetch.is_apng(str(a)) is True
    assert fetch.is_apng(str(s)) is False


def test_apng_to_gif_animated_output(tmp_path):
    src = tmp_path / "a.png"; src.write_bytes(apng_bytes())
    dest = tmp_path / "a.gif"
    fetch.apng_to_gif(str(src), str(dest))
    with Image.open(dest) as im:
        assert im.format == "GIF" and getattr(im, "n_frames", 1) > 1


# ---------- 등록 ----------
def fake_download(payload):
    def _dl(url, dest, timeout=10):
        with open(dest, "wb") as f:
            f.write(payload)
    return _dl


def test_register_from_url_emoji(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monkeypatch.setattr(fetch, "download", fake_download(png_bytes()))
    item = fetch.register_from_url(lib, "https://cdn.discordapp.com/emojis/1.png",
                                   name="wave", keywords=["hi"])
    assert item["type"] == "emoji" and item["animated"] is False
    assert item["source_kind"] == "discord-cdn"
    assert os.path.exists(lib.asset_path(item))


def test_register_from_url_apng_sticker_becomes_gif(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monkeypatch.setattr(fetch, "download", fake_download(apng_bytes()))
    item = fetch.register_from_url(lib, "https://cdn.discordapp.com/stickers/9.png")
    assert item["type"] == "sticker" and item["animated"] is True
    assert item["filename"].endswith(".gif")
    with Image.open(lib.asset_path(item)) as im:
        assert im.format == "GIF" and im.n_frames > 1


def test_register_from_url_rejects_non_discord(tmp_path):
    lib = Library(str(tmp_path / "d"))
    with pytest.raises(ValueError):
        fetch.register_from_url(lib, "https://example.com/x.png")


def test_register_from_file_copies_and_detects(tmp_path):
    lib = Library(str(tmp_path / "d"))
    src = tmp_path / "z.gif"; src.write_bytes(gif_bytes())
    item = fetch.register_from_file(lib, str(src), "gif")
    assert item["animated"] is True and item["name"] == "z"
    assert os.path.exists(lib.asset_path(item))
    assert src.exists()  # 원본 보존


def test_register_from_file_rejects_unknown_ext(tmp_path):
    lib = Library(str(tmp_path / "d"))
    bad = tmp_path / "x.txt"; bad.write_text("no")
    with pytest.raises(ValueError):
        fetch.register_from_file(lib, str(bad), "gif")
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_fetch.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현**

`clipshrink_app/fetch.py`:

```python
# -*- coding: utf-8 -*-
"""디스코드 CDN 자산: URL 파싱·다운로드·APNG→GIF 변환·라이브러리 등록."""
from __future__ import annotations

import os
import re
import shutil
import urllib.request
from dataclasses import dataclass

from PIL import Image, ImageSequence

from . import __version__

# 디스코드가 업로드된 APNG를 재생하지 않으므로 GIF로 변환해 저장한다.
EMOJI_RE = re.compile(
    r"(?:cdn|media)\.discordapp\.(?:com|net)/emojis/(\d+)\.(png|gif|webp)", re.I)
STICKER_RE = re.compile(
    r"(?:cdn|media)\.discordapp\.(?:com|net)/stickers/(\d+)\.(png|gif|json)", re.I)

ACCEPT_FILE_EXTS = (".png", ".gif", ".webp", ".jpg", ".jpeg")


class UnsupportedAssetError(Exception):
    """Lottie(.json) 스티커 등 지원 불가 자산."""


@dataclass
class ParsedAsset:
    kind: str      # "emoji" | "sticker"
    asset_id: str
    ext: str       # 소문자, 점 없음


def parse_discord_url(url: str) -> ParsedAsset | None:
    m = EMOJI_RE.search(url)
    if m:
        return ParsedAsset("emoji", m.group(1), m.group(2).lower())
    m = STICKER_RE.search(url)
    if m:
        ext = m.group(2).lower()
        if ext == "json":
            raise UnsupportedAssetError("lottie")
        return ParsedAsset("sticker", m.group(1), ext)
    return None


def canonical_url(p: ParsedAsset) -> str:
    """쿼리 파라미터를 제거한 원본 바이트 URL (cdn 호스트 고정)."""
    kind_path = "emojis" if p.kind == "emoji" else "stickers"
    return f"https://cdn.discordapp.com/{kind_path}/{p.asset_id}.{p.ext}"


def download(url: str, dest_path: str, timeout: int = 10) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": f"ClipShrink/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r, \
            open(dest_path, "wb") as f:
        shutil.copyfileobj(r, f)


def is_apng(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return im.format == "PNG" and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


def sniff_animated(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return bool(getattr(im, "is_animated", False))
    except Exception:
        return False


def apng_to_gif(src: str, dest: str) -> None:
    """APNG → GIF. GIF 투명도는 1비트라 알파<128은 완전 투명 처리."""
    with Image.open(src) as im:
        frames, durations = [], []
        for frame in ImageSequence.Iterator(im):
            f = frame.convert("RGBA")
            alpha = f.getchannel("A")
            p = f.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            mask = alpha.point(lambda a: 255 if a < 128 else 0)
            p.paste(255, mask)
            frames.append(p)
            durations.append(int(frame.info.get("duration", 50)) or 50)
    frames[0].save(dest, format="GIF", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=2, transparency=255)


def _finalize_asset(library, tmp_path: str, ext: str):
    """APNG면 GIF로 변환해 저장, 아니면 그대로. (최종 파일명, animated) 반환."""
    if ext == ".png" and is_apng(tmp_path):
        filename = library.new_asset_filename(".gif")
        apng_to_gif(tmp_path, os.path.join(library.assets_dir, filename))
        os.remove(tmp_path)
        return filename, True
    filename = library.new_asset_filename(ext)
    os.replace(tmp_path, os.path.join(library.assets_dir, filename))
    final = os.path.join(library.assets_dir, filename)
    return filename, ext == ".gif" or sniff_animated(final)


def register_from_url(library, url: str, name: str = "", keywords=None) -> dict:
    p = parse_discord_url(url)
    if p is None:
        raise ValueError("not a discord asset url")
    ext = "." + p.ext
    tmp = os.path.join(library.assets_dir, "_dl" + library.new_asset_filename(ext))
    download(canonical_url(p), tmp)
    try:
        filename, animated = _finalize_asset(library, tmp, ext)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    type_ = "emoji" if p.kind == "emoji" else "sticker"
    return library.add_item(type_, name or p.asset_id, keywords or [],
                            "discord-cdn", canonical_url(p), filename, animated)


def register_from_file(library, src_path: str, type_: str,
                       name: str = "", keywords=None) -> dict:
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in ACCEPT_FILE_EXTS:
        raise ValueError(f"unsupported extension: {ext}")
    tmp = os.path.join(library.assets_dir, "_cp" + library.new_asset_filename(ext))
    shutil.copyfile(src_path, tmp)
    try:
        filename, animated = _finalize_asset(library, tmp, ext)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    return library.add_item(type_, name or stem, keywords or [],
                            "local", "", filename, animated)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_fetch.py -q`
Expected: `13 passed`

- [ ] **Step 5: 전체 테스트**

Run: `python -m pytest -q`
Expected: 전부 통과

- [ ] **Step 6: Commit**

```
git add clipshrink_app/fetch.py tests/test_fetch.py
git commit -m "feat: discord CDN asset fetch — url parse, APNG→GIF, library registration"
```

---

### Task 5: clipboard_win 확장 — 텍스트 클립보드·포커스 복귀·Ctrl+V 시뮬 + 초과분 압축 준비

**Files:**
- Modify: `clipshrink_app/clipboard_win.py`, `clipshrink_app/picker/window.py`
- Test: `tests/test_clipboard_data.py` (순수 부분), 나머지는 Task 7 수동 검증에 포함

**Interfaces (Produces):**
- `clipboard_win.CF_UNICODETEXT = 13`, `set_clipboard_text(text) -> bool` (마커 포함)
- `clipboard_win.get_foreground_window() -> int` (Task 2에서 추가됨), `focus_window(hwnd) -> bool`, `send_ctrl_v()`
- `picker.window.prepare_for_paste(path, limit_bytes, temp_dir) -> tuple[str, bool]` — (붙여넣을 경로, 한도 초과 경고 여부). 정지 이미지 초과분은 압축, GIF 초과분은 경고만 (스펙 §6.7/§7)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_clipboard_data.py`:

```python
"""클립보드 순수 데이터 빌더 + 붙여넣기 전처리 테스트 (Win32 호출 없음)."""
import io
import struct

from PIL import Image

from clipshrink_app.clipboard_win import build_drop_data
from clipshrink_app.picker.window import prepare_for_paste


def test_build_drop_data_layout():
    data = build_drop_data(r"C:\x\y.gif")
    # DROPFILES: pFiles=20, fWide=1
    pfiles, _, _, _, fwide = struct.unpack_from("<Iiiii", data)
    assert pfiles == 20 and fwide == 1
    body = data[20:].decode("utf-16-le")
    assert body == "C:\\x\\y.gif\0\0"


def test_prepare_small_file_passthrough(tmp_path):
    p = tmp_path / "s.png"
    Image.new("RGB", (8, 8)).save(p)
    path, warn = prepare_for_paste(str(p), 10_000_000, str(tmp_path))
    assert path == str(p) and warn is False


def test_prepare_oversize_static_gets_compressed(tmp_path):
    import random
    p = tmp_path / "big.png"
    img = Image.new("RGB", (900, 900))
    img.putdata([(random.randint(0, 255),) * 3 for _ in range(900 * 900)])
    img.save(p)
    limit = p.stat().st_size // 2
    path, warn = warn_path = prepare_for_paste(str(p), limit, str(tmp_path))
    import os
    assert warn is False and path != str(p)
    assert os.path.getsize(path) <= limit


def test_prepare_oversize_gif_warns_and_passes_through(tmp_path):
    frames = [Image.new("P", (64, 64), i % 4) for i in range(30)]
    p = tmp_path / "big.gif"
    frames[0].save(p, format="GIF", save_all=True, append_images=frames[1:])
    path, warn = prepare_for_paste(str(p), 10, str(tmp_path))  # 10바이트 한도
    assert path == str(p) and warn is True
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_clipboard_data.py -q`
Expected: FAIL (`ImportError: prepare_for_paste`)

- [ ] **Step 3: 구현**

`clipboard_win.py`에 추가:

```python
CF_UNICODETEXT = 13


def set_clipboard_text(text: str) -> bool:
    """URL 등 텍스트를 클립보드에 넣는다 (마커 포함 — Monitor 재처리 방지)."""
    data = text.encode("utf-16-le") + b"\0\0"
    if not _open_clipboard_retry():
        return False
    try:
        user32.EmptyClipboard()
        if not _global_put(CF_UNICODETEXT, data):
            return False
        _put_marker()
        return True
    finally:
        user32.CloseClipboard()


# ---------- 포커스 복귀 + 키 입력 시뮬 ----------
ULONG_PTR = ctypes.c_size_t
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_V = 0x56


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


def send_ctrl_v() -> None:
    """OS 수준 Ctrl+V 입력 (클라이언트 수정·계정 자동화 아님 — Win+. 패널과 동일 방식)."""
    seq = [(VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)]
    arr = (_INPUT * len(seq))()
    for i, (vk, flags) in enumerate(seq):
        arr[i].type = INPUT_KEYBOARD
        arr[i].u.ki = _KEYBDINPUT(vk, 0, flags, 0, 0)
    user32.SendInput(len(seq), arr, ctypes.sizeof(_INPUT))


def focus_window(hwnd: int) -> bool:
    """저장해 둔 창(디스코드)으로 포커스 복귀. AttachThreadInput 폴백 포함."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.GetForegroundWindow() == hwnd:
        return True
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.03)
    if user32.GetForegroundWindow() == hwnd:
        return True
    cur = kernel32.GetCurrentThreadId()
    target = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(cur, target, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        user32.AttachThreadInput(cur, target, False)
    time.sleep(0.03)
    return user32.GetForegroundWindow() == hwnd
```

`picker/window.py`에 추가 (모듈 함수 — Win32 무관, 테스트 가능):

```python
def prepare_for_paste(path: str, limit_bytes: int, temp_dir: str) -> tuple[str, bool]:
    """한도 초과 항목 전처리 (스펙 §6.7/§7).
    정지 이미지: 기존 압축 파이프라인으로 한도 내 재인코딩.
    GIF(애니메이션): 재압축 품질 저하가 커서 그대로 두고 경고만."""
    import os
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
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_clipboard_data.py -q`
Expected: `4 passed`

- [ ] **Step 5: 수동 검증 (텍스트/포커스/키 시뮬)**

Python REPL에서:
```
python -c "from clipshrink_app import clipboard_win as cb; import time; time.sleep(3); cb.set_clipboard_text('https://example.com'); cb.send_ctrl_v()"
```
실행 후 3초 안에 메모장 포커스 → URL이 자동 붙여넣기되면 성공.

- [ ] **Step 6: Commit**

```
git add clipshrink_app/clipboard_win.py clipshrink_app/picker/window.py tests/test_clipboard_data.py
git commit -m "feat: clipboard text setter, focus-return + SendInput Ctrl+V, oversize paste preparation"
```

---

### Task 6: 피커 UI — 디스코드 다크테마 HTML/CSS/JS (전체 구현)

**Files:**
- Modify: `clipshrink_app/picker/ui/index.html`, `ui/app.css`, `ui/app.js` (스켈레톤 전면 교체)
- Test: 브라우저 단독 mock 모드 수동 확인 (pywebview 부재 시 샘플 데이터)

**Interfaces:**
- Consumes (Task 7의 PickerApi와 계약): `pywebview.api.get_state()`, `.select_item(id, mode)`, `.register_url(url, name, keywords)`, `.register_files(paths, type)`, `.add_folder(type)`, `.remove_folder(path)`, `.remove_item(id)`, `.hide()`
- `get_state()` 반환 계약: `{items: [{id,type,name,keywords,animated,url,can_url,is_folder}], recent: [id], folders: [{path,default_type,exists}], strings: {key: str}}`
- Produces: `window.__onShow()` (Python이 표시 시 호출 — 검색 리셋+포커스+refresh)

- [ ] **Step 1: index.html 전체 교체**

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ClipShrink Picker</title>
<link rel="stylesheet" href="app.css">
</head>
<body>
<div id="app">
  <header>
    <input id="search" type="text" autocomplete="off" spellcheck="false">
    <button id="btn-add" class="iconbtn" title="+">＋</button>
    <button id="btn-settings" class="iconbtn" title="settings">⚙</button>
  </header>
  <nav id="tabs">
    <button class="tab active" data-tab="emoji"></button>
    <button class="tab" data-tab="sticker"></button>
    <button class="tab" data-tab="gif"></button>
  </nav>
  <main id="content"></main>
  <footer id="hint"></footer>
</div>

<div id="ctx" class="hidden"></div>

<div id="modal-add" class="modal hidden">
  <div class="modal-box">
    <h3 id="add-title"></h3>
    <input id="add-url" type="text" spellcheck="false">
    <input id="add-name" type="text" spellcheck="false">
    <input id="add-kw" type="text" spellcheck="false">
    <p id="add-note" class="note"></p>
    <p id="add-error" class="error hidden"></p>
    <div class="row">
      <button id="add-submit" class="primary"></button>
      <button id="add-cancel"></button>
    </div>
  </div>
</div>

<div id="modal-settings" class="modal hidden">
  <div class="modal-box">
    <h3 id="st-title"></h3>
    <div id="st-folders"></div>
    <div class="row">
      <button id="st-addfolder" class="primary"></button>
      <button id="st-close"></button>
    </div>
  </div>
</div>

<div id="dropzone" class="hidden"></div>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: app.css 전체 교체 (디스코드 다크테마 토큰)**

```css
/* 디스코드 다크테마 재현 — 자체 CSS (디스코드 자산 미사용) */
:root {
  --bg: #313338; --panel: #2b2d31; --input: #1e1f22;
  --text: #dbdee1; --muted: #949ba4; --accent: #5865f2;
  --hover: #35373c; --danger: #da373c; --radius: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; }
body {
  background: var(--bg); color: var(--text);
  font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif;
  font-size: 14px; user-select: none;
  border: 1px solid #232428; border-radius: 8px;
}
#app { display: flex; flex-direction: column; height: 100vh; }

header { display: flex; gap: 6px; padding: 10px 10px 6px; }
#search {
  flex: 1; background: var(--input); border: none; outline: none;
  color: var(--text); padding: 7px 10px; border-radius: var(--radius);
}
#search::placeholder { color: var(--muted); }
.iconbtn {
  width: 32px; background: var(--input); border: none; color: var(--muted);
  border-radius: var(--radius); cursor: pointer; font-size: 15px;
}
.iconbtn:hover { color: var(--text); background: var(--hover); }

#tabs { display: flex; gap: 4px; padding: 0 10px 6px; }
.tab {
  flex: 1; padding: 6px 0; border: none; cursor: pointer;
  background: transparent; color: var(--muted);
  border-radius: 6px; font-weight: 600;
}
.tab:hover { background: var(--hover); color: var(--text); }
.tab.active { background: var(--panel); color: var(--text); }

#content { flex: 1; overflow-y: auto; padding: 4px 10px 8px; }
#content h4 {
  color: var(--muted); font-size: 11px; text-transform: uppercase;
  letter-spacing: .3px; margin: 8px 2px 4px;
}
.grid { display: grid; gap: 4px; }
.grid.emoji { grid-template-columns: repeat(auto-fill, 40px); }
.grid.sticker, .grid.gif { grid-template-columns: repeat(auto-fill, 92px); }
.cell {
  border: none; background: transparent; padding: 2px; cursor: pointer;
  border-radius: 6px; position: relative;
}
.grid.emoji .cell { width: 40px; height: 40px; }
.grid.sticker .cell, .grid.gif .cell { width: 92px; height: 92px; }
.cell img {
  width: 100%; height: 100%; object-fit: contain; pointer-events: none;
  content-visibility: auto;
}
.cell:hover { background: var(--hover); transform: scale(1.08); }
.empty { color: var(--muted); text-align: center; padding: 24px 8px; }

footer {
  padding: 6px 10px; background: var(--panel); color: var(--muted);
  font-size: 11px; border-radius: 0 0 8px 8px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: #1e1f22; border-radius: 4px; }
::-webkit-scrollbar-track { background: transparent; }

#ctx {
  position: fixed; z-index: 30; background: #111214; border-radius: 6px;
  padding: 4px; min-width: 150px; box-shadow: 0 6px 16px rgba(0,0,0,.5);
}
#ctx button {
  display: block; width: 100%; text-align: left; border: none;
  background: transparent; color: var(--text); padding: 6px 8px;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
#ctx button:hover { background: var(--accent); color: #fff; }
#ctx button.danger:hover { background: var(--danger); }

.modal {
  position: fixed; inset: 0; z-index: 20; background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--bg); border-radius: var(--radius); padding: 14px;
  width: 360px; display: flex; flex-direction: column; gap: 8px;
}
.modal-box h3 { font-size: 15px; }
.modal-box input {
  background: var(--input); border: none; outline: none; color: var(--text);
  padding: 8px 10px; border-radius: 6px; width: 100%;
}
.note { color: var(--muted); font-size: 11.5px; }
.error { color: #fa777c; font-size: 12px; }
.row { display: flex; gap: 6px; justify-content: flex-end; margin-top: 4px; }
.row button {
  border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer;
  background: var(--hover); color: var(--text);
}
.row button.primary { background: var(--accent); color: #fff; }
#st-folders { max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.folder-row {
  display: flex; align-items: center; gap: 6px; background: var(--panel);
  padding: 6px 8px; border-radius: 6px; font-size: 12px;
}
.folder-row.missing { opacity: .45; }
.folder-row span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; }
.folder-row button { border: none; background: transparent; color: var(--muted); cursor: pointer; }
.folder-row button:hover { color: var(--danger); }
.hidden { display: none !important; }

#dropzone {
  position: fixed; inset: 6px; z-index: 40; border: 2px dashed var(--accent);
  border-radius: 10px; background: rgba(88,101,242,.12);
  display: flex; align-items: center; justify-content: center;
  color: var(--text); font-weight: 600; pointer-events: none;
}
</style-guard-not-used
```

주의: 마지막 줄 `</style-guard-not-used`는 오타 방지용 표식이 아니라 **넣지 말 것** — 파일은 `#dropzone { ... }` 블록까지로 끝난다.

- [ ] **Step 3: app.js 전체 교체**

```js
/* ClipShrink Picker UI. pywebview 부재 시(mock) 브라우저 단독 미리보기 지원. */
const $ = (s) => document.querySelector(s);
const state = { items: [], recent: [], folders: [], strings: {}, tab: "emoji", query: "" };
let ctxItem = null;

const str = (k) => state.strings[k] || k;
const api = () => window.pywebview && window.pywebview.api;

/* ---------- 데이터 ---------- */
async function refresh() {
  if (!api()) { mock(); applyStrings(); render(); return; }
  const s = await api().get_state();
  Object.assign(state, { items: s.items, recent: s.recent, folders: s.folders, strings: s.strings });
  applyStrings(); render(); renderFolders();
}

function mock() {
  const sq = (c) => "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' rx='12' fill='${c}'/></svg>`);
  state.items = [
    { id: "1", type: "emoji", name: "smile", keywords: ["happy"], animated: false, url: sq("#f9a62b"), can_url: true, is_folder: false },
    { id: "2", type: "sticker", name: "cat", keywords: [], animated: false, url: sq("#57f287"), can_url: false, is_folder: false },
    { id: "3", type: "gif", name: "dance", keywords: [], animated: true, url: sq("#5865f2"), can_url: false, is_folder: true },
  ];
  state.recent = ["1"];
  state.strings = {};
}

/* ---------- 렌더 ---------- */
function applyStrings() {
  $("#search").placeholder = str("picker_search");
  document.querySelectorAll(".tab").forEach((b) => {
    b.textContent = str("picker_tab_" + b.dataset.tab);
  });
  $("#hint").textContent = str("picker_hint");
  $("#add-title").textContent = str("picker_add_title");
  $("#add-url").placeholder = str("picker_add_url_ph");
  $("#add-name").placeholder = str("picker_add_name_ph");
  $("#add-kw").placeholder = str("picker_add_kw_ph");
  $("#add-note").textContent = str("picker_add_note");
  $("#add-submit").textContent = str("picker_add_submit");
  $("#add-cancel").textContent = str("picker_cancel");
  $("#st-title").textContent = str("picker_folders_title");
  $("#st-addfolder").textContent = str("picker_add_folder");
  $("#st-close").textContent = str("picker_cancel");
  $("#dropzone").textContent = str("picker_drop_hint");
}

function filtered() {
  const q = state.query.trim().toLowerCase();
  return state.items.filter((i) => i.type === state.tab &&
    (!q || i.name.toLowerCase().includes(q) ||
      i.keywords.some((k) => k.toLowerCase().includes(q))));
}

function render() {
  const c = $("#content");
  c.innerHTML = "";
  const items = filtered();
  if (!state.query) {
    const rset = new Set(state.recent);
    const rec = items.filter((i) => rset.has(i.id));
    if (rec.length) c.appendChild(section(str("picker_recent"), rec.slice(0, 16)));
  }
  if (!items.length) {
    const d = document.createElement("div");
    d.className = "empty";
    d.textContent = str("picker_empty");
    c.appendChild(d);
    return;
  }
  c.appendChild(section("", items));
}

function section(title, items) {
  const wrap = document.createElement("div");
  if (title) {
    const h = document.createElement("h4");
    h.textContent = title;
    wrap.appendChild(h);
  }
  const g = document.createElement("div");
  g.className = "grid " + state.tab;
  for (const item of items) {
    const b = document.createElement("button");
    b.className = "cell";
    b.title = item.name;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = item.url;
    b.appendChild(img);
    b.addEventListener("click", () => select(item, "file"));
    b.addEventListener("contextmenu", (e) => { e.preventDefault(); showCtx(e, item); });
    g.appendChild(b);
  }
  wrap.appendChild(g);
  return wrap;
}

function select(item, mode) {
  if (api()) api().select_item(item.id, mode);
}

/* ---------- 컨텍스트 메뉴 ---------- */
function showCtx(e, item) {
  ctxItem = item;
  const ctx = $("#ctx");
  ctx.innerHTML = "";
  const add = (label, fn, danger) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (danger) b.className = "danger";
    b.addEventListener("click", () => { hideCtx(); fn(); });
    ctx.appendChild(b);
  };
  add(str("picker_ctx_file"), () => select(item, "file"));
  if (item.can_url) add(str("picker_ctx_url"), () => select(item, "url"));
  if (!item.is_folder)
    add(str("picker_ctx_delete"), async () => { await api().remove_item(item.id); refresh(); }, true);
  ctx.classList.remove("hidden");
  const x = Math.min(e.clientX, window.innerWidth - 160);
  const y = Math.min(e.clientY, window.innerHeight - ctx.offsetHeight - 8);
  ctx.style.left = x + "px";
  ctx.style.top = y + "px";
}
function hideCtx() { $("#ctx").classList.add("hidden"); ctxItem = null; }

/* ---------- 등록 모달 ---------- */
function openAdd() {
  $("#add-error").classList.add("hidden");
  $("#add-url").value = ""; $("#add-name").value = ""; $("#add-kw").value = "";
  $("#modal-add").classList.remove("hidden");
  $("#add-url").focus();
}
async function submitAdd() {
  const url = $("#add-url").value.trim();
  if (!url) return;
  const res = await api().register_url(url, $("#add-name").value.trim(), $("#add-kw").value.trim());
  if (res.ok) { $("#modal-add").classList.add("hidden"); refresh(); }
  else {
    const el = $("#add-error");
    el.textContent = str("picker_err_" + res.error);
    el.classList.remove("hidden");
  }
}

/* ---------- 폴더 설정 ---------- */
function renderFolders() {
  const box = $("#st-folders");
  box.innerHTML = "";
  for (const f of state.folders) {
    const row = document.createElement("div");
    row.className = "folder-row" + (f.exists ? "" : " missing");
    const span = document.createElement("span");
    span.textContent = f.path + " (" + str("picker_tab_" + f.default_type) + ")";
    span.title = f.path;
    const del = document.createElement("button");
    del.textContent = "✕";
    del.addEventListener("click", async () => { await api().remove_folder(f.path); refresh(); });
    row.appendChild(span); row.appendChild(del);
    box.appendChild(row);
  }
}

/* ---------- 이벤트 배선 ---------- */
$("#search").addEventListener("input", (e) => { state.query = e.target.value; render(); });
$("#search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { const first = filtered()[0]; if (first) select(first, "file"); }
});
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    b.classList.add("active");
    state.tab = b.dataset.tab;
    render();
  }));
$("#btn-add").addEventListener("click", openAdd);
$("#add-submit").addEventListener("click", submitAdd);
$("#add-cancel").addEventListener("click", () => $("#modal-add").classList.add("hidden"));
$("#btn-settings").addEventListener("click", () => $("#modal-settings").classList.remove("hidden"));
$("#st-close").addEventListener("click", () => $("#modal-settings").classList.add("hidden"));
$("#st-addfolder").addEventListener("click", async () => { await api().add_folder(state.tab); refresh(); });

document.addEventListener("click", (e) => { if (!$("#ctx").contains(e.target)) hideCtx(); });
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const modals = [$("#modal-add"), $("#modal-settings")];
  const open = modals.find((m) => !m.classList.contains("hidden"));
  if (open) { open.classList.add("hidden"); return; }
  if (!$("#ctx").classList.contains("hidden")) { hideCtx(); return; }
  if (api()) api().hide();
});
window.addEventListener("blur", () => { if (api()) api().hide(); });

/* ---------- 드래그앤드롭 (pywebviewFullPath) ---------- */
let dragDepth = 0;
window.addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; $("#dropzone").classList.remove("hidden"); });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropzone").classList.add("hidden"); } });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", async (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("#dropzone").classList.add("hidden");
  if (!api()) return;
  const paths = [...e.dataTransfer.files].map((f) => f.pywebviewFullPath).filter(Boolean);
  if (paths.length) { await api().register_files(paths, state.tab); refresh(); }
});

/* ---------- 표시 훅 (Python이 호출) ---------- */
window.__onShow = () => {
  state.query = "";
  $("#search").value = "";
  hideCtx();
  refresh();
  setTimeout(() => $("#search").focus(), 30);
};

if (window.pywebview) refresh();
else window.addEventListener("pywebviewready", refresh);
if (!window.pywebview) setTimeout(refresh, 50); /* 브라우저 mock */
```

- [ ] **Step 4: 브라우저 mock 확인**

Run: `start clipshrink_app\picker\ui\index.html` (기본 브라우저)
Expected: 다크테마 UI, 탭 3개, mock 항목 표시, 검색 필터 동작, ＋/⚙ 모달 열림.

- [ ] **Step 5: Commit**

```
git add clipshrink_app/picker/ui
git commit -m "feat: picker UI — discord dark-theme grid with tabs/search/recent/context-menu/DnD"
```

---

### Task 7: PickerApi 브리지 + 선택 파이프라인 통합

**Files:**
- Modify: `clipshrink_app/picker/window.py` (PickerApi 완성, PickerController.select), `clipshrink_app/app.py` (배선)
- Test: `python -m pytest -q` 회귀 + 수동 e2e

**Interfaces:**
- Consumes: Task 3 `Library`, Task 4 `fetch`, Task 5 `clipboard_win.focus_window/send_ctrl_v/set_clipboard_text`, `prepare_for_paste`, Task 6 UI 계약
- Produces: `PickerController(library, api)` — `.select(item_id, mode)`, `.on_notify: callable(str)|None`; `PickerApi(library)` — Task 6 계약 전부

- [ ] **Step 1: window.py에 PickerApi 완성 (스켈레톤 교체)**

```python
import time
from pathlib import Path

from .. import config, fetch
from ..i18n import tr

PICKER_STRING_KEYS = [
    "picker_search", "picker_tab_emoji", "picker_tab_sticker", "picker_tab_gif",
    "picker_recent", "picker_empty", "picker_hint", "picker_add_title",
    "picker_add_url_ph", "picker_add_name_ph", "picker_add_kw_ph",
    "picker_add_note", "picker_add_submit", "picker_cancel",
    "picker_folders_title", "picker_add_folder", "picker_drop_hint",
    "picker_ctx_file", "picker_ctx_url", "picker_ctx_delete",
    "picker_err_lottie", "picker_err_not_discord", "picker_err_download",
]


class PickerApi:
    """JS 브리지. 각 메서드는 pywebview API 스레드에서 호출된다."""

    def __init__(self, library):
        self.library = library
        self.ctrl: "PickerController | None" = None

    def _display(self, item: dict) -> dict:
        return {
            "id": item["id"], "type": item["type"], "name": item["name"],
            "keywords": item["keywords"], "animated": item["animated"],
            "url": Path(self.library.asset_path(item)).as_uri(),
            "can_url": bool(item.get("source_url")),
            "is_folder": item["source_kind"] == "folder",
        }

    def get_state(self) -> dict:
        import os
        return {
            "items": [self._display(i) for i in self.library.all_display_items()],
            "recent": [i["id"] for i in self.library.recent()],
            "folders": [{**f, "exists": os.path.isdir(f["path"])}
                        for f in self.library.folders()],
            "strings": {k: tr(k) for k in PICKER_STRING_KEYS},
        }

    def select_item(self, item_id: str, mode: str = "file") -> bool:
        if self.ctrl:
            self.ctrl.select(item_id, mode)
        return True

    def register_url(self, url: str, name: str = "", keywords: str = "") -> dict:
        kws = [k.strip() for k in (keywords or "").replace(",", " ").split() if k.strip()]
        try:
            item = fetch.register_from_url(self.library, url, name, kws)
        except fetch.UnsupportedAssetError:
            return {"ok": False, "error": "lottie"}
        except ValueError:
            return {"ok": False, "error": "not_discord"}
        except Exception:
            return {"ok": False, "error": "download"}
        return {"ok": True, "item": self._display(item)}

    def register_files(self, paths, type_: str) -> dict:
        n = 0
        for p in paths or []:
            try:
                fetch.register_from_file(self.library, p, type_)
                n += 1
            except Exception:
                pass
        return {"ok": True, "count": n}

    def add_folder(self, default_type: str = "gif") -> dict:
        import webview
        res = self.ctrl.window.create_file_dialog(webview.FOLDER_DIALOG)
        if res:
            self.library.add_folder(res[0], default_type)
            return {"ok": True}
        return {"ok": False}

    def remove_folder(self, path: str) -> bool:
        self.library.remove_folder(path)
        return True

    def remove_item(self, item_id: str) -> bool:
        self.library.remove_item(item_id)
        return True

    def hide(self) -> bool:
        if self.ctrl:
            self.ctrl.hide()
        return True
```

- [ ] **Step 2: PickerController에 select 파이프라인 추가**

`PickerController.__init__`를 `def __init__(self, library, api=None)`로 확장(`self.library = library`, `self.on_notify = None`)하고 메서드 추가:

```python
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
            import time as _t
            _t.sleep(0.12)
            cb.send_ctrl_v()
            if warn:
                self._notify(tr("picker_oversize_warn"))
        elif ok:
            self._notify(tr("notify_paste_manual"))
        else:
            self._notify(tr("notify_clipboard_fail"))
        self.library.touch(item["id"])
```

필요 임포트를 window.py 상단에 추가: `from .. import config` (fetch/tr은 위 코드 블록 위치 참조).

- [ ] **Step 3: app.py 배선 갱신**

```python
    from .library import Library
    from .picker.window import PickerApi, PickerController

    library = Library(config.DATA_DIR)
    api = PickerApi(library)
    picker = PickerController(library, api=api)
    api.ctrl = picker
    listener = HotkeyListener(on_hotkey=picker.toggle)

    icon = tray.build_icon(monitor, on_quit_extra=lambda: (listener.stop(), picker.destroy()))
    picker.on_notify = lambda msg: icon.notify(msg, APP_NAME)
    picker.create_window()
    icon.run_detached()
    listener.start(get_setting_str("hotkey", "ctrl+shift+e"))
```

- [ ] **Step 4: 회귀 테스트**

Run: `python -m pytest -q`
Expected: 전부 통과 (i18n 신규 키는 Task 8에서 — 이 시점 UI는 키 문자열 그대로 표시될 수 있음, 허용)

- [ ] **Step 5: 수동 e2e (핵심 확인)**

`python clipshrink.py` 실행 후:
1. 디스코드에서 이모지 우클릭 → 링크 복사 → 피커 ＋ → URL 붙여넣기 → 등록됨
2. 그리드에서 클릭 → 피커 닫힘 → 디스코드 입력창에 파일 첨부됨 → Enter로 전송
3. 우클릭 → 링크로 붙여넣기 → URL 텍스트가 입력창에 붙음
4. GIF 폴더 추가(⚙) → GIF 탭에 자동 표시 → 클릭 붙여넣기
5. 최근 사용 섹션에 방금 쓴 항목 등장

- [ ] **Step 6: Commit**

```
git add clipshrink_app/picker/window.py clipshrink_app/app.py
git commit -m "feat: picker JS bridge + select pipeline (clipboard, focus-return, auto Ctrl+V)"
```

---

### Task 8: 트레이 통합 + i18n 신규 키(5개 언어) + 핫키 변경 메뉴

**Files:**
- Modify: `clipshrink_app/i18n.py`, `clipshrink_app/tray.py`, `clipshrink_app/app.py`
- Test: `tests/test_i18n.py` (기존 키 패리티 테스트가 신규 키를 자동 검증) + 수동

**Interfaces:**
- Consumes: `hotkey.HOTKEY_CHOICES/HOTKEY_OFF/label_for`, `HotkeyListener.set_combo`, `PickerController.show_at_cursor/toggle`
- Produces: `tray.build_icon(monitor, picker=None, listener=None, on_quit_extra=None)`

- [ ] **Step 1: i18n 신규 키 30개 × 5개 언어**

`i18n.py`의 각 언어 dict에 아래 키들을 추가한다 (전체 내용 — 그대로 붙여넣기):

```python
_PICKER_STRINGS = {
    "en": {
        "picker_open": "Open emoji & sticker picker",
        "hotkey_menu": "Picker hotkey",
        "hotkey_off": "Disabled",
        "notify_hotkey_fail": "Couldn't register hotkey {combo} — another app may be using it. Pick another in the tray menu.",
        "notify_webview2_missing": "The picker needs Microsoft Edge WebView2 Runtime (built into Windows 11). Compression still works.",
        "notify_paste_manual": "Ready in the clipboard — press Ctrl+V in Discord.",
        "picker_oversize_warn": "This item exceeds the upload limit and was sent as-is — Discord may reject it.",
        "picker_search": "Search",
        "picker_tab_emoji": "Emoji",
        "picker_tab_sticker": "Stickers",
        "picker_tab_gif": "GIFs",
        "picker_recent": "Recently used",
        "picker_empty": "Nothing here yet — press + to add, or drop image files.",
        "picker_hint": "Click = paste · Enter = first result · Esc = close · Right-click = more",
        "picker_add_title": "Add from Discord link",
        "picker_add_url_ph": "Paste an emoji/sticker link (cdn.discordapp.com/…)",
        "picker_add_name_ph": "Name (optional)",
        "picker_add_kw_ph": "Search keywords (optional)",
        "picker_add_note": "In Discord: right-click an emoji → Copy Link. Stickers without a link: save the image and drop the file here.",
        "picker_add_submit": "Add",
        "picker_cancel": "Close",
        "picker_folders_title": "Watched folders",
        "picker_add_folder": "Add folder to current tab",
        "picker_drop_hint": "Drop to add to this tab",
        "picker_ctx_file": "Paste as file",
        "picker_ctx_url": "Paste as link",
        "picker_ctx_delete": "Remove from library",
        "picker_err_lottie": "This is a Lottie sticker (.json) and can't be converted. Save it as an image and add the file instead.",
        "picker_err_not_discord": "That's not a Discord emoji/sticker link.",
        "picker_err_download": "Download failed — check the link or your connection.",
    },
    "ko": {
        "picker_open": "이모지·스티커 피커 열기",
        "hotkey_menu": "피커 단축키",
        "hotkey_off": "끄기",
        "notify_hotkey_fail": "단축키 {combo} 등록 실패 — 다른 앱이 사용 중일 수 있어요. 트레이 메뉴에서 다른 조합을 선택하세요.",
        "notify_webview2_missing": "피커에는 Microsoft Edge WebView2 런타임이 필요합니다(Windows 11 내장). 압축 기능은 계속 동작합니다.",
        "notify_paste_manual": "클립보드에 준비했습니다 — 디스코드에서 Ctrl+V 하세요.",
        "picker_oversize_warn": "업로드 한도를 넘는 항목이라 원본 그대로 보냈습니다 — 디스코드가 거부할 수 있어요.",
        "picker_search": "검색",
        "picker_tab_emoji": "이모지",
        "picker_tab_sticker": "스티커",
        "picker_tab_gif": "GIF",
        "picker_recent": "최근 사용",
        "picker_empty": "아직 비어 있어요 — ＋로 추가하거나 이미지 파일을 끌어다 놓으세요.",
        "picker_hint": "클릭=붙여넣기 · Enter=첫 항목 · Esc=닫기 · 우클릭=메뉴",
        "picker_add_title": "디스코드 링크로 추가",
        "picker_add_url_ph": "이모지/스티커 링크 붙여넣기 (cdn.discordapp.com/…)",
        "picker_add_name_ph": "이름 (선택)",
        "picker_add_kw_ph": "검색 키워드 (선택)",
        "picker_add_note": "디스코드에서 이모지 우클릭 → 링크 복사. 링크가 없는 스티커는 이미지를 저장해 여기로 끌어다 놓으세요.",
        "picker_add_submit": "추가",
        "picker_cancel": "닫기",
        "picker_folders_title": "감시 폴더",
        "picker_add_folder": "현재 탭에 폴더 추가",
        "picker_drop_hint": "놓으면 이 탭에 추가됩니다",
        "picker_ctx_file": "파일로 붙여넣기",
        "picker_ctx_url": "링크로 붙여넣기",
        "picker_ctx_delete": "라이브러리에서 삭제",
        "picker_err_lottie": "Lottie 스티커(.json)라서 변환할 수 없어요. 이미지로 저장한 뒤 파일로 추가해 주세요.",
        "picker_err_not_discord": "디스코드 이모지/스티커 링크가 아니에요.",
        "picker_err_download": "다운로드 실패 — 링크나 네트워크를 확인해 주세요.",
    },
    "ja": {
        "picker_open": "絵文字・スタンプピッカーを開く",
        "hotkey_menu": "ピッカーのホットキー",
        "hotkey_off": "無効",
        "notify_hotkey_fail": "ホットキー {combo} の登録に失敗しました — 他のアプリが使用中かもしれません。トレイメニューから別の組み合わせを選んでください。",
        "notify_webview2_missing": "ピッカーには Microsoft Edge WebView2 ランタイムが必要です（Windows 11 には内蔵）。圧縮機能は引き続き動作します。",
        "notify_paste_manual": "クリップボードに準備しました — Discord で Ctrl+V してください。",
        "picker_oversize_warn": "アップロード上限を超えるためそのまま送信しました — Discord に拒否される場合があります。",
        "picker_search": "検索",
        "picker_tab_emoji": "絵文字",
        "picker_tab_sticker": "スタンプ",
        "picker_tab_gif": "GIF",
        "picker_recent": "最近使用",
        "picker_empty": "まだ空です — ＋で追加するか、画像ファイルをドロップしてください。",
        "picker_hint": "クリック=貼り付け · Enter=先頭 · Esc=閉じる · 右クリック=メニュー",
        "picker_add_title": "Discord リンクから追加",
        "picker_add_url_ph": "絵文字/スタンプのリンクを貼り付け (cdn.discordapp.com/…)",
        "picker_add_name_ph": "名前（任意）",
        "picker_add_kw_ph": "検索キーワード（任意）",
        "picker_add_note": "Discord で絵文字を右クリック → リンクをコピー。リンクのないスタンプは画像を保存してここにドロップしてください。",
        "picker_add_submit": "追加",
        "picker_cancel": "閉じる",
        "picker_folders_title": "監視フォルダー",
        "picker_add_folder": "現在のタブにフォルダーを追加",
        "picker_drop_hint": "ドロップでこのタブに追加",
        "picker_ctx_file": "ファイルとして貼り付け",
        "picker_ctx_url": "リンクとして貼り付け",
        "picker_ctx_delete": "ライブラリから削除",
        "picker_err_lottie": "Lottie スタンプ（.json）のため変換できません。画像として保存してから追加してください。",
        "picker_err_not_discord": "Discord の絵文字/スタンプのリンクではありません。",
        "picker_err_download": "ダウンロードに失敗しました — リンクまたはネットワークを確認してください。",
    },
    "zh": {
        "picker_open": "打开表情·贴纸选择器",
        "hotkey_menu": "选择器快捷键",
        "hotkey_off": "禁用",
        "notify_hotkey_fail": "快捷键 {combo} 注册失败 — 可能被其他程序占用。请在托盘菜单中选择其他组合。",
        "notify_webview2_missing": "选择器需要 Microsoft Edge WebView2 运行时（Windows 11 已内置）。压缩功能仍可使用。",
        "notify_paste_manual": "已放入剪贴板 — 请在 Discord 中按 Ctrl+V。",
        "picker_oversize_warn": "该项目超过上传限制，已按原样发送 — Discord 可能会拒绝。",
        "picker_search": "搜索",
        "picker_tab_emoji": "表情",
        "picker_tab_sticker": "贴纸",
        "picker_tab_gif": "GIF",
        "picker_recent": "最近使用",
        "picker_empty": "这里还是空的 — 点 ＋ 添加，或拖入图片文件。",
        "picker_hint": "点击=粘贴 · Enter=第一项 · Esc=关闭 · 右键=菜单",
        "picker_add_title": "通过 Discord 链接添加",
        "picker_add_url_ph": "粘贴表情/贴纸链接 (cdn.discordapp.com/…)",
        "picker_add_name_ph": "名称（可选）",
        "picker_add_kw_ph": "搜索关键词（可选）",
        "picker_add_note": "在 Discord 中右键表情 → 复制链接。没有链接的贴纸请保存图片后拖到这里。",
        "picker_add_submit": "添加",
        "picker_cancel": "关闭",
        "picker_folders_title": "监视文件夹",
        "picker_add_folder": "为当前标签添加文件夹",
        "picker_drop_hint": "松开即添加到此标签",
        "picker_ctx_file": "作为文件粘贴",
        "picker_ctx_url": "作为链接粘贴",
        "picker_ctx_delete": "从库中删除",
        "picker_err_lottie": "这是 Lottie 贴纸（.json），无法转换。请先保存为图片再添加。",
        "picker_err_not_discord": "这不是 Discord 表情/贴纸链接。",
        "picker_err_download": "下载失败 — 请检查链接或网络。",
    },
    "es": {
        "picker_open": "Abrir selector de emojis y stickers",
        "hotkey_menu": "Atajo del selector",
        "hotkey_off": "Desactivado",
        "notify_hotkey_fail": "No se pudo registrar el atajo {combo}: otra aplicación puede estar usándolo. Elige otro en el menú de la bandeja.",
        "notify_webview2_missing": "El selector necesita Microsoft Edge WebView2 Runtime (incluido en Windows 11). La compresión sigue funcionando.",
        "notify_paste_manual": "Listo en el portapapeles — pulsa Ctrl+V en Discord.",
        "picker_oversize_warn": "Este elemento supera el límite de subida y se envió tal cual — Discord podría rechazarlo.",
        "picker_search": "Buscar",
        "picker_tab_emoji": "Emojis",
        "picker_tab_sticker": "Stickers",
        "picker_tab_gif": "GIF",
        "picker_recent": "Usados recientemente",
        "picker_empty": "Aún no hay nada — pulsa ＋ para añadir o suelta archivos de imagen.",
        "picker_hint": "Clic=pegar · Enter=primero · Esc=cerrar · Clic derecho=menú",
        "picker_add_title": "Añadir desde enlace de Discord",
        "picker_add_url_ph": "Pega un enlace de emoji/sticker (cdn.discordapp.com/…)",
        "picker_add_name_ph": "Nombre (opcional)",
        "picker_add_kw_ph": "Palabras clave (opcional)",
        "picker_add_note": "En Discord: clic derecho en un emoji → Copiar enlace. Para stickers sin enlace, guarda la imagen y suéltala aquí.",
        "picker_add_submit": "Añadir",
        "picker_cancel": "Cerrar",
        "picker_folders_title": "Carpetas vigiladas",
        "picker_add_folder": "Añadir carpeta a esta pestaña",
        "picker_drop_hint": "Suelta para añadir a esta pestaña",
        "picker_ctx_file": "Pegar como archivo",
        "picker_ctx_url": "Pegar como enlace",
        "picker_ctx_delete": "Eliminar de la biblioteca",
        "picker_err_lottie": "Es un sticker Lottie (.json) y no se puede convertir. Guárdalo como imagen y añádelo como archivo.",
        "picker_err_not_discord": "No es un enlace de emoji/sticker de Discord.",
        "picker_err_download": "Error de descarga — comprueba el enlace o tu conexión.",
    },
}

for _lang, _table in _PICKER_STRINGS.items():
    STRINGS[_lang].update(_table)
del _PICKER_STRINGS
```

- [ ] **Step 2: 키 패리티 테스트 통과 확인**

Run: `python -m pytest tests/test_i18n.py -q`
Expected: `7 passed` (`test_all_languages_have_same_keys`가 신규 키 검증)

- [ ] **Step 3: 트레이 메뉴 확장**

`tray.py`의 `build_icon` 시그니처를 `build_icon(monitor, picker=None, listener=None, on_quit_extra=None)`로 확장하고, 메뉴 상단에 피커 항목·핫키 서브메뉴 추가:

```python
from .hotkey import HOTKEY_CHOICES, HOTKEY_OFF, label_for
from .config import get_setting_str, set_setting_str

    # build_icon 내부:
    def on_open_picker(icon, item):
        if picker:
            picker.show_at_cursor()

    def make_hotkey_item(key):
        def on_select(icon, item):
            set_setting_str("hotkey", key)
            if listener:
                listener.set_combo(key)
        label = (lambda item: tr("hotkey_off")) if key == HOTKEY_OFF else HOTKEY_CHOICES[key][2]
        return pystray.MenuItem(
            label, on_select,
            checked=lambda item, key=key: get_setting_str("hotkey", "ctrl+shift+e") == key,
            radio=True,
        )

    hotkey_menu = pystray.Menu(
        *[make_hotkey_item(k) for k in HOTKEY_CHOICES],
        make_hotkey_item(HOTKEY_OFF),
    )

    picker_items = []
    if picker is not None:
        picker_items = [
            pystray.MenuItem(lambda item: tr("picker_open"), on_open_picker, default=False),
            pystray.MenuItem(lambda item: tr("hotkey_menu"), hotkey_menu),
            pystray.Menu.SEPARATOR,
        ]
    # 기존 메뉴 앞에 *picker_items 삽입:
    # menu=pystray.Menu(*picker_items, <기존 항목들…>)
```

- [ ] **Step 4: app.py — 핫키 등록 실패 알림 + WebView2 부재 알림 i18n화**

```python
    icon = tray.build_icon(monitor, picker=picker, listener=listener,
                           on_quit_extra=lambda: (listener.stop(), picker.destroy()))
    listener.on_register_fail = lambda label: icon.notify(
        tr("notify_hotkey_fail", combo=label), APP_NAME)
```

WebView2 부재 분기의 임시 영어 리터럴을 `tr("notify_webview2_missing")`로 교체.

- [ ] **Step 5: 전체 테스트 + 수동 확인**

Run: `python -m pytest -q` → 전부 통과.
수동: 트레이에 "이모지·스티커 피커 열기"/"피커 단축키" 표시(한국어), 핫키를 Ctrl+Alt+E로 바꾸면 즉시 반영, 언어를 English로 바꾸면 피커 문자열도 영어로.

- [ ] **Step 6: Commit**

```
git add clipshrink_app/i18n.py clipshrink_app/tray.py clipshrink_app/app.py
git commit -m "feat: tray picker menu, hotkey switcher, 30 new i18n keys in all 5 languages"
```

---

### Task 9: 빌드·배포 갱신 + 문서 + v2.0.0

**Files:**
- Modify: `requirements.txt`, `build.bat`, `.github/workflows/release.yml`, `clipshrink_app/__init__.py`, `CHANGELOG.md`, `README.md`, `README.ko.md`

- [ ] **Step 1: 버전 v2.0.0**

`clipshrink_app/__init__.py`: `__version__ = "2.0.0"`.

- [ ] **Step 2: 빌드 스크립트/워크플로에 UI 자산 + pywebview 포함**

`build.bat`의 pyinstaller 줄 교체:

```
pyinstaller --onefile --noconsole --name ClipShrink --clean ^
  --add-data "clipshrink_app\picker\ui;clipshrink_app/picker/ui" ^
  --collect-all webview clipshrink.py || goto :error
```

주의: `--add-data`의 목적지 구분자는 Windows에서 `;`, 목적지 경로는 `clipshrink_app/picker/ui` (ui_index_path()가 `sys._MEIPASS/clipshrink_app/picker/ui/index.html`을 찾음).

`.github/workflows/release.yml`의 Build EXE 스텝도 동일 플래그로 교체:

```yaml
      - name: Build EXE
        run: pyinstaller --onefile --noconsole --name ClipShrink --clean --add-data "clipshrink_app\picker\ui;clipshrink_app/picker/ui" --collect-all webview clipshrink.py
```

`build.bat`의 pip 줄: `pip install --upgrade pyinstaller -r requirements.txt`로 교체 (pywebview 포함).

- [ ] **Step 3: 로컬 빌드 + exe 스모크**

Run: `build.bat`
Expected: `dist\ClipShrink.exe` 생성. 실행 → 트레이 + 핫키 + 피커(등록·붙여넣기) 동작. exe 크기를 CHANGELOG에 기록.

- [ ] **Step 4: CHANGELOG.md 2.0.0 엔트리 + README 갱신**

CHANGELOG에 Added(피커·핫키·라이브러리·APNG→GIF·자동 붙여넣기)/Changed(패키지 구조)/Notes(ToS 설계 원칙: 클라이언트 무수정·전송은 사용자) 기재. README.md/README.ko.md에 피커 섹션(등록 방법·핫키·감시 폴더·한계: 받는 쪽에는 첨부/링크로 보임) 추가.

- [ ] **Step 5: 전체 테스트 + Commit**

```
python -m pytest -q
git add -A && git commit -m "chore: v2.0.0 — build with picker UI assets, changelog, docs"
```

---

### Task 10: 수동 QA 체크리스트 (스펙 §8) — 릴리스 게이트

`python clipshrink.py`(개발)와 `dist\ClipShrink.exe`(배포) 각각에서:

- [ ] 1. `Ctrl+Shift+E` 호출/재호출 토글, ESC 닫기, 포커스 아웃 닫기
- [ ] 2. 디스코드 이모지 링크 등록 → 그리드 표시 → 클릭 → 디스코드 입력창 파일 첨부 → Enter 전송 성공
- [ ] 3. APNG 스티커 등록 → GIF 변환 확인 → 피커·디스코드 양쪽에서 애니메이션 재생
- [ ] 4. GIF 폴더 추가 → GIF 탭 자동 표시 → 클릭 붙여넣기 → 새 파일 추가 시 재스캔 반영
- [ ] 5. 우클릭 "링크로 붙여넣기" → URL 텍스트+임베드 확인
- [ ] 6. 최근 사용 섹션 갱신, 검색(이름/키워드) 필터
- [ ] 7. 멀티모니터: 각 모니터에서 팝업 위치가 작업영역 안 (DPI 100%/150% 확인)
- [ ] 8. 10MB 초과 정지 PNG 항목 → 자동 압축 붙여넣기 / 10MB 초과 GIF → 경고 알림
- [ ] 9. 기존 기능 회귀: 큰 이미지 복사 → 자동 압축, 한도 메뉴, 언어 전환, 시작 등록, 단일 인스턴스
- [ ] 10. 핫키 충돌 시나리오: 다른 앱이 Ctrl+Shift+E 선점 → 실패 알림 → 다른 조합 선택으로 복구
- [ ] 11. 종료 → 프로세스·핫키·창 완전 정리 (작업관리자)

전 항목 통과 시:

```
git add -A && git commit -m "test: v2.0 manual QA checklist pass"   # 체크 기록이 있다면
```

---

## Self-Review (계획 자체 점검 결과)

1. **스펙 커버리지**: §2 요구사항 전부 태스크 매핑 확인 — 라이브러리 소스(T3/T4/T6), GIF 탭(T3 폴더+T6), 핫키 팝업(T2/T8), 자동 붙여넣기(T5/T7), 다크테마(T6), ToS 불변조건(Global Constraints+T7 파이프라인). §7 예외 전부: 포커스 폴백(T5/T7), CDN 검증(T4), WebView2(T2/T8), APNG 실패 폴백(T4 `_finalize_asset`의 예외는 등록 실패로 표면화 — 배지 대신 에러 안내로 단순화, 스펙 §7 대비 완화), 초과 GIF 경고(T5), 폴더 소실(T3 스킵+T6 회색), 핫키 선점(T2/T8). 갭 없음.
2. **플레이스홀더**: "원본 그대로 이동" 지시는 이동 대상 라인 범위를 명시했고 소스가 리포에 존재 — 허용. 신규 로직은 전부 전체 코드 수록.
3. **타입 일관성**: `Library.add_item(type_, name, keywords, source_kind, source_url, filename, animated)` — fetch.py 호출과 일치. `PickerApi.get_state()` 반환 키 = app.js `refresh()` 소비 키 일치 (`items/recent/folders/strings`). `HOTKEY_CHOICES` 튜플 순서 (mods, vk, label) = tray `HOTKEY_CHOICES[key][2]` 사용과 일치. `prepare_for_paste(path, limit_bytes, temp_dir)` — 테스트·T7 호출 일치.



