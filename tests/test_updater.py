# -*- coding: utf-8 -*-
import hashlib
import io
import json
import os

from notro_app import updater


# ---------- version parse/compare ----------
def test_parse_version_strips_v_and_suffix():
    assert updater.parse_version("v2.1.0") == (2, 1, 0)
    assert updater.parse_version("2.2.0-beta1") == (2, 2, 0)


def test_is_newer_true_when_latest_greater():
    assert updater.is_newer("v2.3.0", "2.2.0") is True


def test_is_newer_false_when_equal_or_older():
    assert updater.is_newer("v2.2.0", "2.2.0") is False
    assert updater.is_newer("v2.0.0", "2.2.0") is False


# ---------- check_latest (NotroSetup.exe asset) ----------
def _fake_opener(payload):
    def _open(req, timeout=10):
        return io.BytesIO(json.dumps(payload).encode())
    return _open


def test_check_latest_parses_setup_asset():
    payload = {
        "tag_name": "v2.3.0",
        "assets": [
            {"name": "NotroSetup.exe", "browser_download_url": "https://x/NotroSetup.exe"},
            {"name": "NotroSetup.exe.sha256", "browser_download_url": "https://x/NotroSetup.exe.sha256"},
        ],
    }
    rel = updater.check_latest(opener=_fake_opener(payload))
    assert rel == {"tag": "v2.3.0", "exe_url": "https://x/NotroSetup.exe",
                   "sha256_url": "https://x/NotroSetup.exe.sha256"}


def test_check_latest_none_when_no_asset():
    payload = {"tag_name": "v2.3.0", "assets": []}
    assert updater.check_latest(opener=_fake_opener(payload)) is None


# ---------- download + SHA256 ----------
def test_download_and_verify_ok(tmp_path):
    exe_bytes = b"MZ fake setup payload"
    digest = hashlib.sha256(exe_bytes).hexdigest()

    def fake_dl(url, dest, timeout=60):
        data = exe_bytes if url.endswith(".exe") else (digest + "  NotroSetup.exe").encode()
        with open(dest, "wb") as f:
            f.write(data)

    rel = {"tag": "v2.3.0", "exe_url": "https://x/NotroSetup.exe",
           "sha256_url": "https://x/NotroSetup.exe.sha256"}
    out = updater.download_and_verify(rel, str(tmp_path), downloader=fake_dl)
    assert out and os.path.exists(out)
    assert os.path.basename(out) == "NotroSetup.exe"


def test_download_and_verify_rejects_bad_hash(tmp_path):
    def fake_dl(url, dest, timeout=60):
        data = b"real" if url.endswith(".exe") else hashlib.sha256(b"WRONG").hexdigest().encode()
        with open(dest, "wb") as f:
            f.write(data)

    rel = {"tag": "v2.3.0", "exe_url": "https://x/NotroSetup.exe",
           "sha256_url": "https://x/NotroSetup.exe.sha256"}
    assert updater.download_and_verify(rel, str(tmp_path), downloader=fake_dl) is None


def test_download_and_verify_none_without_sha(tmp_path):
    rel = {"tag": "v2.3.0", "exe_url": "https://x/NotroSetup.exe", "sha256_url": None}
    assert updater.download_and_verify(rel, str(tmp_path), downloader=lambda *a, **k: None) is None


# ---------- apply_and_restart (helper bat: wait → silent install → relaunch) ----------
def test_build_apply_bat_waits_and_installs_without_relaunch():
    """배치는 앱 종료를 기다린 뒤 silent 설치만 한다. 재실행은 인스톨러 [Run]이
    담당하므로 배치에 start가 없어야 한다 — 배치가 교체 중 exe를 조기 실행해
    'Failed to load Python DLL'이 나던 경합을 제거한다."""
    bat = updater.build_apply_bat(1234, r"C:\t\NotroSetup.exe")
    assert "1234" in bat
    assert "tasklist" in bat.lower()  # 앱 종료 대기
    assert r"C:\t\NotroSetup.exe" in bat
    assert "/VERYSILENT" in bat
    assert "start " not in bat.lower()  # 재실행은 인스톨러 [Run]이 담당


def test_apply_and_restart_writes_helper_bat_and_spawns_cmd(tmp_path):
    setup = str(tmp_path / "NotroSetup.exe")
    open(setup, "w").close()
    calls = []
    updater.apply_and_restart(setup, _spawn=lambda args, **k: calls.append(list(args)))
    assert calls and calls[0][0] == "cmd"
    bat = os.path.join(str(tmp_path), "apply_update.bat")
    assert os.path.exists(bat)
    with open(bat, encoding="utf-8") as f:
        content = f.read()
    assert "/VERYSILENT" in content
    assert "start " not in content.lower()


# ---------- UpdateChecker ----------
def test_check_once_calls_on_ready_when_newer(tmp_path):
    calls = []
    rel = {"tag": "v9.9.9", "exe_url": "u", "sha256_url": "s"}
    uc = updater.UpdateChecker(
        str(tmp_path), on_ready=lambda tag, exe: calls.append((tag, exe)),
        _check=lambda: rel,
        _download=lambda release, dest: os.path.join(dest, "NotroSetup.exe"))
    uc.check_once()
    assert calls == [("v9.9.9", os.path.join(str(tmp_path), "NotroSetup.exe"))]
    assert uc.ready_tag == "v9.9.9"


def test_check_once_skips_when_not_newer(tmp_path):
    uc = updater.UpdateChecker(
        str(tmp_path),
        on_ready=lambda *a: (_ for _ in ()).throw(AssertionError("should not fire")),
        _check=lambda: {"tag": "v0.0.1", "exe_url": "u", "sha256_url": "s"},
        _download=lambda *a, **k: None)
    uc.check_once()
    assert uc.ready_exe is None


def test_check_once_disabled_is_noop(tmp_path):
    uc = updater.UpdateChecker(
        str(tmp_path),
        on_ready=lambda *a: (_ for _ in ()).throw(AssertionError()),
        is_enabled=lambda: False,
        _check=lambda: (_ for _ in ()).throw(AssertionError("should not check")))
    uc.check_once()
