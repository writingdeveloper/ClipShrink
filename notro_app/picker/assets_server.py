# -*- coding: utf-8 -*-
"""피커 자산 로컬 HTTP 서버 (127.0.0.1 전용).

WebView2는 페이지 origin과 무관하게 file:// 서브리소스 로드를 차단하므로,
라이브러리 자산(등록 캐시 + 감시 폴더의 임의 경로 파일)을 item id 기준으로
127.0.0.1의 임의 포트에서 스트리밍한다. 경로가 URL에 노출되지 않고
resolver(id 조회)를 통해서만 파일에 접근한다.
"""

from __future__ import annotations

import mimetypes
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AssetServer:
    """resolver: item_id -> 절대 경로 (모르는 id면 None)."""

    def __init__(self, resolver):
        self._resolver = resolver
        self._httpd: ThreadingHTTPServer | None = None
        self.port = 0

    def start(self) -> int:
        resolver = self._resolver

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (http.server 규약)
                if not self.path.startswith("/asset/"):
                    self.send_error(404)
                    return
                item_id = urllib.parse.unquote(self.path[len("/asset/"):])
                try:
                    path = resolver(item_id)
                except Exception:
                    path = None
                if not path or not os.path.isfile(path):
                    self.send_error(404)
                    return
                ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                except OSError:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                # 감시 폴더의 파일 교체가 즉시 반영되도록 캐시하지 않는다
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (ConnectionAbortedError, BrokenPipeError):
                    pass

            def log_message(self, *args):  # 콘솔 소음 제거
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self.port

    def url_for(self, item_id: str) -> str:
        return f"http://127.0.0.1:{self.port}/asset/{urllib.parse.quote(item_id, safe='')}"

    def stop(self) -> None:
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
