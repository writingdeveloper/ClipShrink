"""클립보드 순수 데이터 빌더 + 붙여넣기 전처리 테스트 (Win32 호출 없음)."""

import os
import random
import struct

from PIL import Image

from notro_app.clipboard_win import build_drop_data
from notro_app.picker.window import prepare_for_paste


def test_build_drop_data_layout():
    data = build_drop_data(r"C:\x\y.gif")
    # DROPFILES: pFiles=20, fWide=1
    pfiles, _, _, _, fwide = struct.unpack_from("<Iiiii", data)
    assert pfiles == 20 and fwide == 1
    body = data[20:].decode("utf-16-le")
    assert body == "C:\\x\\y.gif\0\0"


def test_prepare_small_file_passthrough(tmp_path):
    p = tmp_path / "s.png"
    Image.new("RGB", (8, 8)).save(p)
    path, warn = prepare_for_paste(str(p), 10_000_000, str(tmp_path))
    assert path == str(p) and warn is False


def test_prepare_oversize_static_gets_compressed(tmp_path):
    p = tmp_path / "big.png"
    img = Image.new("RGB", (900, 900))
    img.putdata([(random.randint(0, 255),) * 3 for _ in range(900 * 900)])
    img.save(p)
    limit = p.stat().st_size // 2
    path, warn = prepare_for_paste(str(p), limit, str(tmp_path))
    assert warn is False and path != str(p)
    assert os.path.getsize(path) <= limit


def test_prepare_oversize_gif_warns_and_passes_through(tmp_path):
    frames = [Image.new("P", (64, 64), i % 4) for i in range(30)]
    p = tmp_path / "big.gif"
    frames[0].save(p, format="GIF", save_all=True, append_images=frames[1:])
    path, warn = prepare_for_paste(str(p), 10, str(tmp_path))  # 10바이트 한도
    assert path == str(p) and warn is True


def test_prepare_missing_file_passthrough(tmp_path):
    path, warn = prepare_for_paste(str(tmp_path / "nope.png"), 100, str(tmp_path))
    assert warn is False
