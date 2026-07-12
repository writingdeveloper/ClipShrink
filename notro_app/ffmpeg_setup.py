# -*- coding: utf-8 -*-
"""ffmpeg 조달.

ffmpeg를 배포물에 넣지 않는다: (1) 설치 크기를 30MB 늘릴 이유가 없고,
(2) x264가 들어간 빌드는 GPL이라 배포 시 고지 의무가 생긴다. 사용자의 승인 아래
사용자 머신이 PyPI에서 받게 하면 두 문제가 모두 사라진다 — WebView2 부트스트래퍼와 같은 구조.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
import zipfile

from . import config

PYPI_JSON = "https://pypi.org/pypi/imageio-ffmpeg/json"
DOWNLOAD_MB = 30      # 사용자에게 보여줄 대략적인 크기


def find_ffmpeg() -> str | None:
    """내려받은 것 → 시스템 PATH 순으로 찾는다. 없으면 None."""
    local = os.path.join(config.BIN_DIR, "ffmpeg.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("ffmpeg")


def _pick_wheel(data: dict) -> tuple[str, str] | None:
    """PyPI JSON에서 최신 win_amd64 wheel의 (url, sha256)."""
    ver = data.get("info", {}).get("version")
    for f in data.get("releases", {}).get(ver, []):
        name = f.get("filename", "")
        if name.endswith(".whl") and "win_amd64" in name:
            return f["url"], f["digests"]["sha256"]
    return None


def _pick_binary(names: list[str]) -> str | None:
    """wheel(zip) 안에서 Windows용 ffmpeg 실행 파일 경로."""
    for n in names:
        if "/binaries/ffmpeg-win" in n and n.endswith(".exe"):
            return n
    return None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: str, on_progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Notro"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if on_progress and total:
                on_progress(done / total)


def download_ffmpeg(on_progress=None) -> str | None:
    """PyPI의 imageio-ffmpeg wheel을 받아 SHA256을 검증하고 ffmpeg.exe만 꺼낸다.
    실패하면 None (치명적이지 않다 — 압축 기능만 못 쓴다)."""
    try:
        with urllib.request.urlopen(PYPI_JSON, timeout=15) as r:
            data = json.load(r)
        picked = _pick_wheel(data)
        if not picked:
            return None
        url, sha = picked
    except Exception:
        return None

    tmp = os.path.join(config.BIN_DIR, "_ffmpeg_wheel.zip")
    try:
        os.makedirs(config.BIN_DIR, exist_ok=True)
        _download(url, tmp, on_progress)
        if _sha256(tmp).lower() != sha.lower():
            return None
        with zipfile.ZipFile(tmp) as z:
            member = _pick_binary(z.namelist())
            if not member:
                return None
            out = os.path.join(config.BIN_DIR, "ffmpeg.exe")
            with z.open(member) as src, open(out, "wb") as f:
                shutil.copyfileobj(src, f)
        return out
    except Exception:
        return None
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
