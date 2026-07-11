"""Library: JSON 영속·CRUD·recent·폴더 스캔 (순수 파일시스템 — tmp_path)."""

import os
import time

from PIL import Image

from clipshrink_app.library import Library, SUPPORTED_EXTS


def make_lib(tmp_path):
    return Library(str(tmp_path / "data"))


def put_asset(lib, name="a.png"):
    p = os.path.join(lib.assets_dir, name)
    Image.new("RGB", (4, 4), (255, 0, 0)).save(p)
    return name


def test_supported_exts_contract():
    assert set(SUPPORTED_EXTS) == {".png", ".gif", ".webp"}


def test_add_get_persist_roundtrip(tmp_path):
    lib = make_lib(tmp_path)
    fn = put_asset(lib)
    item = lib.add_item("emoji", "smile", ["happy"], "discord-cdn",
                        "https://cdn.discordapp.com/emojis/1.png", fn, False)
    assert item["id"] and item["use_count"] == 0
    lib2 = Library(lib.data_dir)  # 재로드
    got = lib2.get(item["id"])
    assert got["name"] == "smile" and got["keywords"] == ["happy"]


def test_remove_item_deletes_asset(tmp_path):
    lib = make_lib(tmp_path)
    fn = put_asset(lib)
    item = lib.add_item("gif", "g", [], "local", "", fn, True)
    path = lib.asset_path(item)
    assert os.path.exists(path)
    lib.remove_item(item["id"])
    assert not os.path.exists(path)
    assert lib.get(item["id"]) is None


def test_touch_updates_recent_order(tmp_path):
    lib = make_lib(tmp_path)
    a = lib.add_item("emoji", "a", [], "local", "", put_asset(lib, "a.png"), False)
    b = lib.add_item("emoji", "b", [], "local", "", put_asset(lib, "b.png"), False)
    lib.touch(a["id"])
    time.sleep(0.01)
    lib.touch(b["id"])
    rec = lib.recent()
    assert [i["name"] for i in rec[:2]] == ["b", "a"]
    assert lib.get(a["id"])["use_count"] == 1


def test_recent_excludes_never_used(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "never", [], "local", "", put_asset(lib), False)
    assert lib.recent() == []


def test_folder_scan_lists_supported_exts_only(tmp_path):
    lib = make_lib(tmp_path)
    folder = tmp_path / "gifs"
    folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "x.png")
    Image.new("RGB", (4, 4)).save(folder / "y.gif")
    (folder / "note.txt").write_text("no")
    lib.add_folder(str(folder), "gif")
    items = lib.scan_folders()
    names = sorted(i["name"] for i in items)
    assert names == ["x", "y"]
    gif = next(i for i in items if i["name"] == "y")
    assert gif["id"].startswith("folder:") and gif["animated"] is True
    assert os.path.samefile(lib.asset_path(gif), folder / "y.gif")


def test_folder_scan_missing_folder_is_skipped(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_folder(str(tmp_path / "ghost"), "gif")
    assert lib.scan_folders() == []


def test_folder_scan_cache_invalidates_on_new_file(tmp_path):
    lib = make_lib(tmp_path)
    folder = tmp_path / "f"
    folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "1.png")
    lib.add_folder(str(folder), "sticker")
    assert len(lib.scan_folders()) == 1
    Image.new("RGB", (4, 4)).save(folder / "2.png")
    assert len(lib.scan_folders()) == 2


def test_corrupt_json_recovers_empty(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "a", [], "local", "", put_asset(lib), False)
    with open(os.path.join(lib.data_dir, "library.json"), "w") as f:
        f.write("{broken")
    lib2 = Library(lib.data_dir)
    assert lib2.items() == []
    assert os.path.exists(os.path.join(lib.data_dir, "library.json.bak"))


def test_all_display_items_merges(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "reg", [], "local", "", put_asset(lib), False)
    folder = tmp_path / "f"
    folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "z.webp")
    lib.add_folder(str(folder), "gif")
    kinds = {i["source_kind"] for i in lib.all_display_items()}
    assert kinds == {"local", "folder"}


def test_touch_folder_item_is_noop(tmp_path):
    lib = make_lib(tmp_path)
    lib.touch("folder:C:/nope/x.gif")  # 예외 없이 무시


def test_remove_folder_stops_scanning(tmp_path):
    lib = make_lib(tmp_path)
    folder = tmp_path / "f"
    folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "1.png")
    lib.add_folder(str(folder), "gif")
    assert len(lib.scan_folders()) == 1
    lib.remove_folder(str(folder))
    assert lib.scan_folders() == []
    assert lib.folders() == []


# ---------- search (스펙 §3: 검색 책임은 library.py) ----------
def test_search_matches_name(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "smile", [], "local", "", put_asset(lib, "a.png"), False)
    lib.add_item("emoji", "frown", [], "local", "", put_asset(lib, "b.png"), False)
    assert [i["name"] for i in lib.search("smi")] == ["smile"]


def test_search_matches_keyword(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "a", ["happy", "joy"], "local", "",
                 put_asset(lib, "a.png"), False)
    lib.add_item("emoji", "b", ["sad"], "local", "", put_asset(lib, "b.png"), False)
    assert [i["name"] for i in lib.search("joy")] == ["a"]


def test_search_is_case_insensitive(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "Smile", ["Happy"], "local", "",
                 put_asset(lib, "a.png"), False)
    assert [i["name"] for i in lib.search("smile")] == ["Smile"]
    assert [i["name"] for i in lib.search("HAP")] == ["Smile"]


def test_search_empty_query_returns_all(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "a", [], "local", "", put_asset(lib, "a.png"), False)
    folder = tmp_path / "f"
    folder.mkdir()
    Image.new("RGB", (4, 4)).save(folder / "z.gif")
    lib.add_folder(str(folder), "gif")
    assert len(lib.search("")) == 2  # all_display_items() 전체
    assert len(lib.search("   ")) == 2  # 공백만인 쿼리도 빈 쿼리로 취급


def test_search_type_filter(tmp_path):
    lib = make_lib(tmp_path)
    lib.add_item("emoji", "e", ["x"], "local", "", put_asset(lib, "a.png"), False)
    lib.add_item("gif", "g", ["x"], "local", "", put_asset(lib, "b.png"), False)
    assert [i["name"] for i in lib.search("", "emoji")] == ["e"]  # 빈 쿼리 + 타입
    assert [i["name"] for i in lib.search("x", "gif")] == ["g"]  # 쿼리 + 타입 동시
