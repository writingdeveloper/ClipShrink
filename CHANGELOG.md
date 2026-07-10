# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

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
