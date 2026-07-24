# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

## [2.7.0] - 2026-07-23

### Added
- **One-click clipboard capture storage.** The picker now has a dedicated button that saves
  the current clipboard image as an emoji in a localized Captures collection. The existing
  <kbd>Ctrl</kbd>+<kbd>V</kbd> current-tab workflow remains available.
- **Optional automatic capture storage.** Picker settings can save each new clipboard PNG or
  bitmap automatically. It is off by default, ignores copied image files, and deduplicates
  identical captures by a persistent SHA-256 hash.

### Changed
- Clipboard-only bitmap captures now fall back through `CF_DIB` when no registered PNG format
  is available, and capture collections keep a stable internal identity across language changes.
- File drops now report partial or complete registration failures instead of silently claiming
  success when nothing was added.

### Fixed
- Clipboard image registration is now visible and reliable instead of depending solely on a
  hidden browser paste-event MIME check.

## [2.6.1] - 2026-07-15

### Fixed
- **A fresh copy made while Notro was still compressing the previous image is no longer
  destroyed.** Compressing a large image takes a few seconds; if you copied something else
  in that window, Notro would finish, overwrite the clipboard with the *old* image's
  compressed file, and swallow the new copy's change event — your new copy vanished with
  no notification. The clipboard swap now checks the clipboard sequence number *while
  holding the clipboard open* and quietly discards the stale result if anything new
  arrived; the new copy is then processed normally on the next poll.
- **Notro no longer reads the clipboard in the middle of a write.** Chromium apps
  (Discord, browsers) write an image copy as several formats over hundreds of
  milliseconds. Waking up mid-write could miss the real PNG bytes and fall back to the
  re-encoded-bitmap size estimate, which can overshoot and compress an image that was
  actually under the limit. The monitor now waits until the sequence number is stable
  across two polls (~0.4 s) before reading, so it only ever sees completed copies.
  (Verified against Chromium: its clipboard writer also silently gives up if another
  process holds the clipboard for ~25 ms during a copy — reads stay short and never
  overlap a write session now.)

## [2.6.0] - 2026-07-12

### Added
- **Video compression.** Copy a game clip that is too big for Discord (the free limit is
  **10 MB**, lowered from 25 MB in 2024) and Notro offers to shrink it: it reads the file
  with ffmpeg, picks a resolution/bitrate/fps that fits, encodes, and puts the compressed
  `.mp4` back on the clipboard so <kbd>Ctrl</kbd>+<kbd>V</kbd> attaches it in Discord.
  - Notro **asks first** in a window (not a toast — toasts never reach users who turned
    notifications off) and shows what to expect: `52MB · 1:12 · 1080p60 → about 9.5MB · 480p30`.
  - If a clip simply cannot fit — the floor is **360p / 300 kbps** — Notro says so instead
    of producing an unwatchable mosaic.
  - **ffmpeg is not bundled.** It is downloaded on demand (about 30 MB, SHA256-verified)
    the first time you compress a video, or taken from PATH if you already have it. Notro
    never ships the binary, so nothing changes for people who don't compress video.

## [2.5.8] - 2026-07-12

### Added
- **The installer now installs the WebView2 Runtime when it is missing.** The picker
  requires WebView2; Windows 11 ships it, but a Windows 10 machine may not have it — and
  the installer neither checked nor installed it, so after a "successful" install the
  picker silently stayed dead. The wizard now detects it and, if absent, downloads
  Microsoft's official bootstrapper and installs it quietly. A failed download is
  non-fatal (compression works without WebView2), and silent auto-updates skip the step
  entirely, so existing users are unaffected.
- **The installer now speaks all five app languages** (English, 한국어, 日本語,
  中文(简体), Español) — wizard text, the task checkboxes, and the finish-page guidance.
  Korean and Simplified Chinese are official in Inno Setup 6.3+, so no language files
  need to be vendored.
- **The exe carries version info** (version, publisher, description in the file
  properties dialog), generated from `__version__` by `build_version_file.py`.

