# -*- coding: utf-8 -*-
"""
ClipShrink - 디스코드 무료(니트로 X) 업로드 한도 자동 압축기

동작 원리:
  - 트레이에 상주하며 클립보드를 감시합니다.
  - 새 이미지가 클립보드에 복사되면, 디스코드가 붙여넣기 시 변환하는 PNG 기준 용량을 계산합니다.
  - 10MB(안전 마진 적용)를 초과하면 WebP/JPEG로 자동 압축하고,
    압축된 "파일"을 클립보드에 넣어 Ctrl+V로 바로 업로드할 수 있게 합니다.
  - 10MB 이하면 아무것도 하지 않습니다 (원본 그대로 붙여넣기 가능).

필요 패키지: pillow, pystray  (pip install -r requirements.txt)
실행: pythonw clipshrink.py  (콘솔 창 없이 실행)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import io
import os
import struct
import sys
import tempfile
import threading
import time
from datetime import datetime

from PIL import Image, ImageGrab

__version__ = "1.1.0"

# ===================== 설정 =====================
LIMIT_MB = 10           # 디스코드 무료 업로드 한도 (MB)
SAFETY = 0.95           # 안전 마진 (10MB의 95% = 9.5MB 목표)
WEBP_QUALITIES = [90, 80, 70, 60, 50]   # 1차: WebP 품질 단계
JPEG_QUALITIES = [85, 75, 65]           # 2차: JPEG 품질 단계 (WebP 실패 시)
MIN_SCALE = 0.4         # 해상도 축소 하한 (원본의 40%까지만)
POLL_INTERVAL = 0.4     # 클립보드 확인 주기 (초)
# ================================================


def compute_limit_bytes(mb: int) -> int:
    """업로드 한도(MB)에 안전 마진을 적용한 바이트 한도."""
    return int(mb * 1024 * 1024 * SAFETY)


LIMIT_BYTES = compute_limit_bytes(LIMIT_MB)
TEMP_DIR = os.path.join(tempfile.gettempdir(), "ClipShrink")
os.makedirs(TEMP_DIR, exist_ok=True)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 64비트 환경에서 핸들/포인터가 잘리지 않도록 시그니처 지정
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

# 우리가 만든 클립보드 데이터에 붙이는 마커 (무한 루프 방지)
MARKER_FORMAT = user32.RegisterClipboardFormatW("ClipShrinkMarker")

APP_NAME = "ClipShrink"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ---------- 시작 프로그램 등록 ----------
def get_launch_command() -> str:
    """현재 실행 형태(EXE 또는 스크립트)에 맞는 실행 명령을 만든다."""
    if getattr(sys, "frozen", False):  # PyInstaller EXE
        return f'"{sys.executable}"'
    script = os.path.abspath(__file__)
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{exe}" "{script}"'


def is_startup_registered() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return value == get_launch_command()
    except OSError:
        return False


def set_startup(enable: bool):
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_launch_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass


SETTINGS_KEY = r"Software\ClipShrink"


def get_setting_int(name: str, default: int = 0) -> int:
    r"""HKCU\Software\ClipShrink 아래의 DWORD 값을 읽는다 (없으면 default)."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except (OSError, ValueError, TypeError):
        return default


def set_setting_int(name: str, value: int):
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))
    except OSError:
        pass


def get_setting_flag(name: str) -> bool:
    return bool(get_setting_int(name, 0))


def set_setting_flag(name: str, value: bool = True):
    set_setting_int(name, 1 if value else 0)


