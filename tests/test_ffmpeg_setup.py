# -*- coding: utf-8 -*-
import os

import notro_app.ffmpeg_setup as fs


def test_prefers_downloaded_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))
    exe = tmp_path / "ffmpeg.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(fs.shutil, "which", lambda _: r"C:\other\ffmpeg.exe")
    assert fs.find_ffmpeg() == str(exe)          # 내려받은 것이 우선


def test_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))   # 비어 있음
    monkeypatch.setattr(fs.shutil, "which", lambda _: r"C:\sys\ffmpeg.exe")
    assert fs.find_ffmpeg() == r"C:\sys\ffmpeg.exe"


def test_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(fs.shutil, "which", lambda _: None)
    assert fs.find_ffmpeg() is None


def test_pick_wheel_selects_win_amd64_with_sha():
    data = {
        "info": {"version": "0.6.0"},
        "releases": {
            "0.6.0": [
                {"filename": "imageio_ffmpeg-0.6.0-py3-none-macosx.whl",
                 "url": "https://x/mac.whl", "digests": {"sha256": "aaa"}},
                {"filename": "imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl",
                 "url": "https://x/win.whl", "digests": {"sha256": "bbb"}},
            ]
        },
    }
    assert fs._pick_wheel(data) == ("https://x/win.whl", "bbb")


def test_pick_wheel_returns_none_when_no_windows_wheel():
    data = {"info": {"version": "1.0"},
            "releases": {"1.0": [{"filename": "x-1.0-py3-none-any.whl",
                                  "url": "u", "digests": {"sha256": "s"}}]}}
    assert fs._pick_wheel(data) is None


def test_pick_binary_finds_windows_exe():
    names = [
        "imageio_ffmpeg/__init__.py",
        "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.1",
        "imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe",
    ]
    assert fs._pick_binary(names) == "imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"


def test_pick_binary_returns_none_when_absent():
    assert fs._pick_binary(["a.py", "b.txt"]) is None


# --- download_ffmpeg 결함 주입: 백그라운드 스레드에서 절대 raise하지 않는다 -------
# download_ffmpeg()는 별도 스레드에서 돈다(app.py의 _work) — 여기서 예외가 새면
# 스레드가 조용히 죽어 진행 창이 영원히 멈춘다. 내부 어느 단계가 터지든 None을
# 돌려줘야 한다는 이 보장을 고정한다.

class _NullCtx:
    """urlopen(...)의 `with` 대상만 흉내낸다 — json.load()는 별도로 monkeypatch한다."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_ffmpeg_returns_none_when_pick_wheel_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *a, **k: _NullCtx())
    monkeypatch.setattr(fs.json, "load", lambda r: {"info": {}, "releases": {}})

    def boom(data):
        raise KeyError("malformed PyPI json")

    monkeypatch.setattr(fs, "_pick_wheel", boom)
    assert fs.download_ffmpeg() is None


def test_download_ffmpeg_returns_none_when_urlopen_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(fs.urllib.request, "urlopen", boom)
    assert fs.download_ffmpeg() is None


def test_download_ffmpeg_extraction_is_atomic_on_partial_write(tmp_path, monkeypatch):
    # Important 3 회귀: 압축 해제 도중 쓰기가 실패해도(디스크 꽉 참 등) 손상된
    # ffmpeg.exe가 남으면 안 된다 — find_ffmpeg()는 os.path.isfile만 확인하므로
    # 그걸 영구히 신뢰하게 되고, probe()가 매번 조용히 실패하는 영구 무응답 상태가 된다.
    monkeypatch.setattr(fs.config, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *a, **k: _NullCtx())
    monkeypatch.setattr(fs.json, "load", lambda r: {})
    monkeypatch.setattr(fs, "_pick_wheel", lambda data: ("https://x/win.whl", "deadbeef"))
    monkeypatch.setattr(fs, "_sha256", lambda path: "deadbeef")

    import zipfile as _zipfile
    zip_path = tmp_path / "_fake_wheel_source.zip"
    member = "imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
    with _zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(member, b"fake ffmpeg binary bytes")

    def fake_download(url, dest, on_progress=None):
        fs.shutil.copyfile(str(zip_path), dest)

    monkeypatch.setattr(fs, "_download", fake_download)

    def boom_copy(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(fs.shutil, "copyfileobj", boom_copy)

    assert fs.download_ffmpeg() is None
    assert not (tmp_path / "ffmpeg.exe").exists()
    assert not (tmp_path / "ffmpeg.exe.part").exists()
