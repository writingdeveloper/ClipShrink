# -*- coding: utf-8 -*-
import hashlib
import io
import json
import os

from notro_app import updater


# ---------- Task 1: version parse/compare ----------
def test_parse_version_strips_v_and_suffix():
    assert updater.parse_version("v2.1.0") == (2, 1, 0)
    assert updater.parse_version("2.2.0-beta1") == (2, 2, 0)


def test_is_newer_true_when_latest_greater():
    assert updater.is_newer("v2.2.0", "2.1.0") is True


def test_is_newer_false_when_equal_or_older():
    assert updater.is_newer("v2.1.0", "2.1.0") is False
    assert updater.is_newer("v2.0.0", "2.1.0") is False


# ---------- Task 2: check_latest ----------
def _fake_opener(payload):
    def _open(req, timeout=10):
        return io.BytesIO(json.dumps(payload).encode())
    return _open


def test_check_latest_parses_assets():
    payload = {
        "tag_name": "v2.2.0",
        "assets": [
            {"name": "Notro.exe", "browser_download_url": "https://x/Notro.exe"},
            {"name": "Notro.exe.sha256", "browser_download_url": "https://x/Notro.exe.sha256"},
        ],
    }
    rel = updater.check_latest(opener=_fake_opener(payload))
    assert rel == {"tag": "v2.2.0", "exe_url": "https://x/Notro.exe",
                   "sha256_url": "https://x/Notro.exe.sha256"}


def test_check_latest_none_when_no_exe():
    payload = {"tag_name": "v2.2.0", "assets": []}
    assert updater.check_latest(opener=_fake_opener(payload)) is None


# ---------- Task 3: download + SHA256 ----------
def test_download_and_verify_ok(tmp_path):
    exe_bytes = b"MZ fake exe payload"
    digest = hashlib.sha256(exe_bytes).hexdigest()

    def fake_dl(url, dest, timeout=60):
        data = exe_bytes if url.endswith(".exe") else (digest + "  Notro.exe").encode()
        with open(dest, "wb") as f:
            f.write(data)

    rel = {"tag": "v2.2.0", "exe_url": "https://x/Notro.exe",
           "sha256_url": "https://x/Notro.exe.sha256"}
    out = updater.download_and_verify(rel, str(tmp_path), downloader=fake_dl)
    assert out and os.path.exists(out)


def test_download_and_verify_rejects_bad_hash(tmp_path):
    def fake_dl(url, dest, timeout=60):
        data = b"real" if url.endswith(".exe") else hashlib.sha256(b"WRONG").hexdigest().encode()
        with open(dest, "wb") as f:
            f.write(data)

    rel = {"tag": "v2.2.0", "exe_url": "https://x/Notro.exe",
           "sha256_url": "https://x/Notro.exe.sha256"}
    assert updater.download_and_verify(rel, str(tmp_path), downloader=fake_dl) is None


def test_download_and_verify_none_without_sha(tmp_path):
    rel = {"tag": "v2.2.0", "exe_url": "https://x/Notro.exe", "sha256_url": None}
    assert updater.download_and_verify(rel, str(tmp_path), downloader=lambda *a, **k: None) is None


# ---------- Task 4: batch helper ----------
def test_build_bat_contains_pid_and_paths():
    bat = updater.build_bat(4321, r"C:\tmp\Notro.exe", r"C:\app\Notro.exe")
    assert "4321" in bat
    assert r"C:\tmp\Notro.exe" in bat
    assert r"C:\app\Notro.exe" in bat
    assert ".bak" in bat
    assert "start" in bat.lower()


# ---------- Task 5: UpdateChecker ----------
def test_check_once_calls_on_ready_when_newer(tmp_path):
    calls = []
    rel = {"tag": "v9.9.9", "exe_url": "u", "sha256_url": "s"}
    uc = updater.UpdateChecker(
        str(tmp_path), on_ready=lambda tag, exe: calls.append((tag, exe)),
        _check=lambda: rel,
        _download=lambda release, dest: os.path.join(dest, "Notro.exe"))
    uc.check_once()
    assert calls == [("v9.9.9", os.path.join(str(tmp_path), "Notro.exe"))]
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
