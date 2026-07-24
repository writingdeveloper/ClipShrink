# Clipboard Capture Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save clipboard screenshots into a dedicated picker collection through a one-click button or an opt-in automatic monitor, with persistent deduplication, clear UI feedback, full regression coverage, and a v2.7.0 release.

**Architecture:** Extend the existing stabilized clipboard `Monitor` instead of adding a competing watcher. A new thread-safe `CaptureStore` owns clipboard image normalization and content-hash deduplication; both the monitor and picker API use the same instance. Library/fetch changes add transactional collection-aware asset registration, while the picker exposes a dedicated button and an off-by-default setting.

**Tech Stack:** Python 3.10+, Pillow, ctypes Windows clipboard helpers, pywebview HTML/CSS/JavaScript, pytest, PyInstaller, Inno Setup, GitHub Actions.

## Global Constraints

- Automatic saving is off by default and stored as DWORD `auto_capture_save` under `HKCU\Software\Notro`.
- Automatic saving accepts registered PNG and `Image.Image` clipboard data but excludes `CF_HDROP` file lists.
- Captures are stored as `emoji` items in reserved collection ID `__notro_captures__`.
- Capture names use `capture-YYYYMMDD-HHMMSS-ffffff`.
- Deduplication uses SHA-256 of PNG bytes and persists in optional item field `content_hash`.
- Manual one-click save always targets the capture collection; existing Ctrl+V registration remains current-tab behavior.
- Automatic successes are silent; automatic failures use a localized tray notification.
- Existing clipboard sequence stabilization, Notro marker exclusion, compression guards, and file/video paths must remain intact.
- All new strings must exist in en, ko, ja, zh, and es with matching placeholders.
- No new pip dependency.
- Final release version is `2.7.0` and tag is `v2.7.0`.

---

### Task 1: Transactional, collection-aware library registration

**Files:**
- Modify: `notro_app/library.py`
- Modify: `notro_app/fetch.py`
- Modify: `tests/test_library.py`
- Modify: `tests/test_fetch.py`

**Interfaces:**
- Produces: `Library.find_by_content_hash(content_hash: str, type_: str, collection: str) -> dict | None`
- Produces: `Library.add_item(..., collection: str = "", content_hash: str = "") -> dict`
- Produces: `fetch.register_from_png_bytes(..., collection: str = "", content_hash: str = "") -> dict`
- Produces: `_finalize_asset(library, tmp_path: str, ext: str, collection: str = "") -> tuple[str, bool, bool]`

- [ ] **Step 1: Write failing library metadata tests**

Append tests proving backward-compatible hash persistence, filtered lookup, and rollback:

```python
def test_content_hash_persists_and_is_searchable(tmp_path):
    lib = make_lib(tmp_path)
    item = lib.add_item("emoji", "cap", [], "local", "",
                        put_asset(lib, "cap.png", "__notro_captures__"), False,
                        collection="__notro_captures__", content_hash="abc123")
    lib2 = Library(lib.data_dir)
    assert lib2.get(item["id"])["content_hash"] == "abc123"
    assert lib2.find_by_content_hash("abc123", "emoji", "__notro_captures__")["id"] == item["id"]
    assert lib2.find_by_content_hash("abc123", "sticker", "__notro_captures__") is None


def test_apply_lib_backfills_content_hash(tmp_path):
    lib = make_lib(tmp_path)
    item = lib.add_item("emoji", "old", [], "local", "", put_asset(lib), False)
    del item["content_hash"]
    lib._save()
    assert Library(lib.data_dir).get(item["id"])["content_hash"] == ""


def test_add_item_rolls_back_memory_when_save_fails(tmp_path, monkeypatch):
    lib = make_lib(tmp_path)
    monkeypatch.setattr(lib, "_save", lambda: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        lib.add_item("emoji", "x", [], "local", "", "x.png", False)
    assert lib.items() == []
```

Add `import pytest` to `tests/test_library.py`.

- [ ] **Step 2: Run the library tests and verify RED**

Run: `python -m pytest tests/test_library.py -q`

Expected: failures for the missing `content_hash` argument/method and failed rollback assertion.

- [ ] **Step 3: Implement metadata and rollback support**

In `_apply_lib`, add `i.setdefault("content_hash", "")`. Extend `add_item` and make in-memory mutation rollback when `_save()` fails:

```python
def add_item(self, type_, name, keywords, source_kind, source_url,
             filename, animated, convert_warning=False,
             favorite=False, collection="", content_hash="") -> dict:
    item = {
        "id": uuid.uuid4().hex[:12], "type": type_, "name": name,
        "keywords": list(keywords or []), "source_kind": source_kind,
        "source_url": source_url, "filename": filename,
        "animated": bool(animated), "convert_warning": bool(convert_warning),
        "favorite": bool(favorite), "collection": collection or "",
        "content_hash": content_hash or "",
        "added_at": _now(), "use_count": 0, "last_used": 0,
    }
    with self._lock:
        self._items[item["id"]] = item
        try:
            self._save()
        except Exception:
            self._items.pop(item["id"], None)
            raise
    return item

def find_by_content_hash(self, content_hash: str, type_: str,
                         collection: str) -> dict | None:
    with self._lock:
        return next((i for i in self._items.values()
                     if i.get("content_hash") == content_hash
                     and i["type"] == type_
                     and i.get("collection", "") == collection), None)
```

