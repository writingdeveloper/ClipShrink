# Notro

<p align="center">
  <img src="docs/icon.png" width="96" alt="Notro icon">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<p align="center"><b>English</b> | <a href="README.ko.md">한국어</a> | <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a></p>

A tiny Windows tray app for Discord free users. It **auto-compresses clipboard
images** that exceed Discord's free upload limit (10 MB), and ships an
**emoji / sticker / GIF picker** (hotkey popup) that fills the Nitro gap
**without modifying the Discord client**. Just paste with <kbd>Ctrl</kbd>+<kbd>V</kbd>.

## How it works (auto-compression)

1. Lives in the system tray and watches the clipboard.
2. When a new image is copied, it computes the **PNG size Discord would produce** on paste.
3. **At or under 10 MB → does nothing** (paste the original as usual).
4. Over the limit → re-encodes to **WebP → JPEG**, lowering quality until it fits under
   ~9.5 MB; if it's still too big, it **scales the resolution down** step by step.
5. The compressed image is placed on the clipboard **as a file**, so <kbd>Ctrl</kbd>+<kbd>V</kbd>
   in Discord uploads it as a file attachment. A tray notification confirms the result.

> Your original capture files on disk are never touched — only the clipboard is replaced.

## The picker (v2.0)

Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> (configurable from the tray)
while typing in Discord — a Discord-styled dark popup opens near your cursor
with three tabs: **Emoji / Stickers / GIFs**.

- **Add items:** press **＋** and paste a Discord *"Copy Link"* emoji URL, or
  drag & drop image files onto the picker, or add **watched folders** (⚙) whose
  PNG/GIF/WebP/APNG files appear automatically in the current tab.
- **Use items:** click one — the picker hides, focus returns to Discord, and the
  image is pasted into the message box as an attachment. **You press Enter to
  send.** Right-click for "paste as link" (CDN items) or remove.
- Animated APNG stickers are converted to GIF on registration, because Discord
  doesn't animate uploaded APNGs.
- Search by name/keywords; a "Recently used" row keeps favorites close.
- Items over the upload limit: static images are auto-compressed; oversized
  GIFs are sent as-is with a warning.

**ToS safety, by design:** Notro never patches the Discord client and never
touches your account or token (no self-bot behavior). It only prepares your
clipboard and simulates a local <kbd>Ctrl</kbd>+<kbd>V</kbd> — the same kind of
input automation as the Windows emoji panel (<kbd>Win</kbd>+<kbd>.</kbd>).
The honest trade-off: recipients see your emojis/stickers as image attachments
or link embeds, not as native inline emojis.

Requires the **WebView2 runtime** (built into Windows 11). Without it, the
picker is disabled and compression keeps working.

## Download & run (recommended)

Grab the latest `NotroSetup.exe` from the [**Releases**](../../releases) page and run it.
It installs to `%LOCALAPPDATA%\Programs\Notro` (no admin rights needed) and adds Start
Menu / Desktop shortcuts. Uninstall any time from **Settings → Apps** or the Start Menu.

- It runs in the tray. Right-click the icon for: open the picker, change the
  picker hotkey, pause/resume, recent history, switch the upload limit
  (10/50/500 MB), change language, open output folder, enable auto-start, and quit.
- **Auto-start is opt-in** — it's *off by default*. Turn on *"Run at Windows startup"*
  from the tray menu if you want it.
- Only one instance runs at a time.

> ⚠️ The EXE is **unsigned**, so Windows SmartScreen or some antivirus tools may warn or
> flag it as a false positive. Click *"More info → Run anyway"* on SmartScreen, or just
> run it from source (below).

## First run — where is it?

Notro has **no main window**. After installing it starts silently and lives in the
**system tray** (bottom-right, next to the clock).

> **Windows 11 hides new tray icons by default.** If you don't see Notro, click the
> **`^`** arrow next to the clock — then **drag the Notro icon onto the taskbar** to
> keep it visible.

From there:

- Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> anywhere to open the picker.
- Copy an image that's too big for Discord — Notro compresses it automatically, then
  just paste with <kbd>Ctrl</kbd>+<kbd>V</kbd>.
- **Right-click the tray icon** for every setting (hotkey, upload limit, language, …).

On the very first launch the picker opens once by itself, so you can see what it does.

## Run from source (development)

```sh
pip install -r requirements.txt
pythonw notro.py
```

Requires **Python 3.10+** on Windows.

## Build the EXE yourself

```sh
build.bat
```

Output: `dist\Notro.exe`. Requires Python 3.10+ (the script installs PyInstaller).

## Configuration

Edit the values in `notro_app/config.py` (limits) and
`notro_app/compress.py` (quality steps):

| Setting | Default | Description |
|---|---|---|
| `LIMIT_MB` | 10 | Default upload limit in MB — or pick 10/50/500 from the tray **Upload limit** menu |
| `SAFETY` | 0.95 | Safety margin (targets ~9.5 MB) |
| `WEBP_QUALITIES` | 90–50 | WebP quality steps |
| `MIN_SCALE` | 0.4 | Lower bound for downscaling |

## Notes

- Compressed files are written to `%TEMP%\Notro` and auto-deleted after 1 day.
- Copying an image **file** (<kbd>Ctrl</kbd>+<kbd>C</kbd>) larger than the limit is
  compressed the same way.
- **Languages:** English, 한국어, 日本語, 中文(简体), Español. Notro auto-detects
  your Windows language and can be switched anytime from the tray **Language** menu.

## Development

```sh
pip install -r requirements-dev.txt
pytest
```

## License

[MIT](LICENSE).

> Notro is an unofficial tool — **not affiliated with, endorsed by, or sponsored by
> Discord Inc.** "Discord" is a trademark of Discord Inc.