### Fixed
- **32-bit Windows could install a 64-bit build.** `ArchitecturesAllowed` was unset, so
  Setup would happily install on x86 where the exe cannot run — it now refuses.

### Changed
- The release workflow publishes only on tag pushes, so `workflow_dispatch` can verify a
  build (and compile the Inno script) without creating a release.

## [2.5.7] - 2026-07-11

### Changed
- **First-run guidance is now a window you read and dismiss, not a timed popup.** v2.5.6
  opened the picker automatically 2.5 s after launch — but Inno runs `[Run]` *before*
  showing its finish page, so the picker landed on top of the install instructions and
  appeared at a moment the user had not chosen. The first launch now shows a small
  **welcome window** that stays until you close it. It renders **the actual tray icon**
  so you know what to look for, and explains: Notro has no window, how to unhide and pin
  the tray icon on Windows 11, which hotkey opens the picker, and that oversized images
  are compressed automatically. Closing it leaves Notro running in the tray (the hidden
  picker window keeps the webview loop alive — verified).
- **The tray tooltip now shows the picker hotkey** (e.g. `Notro v2.5.7 — Ctrl+Shift+E:
  picker · auto-compresses clipboard images`), so hovering the icon reveals it. The
  tooltip follows hotkey and language changes.

## [2.5.6] - 2026-07-11

### Added
- **First-run onboarding.** Notro is a windowless tray app, and Windows 11 hides new
  tray icons by default — so a fresh install could feel like "nothing happened."
  - The **installer's finish page** now says where Notro lives, how to open the picker
    (Ctrl+Shift+E), and how to unhide/pin the tray icon on Windows 11. Silent
    auto-updates skip this page, so existing users are never interrupted by it.
  - **The picker opens once on the very first launch**, so the app proves it is running
    and shows what it does. This is also the only signal for users who have Windows
    notifications turned off.
  - The first-run notification now says **where the tray icon is** (including the `^`
    overflow arrow) and **which hotkey opens the picker**, instead of only mentioning
    auto-start. Builds without the picker (no WebView2) keep a tray-location-only
    message.
- **READMEs in Japanese, Chinese and Spanish.** The app has shipped five UI languages
  since v1.2 but only had English/Korean READMEs. Each README now also carries a
  **"First run — where is it?"** section, and all five share one language switcher.

### Changed
- The GitHub repository description and topics now reflect the emoji/sticker/GIF picker,
  not just clipboard compression.

## [2.5.5] - 2026-07-11

### Fixed
- **Update availability is now visible even with Windows notifications off.** The
  "update ready" signal previously fired only a toast (`on_ready` → `icon.notify`),
  which Focus Assist / disabled notifications suppress — and the "Restart to update"
  tray item stayed hidden because pystray's Windows menu is a cached HMENU that was
  never refreshed. Readiness now also (a) draws an orange badge on the tray icon,
  (b) updates the tray tooltip, and (c) refreshes the menu so the Restart item
  actually appears. The toast still fires for users who have notifications on.
- **Hotkey-listener thread race.** Rebinding the picker hotkey in quick succession
  could leak the listener thread and leave the old hotkey registered — `WM_QUIT` was
  posted before the worker recorded its thread id. `stop()` now waits for the id.
- **Library thread-safety.** The asset HTTP server (multi-threaded) and the picker
  js_api thread could mutate the item/folder maps mid-iteration; guarded with a
  reentrant lock.
- **Clipboard memory leak** on the rare `GlobalLock`/`SetClipboardData` failure path
  (the moved global wasn't freed when ownership didn't transfer to the clipboard).

### Changed
- Localized the picker's ⚙ settings-button tooltip (was hardcoded English "settings").
- Unified Korean UI wording to a consistent polite register (해요체) — fixed a
  mixed-register sentence and the "move to collection" label (`컬렉션으로 이동`).
  Minor English/Chinese fixes (fullwidth `＋`, `素材库`).

## [2.5.4] - 2026-07-11