- [ ] **Step 4: Run the library tests and verify GREEN**

Run: `python -m pytest tests/test_library.py -q`

Expected: all library tests pass.

- [ ] **Step 5: Write failing fetch tests**

Add tests that pass a collection/hash and force metadata failure:

```python
def test_register_png_bytes_writes_directly_to_collection(tmp_path):
    lib = Library(str(tmp_path / "d"))
    item = fetch.register_from_png_bytes(
        lib, png_bytes(), "emoji", name="capture",
        collection="__notro_captures__", content_hash="hash1")
    assert item["collection"] == "__notro_captures__"
    assert item["content_hash"] == "hash1"
    assert os.path.dirname(lib.asset_path(item)).endswith("__notro_captures__")
    assert os.path.exists(lib.asset_path(item))


def test_register_png_bytes_removes_asset_when_metadata_save_fails(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monkeypatch.setattr(lib, "add_item",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("json")))
    with pytest.raises(OSError):
        fetch.register_from_png_bytes(
            lib, png_bytes(), "emoji", collection="__notro_captures__")
    assert list((tmp_path / "d" / "assets" / "__notro_captures__").glob("*")) == []
```

Import `pytest` where needed and reuse the existing PNG helper in `tests/test_fetch.py`.

- [ ] **Step 6: Run fetch tests and verify RED**

Run: `python -m pytest tests/test_fetch.py -q`

Expected: missing keyword argument failures.

- [ ] **Step 7: Implement collection-aware transactional registration**

Pass `collection` into `library.collection_dir(collection)` from `_finalize_asset`. Extend `register_from_png_bytes`, then delete the finalized asset if `add_item` raises:

```python
def register_from_png_bytes(library, data: bytes, type_: str,
                            name: str = "", keywords=None, collection: str = "",
                            content_hash: str = "") -> dict:
    tmp = os.path.join(library.assets_dir, "_pb" + library.new_asset_filename(".png"))
    filename = ""
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        filename, animated, convert_failed = _finalize_asset(
            library, tmp, ".png", collection)
        try:
            return library.add_item(
                type_, name, keywords or [], "local", "", filename, animated,
                convert_failed, collection=collection, content_hash=content_hash)
        except Exception:
            if filename:
                try:
                    os.remove(os.path.join(library.collection_dir(collection), filename))
                except OSError:
                    pass
            raise
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
```

Keep URL/file registration defaults unchanged by giving `_finalize_asset` a default empty collection.

- [ ] **Step 8: Run focused and combined tests**

Run: `python -m pytest tests/test_library.py tests/test_fetch.py tests/test_picker_clipboard.py -q`

Expected: all pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add notro_app/library.py notro_app/fetch.py tests/test_library.py tests/test_fetch.py
git commit -m "feat(library): add transactional capture metadata"
```

---

### Task 2: Thread-safe capture reading and deduplicated storage

**Files:**
- Create: `notro_app/capture_store.py`
- Create: `tests/test_capture_store.py`

**Interfaces:**
- Produces: `CAPTURE_COLLECTION_ID: str = "__notro_captures__"`
- Produces: `CaptureReadResult(data: bytes | None, error: str | None)`
- Produces: `CaptureSaveResult(ok: bool, duplicate: bool = False, item_id: str = "", error: str | None = None)`
- Produces: `image_to_png_bytes(image: Image.Image) -> bytes`
- Produces: `read_clipboard_png() -> CaptureReadResult`
- Produces: `CaptureStore.save_png(data: bytes) -> CaptureSaveResult`
- Produces: `CaptureStore.read_and_save() -> CaptureSaveResult`

- [ ] **Step 1: Write failing clipboard-read tests**

Create tests for registered PNG priority, bitmap fallback, file exclusion, and read failure:

```python
def test_read_prefers_registered_png(monkeypatch):
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: b"raw-png")
    monkeypatch.setattr(cs.ImageGrab, "grabclipboard",
                        lambda: (_ for _ in ()).throw(AssertionError("unused")))
    assert cs.read_clipboard_png() == cs.CaptureReadResult(b"raw-png", None)


def test_read_converts_bitmap_to_png(monkeypatch):
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(cs.ImageGrab, "grabclipboard",
                        lambda: Image.new("RGB", (3, 2), "red"))
    result = cs.read_clipboard_png()
    assert result.error is None
    with Image.open(io.BytesIO(result.data)) as image:
        assert image.format == "PNG" and image.size == (3, 2)