def get_setting_str(name: str, default: str = "") -> str:
    r"""HKCU\Software\ClipShrink 아래의 문자열 값을 읽는다 (없으면 default)."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return default


def set_setting_str(name: str, value: str):
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    except OSError:
        pass


# ---------- 다국어 (i18n) ----------
SUPPORTED_LANGS = ("en", "ko", "ja", "zh")

# GetUserDefaultUILanguage()의 primary language id → 언어 코드
_PRIMARY_LANG_MAP = {0x09: "en", 0x12: "ko", 0x11: "ja", 0x04: "zh"}

STRINGS = {
    "en": {
        "tooltip": "ClipShrink v{ver} — auto-compress images for Discord's upload limit",
        "pause": "Pause watching",
        "resume": "Resume watching",
        "history": "Recent activity",
        "history_empty": "(none yet)",
        "upload_limit": "Upload limit",
        "open_folder": "Open output folder",
        "run_at_startup": "Run at Windows startup",
        "language": "Language",
        "lang_auto": "Auto-detect",
        "quit": "Quit",
        "notify_compress_done": "Compressed: {orig:.1f} MB → {new:.1f} MB (-{pct}%, {fmt}) — just paste it.",
        "notify_compress_fail": "Compression failed: couldn't get under the limit.",
        "notify_clipboard_fail": "Clipboard update failed: another app is using the clipboard. Please copy again in a moment.",
        "notify_file_deleted": "That file has already been deleted.",
        "notify_startup_fail": "Failed to change the startup setting.",
        "notify_first_run": "Running in the tray. To launch at startup, enable it from the menu → 'Run at Windows startup'.",
    },
    "ko": {
        "tooltip": "ClipShrink v{ver} — 디스코드 업로드 한도 자동 압축",
        "pause": "감시 중지",
        "resume": "감시 시작",
        "history": "최근 처리 내역",
        "history_empty": "(아직 없음)",
        "upload_limit": "업로드 한도",
        "open_folder": "처리된 이미지 폴더 열기",
        "run_at_startup": "Windows 시작 시 자동 실행",
        "language": "언어",
        "lang_auto": "자동 감지",
        "quit": "종료",
        "notify_compress_done": "압축 완료: {orig:.1f}MB → {new:.1f}MB ({pct}% 감소, {fmt}) — 그대로 붙여넣으세요.",
        "notify_compress_fail": "압축 실패: 한도 이하로 줄이지 못했습니다.",
        "notify_clipboard_fail": "클립보드 교체 실패: 다른 프로그램이 클립보드를 사용 중입니다. 잠시 후 다시 복사해 주세요.",
        "notify_file_deleted": "파일이 이미 삭제되었습니다.",
        "notify_startup_fail": "시작 프로그램 설정 변경에 실패했습니다.",
        "notify_first_run": "트레이에서 실행 중입니다. 부팅 시 자동 실행하려면 메뉴 → 'Windows 시작 시 자동 실행'을 켜세요.",
    },
    "ja": {
        "tooltip": "ClipShrink v{ver} — Discordのアップロード上限に自動圧縮",
        "pause": "監視を停止",
        "resume": "監視を再開",
        "history": "最近の処理履歴",
        "history_empty": "(まだありません)",
        "upload_limit": "アップロード上限",
        "open_folder": "出力フォルダーを開く",
        "run_at_startup": "Windows起動時に実行",
        "language": "言語",
        "lang_auto": "自動検出",
        "quit": "終了",
        "notify_compress_done": "圧縮完了: {orig:.1f}MB → {new:.1f}MB（{pct}%削減、{fmt}）— そのまま貼り付けてください。",
        "notify_compress_fail": "圧縮失敗: 上限以下に縮小できませんでした。",
        "notify_clipboard_fail": "クリップボードの更新に失敗: 他のアプリが使用中です。少し待ってからもう一度コピーしてください。",
        "notify_file_deleted": "ファイルはすでに削除されています。",
        "notify_startup_fail": "スタートアップ設定の変更に失敗しました。",
        "notify_first_run": "トレイで実行中です。起動時に自動実行するには、メニュー →「Windows起動時に実行」をオンにしてください。",
    },
    "zh": {
        "tooltip": "ClipShrink v{ver} — 自动压缩图片以符合 Discord 上传限制",
        "pause": "暂停监视",
        "resume": "恢复监视",
        "history": "最近处理记录",
        "history_empty": "(暂无)",
        "upload_limit": "上传限制",
        "open_folder": "打开输出文件夹",
        "run_at_startup": "开机时自动运行",
        "language": "语言",
        "lang_auto": "自动检测",
        "quit": "退出",
        "notify_compress_done": "压缩完成: {orig:.1f}MB → {new:.1f}MB（减少 {pct}%，{fmt}）— 直接粘贴即可。",
        "notify_compress_fail": "压缩失败: 无法缩小到限制以下。",
        "notify_clipboard_fail": "剪贴板更新失败: 其他程序正在占用剪贴板。请稍后重新复制。",
        "notify_file_deleted": "该文件已被删除。",
        "notify_startup_fail": "更改开机启动设置失败。",
        "notify_first_run": "正在托盘运行。如需开机自动启动，请在菜单 →「开机时自动运行」中开启。",
    },
}

current_lang = "en"  # 실행 시 set_language()로 설정됨


def detect_system_lang() -> str:
    """Windows UI 언어를 감지해 지원 언어 코드로 매핑 (실패 시 'en')."""
    try:
        langid = kernel32.GetUserDefaultUILanguage()
        return _PRIMARY_LANG_MAP.get(langid & 0x3FF, "en")
    except Exception:
        return "en"


def set_language(pref: str):
    """pref가 'auto'면 시스템 언어를 감지, 아니면 해당 언어로 설정."""
    global current_lang
    if pref == "auto":
        current_lang = detect_system_lang()
    elif pref in STRINGS:
        current_lang = pref
    else:
        current_lang = "en"


def tr(key: str, **kwargs) -> str:
    """현재 언어의 문자열을 반환 (없으면 영어, 그래도 없으면 key)."""
    table = STRINGS.get(current_lang, STRINGS["en"])
    text = table.get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def ensure_single_instance():
    """이미 실행 중이면 조용히 종료 (자동 시작 + 수동 실행 중복 방지).

    use_last_error=True 핸들로 호출해야 CreateMutexW 직후의 GetLastError가
    신뢰 가능하다. 뮤텍스는 현재 세션 범위(Local\\)로 잡아 다중 사용자 환경에서
    다른 사용자 인스턴스를 막지 않는다. 핸들은 프로세스 생명주기 동안 유지되며
    종료 시 OS가 회수한다.
    """
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wt.HANDLE
    k32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
    k32.CreateMutexW(None, False, "Local\\ClipShrink_SingleInstance")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)


# ---------- 클립보드: 파일을 CF_HDROP 형식으로 넣기 ----------
def set_clipboard_file(path: str) -> bool:
    """압축된 이미지 파일을 클립보드에 넣어 Ctrl+V로 파일 업로드가 되게 한다."""
    # DROPFILES 구조체(20바이트) + UTF-16LE 경로 + 이중 널 종료
    files = path + "\0"
    data = struct.pack("<Iiiii", 20, 0, 0, 0, 1) + files.encode("utf-16-le") + b"\0\0"

    for _ in range(10):  # 다른 프로그램이 클립보드를 잡고 있으면 재시도
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()

        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(hmem)
        if not user32.SetClipboardData(CF_HDROP, hmem):
            return False

        # 마커 추가 → 우리가 넣은 데이터는 다시 처리하지 않음 (best-effort)
        marker = b"\x01\x00"
        hmark = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(marker))
        if hmark:
            mptr = kernel32.GlobalLock(hmark)
            if mptr:
                ctypes.memmove(mptr, marker, len(marker))
                kernel32.GlobalUnlock(hmark)
                user32.SetClipboardData(MARKER_FORMAT, hmark)
        return True
    finally:
        user32.CloseClipboard()


def clipboard_has_marker() -> bool:
    return bool(user32.IsClipboardFormatAvailable(MARKER_FORMAT))


# 크로미움 계열(디스코드, 브라우저)이 이미지 복사 시 사용하는 PNG 포맷들
PNG_FORMATS = [
    user32.RegisterClipboardFormatW("PNG"),
    user32.RegisterClipboardFormatW("image/png"),
]


def get_clipboard_png() -> bytes | None:
    """클립보드에 PNG 원본 바이트가 있으면 그대로 읽는다.
    디스코드는 붙여넣기 시 이 PNG를 그대로 업로드하므로, 재인코딩 추정치가 아닌
    이 실제 바이트 크기로 판단해야 정확하다."""
    fmt = next((f for f in PNG_FORMATS if user32.IsClipboardFormatAvailable(f)), None)
    if not fmt:
        return None
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return None
    try:
        handle = user32.GetClipboardData(fmt)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            size = kernel32.GlobalSize(handle)
            data = ctypes.string_at(ptr, size)
        finally:
            kernel32.GlobalUnlock(handle)
        # PNG 시그니처 확인
        return data if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    finally:
        user32.CloseClipboard()


# ---------- 압축 로직 ----------
def estimate_png_size(img: Image.Image) -> int:
    """디스코드가 클립보드 비트맵을 붙여넣을 때 만드는 PNG의 용량을 추정."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.tell()


