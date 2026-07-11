# -*- coding: utf-8 -*-
"""피커 라이브러리: 항목/폴더 JSON 영속 + 자산 캐시.

항목 dict 키: id, type(emoji|sticker|gif), name, keywords[], source_kind
(discord-cdn|local|folder), source_url, filename, animated, added_at,
use_count, last_used. 폴더 스캔 항목은 abs_path가 추가되고 영속되지 않는다.
"""

from __future__ import annotations

import json
import os
import time
import uuid

SUPPORTED_EXTS = (".png", ".gif", ".webp")
SCHEMA_VERSION = 1


def _now() -> float:
    return time.time()


class Library:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.assets_dir = os.path.join(data_dir, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
        self._items: dict[str, dict] = {}
        self._folders: list[dict] = []
        self._scan_cache: dict[str, tuple[tuple, list[dict]]] = {}
        self._load()

    # ---------- 영속 ----------
    def _lib_path(self) -> str:
        return os.path.join(self.data_dir, "library.json")

    def _folders_path(self) -> str:
        return os.path.join(self.data_dir, "folders.json")

    def _load(self) -> None:
        self._items = {}
        self._folders = []
        for path, apply in ((self._lib_path(), self._apply_lib),
                            (self._folders_path(), self._apply_folders)):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    apply(json.load(f))
            except (json.JSONDecodeError, OSError, KeyError, TypeError):
                try:  # 손상 파일은 백업하고 빈 상태로 시작
                    os.replace(path, path + ".bak")
                except OSError:
                    pass

    def _apply_lib(self, data: dict) -> None:
        items = {}
        for i in data.get("items", []):
            i.setdefault("convert_warning", False)  # 구버전 항목 하위호환
            items[i["id"]] = i
        self._items = items

    def _apply_folders(self, data: dict) -> None:
        self._folders = list(data.get("folders", []))

    def _save(self) -> None:
        self._atomic_write(self._lib_path(),
                           {"schema": SCHEMA_VERSION,
                            "items": list(self._items.values())})
        self._atomic_write(self._folders_path(),
                           {"schema": SCHEMA_VERSION, "folders": self._folders})

    @staticmethod
    def _atomic_write(path: str, obj: dict) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ---------- 항목 ----------
    def new_asset_filename(self, ext: str) -> str:
        return uuid.uuid4().hex[:12] + ext

    def add_item(self, type_, name, keywords, source_kind, source_url,
                 filename, animated, convert_warning=False) -> dict:
        item = {
            "id": uuid.uuid4().hex[:12], "type": type_, "name": name,
            "keywords": list(keywords or []), "source_kind": source_kind,
            "source_url": source_url, "filename": filename,
            "animated": bool(animated), "convert_warning": bool(convert_warning),
            "added_at": _now(), "use_count": 0, "last_used": 0,
        }
        self._items[item["id"]] = item
        self._save()
        return item

    def get(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def remove_item(self, item_id: str) -> None:
        item = self._items.pop(item_id, None)
        if item:
            try:
                os.remove(os.path.join(self.assets_dir, item["filename"]))
            except OSError:
                pass
            self._save()

    def touch(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item:
            return  # 폴더 항목 등은 무시
        item["use_count"] += 1
        item["last_used"] = _now()
        self._save()

    def items(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda i: i["name"].lower())

    def recent(self, limit: int = 16) -> list[dict]:
        used = [i for i in self._items.values() if i["last_used"] > 0]
        return sorted(used, key=lambda i: i["last_used"], reverse=True)[:limit]

    def asset_path(self, item: dict) -> str:
        if item.get("abs_path"):
            return item["abs_path"]
        return os.path.join(self.assets_dir, item["filename"])

    # ---------- 폴더 ----------
    def add_folder(self, path: str, default_type: str = "gif") -> None:
        ap = os.path.abspath(path)
        if any(f["path"] == ap for f in self._folders):
            return
        self._folders.append({"path": ap, "default_type": default_type})
        self._save()

    def remove_folder(self, path: str) -> None:
        ap = os.path.abspath(path)
        self._folders = [f for f in self._folders if f["path"] != ap]
        self._scan_cache.pop(ap, None)
        self._save()

    def folders(self) -> list[dict]:
        return list(self._folders)

    def scan_folders(self) -> list[dict]:
        out: list[dict] = []
        for folder in self._folders:
            path, dtype = folder["path"], folder["default_type"]
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                continue  # 소실 폴더는 건너뜀 (UI 회색 처리는 folders()의 exists로)
            names = [n for n in entries
                     if os.path.splitext(n)[1].lower() in SUPPORTED_EXTS]
            sig = (self._dir_sig(path), tuple(names))
            cached = self._scan_cache.get(path)
            if cached and cached[0] == sig:
                out.extend(cached[1])
                continue
            items = []
            for n in names:
                ap = os.path.join(path, n)
                stem, ext = os.path.splitext(n)
                items.append({
                    "id": "folder:" + ap, "type": dtype, "name": stem,
                    "keywords": [], "source_kind": "folder", "source_url": "",
                    "filename": n, "abs_path": ap,
                    "animated": ext.lower() == ".gif",
                    "added_at": 0, "use_count": 0, "last_used": 0,
                })
            self._scan_cache[path] = (sig, items)
            out.extend(items)
        return out

    @staticmethod
    def _dir_sig(path: str) -> float:
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return 0

    def all_display_items(self) -> list[dict]:
        return self.items() + self.scan_folders()

    # ---------- 검색 ----------
    # 정식 검색 책임(스펙 §3)은 여기 있다. 프런트엔드 app.js filtered()는
    # 타이핑 반응성을 위한 동일 규칙의 미러일 뿐이다.
    def search(self, query: str, type_: str | None = None) -> list[dict]:
        """이름·키워드 대소문자 무시 부분일치. 빈 쿼리면 type_ 필터만 적용."""
        items = self.all_display_items()
        if type_ is not None:
            items = [i for i in items if i["type"] == type_]
        q = (query or "").strip().lower()
        if not q:
            return items
        return [i for i in items
                if q in i["name"].lower()
                or any(q in k.lower() for k in i["keywords"])]
