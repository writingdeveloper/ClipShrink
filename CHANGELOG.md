# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

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
