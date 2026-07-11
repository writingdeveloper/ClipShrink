# -*- coding: utf-8 -*-
"""반자동 자동 업데이터 (GitHub Releases + SHA256 검증 + 배치 자기교체).

frozen(exe)일 때만 실제 의미가 있다. 개발 실행에서는 app.py가 기동하지 않는다.
신규 의존성 없이 표준 라이브러리만 사용한다."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import urllib.request

from . import __version__

REPO = "writingdeveloper/Notro"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL = 24 * 3600
CREATE_NO_WINDOW = 0x08000000


def parse_version(s: str) -> tuple[int, ...]:
    """'v2.1.0' / '2.2.0-beta' → (2,1,0). 접두 v와 pre-release/build 접미사 무시."""
    s = s.lstrip("vV").split("-")[0].split("+")[0]
    out = []
    for p in s.split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out)


def is_newer(latest_tag: str, current: str) -> bool:
    return parse_version(latest_tag) > parse_version(current)


def check_latest(opener=urllib.request.urlopen, timeout: int = 10):
    """GitHub Releases 최신본 조회 → {tag, exe_url, sha256_url} 또는 None."""
    req = urllib.request.Request(
        API_LATEST,
        headers={"User-Agent": f"Notro/{__version__}",
                 "Accept": "application/vnd.github+json"})
    with opener(req, timeout=timeout) as r:
        data = json.load(r)
    tag = data.get("tag_name", "")
    exe_url = sha_url = None
    for a in data.get("assets", []):
        n = (a.get("name") or "").lower()
        if n == "notro.exe":
            exe_url = a.get("browser_download_url")
        elif n == "notro.exe.sha256":
            sha_url = a.get("browser_download_url")
    if not tag or not exe_url:
        return None
    return {"tag": tag, "exe_url": exe_url, "sha256_url": sha_url}


def _download(url: str, dest: str, timeout: int = 60) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": f"Notro/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_verify(release: dict, dest_dir: str, downloader=_download):
    """새 exe를 내려받아 SHA256을 검증한다. 검증 성공 시 경로, 아니면 None.
    sha256 자산이 없으면(구버전 릴리스) 자동 설치하지 않는다."""
    if not release.get("sha256_url"):
        return None
    os.makedirs(dest_dir, exist_ok=True)
    exe_path = os.path.join(dest_dir, "Notro.exe")
    sha_path = exe_path + ".sha256"
    downloader(release["exe_url"], exe_path)
    downloader(release["sha256_url"], sha_path)
    with open(sha_path, "r", encoding="utf-8", errors="ignore") as f:
        expected = f.read().split()[0].strip().lower()
    if _sha256(exe_path).lower() != expected:
        try:
            os.remove(exe_path)
        except OSError:
            pass
        return None
    return exe_path


def build_bat(pid: int, new_exe: str, target_exe: str) -> str:
    """실행 중 프로세스(pid) 종료 대기 → 백업 → 교체 → 재시작. 실패 시 .bak 롤백."""
    return f'''@echo off
:wait
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
  timeout /t 1 /nobreak >NUL
  goto wait
)
copy /Y "{target_exe}" "{target_exe}.bak" >NUL
move /Y "{new_exe}" "{target_exe}" >NUL
if errorlevel 1 (
  move /Y "{target_exe}.bak" "{target_exe}" >NUL
) else (
  del "{target_exe}.bak" >NUL 2>&1
)
start "" "{target_exe}"
del "%~f0"
'''


def apply_and_restart(new_exe: str, bat_dir: str) -> None:
    """배치 헬퍼를 만들어 실행하고 즉시 반환한다. 호출자가 앱을 종료하면
    배치가 종료를 감지해 교체·재시작한다."""
    os.makedirs(bat_dir, exist_ok=True)
    target = sys.executable
    bat = os.path.join(bat_dir, "apply_update.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(build_bat(os.getpid(), new_exe, target))
    subprocess.Popen(["cmd", "/c", bat], creationflags=CREATE_NO_WINDOW, close_fds=True)


class UpdateChecker(threading.Thread):
    """백그라운드로 시작 시 + interval마다 확인. 준비되면 on_ready(tag, exe) 호출.

    _check/_download는 테스트 주입용. 실제로는 check_latest / download_and_verify."""

    def __init__(self, dest_dir, on_ready, is_enabled=lambda: True,
                 interval=CHECK_INTERVAL, _check=None, _download=None):
        super().__init__(daemon=True)
        self.dest_dir = dest_dir
        self.on_ready = on_ready
        self.is_enabled = is_enabled
        self.interval = interval
        self._check = _check or check_latest
        self._download = _download or (lambda release, dest: download_and_verify(release, dest))
        self._stop = threading.Event()
        self.ready_exe = None
        self.ready_tag = None

    def check_once(self):
        if not self.is_enabled():
            return
        try:
            rel = self._check()
        except Exception:
            return
        if not rel or not is_newer(rel["tag"], __version__):
            return
        try:
            exe = self._download(rel, self.dest_dir)
        except Exception:
            exe = None
        if exe:
            self.ready_exe, self.ready_tag = exe, rel["tag"]
            self.on_ready(rel["tag"], exe)

    def run(self):
        while not self._stop.is_set():
            self.check_once()
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