def test_read_excludes_file_list(monkeypatch):
    monkeypatch.setattr(cs.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(cs.ImageGrab, "grabclipboard", lambda: [r"C:\x.png"])
    assert cs.read_clipboard_png() == cs.CaptureReadResult(None, "no_image")


def test_read_reports_clipboard_failure(monkeypatch):
    monkeypatch.setattr(cs.cb, "get_clipboard_png",
                        lambda: (_ for _ in ()).throw(OSError("busy")))
    monkeypatch.setattr(cs.ImageGrab, "grabclipboard",
                        lambda: (_ for _ in ()).throw(OSError("busy")))
    assert cs.read_clipboard_png() == cs.CaptureReadResult(None, "read")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_capture_store.py -q`

Expected: import error because `notro_app.capture_store` does not exist.

- [ ] **Step 3: Implement read result and bitmap normalization**

Create the module with frozen dataclasses and `io.BytesIO`. `read_clipboard_png()` must try registered PNG, then `ImageGrab`, returning `read` only if clipboard APIs raised and no image was recovered.

- [ ] **Step 4: Run read tests and verify GREEN**

Run: `python -m pytest tests/test_capture_store.py -q`

Expected: four read tests pass.

- [ ] **Step 5: Add failing save/dedup/concurrency tests**

```python
def test_save_places_capture_in_reserved_collection(tmp_path):
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)
    result = store.save_png(png_bytes())
    item = lib.get(result.item_id)
    assert result.ok and not result.duplicate
    assert item["type"] == "emoji"
    assert item["collection"] == cs.CAPTURE_COLLECTION_ID
    assert item["name"].startswith("capture-")
    assert item["content_hash"] == hashlib.sha256(png_bytes()).hexdigest()


def test_save_same_png_returns_existing_item(tmp_path):
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)
    first = store.save_png(png_bytes())
    second = store.save_png(png_bytes())
    assert second == cs.CaptureSaveResult(True, True, first.item_id, None)
    assert len(lib.items()) == 1


def test_concurrent_save_creates_one_item(tmp_path):
    lib = Library(str(tmp_path / "d"))
    store = cs.CaptureStore(lib)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.save_png(png_bytes()), range(8)))
    assert len(lib.items()) == 1
    assert sum(not r.duplicate for r in results) == 1


def test_read_and_save_preserves_read_error(tmp_path, monkeypatch):
    store = cs.CaptureStore(Library(str(tmp_path / "d")))
    monkeypatch.setattr(cs, "read_clipboard_png",
                        lambda: cs.CaptureReadResult(None, "read"))
    assert store.read_and_save() == cs.CaptureSaveResult(False, error="read")
```

- [ ] **Step 6: Run save tests and verify RED**

Run: `python -m pytest tests/test_capture_store.py -q`

Expected: missing `CaptureStore` and save result failures.

- [ ] **Step 7: Implement locked hash deduplication**

Use a `threading.Lock`, SHA-256, and microsecond timestamp inside the lock:

```python
def save_png(self, data: bytes) -> CaptureSaveResult:
    if not data:
        return CaptureSaveResult(False, error="no_image")
    digest = hashlib.sha256(data).hexdigest()
    with self._lock:
        existing = self._library.find_by_content_hash(
            digest, "emoji", CAPTURE_COLLECTION_ID)
        if existing:
            return CaptureSaveResult(True, True, existing["id"], None)
        name = datetime.now().strftime("capture-%Y%m%d-%H%M%S-%f")
        try:
            item = fetch.register_from_png_bytes(
                self._library, data, "emoji", name=name,
                collection=CAPTURE_COLLECTION_ID, content_hash=digest)
        except Exception:
            return CaptureSaveResult(False, error="register")
        return CaptureSaveResult(True, False, item["id"], None)
```

- [ ] **Step 8: Run capture store tests and full focused regression**

Run: `python -m pytest tests/test_capture_store.py tests/test_library.py tests/test_fetch.py tests/test_picker_clipboard.py -q`

Expected: all pass.

- [ ] **Step 9: Commit Task 2**

```powershell
git add notro_app/capture_store.py tests/test_capture_store.py
git commit -m "feat(capture): add deduplicated clipboard storage"
```

---

### Task 3: Extend Monitor without regressing compression races

**Files:**
- Modify: `notro_app/monitor.py`
- Create: `tests/test_monitor_capture.py`
- Modify: `tests/test_monitor_races.py`

**Interfaces:**
- Consumes: `image_to_png_bytes(image: Image.Image) -> bytes`
- Produces: `Monitor.capture_enabled: Callable[[], bool] | None`
- Produces: `Monitor.on_capture_image: Callable[[bytes], object] | None`
- Produces: `Monitor._emit_capture(data: bytes) -> None`

- [ ] **Step 1: Write failing Monitor callback tests**

Tests must cover small registered PNG before the existing size early return, bitmap normalization, disabled setting, file list exclusion, and exception isolation:

```python
def configured_monitor(monkeypatch):
    monkeypatch.setattr(mon.cb, "get_sequence_number", lambda: 7)
    monkeypatch.setattr(mon.cb, "clipboard_has_marker", lambda: False)
    m = Monitor()
    m.capture_enabled = lambda: True
    m.captured = []
    m.on_capture_image = m.captured.append
    return m