### Fixed
- **Root-caused and eliminated the "Failed to load Python DLL ... _MEI...\\python312.dll"
  error that kept recurring after auto-update.** v2.5.1 (a delay) and v2.5.2
  (installer-driven relaunch) only changed *when* the app relaunched; the real cause
  was the **onefile** build itself. onefile extracts the entire ~37 MB payload —
  including the Python DLL — into a fresh `%TEMP%\\_MEIxxxxx` folder on every launch,
  and the post-install relaunch fired while that extraction was still racing (AV scan
  / file-handle settle) on the just-written exe, so the DLL was momentarily
  unloadable. Relaunching from the Start Menu seconds later always worked — the tell
  that the installed exe itself was fine. Switched the build to **onedir**: the Python
  DLL and its dependencies now live permanently in the installed `_internal\\` folder
  and load directly, so there is no per-launch extraction and thus no race. The
  installer packages the whole folder; the download is still a single `NotroSetup.exe`.
  Verified locally that the onedir exe creates no `_MEI` folder and loads its DLL from
  `_internal\\`.

## [2.5.3] - 2026-07-11

### Fixed
- **The app, its installer, and the Start-menu / desktop / taskbar shortcuts now
  show the Notro icon instead of the generic default.** The build pipeline never
  embedded an icon: no `.ico` existed in the repo (only `docs/icon.png`), and
  neither the PyInstaller build (`release.yml` / `build.bat` / `Notro.spec`) nor
  the Inno Setup script passed one — so every shortcut, the setup wizard, and the
  running app's taskbar entry inherited the default icon from an icon-less
  `Notro.exe`. Added a multi-resolution `assets/notro.ico` (16–256 px) wired into
  the EXE build (`--icon`) and the installer (`SetupIconFile`), plus an explicit
  AppUserModelID so the taskbar groups the running app under the Notro icon
  rather than pythonw/WebView2's default.

## [2.5.2] - 2026-07-11

### Fixed
- **Actually fixed "Failed to load Python DLL" after auto-update.** The v2.5.1
  fix (a 3-second delay) wrongly blamed antivirus — but this machine has Defender
  disabled, so that was never the cause, and the delay didn't help. The real root
  cause: the helper batch launched the app right after kicking off the silent
  install, but Inno Setup relaunches itself from a temp copy and returns *before*
  the install finishes, so the app was started while its exe was still being
  replaced — breaking onefile's Python-DLL extraction. Now the batch **only runs
  the installer**, and the **installer's own `[Run]` step relaunches the app once
  the install fully completes** (`postinstall` removed so it fires in silent
  installs too; `RestartApplications=no` avoids a double launch). The installed
  exe is never actually corrupted — if a launch ever fails, relaunching from the
  Start Menu works.

### Note
- Upgrading *to* v2.5.2 must be done once manually (download `NotroSetup.exe`),
  because the still-installed v2.5.0/v2.5.1 has the old broken relaunch. From
  v2.5.2 onward the installer handles relaunch correctly.

## [2.5.1] - 2026-07-11

### Fixed
- **"Failed to load Python DLL ... LoadLibrary" right after auto-update.**
  Confirmed root cause: the updater's helper batch relaunched the freshly
  reinstalled (unsigned) `Notro.exe` immediately after the silent install
  finished, racing Windows Defender's real-time scan / file-handle settling
  on the newly-written binary — the same exe launches fine moments later.
  Added a short delay between the silent install and the relaunch. If this
  still recurs for anyone, just relaunch Notro manually from the Start Menu;
  the installed file itself is never corrupted by this.

## [2.5.0] - 2026-07-11

