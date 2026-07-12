# Notro

<p align="center">
  <img src="docs/icon.png" width="96" alt="Notro 图标">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<p align="center"><a href="README.md">English</a> | <a href="README.ko.md">한국어</a> | <a href="README.ja.md">日本語</a> | <b>中文</b> | <a href="README.es.md">Español</a></p>

一款面向 Discord 免费用户的小巧 Windows 托盘应用。当剪贴板中的图片超过 Discord 免费上传限制（10 MB）时**自动压缩**，并以热键弹窗提供 Nitro 锁定的**表情·贴纸·GIF 选择器**，**完全不修改 Discord 客户端**。只需 <kbd>Ctrl</kbd>+<kbd>V</kbd> 粘贴即可。

## 工作原理（自动压缩）

1. 常驻系统托盘并监视剪贴板。
2. 复制新图片时，计算 **Discord 粘贴时会生成的 PNG 大小**。
3. **不超过 10 MB 则不做任何处理**（照常粘贴原图）。
4. 超过限制时，按 **WebP → JPEG** 降低质量以压到约 9.5 MB 以内；若仍然过大，则**逐步缩小分辨率**。
5. 压缩后的图片以**文件形式**放入剪贴板，因此在 Discord 中 <kbd>Ctrl</kbd>+<kbd>V</kbd> 会作为文件附件上传。托盘通知会告知结果。

> 不会改动磁盘上的原始截图文件，只替换剪贴板。

## 选择器（v2.0）

在 Discord 中输入时按 <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>（可在托盘中更改），光标附近会弹出 Discord 风格的深色弹窗，包含 **表情 / 贴纸 / GIF** 三个标签页。

- **添加:** 点击 **＋** 粘贴 Discord *“复制链接”* 得到的表情 URL，或将图片文件拖放到选择器，或添加**监视文件夹**（⚙）——其中的 PNG/GIF/WebP/APNG 会自动显示在当前标签页。
- **使用:** 点击某项后选择器关闭、焦点回到 Discord，图片会作为附件插入消息框。**发送（Enter）由你自己按。** 右键可“作为链接粘贴”（CDN 项目）或删除。
- 动态 APNG 贴纸会在注册时自动转换为 GIF（因为 Discord 不会播放上传的 APNG）。
- 支持按名称·关键词搜索，以及“最近使用”栏。
- 超过上传限制的项目: 静态图片自动压缩，过大的 GIF 会附带警告按原样发送。

**遵守 ToS 的设计:** Notro 不给 Discord 客户端打补丁，也完全不碰你的账号或令牌（并非自助机器人）。它只准备剪贴板并模拟本地 <kbd>Ctrl</kbd>+<kbd>V</kbd> 输入——与 Windows 表情面板（<kbd>Win</kbd>+<kbd>.</kbd>）属于同一类输入自动化。诚实的取舍: 接收者看到的是图片附件或链接嵌入，而非原生内联表情。

需要 **WebView2 运行时**（Windows 11 已内置）。没有它时仅选择器被禁用，压缩功能照常工作。

## 下载与运行（推荐）

从 [**Releases**](../../releases) 页面获取最新的 `NotroSetup.exe` 并运行。它会安装到 `%LOCALAPPDATA%\Programs\Notro`（无需管理员权限），并创建开始菜单和桌面快捷方式。随时可在 **设置 → 应用** 或开始菜单中卸载。

- 常驻托盘。右键点击图标可: 打开选择器、更改选择器热键、暂停/恢复、最近记录、切换上传限制（10/50/500 MB）、更改语言、打开输出文件夹、启用开机自启、退出。
- **开机自启默认关闭（opt-in）**。如需要，请在托盘菜单中打开*“开机时自动运行”*。
- 同一时间只运行一个实例。

> ⚠️ 该 EXE **未经代码签名**，因此 Windows SmartScreen 或某些杀毒软件可能发出警告或误报。在 SmartScreen 上点击*“更多信息 → 仍要运行”*，或按下方从源码直接运行。

## 首次运行 — 它在哪里？

Notro **没有主窗口**。安装后会静默启动，常驻在**系统托盘**（屏幕右下角、时钟旁）。

> **Windows 11 默认隐藏新的托盘图标。** 如果看不到 Notro，请点击时钟旁的 **`^`** 箭头，
> 然后把 **Notro 图标拖到任务栏上**以保持显示。

之后:

- 在任意位置按 <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> 打开选择器。
- 复制一张对 Discord 来说过大的图片，Notro 会自动压缩 — 直接
  <kbd>Ctrl</kbd>+<kbd>V</kbd> 粘贴即可。
- **右键点击托盘图标**可访问所有设置（热键、上传限制、语言 …）。

首次启动时会弹出一个**说明窗口**介绍以上内容 — 并显示你要寻找的托盘图标。关闭它后，
Notro 仍在托盘中运行。

## 从源码运行（开发）

```sh
pip install -r requirements.txt
pythonw notro.py
```

需要 Windows 与 **Python 3.10 及以上**。

## 自行构建 EXE

```sh
build.bat
```

输出: `dist\Notro.exe`。需要 Python 3.10+（脚本会安装 PyInstaller）。

## 配置

编辑 `notro_app/config.py`（限制）与 `notro_app/compress.py`（质量档位）中的值:

| 设置 | 默认值 | 说明 |
|---|---|---|
| `LIMIT_MB` | 10 | 默认上传限制（MB）——可在托盘 **上传限制** 菜单中选择 10/50/500 |
| `SAFETY` | 0.95 | 安全余量（目标约 9.5 MB） |
| `WEBP_QUALITIES` | 90–50 | WebP 质量档位 |
| `MIN_SCALE` | 0.4 | 缩小的下限 |

## 说明

- 压缩文件写入 `%TEMP%\Notro`，超过 1 天后自动删除。
- 复制（<kbd>Ctrl</kbd>+<kbd>C</kbd>）超过限制的图片**文件**时也会同样压缩。
- **多语言:** English·한국어·日本語·中文(简体)·Español。自动检测 Windows 语言，也可随时在托盘 **语言** 菜单中切换。

## 开发

```sh
pip install -r requirements-dev.txt
pytest
```

## 许可证

[MIT](LICENSE)。

> Notro 是非官方工具，**与 Discord Inc. 无隶属、认可或赞助关系。**“Discord” 是 Discord Inc. 的商标。
