# -*- coding: utf-8 -*-
"""Windows 클립보드: CF_HDROP 파일·텍스트·마커·PNG 읽기 + 포커스/키 입력."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import time

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
kernel32.GlobalFree.restype = wt.HGLOBAL
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
user32.SetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.GetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]

CF_HDROP = 15
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# 우리가 만든 클립보드 데이터에 붙이는 마커 (무한 루프 방지)
MARKER_FORMAT = user32.RegisterClipboardFormatW("NotroMarker")

# 크로미움 계열(디스코드, 브라우저)이 이미지 복사 시 사용하는 PNG 포맷들
PNG_FORMATS = [
    user32.RegisterClipboardFormatW("PNG"),
    user32.RegisterClipboardFormatW("image/png"),
]


def build_drop_data(path: str) -> bytes:
    """CF_HDROP용 DROPFILES 구조체 바이트를 만든다 (순수 함수).

    DROPFILES(20바이트) + UTF-16LE 경로 + 이중 널 종료.
    """
    files = path + "\0"
    return struct.pack("<Iiiii", 20, 0, 0, 0, 1) + files.encode("utf-16-le") + b"\0\0"


def _open_clipboard_retry() -> bool:
    for _ in range(10):  # 다른 프로그램이 클립보드를 잡고 있으면 재시도
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
        kernel32.GlobalFree(hmem)  # 잠금 실패 — 소유권을 넘기지 못했으니 해제
        return False
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(hmem)
    if user32.SetClipboardData(fmt, hmem):
        return True  # 성공 시 소유권이 클립보드로 넘어가므로 해제하지 않는다
    kernel32.GlobalFree(hmem)  # 실패 시 소유권이 넘어가지 않았으니 해제
    return False


def _put_marker() -> None:
    _global_put(MARKER_FORMAT, b"\x01\x00")  # best-effort


def set_clipboard_file(path: str, guard_seq: int | None = None) -> bool | None:
    """파일을 CF_HDROP로 클립보드에 넣어 Ctrl+V로 파일 업로드가 되게 한다.

    guard_seq가 주어지면 클립보드를 연 뒤(다른 프로세스가 더는 끼어들 수 없는
    상태에서) 시퀀스를 비교해, 달라져 있으면 아무것도 바꾸지 않고 None을 반환한다.
    이미지를 읽고 압축하는 몇 초 사이에 사용자가 새로 복사한 내용을 지우지 않기
    위한 가드다. 반환: True(교체) / False(실패) / None(새 복사 감지 — 중단).
    """
    if not _open_clipboard_retry():
        return False
    try:
        if guard_seq is not None and get_sequence_number() != guard_seq:
            return None
        user32.EmptyClipboard()
        if not _global_put(CF_HDROP, build_drop_data(path)):
            return False
        _put_marker()
        return True
    finally:
        user32.CloseClipboard()


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


def clipboard_has_marker() -> bool:
    return bool(user32.IsClipboardFormatAvailable(MARKER_FORMAT))


def clipboard_has_files() -> bool:
    """Explorer 파일 복사(CF_HDROP) 여부를 클립보드를 열지 않고 확인한다."""
    return bool(user32.IsClipboardFormatAvailable(CF_HDROP))


def get_sequence_number() -> int:
    return user32.GetClipboardSequenceNumber()


def get_clipboard_png() -> bytes | None:
    """클립보드에 PNG 원본 바이트가 있으면 그대로 읽는다.
    디스코드는 붙여넣기 시 이 PNG를 그대로 업로드하므로, 재인코딩 추정치가 아닌
    이 실제 바이트 크기로 판단해야 정확하다."""
    fmt = next((f for f in PNG_FORMATS if user32.IsClipboardFormatAvailable(f)), None)
    if not fmt:
        return None
    if not _open_clipboard_retry():
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


def get_foreground_window() -> int:
    return user32.GetForegroundWindow()


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