def test_small_registered_png_emits_capture(monkeypatch):
    m = configured_monitor(monkeypatch)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png_bytes())
    m.process_clipboard()
    assert m.captured == [png_bytes()]
    assert m.history == []


def test_bitmap_emits_normalized_png(monkeypatch):
    m = configured_monitor(monkeypatch)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(mon.ImageGrab, "grabclipboard",
                        lambda: Image.new("RGB", (4, 4), "blue"))
    m.process_clipboard()
    assert len(m.captured) == 1 and m.captured[0].startswith(b"\x89PNG")


def test_file_list_does_not_emit_capture(monkeypatch, tmp_path):
    m = configured_monitor(monkeypatch)
    path = tmp_path / "x.png"
    Image.new("RGB", (2, 2)).save(path)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: None)
    monkeypatch.setattr(mon.ImageGrab, "grabclipboard", lambda: [str(path)])
    m.process_clipboard()
    assert m.captured == []


def test_disabled_capture_does_not_emit(monkeypatch):
    m = configured_monitor(monkeypatch)
    m.capture_enabled = lambda: False
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: png_bytes())
    m.process_clipboard()
    assert m.captured == []


def test_capture_callback_failure_does_not_block_compression(monkeypatch, tmp_path):
    m = configured_monitor(monkeypatch)
    m.on_capture_image = lambda data: (_ for _ in ()).throw(RuntimeError("save"))
    large = png_bytes(size=(2200, 2200), noisy=True)
    monkeypatch.setattr(mon.cb, "get_clipboard_png", lambda: large)
    monkeypatch.setattr(mon.config, "LIMIT_BYTES", 1024)
    monkeypatch.setattr(mon.config, "TEMP_DIR", str(tmp_path))
    replaced = []
    monkeypatch.setattr(mon.cb, "set_clipboard_file",
                        lambda path, guard_seq=None: replaced.append(path) or True)
    m.process_clipboard()
    assert replaced
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_monitor_capture.py -q`

Expected: missing Monitor capture attributes/behavior.

- [ ] **Step 3: Implement `_emit_capture` and call sites**

Initialize both callbacks to `None`. `_emit_capture` checks the setting callable and callback, catches exceptions, and never mutates the clipboard. Call it once immediately after reading registered PNG. For `Image.Image`, call it with `image_to_png_bytes(img)` before size estimation. Do not call it in the list branch.

- [ ] **Step 4: Run new tests and race regression**

Run: `python -m pytest tests/test_monitor_capture.py tests/test_monitor_races.py tests/test_monitor.py tests/test_monitor_video.py -q`

Expected: all pass, including guard-sequence and mid-write tests.

- [ ] **Step 5: Commit Task 3**

```powershell
git add notro_app/monitor.py tests/test_monitor_capture.py tests/test_monitor_races.py
git commit -m "feat(monitor): emit clipboard captures for opt-in storage"
```

---

### Task 4: Wire CaptureStore and expose picker API/settings contracts

**Files:**
- Modify: `notro_app/app.py`
- Modify: `notro_app/picker/window.py`
- Modify: `tests/test_picker_clipboard.py`
- Create: `tests/test_app_capture_wiring.py`

**Interfaces:**
- Consumes: one shared `CaptureStore`
- Produces: `PickerApi(..., capture_store=None)`
- Produces: `PickerApi.register_capture() -> dict`
- Produces: `PickerApi.set_auto_capture_save(enabled: bool) -> bool`
- Produces: state keys `auto_capture_save: bool`, `capture_collection: str`
- Changes: `register_files()` returns `{ok, count, failed}`

- [ ] **Step 1: Write failing PickerApi tests**

Use a fake store returning real dataclasses:

```python
def test_register_capture_returns_new_item(tmp_path):
    lib = Library(str(tmp_path / "d"))
    store = Mock()
    store.read_and_save.return_value = CaptureSaveResult(True, False, "item1", None)
    api = window.PickerApi(library=lib, capture_store=store)
    assert api.register_capture() == {
        "ok": True, "duplicate": False, "item_id": "item1",
        "collection": CAPTURE_COLLECTION_ID,
    }


@pytest.mark.parametrize("error", ["no_image", "read", "register"])
def test_register_capture_preserves_error(tmp_path, error):
    store = Mock()
    store.read_and_save.return_value = CaptureSaveResult(False, error=error)
    api = window.PickerApi(library=Library(str(tmp_path / "d")), capture_store=store)
    assert api.register_capture() == {"ok": False, "error": error}


