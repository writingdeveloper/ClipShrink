# -*- coding: utf-8 -*-
"""메인 감시 루프: 클립보드의 큰 이미지를 자동 압축해 파일로 교체."""

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
from .capture_store import image_to_png_bytes
from .i18n import tr


class Monitor:
    def __init__(self):
        self.enabled = True
        self.stop_flag = False
        self.last_seq = cb.get_sequence_number()
        self._pending_seq = self.last_seq  # 변화 감지 후 안정화 대기용
        self.status_cb = None  # 트레이 알림 콜백
        self.history = []  # 처리 내역: {time, path, orig_mb, new_mb, pct}
        self.history_lock = threading.Lock()  # 감시 스레드 ↔ 트레이 메뉴 스레드 동시 접근 보호
        self.on_history_change = None  # 트레이 메뉴 갱신 콜백
        self.on_video_oversize = None  # 한도 초과 비디오 감지 콜백 (app.py가 배선)
        self.capture_enabled = None  # 자동 캡처 저장 설정 판정 콜백
        self.on_capture_image = None  # PNG 바이트 저장 콜백 (app.py가 배선)

    def notify(self, title, msg):
        if self.status_cb:
            try:
                self.status_cb(title, msg)
            except Exception:
                pass

    def _emit_capture(self, data: bytes) -> None:
        """자동 저장이 켜졌을 때 캡처 바이트를 전달한다.

        저장 실패가 원래 책임인 대용량 압축을 막지 않도록 완전히 격리한다.
        """
        try:
            if not self.capture_enabled or not self.capture_enabled():
                return
            if self.on_capture_image:
                self.on_capture_image(data)
        except Exception:
            pass

    def process_clipboard(self):
        if cb.clipboard_has_marker():
            return

        # 지금 읽는 내용의 시퀀스. 압축하는 몇 초 사이에 사용자가 새로 복사하면
        # 시퀀스가 달라지므로, 교체 직전 이 값으로 검사해 새 복사를 지우지 않는다.
        guard_seq = cb.get_sequence_number()

        img = None
        orig_bytes = None

        # 1) 크로미움 계열(디스코드 등)이 넣은 PNG 원본이 있으면 그 실제 크기로 판단.
        #    디스코드는 붙여넣기 시 이 PNG를 그대로 업로드하므로 가장 정확하다.
        try:
            png = cb.get_clipboard_png()
        except Exception:
            png = None
        if png is not None:
            if not cb.clipboard_has_files():
                self._emit_capture(png)
            if len(png) <= config.LIMIT_BYTES:
                return  # 실제 PNG가 한도 이하 → 그대로 둠
            orig_bytes = len(png)
            try:
                img = Image.open(io.BytesIO(png))
                img.load()
            except Exception:
                img = None
            if img is not None:
                self._compress_and_replace(img, orig_bytes, guard_seq)
                return

        # 2) 일반 비트맵 / 복사된 파일 처리
        try:
            content = ImageGrab.grabclipboard()
        except Exception:
            return

        if isinstance(content, Image.Image):
            img = content
        elif isinstance(content, list):
            # 파일이 복사된 경우(CF_HDROP). 비디오는 감지만 하고 오케스트레이션에
            # 위임한다 — 인코딩은 수십 초라 감시 루프를 막으면 안 된다.
            paths = [p for p in content if isinstance(p, str)]
            if len(paths) != 1:
                return
            path = paths[0]
            ext = os.path.splitext(path)[1].lower()

            if ext in config.VIDEO_EXTS:
                try:
                    size = os.path.getsize(path)
                except OSError:
                    return
                if size > config.LIMIT_BYTES and self.on_video_oversize:
                    self.on_video_oversize(path)
                return

            if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"):
                try:
                    size = os.path.getsize(path)
                    if size > config.LIMIT_BYTES:
                        orig_bytes = size
                        img = Image.open(path)
                        img.load()
                except Exception:
                    return
            if img is None:
                return
        else:
            return

        # 비트맵이면 PNG 기준 용량으로 판단 (디스코드가 PNG로 변환해서 올리므로)
        if isinstance(content, Image.Image):
            try:
                self._emit_capture(image_to_png_bytes(img))
            except Exception:
                pass
            orig_bytes = compress.estimate_png_size(img)
            if orig_bytes <= config.LIMIT_BYTES:
                return  # 한도 이하 → 그대로 둠

        self._compress_and_replace(img, orig_bytes, guard_seq)

    def _compress_and_replace(self, img: Image.Image, orig_bytes: int,
                              guard_seq: int):
        result = compress.compress_image(img, config.LIMIT_BYTES)
        if result is None:
            self.notify(APP_NAME, tr("notify_compress_fail"))
            return

        data, ext = result
        out_path = os.path.join(
            config.TEMP_DIR, datetime.now().strftime("capture_%Y%m%d_%H%M%S_%f") + ext
        )
        with open(out_path, "wb") as f:
            f.write(data)

        replaced = cb.set_clipboard_file(out_path, guard_seq=guard_seq)
        if replaced is None:
            # 압축하는 사이 사용자가 새로 복사했다 — 새 내용을 지우지 않고 이번
            # 결과는 버린다. last_seq를 갱신하지 않으므로 새 복사는 다음 폴에서
            # 정상적으로 처리된다.
            return
        if replaced:
            self.last_seq = cb.get_sequence_number()
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

    def _tick(self):
        """폴 한 번: 시퀀스가 두 폴 연속 같을 때만 처리한다.

        크로미움(디스코드)은 이미지 하나를 복사할 때 여러 포맷을 수백 ms에 걸쳐
        쓰고, 그동안 시퀀스가 계속 증가한다. 변화 직후에 바로 읽으면 아직 PNG
        포맷이 없어 비트맵 추정 경로로 빠지는 mid-write 읽기가 생기므로, 쓰기
        세션이 끝나 시퀀스가 안정된 뒤에만 읽는다."""
        seq = cb.get_sequence_number()
        if seq == self.last_seq:
            return
        if seq != self._pending_seq:
            self._pending_seq = seq  # 방금 변했다 — 다음 폴까지 기다린다
            return
        self.last_seq = seq
        try:
            self.process_clipboard()
        except Exception:
            pass

    def run(self):
        last_cleanup = time.time()
        while not self.stop_flag:
            time.sleep(config.POLL_INTERVAL)
            if time.time() - last_cleanup > 3600:  # 1시간마다 오래된 임시파일 정리
                config.cleanup_temp()
                last_cleanup = time.time()
            if not self.enabled:
                continue
            self._tick()
        # 종료 시 임시 파일 정리 (1일 이상 지난 것)
        config.cleanup_temp()
