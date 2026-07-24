# -*- coding: utf-8 -*-
"""클립보드 캡처 읽기와 피커 라이브러리 저장.

수동 버튼과 자동 Monitor가 같은 CaptureStore를 공유해, 해시 확인부터
메타데이터 저장까지 하나의 임계 구역에서 처리한다.
"""

from __future__ import annotations

import hashlib
import io
import threading
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageGrab

from . import clipboard_win as cb
from . import fetch

CAPTURE_COLLECTION_ID = "__notro_captures__"


@dataclass(frozen=True)
class CaptureReadResult:
    data: bytes | None
    error: str | None


@dataclass(frozen=True)
class CaptureSaveResult:
    ok: bool
    duplicate: bool = False
    item_id: str = ""
    error: str | None = None


def image_to_png_bytes(image: Image.Image) -> bytes:
    """Windows 비트맵을 라이브러리의 표준 PNG 바이트로 정규화한다."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def read_clipboard_png() -> CaptureReadResult:
    """원본 PNG 우선, CF_DIB 비트맵 폴백으로 클립보드 이미지를 읽는다.

    ImageGrab의 경로 리스트는 Explorer 파일 복사이므로 캡처로 보지 않는다.
    """
    read_failed = False
    try:
        data = cb.get_clipboard_png()
    except Exception:
        data = None
        read_failed = True
    if data:
        return CaptureReadResult(data, None)

    try:
        content = ImageGrab.grabclipboard()
    except Exception:
        return CaptureReadResult(None, "read")
    if isinstance(content, Image.Image):
        try:
            return CaptureReadResult(image_to_png_bytes(content), None)
        except Exception:
            return CaptureReadResult(None, "read")
    if read_failed:
        return CaptureReadResult(None, "read")
    return CaptureReadResult(None, "no_image")


class CaptureStore:
    """예약 컬렉션에 캡처를 저장하고 동일 PNG를 한 번만 등록한다."""

    def __init__(self, library):
        self._library = library
        self._lock = threading.Lock()

    def save_png(self, data: bytes) -> CaptureSaveResult:
        if not data:
            return CaptureSaveResult(False, error="no_image")
        digest = hashlib.sha256(data).hexdigest()
        with self._lock:
            existing = self._library.find_by_content_hash(
                digest, "emoji", CAPTURE_COLLECTION_ID)
            if existing:
                return CaptureSaveResult(True, True, existing["id"], None)
            name = datetime.now().strftime("capture-%Y%m%d-%H%M%S-%f")
            try:
                item = fetch.register_from_png_bytes(
                    self._library, data, "emoji", name=name,
                    collection=CAPTURE_COLLECTION_ID, content_hash=digest)
            except Exception:
                return CaptureSaveResult(False, error="register")
            return CaptureSaveResult(True, False, item["id"], None)

    def read_and_save(self) -> CaptureSaveResult:
        read = read_clipboard_png()
        if not read.data:
            return CaptureSaveResult(False, error=read.error or "no_image")
        return self.save_png(read.data)