def test_auto_capture_setting_defaults_off_and_persists(tmp_path, monkeypatch):
    values = {}
    monkeypatch.setattr(window.config, "get_setting_flag", lambda key: values.get(key, False))
    monkeypatch.setattr(window.config, "set_setting_flag",
                        lambda key, value=True: values.__setitem__(key, bool(value)))
    api = window.PickerApi(library=Library(str(tmp_path / "d")), asset_server=FakeServer())
    assert api.get_state()["auto_capture_save"] is False
    assert api.set_auto_capture_save(True) is True
    assert values["auto_capture_save"] is True


def test_register_files_reports_failures(tmp_path, monkeypatch):
    api = window.PickerApi(library=Library(str(tmp_path / "d")))
    monkeypatch.setattr(fetch, "register_from_file",
                        lambda lib, path, type_: (_ for _ in ()).throw(ValueError(path))
                        if path == "bad" else {"id": path})
    assert api.register_files(["good", "bad"], "emoji") == {
        "ok": True, "count": 1, "failed": 1,
    }
```

- [ ] **Step 2: Run API tests and verify RED**

Run: `python -m pytest tests/test_picker_clipboard.py -q`

Expected: missing constructor parameter/method/state keys.

- [ ] **Step 3: Implement PickerApi contracts**

Store the capture service in a private `_capture_store` attribute. Convert `CaptureSaveResult` to plain dictionaries exactly as tested. Add `auto_capture_save` and `capture_collection` to state. Keep the old `register_clipboard(type_)`, but read through `read_clipboard_png()` so bitmap-only captures work and return `read` separately from `no_image`.

- [ ] **Step 4: Run API tests and verify GREEN**

Run: `python -m pytest tests/test_picker_clipboard.py -q`

Expected: all pass.

- [ ] **Step 5: Write failing app wiring test**

Extract a small testable helper rather than invoking the full GUI:

```python
def test_configure_capture_storage_wires_shared_store(tmp_path, monkeypatch):
    lib = Library(str(tmp_path / "d"))
    monitor = SimpleNamespace(capture_enabled=None, on_capture_image=None, notifications=[])
    monitor.notify = lambda title, message: monitor.notifications.append((title, message))
    monkeypatch.setattr(config, "get_setting_flag", lambda key: key == "auto_capture_save")
    store = configure_capture_storage(monitor, lib)
    assert monitor.capture_enabled() is True
    store.save_png = lambda data: CaptureSaveResult(True, False, "x", None)
    monitor.on_capture_image(b"png")
    assert monitor.notifications == []
```

Add a failure case asserting `notify_capture_save_fail` is sent only for `ok=False`.

- [ ] **Step 6: Implement `configure_capture_storage(monitor, library)` and app startup order**

Create Library and CaptureStore before starting the Monitor thread, even when WebView2 is unavailable. Pass the same store to `PickerApi`. The helper returns the store and wires callbacks without importing GUI modules.

- [ ] **Step 7: Run API/wiring/full app-adjacent tests**

Run: `python -m pytest tests/test_picker_clipboard.py tests/test_app_capture_wiring.py tests/test_monitor_capture.py -q`

Expected: all pass.

- [ ] **Step 8: Commit Task 4**

```powershell
git add notro_app/app.py notro_app/picker/window.py tests/test_picker_clipboard.py tests/test_app_capture_wiring.py
git commit -m "feat(picker-api): wire capture storage and settings"
```

---

### Task 5: Add the dedicated capture button, settings switch, and honest UI feedback

**Files:**
- Modify: `notro_app/picker/ui/index.html`
- Modify: `notro_app/picker/ui/app.js`
- Modify: `notro_app/picker/ui/app.css`
- Modify: `notro_app/i18n.py`
- Modify: `notro_app/picker/window.py`
- Modify: `tests/test_i18n.py`
- Create: `tests/test_picker_ui_contract.py`

**Interfaces:**
- Consumes: `register_capture`, `set_auto_capture_save`, `capture_collection`, `auto_capture_save`
- Produces DOM IDs: `btn-capture`, `st-auto-capture`, `st-auto-capture-note`, `st-folders-subtitle`
- Produces i18n keys listed below

- [ ] **Step 1: Write failing DOM/JavaScript contract tests**

```python
UI_DIR = Path(__file__).parents[1] / "notro_app" / "picker" / "ui"


def test_capture_button_and_auto_setting_exist():
    html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    for dom_id in ("btn-capture", "st-auto-capture", "st-auto-capture-note",
                   "st-folders-subtitle"):
        assert f'id="{dom_id}"' in html


def test_capture_ui_calls_backend_and_selects_reserved_collection():
    js = (UI_DIR / "app.js").read_text(encoding="utf-8")
    assert "api().register_capture()" in js
    assert "state.collection = res.collection" in js
    assert "api().set_auto_capture_save" in js


