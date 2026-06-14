# ClipShrink

<p align="center">
  <img src="docs/icon.png" width="96" alt="ClipShrink icon">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<p align="center"><b>English</b> | <a href="README.ko.md">한국어</a></p>

A tiny Windows tray app that **auto-compresses clipboard images** that exceed
Discord's free upload limit (10 MB) — so you can just paste with <kbd>Ctrl</kbd>+<kbd>V</kbd>
and upload instantly, with no manual resizing or re-saving.

## How it works

1. Lives in the system tray and watches the clipboard.
2. When a new image is copied, it computes the **PNG size Discord would produce** on paste.
3. **At or under 10 MB → does nothing** (paste the original as usual).
4. Over the limit → re-encodes to **WebP → JPEG**, lowering quality until it fits under
   ~9.5 MB; if it's still too big, it **scales the resolution down** step by step.
5. The compressed image is placed on the clipboard **as a file**, so <kbd>Ctrl</kbd>+<kbd>V</kbd>
   in Discord uploads it as a file attachment. A tray notification confirms the result.

> Your original capture files on disk are never touched — only the clipboard is replaced.

## Download & run (recommended)

Grab the latest `ClipShrink.exe` from the [**Releases**](../../releases) page and run it.

- It runs in the tray. Right-click the icon for: pause/resume, recent history,
  switch the upload limit (10/50/500 MB), change language, open output folder,
  enable auto-start, and quit.
- **Auto-start is opt-in** — it's *off by default*. Turn on *"Run at Windows startup"*
  from the tray menu if you want it.
- Only one instance runs at a time.

> ⚠️ The EXE is **unsigned**, so Windows SmartScreen or some antivirus tools may warn or
> flag it as a false positive. Click *"More info → Run anyway"* on SmartScreen, or just
> run it from source (below).

## Run from source (development)

```sh
pip install -r requirements.txt
pythonw clipshrink.py
```

Requires **Python 3.10+** on Windows.

## Build the EXE yourself

```sh
build.bat
```

Output: `dist\ClipShrink.exe`. Requires Python 3.10+ (the script installs PyInstaller).

## Configuration

Edit the values at the top of `clipshrink.py`:

| Setting | Default | Description |
|---|---|---|
| `LIMIT_MB` | 10 | Default upload limit in MB — or pick 10/50/500 from the tray **Upload limit** menu |
| `SAFETY` | 0.95 | Safety margin (targets ~9.5 MB) |
| `WEBP_QUALITIES` | 90–50 | WebP quality steps |
| `MIN_SCALE` | 0.4 | Lower bound for downscaling |

## Notes

- Compressed files are written to `%TEMP%\ClipShrink` and auto-deleted after 1 day.
- Copying an image **file** (<kbd>Ctrl</kbd>+<kbd>C</kbd>) larger than the limit is
  compressed the same way.
- **Languages:** English, 한국어, 日本語, 中文(简体). ClipShrink auto-detects your
  Windows language and can be switched anytime from the tray **Language** menu.

## Development

```sh
pip install -r requirements-dev.txt
pytest
```

## License

[MIT](LICENSE).

> ClipShrink is an unofficial tool — **not affiliated with, endorsed by, or sponsored by
> Discord Inc.** "Discord" is a trademark of Discord Inc.