### Added
- **Assets are now organized into per-collection folders** on disk
  (`%APPDATA%\Notro\assets\<collection>\`) instead of one flat pile of files —
  opening the library folder (tray, or picker settings) is actually browsable
  now. Existing files migrate automatically the next time Notro starts.
- **Collections show a representative thumbnail** on the left rail instead of
  2-letter text, using the collection's first item (falls back to text if the
  collection is empty).

### Fixed
- `remove_item` now deletes the asset from its actual (collection) folder
  instead of a stale flat path — a latent bug from the v2.4.0 rail feature that
  would have left orphaned files behind.

## [2.4.1] - 2026-07-10

### Fixed
- **Auto-update now actually restarts and installs.** In v2.3.0–2.4.0 the updater
  ran the silent installer and quit the app, but Inno's `[Run] postinstall` never
  fires under `/VERYSILENT` (there's no finished page), so the app never came back;
  the quit-vs-install race also left the update unapplied. The updater now writes a
  helper batch that waits for the app to exit, runs the silent install, then
  relaunches the installed exe — the same robust pattern as the pre-installer build.

## [2.4.0] - 2026-07-10

### Added
- **Favorites** — right-click any item to star it. A ★ tab on the new left rail
  shows just favorites, and a Favorites row appears at the top of other views.
- **Collections** — a left rail groups items like Discord's per-server emoji.
  Watched-folder items auto-group by folder name; registered items can be moved
  to a named collection via right-click. The bundled Miku items are grouped as
  **miku**. The rail crosses with the Emoji/Sticker/GIF tabs.
- **Open library folder** — from the tray and the picker settings (⚙), to browse
  the cached assets under `%APPDATA%\Notro`.

## [2.3.0] - 2026-07-10

### Changed
- **Now ships as an installer (`NotroSetup.exe`)** instead of a portable exe.
  Installs to `%LOCALAPPDATA%\Programs\Notro` (no admin rights), adds a Start Menu
  entry and an optional Desktop shortcut, an optional "run at startup" step, and a
  proper uninstaller (Settings → Apps). Fixes the "lost the file / must remember
  where it is" problem of the portable build.
- The auto-updater now downloads `NotroSetup.exe` and runs it silently
  (`/VERYSILENT`) to update in place, replacing the batch self-replace.

### Migration
- **v2.2.0 → v2.3.0 must be done manually once:** the v2.2.0 updater looks for a
  `Notro.exe` asset, which v2.3.0 no longer publishes. Download and run
  `NotroSetup.exe` once; your library (`%APPDATA%\Notro`) and settings carry over.
  From v2.3.0 onward, updates are automatic again.

## [2.2.0] - 2026-07-10

### Added
- **Semi-automatic updater** — Notro checks the GitHub Releases API on startup
  and every 24h, downloads the new `Notro.exe` in the background, verifies its
  **SHA256**, and offers **"Restart to update now"** from the tray. The swap is a
  batch helper that waits for the process to exit, backs up the old exe
  (`.bak` rollback on failure), replaces it, and relaunches. The tray also gains
  a manual **"Check for updates"** item and an **"Automatic update checks"**
  toggle. Frozen (exe) builds only — the dev run (`pythonw notro.py`) never
  updates itself. The exe stays unsigned, so the first launch of a new version
  still shows SmartScreen. Updater strings added in all five languages.
- Release workflow now attaches `Notro.exe.sha256` for update verification.

### Notes
- The v2.1.0 → v2.2.0 hop is the last manual one (v2.1.0 has no updater); from
  v2.2.0 onward, updates are delivered semi-automatically.

## [2.1.0] - 2026-07-10

### Changed
- **Renamed the project from ClipShrink to Notro** — a nod to "not Nitro". What
  began as a clipboard image compressor is now a ToS-safe companion for Discord's
  Nitro-gated emoji/sticker/GIF picker, and the name reflects that. On first
  launch your existing library (`%APPDATA%\ClipShrink`) and settings are migrated
  automatically to the new location (`%APPDATA%\Notro`); if you had "Run at
  Windows startup" enabled, it is re-registered under the new name.
- New app / tray icon.
- Package renamed `clipshrink_app` → `notro_app`, entry point `clipshrink.py` →
  `notro.py`, executable `ClipShrink.exe` → `Notro.exe`.

### Fixed
- Three picker gaps surfaced by a v2.0 spec audit, each fixed with tests
  (49 → 62 passing):
  - **APNG→GIF conversion failure** now falls back to a static first-frame PNG
    and flags the item with a warning badge, instead of aborting registration
    with a misleading "download failed" error (spec §7).
  - **Clipboard image paste** — you can now paste an image straight into the
    picker to add it; previously only drag-and-drop registered files (spec §5).
  - Search moved into the library module as the canonical owner (spec §3).

## [2.0.0] - 2026-07-09

### Added
- **Emoji / Sticker / GIF picker** — a hotkey popup (default `Ctrl+Shift+E`,
  configurable from the tray) that replaces Discord's Nitro-gated picker panel
  without modifying the Discord client:
  - Personal library: register emojis/stickers by pasting a Discord
    "Copy Link" URL, by drag-and-dropping image files, or by watching local
    folders (PNG/GIF/WebP/APNG shown automatically per tab).
  - Animated APNG stickers are converted to GIF on registration (Discord
    does not animate uploaded APNGs).
  - Click an item → the picker hides, focus returns to Discord, and the file
    is pasted into the message box automatically. **Sending (Enter) is always
    up to you** — the app never automates your account (no self-bot behavior).
  - Right-click → paste as CDN link instead of a file, or remove the item.
  - Search by name/keywords, "Recently used" section, Discord-style dark UI.
  - Items over the upload limit: static images are auto-compressed through the
    existing pipeline; oversized GIFs are sent as-is with a warning.
- Tray menu: "Open emoji & sticker picker" and a hotkey selector
  (Ctrl+Shift+E / Ctrl+Alt+E / Ctrl+Shift+Space / Disabled).
- 30 new UI strings translated in all five languages.

### Changed
- Codebase split from a single script into the `clipshrink_app` package
  (config / i18n / compress / clipboard_win / monitor / hotkey / library /
  fetch / tray / app / picker). `clipshrink.py` remains the entry point.
- New dependency: `pywebview` (picker window via Windows 11's built-in
  WebView2). If the WebView2 runtime is missing, the app falls back to
  compression-only mode with a notification.
- EXE size grows to ~36 MB (pywebview + pythonnet runtime; was ~11 MB).

### Notes
- Design constraint (ToS safety): the app never modifies the Discord client
  and never calls Discord APIs with your user token. It only prepares the
  clipboard and simulates a local Ctrl+V — the same class of input automation
  as the Windows emoji panel (Win+.). Recipients see pasted items as image
  attachments/links, not as native inline emojis — that is the honest ceiling
  of a ToS-safe companion tool.

## [1.2.0] - 2026-06-13

### Added
- Spanish (Español) UI translation, bringing supported languages to five:
  English, 한국어, 日本語, 中文(简体), Español.

## [1.1.0] - 2026-06-13

### Added
- Multi-language UI — English, 한국어, 日本語, 中文(简体) — with automatic
  Windows-language detection and a tray **Language** menu (choice is persisted).
- Configurable upload limit (10 / 50 / 500 MB) from the tray **Upload limit** menu,
  matching Discord Free / Nitro Basic / Nitro (persisted).
- Periodic cleanup of old temp files while running (previously only on start/quit).

### Fixed
- Filename collision when two images were compressed within the same second
  (now microsecond-precise) — earlier history entries no longer point to the wrong file.
- Silent failure when the clipboard couldn't be updated (another app holding it)
  now shows a notification instead of doing nothing.
- Transparent images that fall back to JPEG are composited on white instead of
  turning black.

## [1.0.0] - 2026-06-13

### Added
- Initial public release.
- System-tray app that auto-compresses oversized clipboard images for Discord's
  10 MB free upload limit.
- Detection based on the actual PNG bytes Discord would upload, with a safety margin.
- WebP → JPEG quality fallback, then stepwise downscaling, to fit under the limit.
- Compressed image placed on the clipboard **as a file** for direct Ctrl+V upload.
- Opt-in "Run at Windows startup" toggle, recent-history submenu, and single-instance guard.
- Automatic cleanup of temp files older than 1 day.