def test_paste_attempts_backend_without_blocking_text_paste():
    js = (UI_DIR / "app.js").read_text(encoding="utf-8")
    assert "const hasImage" in js
    assert "if (hasImage) e.preventDefault()" in js
    assert "register_clipboard(state.tab)" in js


def test_drop_feedback_checks_failed_count():
    js = (UI_DIR / "app.js").read_text(encoding="utf-8")
    assert "res.failed" in js
```

- [ ] **Step 2: Add failing i18n parity/key tests**

Add this exact required-key set:

```python
CAPTURE_KEYS = {
    "picker_capture_add", "picker_capture_saved", "picker_capture_duplicate",
    "picker_capture_no_image", "picker_capture_read_error",
    "picker_capture_register_error", "picker_capture_collection",
    "picker_auto_capture", "picker_auto_capture_note",
    "notify_capture_save_fail", "picker_settings_title",
    "picker_folders_subtitle", "picker_drop_partial", "picker_drop_failed",
}

def test_capture_keys_exist_in_all_languages():
    for lang in i18n.SUPPORTED_LANGS:
        assert CAPTURE_KEYS <= set(i18n.STRINGS[lang])
```

- [ ] **Step 3: Run UI/i18n tests and verify RED**

Run: `python -m pytest tests/test_picker_ui_contract.py tests/test_i18n.py -q`

Expected: missing DOM IDs, JS calls, and string keys.

- [ ] **Step 4: Add exact localized strings**

Use these translations:

| Key | en | ko | ja | zh | es |
|---|---|---|---|---|---|
| `picker_capture_add` | Add clipboard image | 클립보드 이미지 추가 | クリップボード画像を追加 | 添加剪贴板图片 | Añadir imagen del portapapeles |
| `picker_capture_saved` | Capture saved. | 캡처를 저장했습니다. | キャプチャを保存しました。 | 已保存截图。 | Captura guardada. |
| `picker_capture_duplicate` | This capture is already saved. | 이미 저장된 캡처입니다. | このキャプチャは保存済みです。 | 此截图已保存。 | Esta captura ya está guardada. |
| `picker_capture_no_image` | No image is available in the clipboard. | 클립보드에 저장할 이미지가 없습니다. | クリップボードに画像がありません。 | 剪贴板中没有可保存的图片。 | No hay ninguna imagen en el portapapeles. |
| `picker_capture_read_error` | Couldn't read the clipboard. Try again. | 클립보드를 읽지 못했습니다. 다시 시도하세요. | クリップボードを読み取れませんでした。再試行してください。 | 无法读取剪贴板，请重试。 | No se pudo leer el portapapeles. Inténtalo de nuevo. |
| `picker_capture_register_error` | Couldn't save the capture. | 캡처를 저장하지 못했습니다. | キャプチャを保存できませんでした。 | 无法保存截图。 | No se pudo guardar la captura. |
| `picker_capture_collection` | Captures | 캡처 | キャプチャ | 截图 | Capturas |
| `picker_auto_capture` | Automatically save new clipboard images | 새 클립보드 이미지 자동 저장 | 新しいクリップボード画像を自動保存 | 自动保存新的剪贴板图片 | Guardar automáticamente imágenes nuevas |
| `picker_auto_capture_note` | Off by default. Copied image files are excluded. | 기본적으로 꺼져 있습니다. 복사한 이미지 파일은 제외됩니다. | 初期設定はオフです。コピーした画像ファイルは除外されます。 | 默认关闭。复制的图片文件不会保存。 | Desactivado de forma predeterminada. Se excluyen los archivos de imagen copiados. |
| `notify_capture_save_fail` | Couldn't automatically save the clipboard image. | 클립보드 이미지를 자동 저장하지 못했습니다. | クリップボード画像を自動保存できませんでした。 | 无法自动保存剪贴板图片。 | No se pudo guardar automáticamente la imagen del portapapeles. |
| `picker_settings_title` | Picker settings | 피커 설정 | ピッカー設定 | 选择器设置 | Ajustes del selector |
| `picker_folders_subtitle` | Watched folders | 감시 폴더 | 監視フォルダー | 监视文件夹 | Carpetas vigiladas |
| `picker_drop_partial` | Added {count}; {failed} failed. | {count}개 추가, {failed}개 실패했습니다. | {count}件追加、{failed}件失敗しました。 | 已添加 {count} 个，{failed} 个失败。 | Se añadieron {count}; fallaron {failed}. |
| `picker_drop_failed` | No files could be added. | 파일을 추가하지 못했습니다. | ファイルを追加できませんでした。 | 无法添加文件。 | No se pudo añadir ningún archivo. |

Add all keys to `PICKER_STRING_KEYS`.

- [ ] **Step 5: Implement HTML and CSS**

Place `btn-capture` before `btn-add`. In the settings modal, change the main heading to `st-title`, add a labeled native checkbox and explanatory paragraph, then add `st-folders-subtitle` before the existing folder list. Style the setting row with existing panel/radius tokens and visible focus behavior; keep the 500×420 window and avoid new dependencies.

- [ ] **Step 6: Implement JS state and result feedback**

Add `captureCollection`, `autoCaptureSave`, and localized collection labels to state. Implement:

```javascript
async function addCapture() {
  if (!api()) return;
  const res = await api().register_capture();
  if (res.ok) {
    state.collection = res.collection;
    flashHint(res.duplicate ? "picker_capture_duplicate" : "picker_capture_saved");
    await refresh();
    state.collection = res.collection;
    renderRail();
    render();
    return;
  }
  const key = {
    no_image: "picker_capture_no_image",
    read: "picker_capture_read_error",
    register: "picker_capture_register_error",
  }[res.error] || "picker_capture_register_error";
  flashHint(key);
}
```

Wire the checkbox with `change`, preserve text paste by preventing default only when `hasImage`, and show partial/full drop failures from `res.failed`.

- [ ] **Step 7: Run UI and i18n tests and verify GREEN**

Run: `python -m pytest tests/test_picker_ui_contract.py tests/test_i18n.py tests/test_picker_clipboard.py -q`

Expected: all pass.

- [ ] **Step 8: Render and inspect picker UI**

Open `notro_app/picker/ui/index.html` in the in-app browser or run the existing pywebview development entry point. Verify at 500×420: no clipping, button order matches the approved A mockup, settings content fits, focus ring is visible, and English/Korean long strings do not overflow.

- [ ] **Step 9: Commit Task 5**

```powershell
git add notro_app/picker/ui/index.html notro_app/picker/ui/app.js notro_app/picker/ui/app.css notro_app/i18n.py notro_app/picker/window.py tests/test_i18n.py tests/test_picker_ui_contract.py
git commit -m "feat(picker-ui): add one-click capture storage"
```

---

### Task 6: Update release documentation and version

**Files:**
- Modify: `notro_app/__init__.py`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `README.ja.md`
- Modify: `README.zh.md`
- Modify: `README.es.md`
- Modify: `tests/test_i18n.py` only if version documentation adds no test elsewhere

**Interfaces:**
- Produces: `notro_app.__version__ == "2.7.0"`

- [ ] **Step 1: Write a failing release metadata assertion**

Add to an appropriate version test or `tests/test_i18n.py`:

```python
def test_release_version_is_2_7_0():
    import notro_app
    assert notro_app.__version__ == "2.7.0"