def _to_rgb_on_white(im: Image.Image) -> Image.Image:
    """JPEG는 알파를 지원하지 않으므로 RGBA는 흰 배경에 합성해 RGB로 변환한다.
    (단순 convert('RGB')는 투명 영역을 검게 만든다.)"""
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        return bg
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def compress_image(img: Image.Image, limit: int):
    """
    한도 이하가 될 때까지 압축. (포맷 변환 → 품질 하향 → 해상도 축소 순)
    반환: (bytes, 확장자) 또는 None(실패)
    """
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    def try_encode(im, fmt, quality):
        buf = io.BytesIO()
        if fmt == "WEBP":
            im.save(buf, format="WEBP", quality=quality, method=4)
        else:
            rgb = _to_rgb_on_white(im)
            rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()

    scale = 1.0
    current = img
    while scale >= MIN_SCALE:
        # WebP는 한 변 16383px 제한
        if max(current.size) <= 16383:
            for q in WEBP_QUALITIES:
                data = try_encode(current, "WEBP", q)
                if len(data) <= limit:
                    return data, ".webp"
        for q in JPEG_QUALITIES:
            data = try_encode(current, "JPEG", q)
            if len(data) <= limit:
                return data, ".jpg"
        # 그래도 크면 해상도 15%씩 축소
        scale *= 0.85
        new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        current = img.resize(new_size, Image.LANCZOS)
    return None