```

- [ ] **Step 2: Run it and verify RED**

Run: `python -m pytest tests/test_i18n.py::test_release_version_is_2_7_0 -q`

Expected: `2.6.1 != 2.7.0`.

- [ ] **Step 3: Update version and changelog**

Set `__version__ = "2.7.0"`. Add `## [2.7.0] - 2026-07-23` with:

- Added: one-click clipboard capture button and off-by-default automatic capture collection.
- Changed: capture collection localization, bitmap fallback, file-drop result feedback.
- Fixed: hidden/unreliable paste-only discovery and silent all-file registration failure.

- [ ] **Step 4: Update all five READMEs**

In each picker registration section, state that the clipboard button saves the current image to the Captures collection, Ctrl+V remains available, automatic saving can be enabled in picker settings, it is off by default, and copied image files are excluded from automatic saving.

- [ ] **Step 5: Run release metadata test and docs consistency checks**

Run:

```powershell
python -m pytest tests/test_i18n.py -q
rg -n "2\.7\.0|auto.*save|자동 저장|自動保存|自动保存|automáticamente" CHANGELOG.md README.md README.ko.md README.ja.md README.zh.md README.es.md notro_app/__init__.py
python build_version_file.py
```

Expected: tests pass; every README has the feature; generated version file contains `2.7.0`.

- [ ] **Step 6: Commit Task 6**

```powershell
git add notro_app/__init__.py CHANGELOG.md README.md README.ko.md README.ja.md README.zh.md README.es.md tests/test_i18n.py
git commit -m "docs: prepare v2.7.0 capture release"
```

---

### Task 7: Full automated QA, code review, and Windows smoke QA

**Files:**
- Modify only files needed for defects reproduced by a failing test
- Record QA: `docs/superpowers/qa/2026-07-23-v2.7.0-capture-qa.md`