# ---------- 메인 감시 루프 ----------
class Monitor:
    def __init__(self):
        self.enabled = True
        self.stop_flag = False
        self.last_seq = user32.GetClipboardSequenceNumber()
        self.status_cb = None  # 트레이 알림 콜백
        self.history = []  # 처리 내역: {time, path, orig_mb, new_mb, pct}
        self.history_lock = threading.Lock()  # 감시 스레드 ↔ 트레이 메뉴 스레드 동시 접근 보호
        self.on_history_change = None  # 트레이 메뉴 갱신 콜백

    def notify(self, title, msg):
        if self.status_cb:
            try:
                self.status_cb(title, msg)
            except Exception:
                pass

    def process_clipboard(self):
        if clipboard_has_marker():
            return

        img = None
        orig_bytes = None

        # 1) 크로미움 계열(디스코드 등)이 넣은 PNG 원본이 있으면 그 실제 크기로 판단.
        #    디스코드는 붙여넣기 시 이 PNG를 그대로 업로드하므로 가장 정확하다.
        try:
            png = get_clipboard_png()
        except Exception:
            png = None
        if png is not None:
            if len(png) <= LIMIT_BYTES:
                return  # 실제 PNG가 한도 이하 → 그대로 둠
            orig_bytes = len(png)
            try:
                img = Image.open(io.BytesIO(png))
                img.load()
            except Exception:
                img = None
            if img is not None:
                self._compress_and_replace(img, orig_bytes)
                return

        # 2) 일반 비트맵 / 복사된 파일 처리
        try:
            content = ImageGrab.grabclipboard()
        except Exception:
            return

        if isinstance(content, Image.Image):
            img = content
        elif isinstance(content, list):
            # 파일이 복사된 경우: 이미지 파일이고 한도 초과면 그것도 압축
            paths = [p for p in content if isinstance(p, str)]
            if len(paths) == 1 and paths[0].lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")
            ):
                try:
                    size = os.path.getsize(paths[0])
                    if size > LIMIT_BYTES:
                        orig_bytes = size
                        img = Image.open(paths[0])
                        img.load()
                except Exception:
                    return
            if img is None:
                return
        else:
            return

        # 비트맵이면 PNG 기준 용량으로 판단 (디스코드가 PNG로 변환해서 올리므로)
        if isinstance(content, Image.Image):
            orig_bytes = estimate_png_size(img)
            if orig_bytes <= LIMIT_BYTES:
                return  # 한도 이하 → 그대로 둠

        self._compress_and_replace(img, orig_bytes)

    def _compress_and_replace(self, img: Image.Image, orig_bytes: int):
        result = compress_image(img, LIMIT_BYTES)
        if result is None:
            self.notify(APP_NAME, tr("notify_compress_fail"))
            return

        data, ext = result
        out_path = os.path.join(
            TEMP_DIR, datetime.now().strftime("capture_%Y%m%d_%H%M%S_%f") + ext
        )
        with open(out_path, "wb") as f:
            f.write(data)

        if set_clipboard_file(out_path):
            self.last_seq = user32.GetClipboardSequenceNumber()
            orig_mb = orig_bytes / 1024 / 1024
            new_mb = len(data) / 1024 / 1024
            pct = round((1 - new_mb / orig_mb) * 100) if orig_mb else 0
            with self.history_lock:
                self.history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "path": out_path,
                    "orig_mb": orig_mb,
                    "new_mb": new_mb,
                    "pct": pct,
                })
                del self.history[:-15]  # 최근 15개만 유지
            if self.on_history_change:
                try:
                    self.on_history_change()
                except Exception:
                    pass
            self.notify(
                APP_NAME,
                tr(
                    "notify_compress_done",
                    orig=orig_mb,
                    new=new_mb,
                    pct=pct,
                    fmt=ext[1:].upper(),
                ),
            )
        else:
            self.notify(APP_NAME, tr("notify_clipboard_fail"))

    def run(self):
        last_cleanup = time.time()
        while not self.stop_flag:
            time.sleep(POLL_INTERVAL)
            if time.time() - last_cleanup > 3600:  # 1시간마다 오래된 임시파일 정리
                cleanup_temp()
                last_cleanup = time.time()
            if not self.enabled:
                continue
            seq = user32.GetClipboardSequenceNumber()
            if seq != self.last_seq:
                self.last_seq = seq
                try:
                    self.process_clipboard()
                except Exception:
                    pass
        # 종료 시 임시 파일 정리 (1일 이상 지난 것)
        cleanup_temp()


def cleanup_temp():
    now = time.time()
    try:
        for name in os.listdir(TEMP_DIR):
            p = os.path.join(TEMP_DIR, name)
            if now - os.path.getmtime(p) > 86400:
                os.remove(p)
    except Exception:
        pass


# ---------- 트레이 아이콘 ----------
def make_icon_image(active=True):
    from PIL import ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (88, 101, 242, 255) if active else (128, 128, 128, 255)  # 디스코드 블루
    d.rounded_rectangle([4, 12, 60, 52], radius=10, fill=color)
    d.ellipse([24, 22, 40, 42], fill=(255, 255, 255, 255))
    return img


def main():
    import pystray

    global LIMIT_MB, LIMIT_BYTES

    ensure_single_instance()
    cleanup_temp()

    # 저장된 업로드 한도 불러오기 (없으면 기본값 유지)
    LIMIT_MB = get_setting_int("limit_mb", LIMIT_MB)
    LIMIT_BYTES = compute_limit_bytes(LIMIT_MB)

    # 언어: 저장된 설정(없으면 'auto' → 시스템 언어 감지)
    set_language(get_setting_str("lang", "auto"))

    # 자동 시작은 opt-in: 첫 실행이면 안내만 하고, 등록은 사용자가 트레이 메뉴에서 직접 켠다.
    first_run = not get_setting_flag("welcomed")
    if first_run:
        set_setting_flag("welcomed")

    monitor = Monitor()
    t = threading.Thread(target=monitor.run, daemon=True)
    t.start()

    def on_toggle(icon, item):
        monitor.enabled = not monitor.enabled
        icon.icon = make_icon_image(monitor.enabled)

    def on_toggle_startup(icon, item):
        try:
            set_startup(not is_startup_registered())
        except Exception:
            icon.notify(tr("notify_startup_fail"), APP_NAME)

    def on_quit(icon, item):
        monitor.stop_flag = True
        icon.stop()

    def on_open_folder(icon, item):
        os.startfile(TEMP_DIR)

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
            global LIMIT_MB, LIMIT_BYTES
            LIMIT_MB = mb
            LIMIT_BYTES = compute_limit_bytes(mb)
            set_setting_int("limit_mb", mb)
            icon.update_menu()

        return pystray.MenuItem(
            f"{mb} MB",
            on_select,
            checked=lambda item, mb=mb: LIMIT_MB == mb,
            radio=True,
        )

    # 디스코드 한도: 무료 10 / 니트로 베이직 50 / 니트로 500 MB
    limit_menu = pystray.Menu(
        make_limit_item(10),
        make_limit_item(50),
        make_limit_item(500),
    )

    # 언어 메뉴 (자동 감지 + 각 언어). 언어명은 해당 언어 표기 그대로 둔다.
    lang_names = {"en": "English", "ko": "한국어", "ja": "日本語", "zh": "中文(简体)"}

    def make_lang_item(code):
        def on_select(icon, item):
            set_setting_str("lang", code)
            set_language(code)
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
    )

    icon = pystray.Icon(
        APP_NAME,
        make_icon_image(True),
        tr("tooltip", ver=__version__),
        menu=pystray.Menu(
            pystray.MenuItem(
                lambda item: tr("pause") if monitor.enabled else tr("resume"),
                on_toggle,
            ),
            pystray.MenuItem(lambda item: tr("history"), pystray.Menu(history_items)),
            pystray.MenuItem(lambda item: tr("upload_limit"), limit_menu),
            pystray.MenuItem(lambda item: tr("open_folder"), on_open_folder),
            pystray.MenuItem(lambda item: tr("language"), lang_menu),
            pystray.MenuItem(
                lambda item: tr("run_at_startup"),
                on_toggle_startup,
                checked=lambda item: is_startup_registered(),
            ),
            pystray.MenuItem(lambda item: tr("quit"), on_quit),
        ),
    )
    monitor.on_history_change = icon.update_menu
    monitor.status_cb = lambda title, msg: icon.notify(msg, title)
    if first_run:
        threading.Timer(
            1.5,
            lambda: icon.notify(tr("notify_first_run"), APP_NAME),
        ).start()
    icon.run()


if __name__ == "__main__":
    main()