**Interfaces:**
- Verifies every requirement in `docs/superpowers/specs/2026-07-23-clipboard-capture-library-design.md`

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
python -m pytest -q
python -m compileall -q notro_app tests
git diff --check HEAD~6..HEAD
```

Expected: zero test failures, compile exit 0, no whitespace errors.

- [ ] **Step 2: Review changed code against the design**

Inspect `git diff 918eadf..HEAD` line by line. Confirm:

- no second clipboard watcher exists;
- file lists never reach automatic capture storage;
- small PNGs emit before the upload-limit return;
- callback errors do not block compression;
- one shared `CaptureStore` is passed to Monitor and PickerApi;
- every result branch has user-facing feedback;
- hash lookup and save happen under one lock;
- finalized assets are removed when metadata persistence fails;
- all five languages have parity;
- no broad unrelated refactor or new dependency was introduced.

If a defect is found, add a failing regression test, verify RED, implement the minimal fix, and rerun the focused test before continuing.

- [ ] **Step 3: Build the Windows application**

Run:

```powershell
python build_version_file.py
pyinstaller --onedir --noconsole --name Notro --clean --icon assets/notro.ico --version-file version_info.txt --add-data "notro_app\picker\ui;notro_app/picker/ui" --collect-all webview notro.py
```

Expected: PyInstaller exits 0 and `dist\Notro\Notro.exe` exists.

- [ ] **Step 4: Build the installer when Inno Setup is available**

Resolve `ISCC.exe`, then run:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss /DAppVersion=2.7.0
```

Expected: `dist\NotroSetup.exe` exists. If Inno Setup is unavailable locally, the GitHub Actions release build remains the required installer gate and the QA record must state this exact limitation.

- [ ] **Step 5: Perform feasible Windows manual QA**

Run the development app or built EXE and record pass/fail for the nine cases in design §7: default off, one-click save, duplicate, background auto-save, file-copy exclusion, Snipping Tool, Chromium copy, oversized compression coexistence, and existing picker/paste/language regression. Do not claim any manual case that cannot be exercised in the current desktop session; record it as `Not run` with reason.

- [ ] **Step 6: Write the QA record**

Create `docs/superpowers/qa/2026-07-23-v2.7.0-capture-qa.md` with exact commands, exit codes/counts, build artifact paths/hashes, manual QA results, and any limitations. Every section must contain a final result rather than an unfinished marker.

- [ ] **Step 7: Rerun final verification after all fixes and QA documentation**

Run:

```powershell
python -m pytest -q
python -m compileall -q notro_app tests
git diff --check
git status --short
```

Expected: all tests pass, compile succeeds, diff check is empty, and status contains only intended QA/documentation changes.

- [ ] **Step 8: Commit QA and any verified fixes**

```powershell
git add docs/superpowers/qa/2026-07-23-v2.7.0-capture-qa.md
git commit -m "test: verify v2.7.0 capture release"
```

---

### Task 8: Tag, push, and verify the v2.7.0 GitHub release

**Files:**
- No source changes expected

**Interfaces:**
- Consumes: clean verified branch with `notro_app.__version__ == "2.7.0"`
- Produces: remote `v2.7.0` tag and GitHub Release assets `NotroSetup.exe`, `NotroSetup.exe.sha256`

- [ ] **Step 1: Verify release preconditions from fresh evidence**

Run:

```powershell
git status --short
git branch --show-current
git remote -v
git tag --list v2.7.0
python -m pytest -q
python -c "import notro_app; assert notro_app.__version__ == '2.7.0'; print(notro_app.__version__)"
```

Expected: clean status, branch `main`, configured `origin`, no existing `v2.7.0` tag, full suite passes, version prints `2.7.0`.

- [ ] **Step 2: Push the verified commits**

Run: `git push origin main`

Expected: origin/main advances to the final QA commit. If protected-branch policy rejects the push, stop before tagging and report the required PR workflow.

- [ ] **Step 3: Create and push the annotated release tag**

```powershell
git tag -a v2.7.0 -m "Notro v2.7.0"
git push origin v2.7.0
```

Expected: tag push succeeds and triggers `.github/workflows/release.yml`.

- [ ] **Step 4: Verify GitHub Actions and release assets**

Use configured GitHub CLI if available:

```powershell
gh run list --workflow release.yml --limit 5
gh run watch --exit-status
gh release view v2.7.0 --json url,tagName,assets
```

Expected: workflow completes successfully and release contains both `NotroSetup.exe` and `NotroSetup.exe.sha256`. If `gh` is unavailable but tag push succeeded, verify through the repository's Actions/Release URL using the browser. Do not claim deployment completion until the workflow and assets are observed.

- [ ] **Step 5: Report deployment result**

Provide the release URL, pushed branch/tag, final test count, installer build result, and any manual QA limitations. If authentication, branch protection, or CI failure blocks release, preserve the verified commits and report the exact command/output and recovery action without bypassing permissions.

---

## Plan Self-Review

1. **Spec coverage:** Tasks 1–5 cover storage, deduplication, monitor reuse, API, UI, settings, errors, and five-language parity. Task 6 covers release metadata/docs. Tasks 7–8 cover automated QA, honest manual QA, build, tag, CI, and release assets.
2. **Placeholder scan:** The plan contains no deferred implementation markers. Every failure branch, interface, command, and release gate has a concrete expected result.
3. **Type consistency:** `CaptureReadResult` and `CaptureSaveResult` are defined in Task 2 and consumed unchanged in Tasks 4–5. Reserved collection ID is identical across all tasks. Picker API dictionary keys match the JavaScript consumers.
